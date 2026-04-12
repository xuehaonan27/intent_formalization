# Gamma Review — Bitmap

## Confirmed Gaps
- neg_1/2/13: new() no liveness (HIGH)
- neg_3/5/6/7/9/11: error codes unconstrained (HIGH)
- neg_14: set() merges OOB + already-set (MEDIUM)
- neg_15: clear() merges OOB + already-clear (MEDIUM)

## Rejected
- neg_4: set() Err on valid unset — Err guard constrains (FP)
- neg_8: alloc() on non-full — is_full() constrains (FP)

## Reclassified
- neg_10/12: nondeterministic alloc → DESIGN CHOICE
- neg_16: next_free hint → PROPER ABSTRACTION

## Key Finding
**Alloc frame condition EXISTS** — both alloc and alloc_range have explicit
forall|i| i != index ==> is_bit_set(i) == old.is_bit_set(i)
This contradicts findings_v2.md Gap 3. NEED TO VERIFY.

## No Missed Categories
Gamma found brainstorm was comprehensive.
