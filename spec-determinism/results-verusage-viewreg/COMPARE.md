# A-2 — Baseline vs. View-Registry Run

_Status: **DRAFT — numbers will be filled in by `scripts/compare_runs.py` after the auto-chain completes.**_

| | |
|---|---|
| Baseline run | `spec-determinism/results-verusage/` (commit `afec6c9`, 2026-05-09) |
| Candidate run | `spec-determinism/results-verusage-viewreg/` (`--use-view-registry`, this batch) |
| Comparator | `scripts/compare_runs.py BASELINE CANDIDATE` |
| Metric of record | **`ok_with_witness`** — Verus accepted the equal-fn yet z3 found a counterexample. This is the A-2 false-positive count. |
| Pre-stated target | ≤ 30 (a ~92 % drop from the baseline 376) |

## Headline (TODO)

> _Insert one paragraph: total drop in `ok_with_witness`, % change, plus any
> regressions in the `ok → verus_err` column._

## Totals

| project | n | ok (B) | ok (C) | verus_err (B) | verus_err (C) | **witness (B)** | **witness (C)** | Δ witness |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| atmosphere       | 1363 | 1262 |  …  | 100 |  …  | **289** | **…** | … |
| ironkv           |  214 |  170 |  …  |  44 |  …  |  **76** | **…** | … |
| memory-allocator |   16 |   15 |  …  |   1 |  …  |   **9** | **…** | … |
| nrkernel         |    8 |    6 |  …  |   2 |  …  |   **1** | **…** | … |
| vest             |    2 |    2 |  …  |   0 |  …  |   **1** | **…** | … |
| storage          |   43 |    0 |  …  |  43 |  …  |     0  |  **…** | … |
| anvil-library    |    1 |    0 |  …  |   1 |  …  |     0  |  **…** | … |
| **TOTAL**        | **1647** | **1455** | **…** | **191** | **…** | **376** | **…** | **…** |

## Per-project transition tables

For each project below, the comparator emits three sub-tables:

1. **Fixed** (witness → ok): functions where Verus now proves the equal-fn
   without a counterexample. **This is the win column.**
2. **Hardened** (witness → verus_err): functions whose equal-fn no longer
   compiles. Most likely cause: a generated `impl View` referenced a
   dependency view that isn't really in scope, or the view body used a
   primitive `@` that doesn't typecheck. Non-zero entries here need
   triage.
3. **Regressed** (ok → verus_err): functions whose equal-fn used to
   compile but no longer does. **Must be zero or near-zero** for the
   change to be considered safe to land.

### atmosphere

#### Fixed (witness → ok)
| function | viewed types involved |
|---|---|

#### Hardened (witness → verus_err)
| function | new error excerpt | likely culprit view |
|---|---|---|

#### Regressed (ok → verus_err)
| function | new error excerpt | likely culprit view |
|---|---|---|

### ironkv
_See same three sub-tables as above._

### memory-allocator
_See same three sub-tables as above._

### nrkernel
_See same three sub-tables as above._

### vest
_See same three sub-tables as above._

### storage
_See same three sub-tables as above. (Baseline had 0 witnesses but 43 verus errors; this is a recovery-direction check.)_

### anvil-library
_See same three sub-tables as above. (1 baseline verus error.)_

## View registry coverage

| project | uncovered types (pre-prefill) | L1 / L2 / L3 hits | L4 cached (accept) | L4 rejected | unresolved (any reason) |
|---|---:|---:|---:|---:|---:|
| atmosphere       | … | … | … | … | … |
| ironkv           | … | … | … | … | … |
| memory-allocator | … | … | … | … | … |
| nrkernel         | … | … | … | … | … |
| vest             | … | … | … | … | … |
| storage          | … | … | … | … | … |
| anvil-library    | … | … | … | … | … |

## Notes

- The candidate run pulls views from `spec-determinism/results-verusage/view_registry/`, which is the durable L4 cache produced by `python -m spec_determinism.view.llm prefill --project <p>`.
- Every L4 entry is gated by the **codex critic** (`spec_determinism/view/critic.py`); rejected candidates are not cached and are durably recorded in `<cache_root>/<project>/_rejected.jsonl`.
- Verdict distribution (across all `_prefill_summary.json` files): TODO.
- For any **Hardened** or **Regressed** row, the recommended triage path is:
  1. Identify the type whose `impl View` the equal-fn imports (`results-verusage-viewreg/<project>/<fn>/__equal_v.rs` will show the prelude block).
  2. Open `results-verusage/view_registry/<project>/<Type>.json`, look at `critic_issues`.
  3. If the view is wrong, delete the entry (or move it to `_rejected.jsonl`) and re-prefill that one type.

## Rerun command (for reproducibility)

```bash
# 1. (Re)build the L4 cache for each project — only needed once or when the
#    type registry has changed.
./scripts/prefill_all.sh

# 2. Run the corpus with --use-view-registry.
./scripts/rerun_corpus.sh

# 3. Generate this report.
python scripts/compare_runs.py \
    spec-determinism/results-verusage \
    spec-determinism/results-verusage-viewreg \
    > spec-determinism/results-verusage-viewreg/COMPARE.md
```
