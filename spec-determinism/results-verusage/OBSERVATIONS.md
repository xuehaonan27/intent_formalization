# verusage spec-determinism run — observations (2026-04-24)

Source: `~/intent_formalization/verusage/source-projects/<proj>/verified/`
Run:    `nohup spec-determinism-verusage` per project, `--timeout 60`s
Total wall: 65 minutes for 1 647 targets across 9 projects.

Numbers per project — see `SUMMARY.json` for the canonical breakdown.
Headline figures:

|                | total | ok  | with witness | verus_error | search_error |
|----------------|------:|----:|-------------:|------------:|-------------:|
| atmosphere     | 1 363 | 757 |          757 |         602 |            3 |
| ironkv         |   214 |  85 |           68 |         129 |            0 |
| memory-alloc.  |    16 |  10 |            5 |           2 |            4 |
| nrkernel       |     8 |   6 |            6 |           2 |            0 |
| storage        |    43 |   0 |            0 |          43 |            0 |
| vest           |     2 |   2 |            1 |           0 |            0 |
| anvil-library  |     1 |   0 |            0 |           1 |            0 |
| anvil-control. |     0 |   — |            — |           — |            — |
| node-replic.   |     0 |   — |            — |           — |            — |
| **total**      | **1 647** | **860** | **837** | **779** | **7** |

`runner_crash` = 1 (atmosphere) is in the rounding above.

## Three failure modes diagnosed

### 1. `storage` — 43/43 verus_error: missing dependency crate

Every target file imports `deps_hack`:

```
error[E0432]: unresolved import `deps_hack`
 --> ...:2:5
  | use deps_hack::{PmSized, pmsized_primitive};
  |     ^^^^^^^^^ use of unresolved module or unlinked crate `deps_hack`
```

`deps_hack` is a sibling crate the original project pulls from cargo
metadata. The verusage drop just dumped the `.rs` files without the
companion crates, so single-file invocation can never link. **This is
a corpus problem, not a spec-determinism bug.** Fixing it requires
either bundling stubs for `deps_hack` symbols or excluding this project
from the corpus.

### 2. `ironkv` 60% / `anvil-library` 100% verus_error: generic params not lifted

Representative tail:

```
error[E0411]: `Self` is only available in impls, traits, and type definitions
   --> .../delegation_map_v__impl1_erase.rs:165:182
    | proof fn det_remove(... pre_self_: Self, ... r1: K, ...)
    |       ----------                          ^^^^
    |       `Self` not allowed in a function

error[E0425]: cannot find type `K` in this scope
```

When the target is a generic `impl<K: KeyTrait + VerusClone>` method,
`gen_det.build_template` emits `det_<fn>(...)` at module scope without
re-introducing the type parameters, and copies `Self` / generic types
verbatim into the param list. Verus then rejects them because det fn is
no longer inside an impl. **This is a real spec-determinism limitation
that becomes the dominant breakage as soon as the corpus has generics.**

Fix sketch: extract should record (a) the impl's `Self` resolved type
and (b) the function's generic-param list with bounds; gen_det should
emit `proof fn det_<fn><K: KeyTrait + VerusClone>(... pre_self_:
StrictlyOrderedVec<K> ...)`. Affects 130 targets out of 1 647.

### 3. `atmosphere` — 100% witness rate is suspicious

Every OK case in atmosphere reports a witness, including ones that
should be trivially deterministic. Smoking gun:

`atmosphere__...__page_ptr2page_index` reports witness:
- `ptr == 0`, `r1 == 0`, `r2 == 0`, `!det_page_ptr2page_index_equal(r1, r2)`

But `det_page_ptr2page_index_equal(r1, r2) == (r1 == r2)`, so the
conjunction `r1 == 0 ∧ r2 == 0 ∧ !(r1 == r2)` is **directly unsat** in
the SMT solver. Yet schema search committed it. Likely cause: the
ensures `r1 == spec_page_ptr2page_index(ptr) ∧ r2 == spec_page_ptr2page_index(ptr)`
involves an `uninterp spec fn`, and the functional axiom (same input ⇒
same output) for `spec_page_ptr2page_index` is **not** present in the
SMT2 prelude that `build_schema_ctx` extracts from Verus's `--log-all`
dump. Without that axiom z3 has no reason to conclude `r1 == r2` and
returns sat for the whole tuple.

Counter-evidence in the same run:
- `ironkv` 68 witnesses look more plausible (assumes mention concrete
  pre-state predicates like `pre_self_@.len() == ...`).
- nanvix's `kernel::layout_to_allocator` works correctly because we
  **explicitly inject** `spec_layout_size` / `spec_layout_align`
  projections via the LLM hook landed in `6f51581`.

The atmosphere finding is a strong hint that **for opaque/uninterp
spec fns we are silently dropping their functionality axiom from
the schema solver**. Verifying this is the next investigation step.

## Witness table — useful pointers

837 targets reported a witness. Most are atmosphere (757) and ironkv
(68). The interesting tier (likely real, not the atmosphere artefact):

- `ironkv` — 68 witnesses involving `StrictlyOrderedVec`, etc.
- `nrkernel` — all 6 OK cases produce witnesses; small enough to
  audit by hand.
- `memory-allocator` — 5 witnesses on bin-size / pigeonhole helpers.
- `vest` — `set_range` (already known: Vec/slice UNKNOWN, partial).

Per-target details with assume lists are in `SUMMARY.md`
("Targets with determinism witnesses").

## Suggested next step

Decide ranking among:

1. Verify the atmosphere "100 % witness" hypothesis by re-running ONE
   target with hand-injected functional axioms for the uninterp spec
   fn. If the witness disappears, write a fix that copies relevant
   `(define-fun ...)` / function-axiom blocks from Verus's SMT2 dump
   into `build_schema_ctx`'s schema solver.
2. Implement the generics-lifting fix (item 2 above) — unlocks ~130
   more ironkv targets and changes the tier from "60 % broken" to
   "mostly green".
3. Add narrow strategies for `Vec<T>`, `Seq<T>`, `Map<K,V>`,
   `[T]` (slice), `Option<T>` so the "partial witness" flag goes
   away — most relevant for the witnesses we already have.

(1) is highest-priority because it determines whether the 757
atmosphere witnesses have any research value at all. (2) gives the
biggest quantitative win on coverage. (3) improves witness quality
once we trust the engine again.

## What's checked in

- `results-verusage/SUMMARY.md` — full per-target witness list +
  failure-mode samples (4 523 lines)
- `results-verusage/SUMMARY.json` — by-status counts per project
- `results-verusage/<proj>/full_run.json` — every target's raw result
- `results-verusage/logs/` — per-project stdout/stderr from the run
- `.gitignore` — `results-verusage/*/artifacts/` (1.6 k regeneratable
  per-target det_spec.json files; 108 MB; can be rebuilt by re-running
  the batch script)
