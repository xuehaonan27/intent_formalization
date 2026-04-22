# Summary: schema-driven A' for Verus nondeterminism detection

`spec-determinism` decides whether a Verus `exec` function is
deterministic, and if not, produces a witness — a set of Rust-level
assumptions under which two runs can still diverge. The old pipeline
re-invoked `cargo verus verify` once per binary-search round (~2.5 s
each, 20–100 rounds per function; up to ~13 min on `kernel::allocate`).

A natural "optimisation" was to parse Verus's `(get-model)` response
from the SMT transcript and read the witness straight out of it. That
turned out to hit two hard walls.

## Two challenges

**1. `(check-sat)` often returns `unknown`, so there is no model to
read.** Verus disables MBQI and uses arithmetic-incomplete quantifier
patterns; on many real queries Z3 returns
`unknown ; (incomplete (theory arithmetic))`. In that state there is
no canonical model, and `(get-model)` may return stale or default
values. Worse, Verus *also* treats `unknown` as "verification failed",
so from the outside we cannot tell "genuinely nondeterministic" from
"solver gave up" — exactly the distinction the witness is supposed to
carry.

**2. Model values are abstract.** Even when Z3 returns `sat`, complex
structs land as opaque universe elements (`Slab!val!N`, `Poly!val!N`,
`Set#N`). Z3 only commits to concrete interpretations for facts the
goal forces; nested fields, `Set<usize>` contents, and similar pieces
stay symbolic. Our model decoder could walk view functions for simple
views, but could not synthesise readable witnesses for
`Seq<Struct<Set, Set>>`-shaped inputs like `kernel::allocate`.

## High-level resolution

Two ideas that work together.

**(a) Drive the whole search at the SMT / model level.** Call Verus
exactly once to produce the SMT vocabulary (types, predicates, goal),
load it into z3-py, and run the entire narrowing loop by adding and
removing assumes on that single in-memory model. Each round becomes a
sub-millisecond `solver.check()` rather than a 2.5 s subprocess call,
and we control exactly what is asserted — no reliance on whatever
`(get-model)` happens to return.

**(b) Fuse binary search with witness generation.** Instead of
treating the model as "the witness" and search as a fallback, treat
binary search as the witness generator:

- when the solver returns `unsat` for a dimension, that dimension is
  part of the must-hold condition — record it as a Rust-level assume;
- when the solver returns `sat` / `unknown`, or when the candidate
  value is still abstract (`Poly!val!N`, `Set#N`), keep narrowing on
  that dimension until something concrete is forced.

The resulting witness is a set of Rust-level must-hold conditions
(`post_self_.set_bits.contains(0)`, `slabs[6].block_size == 512`),
not a single exists-example, and is concrete by construction.

Concretely, we pre-enumerate every narrowing dimension as a
`(guard: Bool, k: Int)` schema pair, inject them into the `det_fn`
template, and let Verus compile the whole thing once. The z3-py
search then translates each Rust-level assume into an assumption
list and calls `solver.check(*assumptions)` — crucially using
assumption-based incremental solving (not `push / pop`) so that
learned clauses are reused across rounds. Schemas that cannot match a
Rust expression fall through as `pass_untranslatable`, keeping search
sound at the cost of a slightly less detailed witness.

## Results

On 14 `exec` functions across `bitmap`, `slab`, `kernel`:

| Version | Total search time | `kernel::allocate` |
|---|---|---|
| Old pipeline (subprocess per round) | 1756 s | ~13 min |
| A' Phase 2 (scalar / variant / bool schemas) | 56 s | 0.7 s |
| A' Phase 3 (+ Set/Seq, + assumption-based `check`) | **187 s** | 176 s |

Overall **≈ 9.4× faster** than the old pipeline, and witnesses are
strictly richer. `kernel::allocate`, previously impractical, now
produces a 116-assume witness that reconstructs the slab allocator's
size ladder (8, 16, 32, 64, 128, 256, 512) and pinpoints the
divergence at `slabs[6]`'s `allocated_addrs` / `free_addrs`.

The switch from `push / pop` to `solver.check(*assumptions)` alone
cut worst-case per-round time from 672 ms to 49 ms (~14×) by letting
Z3 reuse learned clauses across rounds, which is what made the full
Set/Seq schema set viable on deeply nested types.
