# Enhanced Pipeline Results — All Three Modules

**Date:** 2026-04-12
**Method:** Agentic reasoning (Alpha/Meta-Prompter → Beta/Reasoner → Gamma/Verifier)
**Budget used:** ~1.5 hours of 8

## Results Summary

### bitmap
| Metric | Original (v2) | Enhanced |
|--------|---------------|----------|
| Brainstorm candidates | 55 | 16 (more focused) |
| Confirmed gaps | 3 | 2 real + error codes |
| **FP corrected** | 0 | **1 (alloc frame was FALSE POSITIVE in v2)** |

**Critical correction:** v2's Gap 3 ("alloc missing frame condition") was **WRONG**. The alloc spec DOES have `forall|i| i != index ==> is_bit_set(i) == old.is_bit_set(i)`. Gamma caught this.

Enhanced confirmed gaps:
1. new() no liveness (HIGH) — same as v2
2. Error code opacity across all Err(_) branches (HIGH) — expanded from v2's set-only finding
3. set()/clear() merge distinct failure modes in Err guard (MEDIUM) — new finding

### slab
| Metric | Original | Enhanced |
|--------|----------|----------|
| Brainstorm candidates | 97 | 14 (much more focused) |
| Confirmed gaps | 6 | 9 (with root cause analysis) |
| FP rejected early | ~45 | 3 (inv constrains them) |

Enhanced additions:
- Root cause identified: totality missing in inv() is ROOT CAUSE of gaps 1/2/3/9
- New: from_raw_parts Err code assumption gap (#15)
- New: from_raw_parts no liveness (#16)

### sorted-vec
| Metric | Original | Enhanced |
|--------|----------|----------|
| Brainstorm candidates | 4 | 12 |
| Confirmed gaps | 2 | 4 (2 new) |
| FP killed by counting | 0 | 1 (#4 reverse frame) |

**NEW gaps found by enhanced protocol:**
1. **remove return not pinned to old sequence** — Gamma discovered this. Beta missed it entirely. Verus verified ✅.
2. **insert(replace) — neither old nor new structurally present** — refinement of original gap. Verus verified ✅.
3. **Reverse frame correctly killed** — Gamma's counting argument proven correct by Verus rejection ❌.

## Protocol Analysis

### What the agentic protocol improved:

1. **Alpha (Meta-Prompter) → focused brainstorm**: Instead of shotgun brainstorm, Beta was guided to specific high-value categories. Resulted in fewer but higher-quality candidates (16 vs 55 for bitmap).

2. **Gamma (Verifier) → caught FPs early**: 
   - bitmap: Killed alloc frame condition FP that v2's pipeline MISSED for months
   - slab: Rejected 3 FPs that inv() already covers
   - sorted-vec: Killed reverse frame with tight counting argument

3. **Gamma → found new gaps**:
   - sorted-vec: remove return not pinned (entirely new finding)
   - slab: from_raw_parts Err code assumption

4. **Self-correction**: Beta self-corrected 4 candidates (set liveness, alloc on non-full, remove round-trip, allocation order). This is a feature of the iterative protocol.

### Cost analysis:
- 3 modules × 3 phases (Alpha + Beta + Gamma) = 9 sub-agent calls
- ~1 min each = ~10 min total LLM time
- Formalize + Verus: ~5 min
- Total: ~1.5 hours human-equivalent vs ~8 hours for v2 pipeline

### Key lesson:
The biggest value-add was **Gamma correcting a false positive** (bitmap alloc frame). A wrong "Critical" finding in the v2 report would have misled paper reviewers. The adversarial review step is essential.

## Verus Verification Results (sorted-vec enhanced tests)

| Test | Result | Finding |
|------|--------|---------|
| phi_remove_return_not_pinned | ✅ Verified | NEW GAP — remove return value can be fabricated |
| phi_insert_replace_neither_present | ✅ Verified | REFINED GAP — third element at sv_eq position |
| phi_insert_spurious_element | ❌ Error | CORRECTLY REJECTED — counting argument confirmed |
