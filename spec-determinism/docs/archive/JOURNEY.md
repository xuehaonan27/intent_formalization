# From "Let Z3 emit the witness directly" to schema-driven A'

This document summarises the architectural pivot we made recently. We
started from the natural idea of extracting a witness straight out of
Z3's `(get-model)` response, ran into two fundamental problems, and
eventually arrived at the current schema-driven A' approach.

## Starting point

`spec-determinism` is a Verus-based nondeterminism detector. The old
pipeline performed binary search by re-invoking `cargo verus verify`
once per round — roughly 2–3 s per call, 20–100 rounds per function,
and up to ~13 min on `kernel::allocate`.

When a proof obligation fails, Verus automatically emits a
`(get-model)` after the failing `(check-sat)`, and the full response
lands in `--log smt-transcript`. The naive plan was: parse that model,
decode Verus's SMT encoding back into Rust-level facts, and call it
the witness. One Verus call, one witness. Done.

We implemented this as `Z3Backend` + a model decoder (`model_eval.py`),
and it *did* give us impressive speedups on small functions (up to
76× on `bitmap::alloc_range`). But two problems kept surfacing on
realistic inputs.

## The two problems

### Problem 1. `(check-sat)` returns `unknown` — there is no model to read

Verus's default configuration disables MBQI and uses quantifier
instantiation patterns that are *incomplete for arithmetic*. On many
real queries, Z3 returns

    unknown ; (incomplete (theory arithmetic))

When this happens there is no canonical model: a later
`(get-model)` may return defaults or stale values from an earlier
branch, and trying to `solver.check()` again in z3-py raises
`there is no current model`. Worse, Verus itself also treats this
`unknown` as **verification failed**, so we could not distinguish
"genuinely nondeterministic" from "solver gave up" — which is exactly
the signal a witness is supposed to carry.

### Problem 2. Model values are `Poly!val!N`, nested fields stay opaque

Even on queries where Z3 does return `sat`, the values it gives for
complex structs are opaque universe elements. For `kernel::allocate`
we got:

    pre_self_! = (Kheap./Kheap Slab!val!0 Slab!val!1 ... Slab!val!6)
    r1!        = (Result./Ok Poly!val!81)
    r2!        = (Result./Ok Poly!val!36)

`Slab!val!N` and `Poly!val!N` are only named universe elements; Z3 is
under no obligation to commit to concrete interpretations for fields
that the proof goal does not force. Our `model_eval.py` could walk
view functions to recover `block_size`, `start_addr`, `end_addr` for
each slab, but `Set<usize>` (an uninterpreted sort) and any field
whose exact value is not required by the goal simply stayed as
`Set#12`, `Poly!val!80`, etc. The resulting "witness" looked concrete
but was unusable for downstream reasoning.

## Our solution

### High level

Two ideas, working together:

1. **Do all search at the model / SMT level, not the subprocess
   level.** Call Verus exactly once to produce the SMT vocabulary
   (types, predicates, goal); load it into z3-py; drive the entire
   narrowing loop by adding and removing assumes on that same in-memory
   model. This turns each round from a 2.5 s `cargo verus` call into a
   sub-millisecond z3-py `check()`, and it gives us direct control
   over what gets asserted — no more hoping Z3 volunteers the right
   information in a `(get-model)` response.

2. **Fuse binary search with witness generation.** Instead of treating
   the model as "the witness" and the search as "a fallback", we treat
   binary search as the witness generator:

   - when the solver returns `unsat` for some dimension, that dimension
     is part of the must-hold condition — record it and move on;
   - when the solver returns `sat` / `unknown`, or when the current
     value is still an abstract `Poly!val!N` / `Set#N`, keep
     narrowing on the offending dimension.

   The output is always a set of Rust-level assumes
   (`post_self_.set_bits.contains(0)`, `slabs[6].block_size == 512`,
   …), which are must-hold conditions rather than one exists-example,
   and they are concrete by construction — we only stop narrowing a
   dimension once we have something better than a universe element.

### Detail

1. **Schema enumeration** (`src/a_prime/schemas.py`). For every
   spec-level symbol we emit a small fixed set of schemas based on its
   type:

   - Int: `SCALAR_EQ`, `SCALAR_RANGE`
   - Bool: `BOOL_EQ`
   - Result / Option / enum: `VARIANT_IS` per variant, recursing into
     the variant payload with a parent-guard chain
   - Struct: recurse into fields
   - Set: `SET_EMPTY`, `SET_LEN_GT/EQ/RANGE`, `SET_CONTAINS`
   - Seq: `SEQ_LEN_EQ/RANGE` plus element pre-enumeration up to
     `MAX_SEQ_LEN = 8`
   - One terminal `NOT_EQUAL_FN` for the distinctness goal.

   Each schema reserves a `(guard_name, k_params)` slot in the
   generated `det_fn` template. Dependent schemas (e.g. fields of
   `r1->Ok_0`) only fire when their parent guard is on, so we never
   pre-enumerate conflicting dimensions simultaneously.

2. **One-shot template compilation**. `render_guarded_template`
   injects the extra parameters into the `det_fn` signature and emits
   `if guard_i { assume(expr_i(k_i)); }` lines in the body. A single
   `cargo verus verify` compiles this template and dumps the full SMT
   to `mm__<module>.smt2`.

3. **z3-py search loop** (`src/a_prime/search.py`). We load the SMT
   once into a `z3.Solver`, resolve each schema's guard/k SMT name by
   reflection, and run `binary_search_a_prime` which reuses the
   existing `narrow()` strategies. Inside `test_and_set`:

   - translate the Rust assume into `(schema_id, k_bindings)`;
   - build the current assumption list from all committed node
     assumes;
   - `r = solver.check(*assumptions)`;
   - `unsat ⇒ pass` (determinism forced, commit the assume),
     otherwise ⇒ `fail` (keep narrowing).

   Crucially we use `solver.check(*assumptions)` instead of
   `push / add / check / pop`. The former keeps all learned clauses
   across rounds; the latter discards them on every pop, which is what
   crushed us on deeply nested `Seq<Struct<Set, Set>>` inputs.

4. **Untranslatable assumes** fall through as `pass_untranslatable`:
   the search treats them as "too weak to prove determinism here",
   moves on, and still produces a sound (possibly less detailed)
   witness. This keeps the system robust when a schema happens not to
   cover a Rust expression shape.

## Results

14 `exec` functions across `bitmap`, `slab`, `kernel`:

| Version | Total search time | `kernel::allocate` | Witness quality |
|---|---|---|---|
| Old pipeline (subprocess per round) | 1756 s | ~13 min | narrow output |
| Z3Backend (raw `(get-model)`) | — | ~7 s | concrete where forced, `Poly!val!N` / `Set#N` elsewhere |
| A' Phase 2 (scalar / variant / bool) | 56 s | 0.7 s | Set/Seq skipped |
| A' Phase 3 (full schemas + assumption-based `check`) | **187 s** | 176 s | full, incl. all 7 slabs' `block_size` / `start_addr` / `end_addr` and Set narrowing |

Overall **≈ 9.4× faster** than the old pipeline, with strictly richer
witnesses. `kernel::allocate`, which the old pipeline could not finish
in reasonable time, now produces a 116-assume witness that correctly
reconstructs the slab allocator's size ladder (8, 16, 32, 64, 128,
256, 512) and pinpoints the divergence at `slabs[6]`.

The per-round cost inside the z3-py loop went from 672 ms under
`push/pop` down to ~49 ms with `solver.check(*assumptions)` on the
worst case — a 14× improvement from clause reuse alone, which is what
made Phase 3 viable.
