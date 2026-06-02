# atmosphere determinism corpus — status ledger (2026-06-01)

> Consolidated view of every artifact in atmosphere's verusage corpus, post the 2026-05-26 → 2026-06-01 audit chain.
> Source dataset: `/tmp/corpus_baseline/atmosphere/full_run.json` (May 24 baseline; 1363 corpus artifacts).
>
> **What changed on 2026-06-01**: 20 raw / 4 unique source-level spec functions that were classified `r0_z3 == unknown` in the baseline are now **reclassified as `complete`**. Root cause: a codegen defect (top-level-self view-registry gap; the generator falls back to structural `==` on top-level `self` instead of consulting `view_registry`). The source-level specs are themselves complete under the project's view-first equality policy — only a codegen fix (≈10 lines in `gen_det.py`'s `build_det_check_spec`) is required to flip these artifacts from `unknown` → `unsat` on the next corpus rerun. No spec change is needed for them. See [`atmosphere-unknown-A-view-gap-2026-05-28.en.md`](./atmosphere-unknown-A-view-gap-2026-05-28.en.md) for the per-case audit.

## Top-line ledger

| Class | Raw artifacts | Unique source specs | Source-level status | Tool-level status |
|---|---:|---:|---|---|
| **Complete (z3 R0 = unsat)** | 1059 | — | Complete | Proven by tool |
| **Complete (reclassified codegen-defect false positives)** | 20 | 4 | Complete (view-first policy) | Pending codegen fix to be tool-proven |
| **Complete subtotal** | **1079** | — | — | — |
| Real spec incompletes (audited) | 5 | 2 | Incomplete (`Array::new`, `StaticLinkedList::push`) | All `permitted=False` but caller chains tag `permitted=True` at the public surface; knowingly tolerated |
| z3 tool limitation, residual unknown (B+C+D) | 136 | ~60 | Likely complete (unproven) | Tool-level gap; needs trigger / quantifier engineering |
| Permitted nondeterminism (acceptable, LLM-marked) | 29 | — | Intentional public-API nondeterminism | `permitted=True` |
| Verus compile failure | 49 | — | N/A | Tool failure (artifact won't even compile) |
| Runner / infra crash | 65 | — | N/A | Tool failure (runner died) |
| **Total atmosphere corpus** | **1363** | — | — | — |

**Headline numbers under the project view-first policy:**

- `1079 / 1363` (79.2%) of atmosphere artifacts are **source-level complete and tool-confirmed (or pending only a codegen fix)**.
- `5 / 1363` (0.37%) are **real spec incompletes** (2 unique source specs, both with knowingly-tolerated public-API leak).
- `136 / 1363` (10.0%) are **z3 tool limitations** — likely complete but unproven; needs tool-side work, not spec-side.
- `29 / 1363` (2.1%) are **intentional public-API nondeterminism**.
- `114 / 1363` (8.4%) are **tool-infra failures** (verus_error or runner_crash); unclassifiable until the artifact compiles / runs.

## Audit doc index

| Doc | Scope | Cases |
|---|---|---:|
| [`atmosphere-incompleteness-cases-2026-05-26.en.md`](./atmosphere-incompleteness-cases-2026-05-26.en.md) | Real spec incompleteness (12 cases / 16 unique specs / 34 corpus artifacts). The "12 cases" merge sibling-spec families; the "16 unique specs" count each separately-authored Rust function once. The "34 corpus artifacts" reflect single-file packaging inlining and is **not** a count of distinct source-level defects. | 12 |
| [`atmosphere-unknown-A-view-gap-2026-05-28.en.md`](./atmosphere-unknown-A-view-gap-2026-05-28.en.md) | Codegen-defect false positives (4 unique specs / 20 corpus artifacts). **Reclassified to `complete`** as of 2026-06-01. Source-level complete; needs codegen fix only. | 4 |
| [`atmosphere-unknown-bucket-2026-05-27.en.md`](./atmosphere-unknown-bucket-2026-05-27.en.md) | z3 tool limitations: B (forall trigger explosion, 26 unique / 66 raw), C (multi-instance forall coordination, 33 unique / 63 raw), D (page-table walk runaway, 2 unique / 7 raw). | 61 |

## What counts as "complete"

The atmosphere project consistently writes ensures using `view()` rather than structural fields, so the **project view-first equality policy** is:

> If the self type has a `View` impl, the det check should compare `post1@ == post2@` (with `=~=` or via `view()` accessor), **not** the underlying struct's field-wise structural equality.

Under this policy:

- **Complete** = the spec uniquely determines the post-state **up to view equality**. Two implementations producing the same `@` view but differing on hidden ghost-witness bits / padding are considered equal.
- **Incomplete** = there exist two implementations that produce **different `@` views** while both satisfying the spec — i.e., the public observation under the project's chosen abstraction differs.

The 4 codegen-defect spec functions reclassified on 2026-06-01 are complete under this policy. The 2 real incomplete spec functions (`Array::new`, `StaticLinkedList::push`) admit witnesses that differ even at the view layer (e.g., `Array::new`'s `seq@` content is free; `SLL::push`'s returned `SLLIndex` is free) — those are genuine source-level defects.

## Next levers (in rough priority order)

1. **Codegen fix for top-level-self view dispatch** (≈10 lines, `gen_det.py:680-720`). Mechanically reclaims 20 raw / 4 unique unknowns → unsat on next rerun. No spec change. ([A view-gap doc](./atmosphere-unknown-A-view-gap-2026-05-28.en.md))
2. **Spec fixes for the 2 real incompletes** (`Array::new`: add per-slot ghost constraint; `SLL::push`: pin `ret == pre.free_list_head`). 5 raw artifacts removed from `permitted=False` count; all caller chains can drop `permitted=True`. ([Incompleteness doc #11 + #12](./atmosphere-incompleteness-cases-2026-05-26.en.md))
3. **Tool-level work on multi-instance forall coordination** (C bucket, 33 unique / 63 raw). Per-axis `Seq/Set/Map::ext_equal` lemma harness + r1↔r2 trigger pairing in det-check template. Single largest residual lever. ([B/C/D doc, Part C](./atmosphere-unknown-bucket-2026-05-27.en.md#part-c))
4. **Tool-level work on wide-state setter forall triggers** (B bucket, 26 unique / 66 raw). Tighter triggers, stratified narrowing. ([B/C/D doc, Part B](./atmosphere-unknown-bucket-2026-05-27.en.md#part-b))
5. **Page-table walk runaway** (D bucket, 2 unique / 7 raw). Round cap + symbolic VA enumeration. ([B/C/D doc, Part D](./atmosphere-unknown-bucket-2026-05-27.en.md#part-d))
