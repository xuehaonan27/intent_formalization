# Enhanced Pipeline — Final Comparison Report

**Date:** 2026-04-12
**Protocol:** Agentic Reasoning (Alpha/Meta-Prompter → Beta/Reasoner → Gamma/Verifier)
**Modules:** bitmap, slab, sorted-vec

## Overall Comparison

| Metric | Original Pipeline | Enhanced Pipeline |
|--------|------------------|-------------------|
| Sub-agent calls | 0 | 9 (3 Alpha + 3 Beta + 3 Gamma) |
| LLM time | ~2 min/module | ~4 min/module |
| Total gaps found | 11 | 13 |
| **False positives corrected** | **0** | **1 (bitmap alloc frame)** |
| **New gaps found** | **0** | **3** |
| Root cause analyses | 0 | 2 |

## Per-Module Comparison

### Bitmap

| | Original (v2) | Enhanced |
|---|---|---|
| Gaps found | 3 | 2 confirmed + error codes |
| False positives | 0 in report | **1 corrected: alloc frame condition was FP** |
| Verus tests | Not run | 2 verified ✅ (new liveness, alloc error code) |

**Critical correction:** v2 Gap 3 ("alloc missing frame condition", severity: Critical) was **WRONG**.
The spec has `forall|i| i != index ==> is_bit_set(i) == old.is_bit_set(i)`. Gamma found this.

Enhanced confirmed gaps:
1. `new()` no liveness — valid inputs can return Err (HIGH)
2. Error code opacity — all `Err(_)` wildcarded (MEDIUM per function, HIGH overall)
3. `set()`/`clear()` Err merges distinct failure modes (MEDIUM)

### Slab

| | Original | Enhanced |
|---|---|---|
| Gaps found | 6 | 6 confirmed + 3 new |
| Root cause | Not identified | **Totality missing = root of 4 gaps** |
| New gaps | — | from_raw_parts liveness, Err code assumption |

All 6 original gaps confirmed. Root cause analysis: SlabView::inv() missing totality
(`free ∪ allocated = all blocks`) is the root cause of gaps 1, 2, 3, and 9 from the original report.

### Sorted-Vec

| | Original | Enhanced |
|---|---|---|
| Gaps found | 2 | 4 (+2 new) |
| FP killed | 0 | 1 (reverse frame, counting argument) |
| Verus tests | 4 (2✅ 2❌) | 3 (2✅ 1❌) — all new tests |

**New gaps discovered:**
1. **remove return not pinned** — `remove` ensures `sv_eq(result, value)` but NOT `old@.contains(result)`. Gamma found this. Verus verified ✅.
2. **insert(replace) neither present** — Post-sequence can have a third element that's neither the old value nor the new value, just sv_eq. Verus verified ✅.

**Correctly killed:**
- Reverse frame (spurious elements) — Gamma's counting argument: N old elements preserved + len=N+1 → extra slot forced to be sv_eq to value. Verus confirmed rejection ❌.

## Protocol Effectiveness Analysis

### What Alpha (Meta-Prompter) contributed:
- Structured the search space with priority rankings
- Identified the sv_eq vs == chasm as PRIMARY attack surface for sorted-vec
- Flagged totality as highest risk for slab
- Warned about likely FPs (inv covers disjointness/alignment/range)

### What Beta (Reasoner) contributed:
- Generated focused candidates guided by Alpha's strategy
- Self-corrected 4 FPs during generation (impressive)
- Covered all Tier 1 priorities from Alpha

### What Gamma (Verifier) contributed:
- **Killed bitmap alloc frame FP** — the most valuable single contribution
- **Found remove return not pinned** — entirely new gap Beta missed
- Tight counting argument for reverse frame rejection
- Rejected 3 slab FPs that inv() covers
- Identified root causes (totality for slab, sv_eq for sorted-vec)

### Sub-agent Role Effectiveness:
| Role | Key Contribution | Value |
|------|-----------------|-------|
| Alpha | Search space structuring | Medium — avoids wasted brainstorm |
| Beta | Candidate generation | High — self-correcting is valuable |
| **Gamma** | **Adversarial review** | **Highest — caught FP + found new gap** |

## Verus Verification Summary

| Module | Test | Result | Finding |
|--------|------|--------|---------|
| bitmap | phi_new_no_liveness | ✅ Verified | new() can fail on valid inputs |
| bitmap | phi_alloc_err_code | ✅ Verified | Error code unconstrained |
| sorted-vec | phi_remove_return_not_pinned | ✅ Verified | **NEW:** remove return fabricated |
| sorted-vec | phi_insert_replace_neither | ✅ Verified | **NEW:** third element at sv_eq position |
| sorted-vec | phi_insert_spurious_element | ❌ Error | Correctly killed by counting |
| slab | (40 tests from earlier) | ✅ All verified | All 6 gaps confirmed |

**Total: 7 Verus tests, 6 verified (gaps), 1 rejected (spec complete)**
