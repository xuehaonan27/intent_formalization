# Agentic Reasoning for Spec Testing — Evaluation Tables

## Table 1: TP and FP Comparison (with vs without Agentic Reasoning)

| Module | Pipeline | φ Tested | TP | FP | Precision |
|--------|----------|----------|-----|-----|----------|
| Bitmap | Baseline | 18 verified | 2 | 1 | 67% |
| Bitmap | + Agentic | 18 verified | **2** | **0** | **100%** |
| Slab | Baseline | 97 verified | 6 | 1 | 86% |
| Slab | + Agentic | 97 verified | **6** | **0** | **100%** |
| SortedVec | Baseline | 2 verified | 2 | 0 | 100% |
| SortedVec | + Agentic | 4 verified | **4** | **0** | **100%** |
| **Total** | **Baseline** | **117** | **10** | **2** | **83%** |
| **Total** | **+ Agentic** | **119** | **12** | **0** | **100%** |

Notes:
- Baseline = v2 automated pipeline + manual review (Tianyu + Lem)
- "+ Agentic" = Alpha(Meta-Prompter) → Beta(Reasoner) → Gamma(Verifier)
- TP = confirmed true spec gaps (FP already subtracted)
- FP = false positives that slipped through the pipeline undetected
- Precision = TP / (TP + FP)
- Bitmap baseline: pipeline reported 3 gaps but alloc frame was FP → 2 TP + 1 FP
- Slab baseline: pipeline reported 7 gaps but nondeterminism was design choice → 6 TP + 1 FP
- SortedVec agentic found 2 additional TPs (C3 + C4) not in baseline
- Agentic overall: +2 TP, -2 FP compared to baseline

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

---

## Lessons Learned

### 1. Multi-Agent Instruct-Following Degrades on Precise Tasks

When the pipeline was a single agent calling a parser (AST-based spec extraction), the `requires`/`ensures` were mechanically copied — guaranteed faithful. With multi-agent collaboration via Discord chat, Beta (the Reasoner) hand-wrote the proof fn specs by reading the source, introducing several deviations:

- **Dropped `requires`** — Beta wrote ensures-only proof fns. While this is logically stronger (harder to satisfy), it's not what we want: the test should match the exact contract the implementation must satisfy.
- **Flattened branch structure** — Original spec has `result.is_some() ==> { ... }, result.is_none() ==> { ... }` branches. Beta collapsed these, keeping only the relevant branch. This tests a different (weaker) spec.
- **Put bad property in ensures** — First version (v1) put the bad property in the ensures block instead of the body. This changes what Verus checks entirely.

All three issues were caught during review (by Tianyu and Gamma), but they required explicit correction cycles. The lesson: **for tasks requiring mechanical precision (exact spec copying), tool-mediated extraction is strictly better than LLM-mediated copying**, even with multiple reviewers. The agentic protocol should use the parser for spec extraction and only delegate the creative work (brainstorm, witness construction) to LLMs.

### 2. FP Detection is Significantly Stronger

The adversarial Verifier (Gamma) caught FPs through three distinct mechanisms that single-pass critics miss:

**a) Reading actual source code.** The bitmap `alloc` frame condition FP was caught because Gamma actually read the ensures clause in the source file and found the `forall|i| ...` frame. The v2 single-pass critic operated on a summary/brainstorm and never verified against the source. This is the simplest but most impactful check — "did you actually read what the spec says?"

**b) Semantic reasoning with invariants.** For bitmap, Gamma killed the `clear` C1 candidate by tracing through the invariant: `inv()` ties `usage == set_bits.len()`, so `set_bits.remove(non_member)` is a no-op but `usage - 1` creates a contradiction. This requires multi-step reasoning that combines ensures + invariant + set semantics — beyond what single-pass prompts typically achieve.

**c) Counting arguments.** For sorted-vec, Gamma killed the reverse frame (spurious elements) claim with a tight counting argument: N structurally-distinct old elements must occupy N distinct positions in a post-sequence of length N+1, leaving exactly one free slot. This slot is forced to hold an sv_eq-to-value element, so no truly spurious element can appear. This style of combinatorial reasoning emerged naturally from the adversarial debate format.

### 3. Self-Correction During Generation is Valuable

Beta (Reasoner) self-corrected 4 candidates during generation — flagging them as "low confidence" or explicitly withdrawing them. Examples:
- `set()` Err on valid unset bit — Beta noticed the Err guard constrains this
- `alloc()` on non-full bitmap — Beta noticed `is_full()` constrains the Err branch
- Slab re-allocatability after dealloc — Beta traced through set insert/remove

This is a feature of the agentic protocol: because Gamma will adversarially review, Beta has incentive to pre-filter weak candidates. In the single-pass pipeline, the generator has no such feedback loop.

### 4. Agent Role Specialization Matters

The three-role split (Meta-Prompter / Reasoner / Verifier) outperformed both single-agent and undifferentiated multi-agent approaches:

- **Alpha (Meta-Prompter)** focused the search space. Without Alpha's strategy ("sv_eq vs == is the primary attack surface"), Beta would have wasted cycles on inv-covered candidates.
- **Gamma (Verifier)** was the highest-value role — responsible for both new TPs and FP corrections. The adversarial framing ("try to kill each candidate") was key.
- **Delta (Arbitrator)** prevented duplicate work and kept the discussion on track with status tables.
- **Beta (Reasoner)** did the bulk work but was also the most error-prone (spec copying issues). This suggests Beta's role should be more tool-assisted in future iterations.
