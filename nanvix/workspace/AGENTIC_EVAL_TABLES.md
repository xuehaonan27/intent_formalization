# Agentic Reasoning for Spec Testing — Evaluation Tables

## Table 1: TP and FP Comparison (with vs without Agentic Reasoning)

| Module | Pipeline | φ Tested | TP (True Gaps) | FP (False Positives) | Precision |
|--------|----------|----------|---------------|---------------------|-----------|
| Bitmap | Baseline | 18 verified | 3 | 1 (alloc frame) | 75% |
| Bitmap | + Agentic | 18 verified | **2** | **0** | **100%** |
| Slab | Baseline | 97 verified | 7 | 1 (nondeterminism) | 88% |
| Slab | + Agentic | 97 verified | **6** | **0** | **100%** |
| SortedVec | Baseline | 2 verified | 2 | 0 | 100% |
| SortedVec | + Agentic | 4 verified | **4** | **0** | **100%** |
| **Total** | **Baseline** | **117** | **12** | **2** | **86%** |
| **Total** | **+ Agentic** | **119** | **12** | **0** | **100%** |

Notes:
- Baseline = v2 automated pipeline + manual review (Tianyu + Lem)
- "+ Agentic" = Alpha(Meta-Prompter) → Beta(Reasoner) → Gamma(Verifier)
- Bitmap baseline had 3 TP but 1 was FP (alloc frame "Critical" gap was wrong) → net 2
- Slab baseline had 7 TP (6 gaps + 1 nondeterminism) but nondeterminism = design choice → net 6
- SortedVec agentic found 2 additional TPs not in baseline

## Table 2: New True Positives Found by Agentic Reasoning

| # | Module | Function | Gap | Found by | Verus |
|---|--------|----------|-----|----------|-------|
| 1 | SortedVec | `insert` (replace) | Neither old nor new value structurally present — a third sv_eq element instead | Gamma (adversarial review) | ✅ verified |
| 2 | SortedVec | `remove` | Return value not pinned to old sequence — `sv_eq(result, value)` but no `old@.contains(result)` | Gamma (found gap Beta missed) | ✅ verified |

## Table 3: False Positives Corrected by Agentic Reasoning

| # | Module | Function | Claimed Gap | Corrected by | Root Cause of FP |
|---|--------|----------|-------------|-------------|-----------------|
| 1 | Bitmap | `alloc` | Missing frame condition (v2 severity: Critical) | Gamma read actual spec | Spec HAS `forall\|i\| i!=idx ==> is_bit_set(i)==old.is_bit_set(i)` — v2 critic missed it |
| 2 | Slab | `allocate` | Nondeterministic block selection | Gamma classified as design choice | Standard allocator spec practice — deliberate underspecification |
| 3 | SortedVec | `insert` | Reverse frame — spurious elements added | Gamma counting argument | N old elements preserved + len=N+1 → extra slot forced to be sv_eq to value |

## Example 1: New TP — `remove` Return Value Not Pinned (SortedVec)

**Gap:** `remove` returns `Option<T>` where the `Some` case only guarantees `sv_eq(result, value)`. It does NOT guarantee the returned element was actually in the sequence (`old@.contains(result)` is missing). A degenerate implementation could fabricate the return value.

**Impact:** For types like `KeyValue{key, payload}` where Ord compares by key only, calling `remove(&KeyValue{key:1, payload:""})` on a vec containing `KeyValue{key:1, payload:"important"}` — the spec allows returning `KeyValue{key:1, payload:"garbage"}` that was never stored.

**Test (Verus verified ✅ = gap confirmed):**

```rust
// Target: SortedVec::remove(&mut self, value: &T) -> Option<T>
proof fn phi_c4_remove_return_not_pinned<T: Ord>(
    pre: SortedVec<T>, post: SortedVec<T>, value: T, result: Option<T>,
)
    requires
        pre.inv(),
    ensures
        post.inv(),
        result.is_some() ==> {
            &&& sv_eq(result.unwrap(), value)
            &&& post@.len() == pre@.len() - 1
            &&& !spec_contains(post@, value)
        },
        result.is_none() ==> {
            &&& !spec_contains(pre@, value)
            &&& post@ == pre@
        },
        forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post@.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    // pre = [a, b, c] sorted, b is sv_eq to value
    assume(pre@.len() == 3);
    assume(spec_lt(pre@[0], pre@[1]));
    assume(spec_lt(pre@[1], pre@[2]));
    assume(sv_eq(pre@[1], value));
    assume(spec_contains(pre@, value));
    // Fabricate return — sv_eq to value but never in sequence
    let fake_return: T;
    assume(sv_eq(fake_return, value));
    assume(!pre@.contains(fake_return));
    assume(result == Some(fake_return));
    // Post: b removed, a and c remain
    assume(post@.len() == 2);
    assume(post@[0] == pre@[0]);
    assume(post@[1] == pre@[2]);
    assume(spec_strictly_sorted(post@));
    assume(!spec_contains(post@, value));
}
// Verus: 22 verified, 0 errors (baseline 18 + 4 phi)
```

## Example 2: FP Corrected — Bitmap `alloc` Frame Condition

**Claimed gap (v2, severity: Critical):** `alloc()` spec does not preserve other bits — after allocating bit N, arbitrary other bits could be flipped.

**Why it was wrong:** The spec explicitly contains:
```rust
forall|i: int| 0 <= i < self@.num_bits && i != index
    ==> self@.is_bit_set(i) == old(self)@.is_bit_set(i)
```
This is a complete frame condition. The v2 pipeline's single-pass critic failed to check the actual ensures clauses carefully enough.

**How Gamma caught it:** During adversarial review, Gamma read the actual `alloc()` spec in the source file and found the `forall` frame condition. It explicitly marked this as "REJECTED as gap — alloc spec DOES have a frame condition" and cited the exact code.

**Impact:** Without correction, this would have been reported as a Critical severity finding in the paper — a significant error that would undermine credibility.
