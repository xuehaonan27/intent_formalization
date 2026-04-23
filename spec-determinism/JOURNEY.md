# From "let Z3 emit the witness" to schema-driven search

This is the story of how `spec-determinism` went from a naive Verus-
per-round pipeline, through a raw-`(get-model)` shortcut that looked
9× faster but produced unusable witnesses, to the current schema-
driven approach that is both fast and produces structurally complete
witnesses.

## Starting point

The first working pipeline performed binary search by re-invoking
`cargo verus verify` once per narrowing round — about 2–3 s per call,
20–100 rounds per function, up to ~13 min on `kernel::allocate`. When
verification fails, Verus emits `(get-model)` after the failing
`(check-sat)`, and the full SMT response lands in the log transcript.
The obvious plan was: parse that model, decode Verus's SMT encoding
back into Rust-level facts, call it the witness. One Verus call, one
witness. Done.

We implemented this as `Z3Backend` + `model_eval.py` (a pure-Python
SMT s-expr evaluator), and it *did* give headline-worthy speedups on
small functions. But two problems surfaced the moment we tried it on
realistic inputs.

## The two problems

### (1) `(check-sat)` returns `unknown`

Verus disables MBQI and uses quantifier instantiation patterns that
are *incomplete for arithmetic*. On many realistic goals Z3 answers

```
unknown ; (incomplete (theory arithmetic))
```

There is no canonical model to read: a subsequent `(get-model)` may
return stale values from an earlier branch, and any `solver.check()`
afterward raises `there is no current model`. Worse, Verus itself
treats this `unknown` as "verification failed", so we could not even
distinguish "genuinely nondeterministic" from "solver gave up" — which
is exactly the signal the witness is supposed to carry.

### (2) Model values are `Poly!val!N`; nested fields stay opaque

Even when Z3 *does* return `sat`, values for complex structs come back
as named universe elements:

```
pre_self_! = (Kheap./Kheap Slab!val!0 Slab!val!1 ... Slab!val!6)
r1!        = (Result./Ok Poly!val!81)
r2!        = (Result./Ok Poly!val!36)
```

`Slab!val!N` and `Poly!val!N` are arbitrary universe names; Z3 is
under no obligation to commit to concrete interpretations for fields
the proof goal does not force. Our evaluator could recover
`block_size`, `start_addr`, `end_addr` by walking view functions, but
a `Set<usize>` (uninterpreted sort) or any under-constrained field
simply stayed as `Set#12`, `Poly!val!80`, etc. The resulting "witness"
looked concrete but was unusable for downstream reasoning.

## The solution: two ideas, working together

### Idea 1 — drive search at the SMT level, not the subprocess level

Instead of spending one Verus call per round, spend one Verus call
per **function** to produce the SMT vocabulary (types, predicates,
goal), then load it into an in-memory `z3.Solver` and drive narrowing
by toggling assumption literals on that same solver. Each round
becomes a `solver.check(*bools)` — sub-millisecond vs 2.5 s — and we
get direct control over what gets asserted, with no dependence on
what Z3 volunteers in `(get-model)`.

We originally tried this with `push / add / check / pop` per round,
which was still slow because pop discards learned clauses. Switching
to `solver.check(*assumptions)` (unit-literal assumptions that live
only for one `check`) keeps learned clauses across rounds and
gave us a 14× speedup on the worst case (672 ms → 49 ms per round).

### Idea 2 — make binary search itself emit the witness

The key inversion: stop treating "read the model" as the primary
witness-generator. Instead, treat **binary search itself** as the
witness generator:

- when the solver returns `unsat` for a candidate assume, that assume
  is a **must-hold** condition — commit it to the witness and move on;
- when it returns `sat` / `unknown`, or when the forced value is still
  an abstract `Poly!val!N` / `Set#N`, keep narrowing the same
  dimension until it is pinned.

The output is always a set of Rust-level assumes
(`post1_self_.set_bits.contains(0)`, `slabs[6].block_size == 512`, …)
which are must-hold conditions, not one-shot exists-examples, and they
are concrete by construction — we never stop a dimension on an
abstract universe element.

## How it's implemented today

1. **Schema enumeration** (`spec_determinism/schema_search/schemas.py`). For every
   spec-level symbol we emit a small, type-directed set of schemas:
   - Int: `SCALAR_EQ`, `SCALAR_RANGE`
   - Bool: `BOOL_EQ`
   - Result / Option / enum: `VARIANT_IS` per variant, recursing into
     the variant payload via a parent-guard chain
   - Struct: recurse into fields
   - Set: `SET_EMPTY`, `SET_LEN_GT/EQ/RANGE`, `SET_CONTAINS`
   - Seq: `SEQ_LEN_EQ/RANGE` plus element pre-enumeration up to
     `MAX_SEQ_LEN = 8`
   - one terminal `NOT_EQUAL_FN` for the distinctness goal.

   Each schema reserves a `(guard_name, k_params...)` slot. Dependent
   schemas (e.g. fields of `r1->Ok_0`) only fire when the parent guard
   is on, so we never activate conflicting dimensions simultaneously.

2. **One-shot template compilation**. `render_guarded_template`
   injects the guard/k parameters into the `det_fn` signature and
   emits `if guard_i { assume(expr_i(k_i)); }` in the body. One
   `cargo verus verify` produces a single `mm__<module>.smt2`.

3. **Pred ↔ schema dispatch lives in `predicates.py`**. Each
   `AssumePred` subclass has a `match_and_bind(schema) -> Optional[k_bindings]`
   method. Adding a new pred kind is a one-place extension.

4. **z3-py search** (`spec_determinism/schema_search/search.py`). `build_schema_ctx`
   parses the `.smt2` into an in-memory solver and resolves each
   schema's guard / k constants by name. `SchemaSearchContext.test_and_set`
   then drives rounds:
   - translate the Rust assume → `(schema_id, k_bindings)` via
     `translate_assume` (which calls `pred.match_and_bind` over the
     available schemas);
   - `r = solver.check(*current_guards_and_ks)`;
   - `unsat ⇒ pass` (commit the assume), otherwise ⇒ `fail`
     (keep narrowing).

5. **Untranslatable assumes** fall through as `pass_untranslatable`:
   the search treats them as "too weak to prove determinism here",
   moves on, and still produces a sound (possibly less detailed)
   witness. This keeps the system robust when a pred happens not to
   correspond to any emitted schema.

No Z3 model is ever read in this path. `solver.model()` is not called;
we use Z3 purely as a sat/unsat oracle.

## Results

14 `exec` functions across `bitmap`, `slab`, `kernel`:

| Version | Total time | `kernel::allocate` | Witness quality |
|---|---|---|---|
| Verus-per-round | ~1756 s | ~13 min | narrow output |
| Raw `(get-model)` shortcut | — | ~7 s | concrete where forced, `Poly!val!N` / `Set#N` elsewhere |
| Schema search, push / pop | 672 ms/round | — | full |
| **Schema search, `check(*assumptions)`** | **~159 s** | **~100 s / 3567 rounds** | **full, incl. all 7 slabs' `block_size` / `start_addr` / `end_addr` and Set narrowing** |

Overall ~11× faster than the original pipeline, with strictly richer
witnesses. `kernel::allocate`, which the old pipeline could not
finish in reasonable time, now produces a witness that reconstructs
the full slab size ladder (8, 16, 32, 64, 128, 256, 512) and
pinpoints the divergence at `slabs[6]`.
