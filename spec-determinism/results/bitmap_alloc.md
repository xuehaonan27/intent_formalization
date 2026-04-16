# bitmap::alloc — Determinism Check Result

**Function:** `pub fn alloc(&mut self) -> Result<usize, Error>`
**Crate:** bitmap (nanvix)
**Tool:** spec-determinism v0.1
**Total Verus calls:** 60

## Verdict: NONDETERMINISTIC

**Gap type:** Design choice — nondeterministic bit selection

## Complete Witness

```
INPUT:
  pre = Bitmap {
    num_bits: 8,
    set_bits: {},          // empty — all bits free
  }

OUTPUT 1 (y1):
  result = Ok(0)
  post = Bitmap {
    num_bits: 8,
    set_bits: {0},         // bit 0 allocated
  }

OUTPUT 2 (y2):
  result = Ok(1)
  post = Bitmap {
    num_bits: 8,
    set_bits: {1},         // bit 1 allocated
  }
```

Both outputs satisfy the spec. The spec does not constrain which free bit is selected.

## Final Assumes (12)

```
pre_self_@.num_bits == 8
pre_self_@.set_bits == Set::<int>::empty()
r1 is Ok
r1->Ok_0 == 0
r2 is Ok
r2->Ok_0 == 1
post1_self_@.num_bits == 8
post1_self_@.set_bits.len() == 1
post1_self_@.set_bits == Set::<int>::empty().insert(0)
post2_self_@.num_bits == 8
post2_self_@.set_bits.len() == 1
post2_self_@.set_bits == Set::<int>::empty().insert(1)
```

## Binary Search Trace

| Round | Phase | Constraint | Result |
|-------|-------|-----------|--------|
| R0 | initial | (none) | ❌ FAIL |
| R1 | P1:input | `pre@.num_bits >= -8 && pre@.num_bits <= 8` | ❌ FAIL |
| R2 | P1:input | `pre@.num_bits >= -8 && pre@.num_bits <= 0` | ✅ PASS |
| R3 | P1:input | `pre@.num_bits >= 1 && pre@.num_bits <= 4` | ✅ PASS |
| R4 | P1:input | `pre@.num_bits >= 5 && pre@.num_bits <= 6` | ✅ PASS |
| R5 | P1:input | `pre@.num_bits == 7` | ✅ PASS |
| R6 | P1:input | `pre@.num_bits == 8` | ❌ FAIL |
| R7 | P1:input | `pre@.set_bits == Set::empty()` | ❌ FAIL |
| R8 | P2a:result | `r1 is Ok` | ❌ FAIL |
| R9 | P2a:result | `r1->Ok_0 >= 0 && r1->Ok_0 <= 16` | ❌ FAIL |
| R10 | P2a:result | `r1->Ok_0 >= 0 && r1->Ok_0 <= 8` | ❌ FAIL |
| R11 | P2a:result | `r1->Ok_0 >= 0 && r1->Ok_0 <= 4` | ❌ FAIL |
| R12 | P2a:result | `r1->Ok_0 >= 0 && r1->Ok_0 <= 2` | ❌ FAIL |
| R13 | P2a:result | `r1->Ok_0 >= 0 && r1->Ok_0 <= 1` | ❌ FAIL |
| R14 | P2a:result | `r1->Ok_0 == 0` | ❌ FAIL |
| R15 | P2a:result | `r1->Ok_0 == 0` (dup) | ❌ FAIL |
| R16 | P2a:result | `r2 is Ok` | ❌ FAIL |
| R17 | P2a:result | `r2->Ok_0 >= 0 && r2->Ok_0 <= 16` | ❌ FAIL |
| R18 | P2a:result | `r2->Ok_0 >= 0 && r2->Ok_0 <= 8` | ❌ FAIL |
| R19 | P2a:result | `r2->Ok_0 >= 0 && r2->Ok_0 <= 4` | ❌ FAIL |
| R20 | P2a:result | `r2->Ok_0 >= 0 && r2->Ok_0 <= 2` | ❌ FAIL |
| R21 | P2a:result | `r2->Ok_0 >= 0 && r2->Ok_0 <= 1` | ❌ FAIL |
| R22 | P2a:result | `r2->Ok_0 == 0` | ✅ PASS |
| R23 | P2a:result | `r2->Ok_0 == 1` | ❌ FAIL |
| R24 | P2b:post | `post1@.num_bits >= -8 && post1@.num_bits <= 8` | ❌ FAIL |
| R25 | P2b:post | `post1@.num_bits >= -8 && post1@.num_bits <= 0` | ✅ PASS |
| R26 | P2b:post | `post1@.num_bits >= 1 && post1@.num_bits <= 4` | ✅ PASS |
| R27 | P2b:post | `post1@.num_bits >= 5 && post1@.num_bits <= 6` | ✅ PASS |
| R28 | P2b:post | `post1@.num_bits == 7` | ✅ PASS |
| R29 | P2b:post | `post1@.num_bits == 8` | ❌ FAIL |
| R30 | P2b:post | `post1@.set_bits == Set::empty()` | ✅ PASS |
| R31 | P2b:post | `post1@.set_bits.len() == 1` | ❌ FAIL |
| R32-39 | P2b:post | `post1@.set_bits.contains(-8...-1)` | ✅ PASS |
| R40 | P2b:post | `post1@.set_bits.contains(0)` | ❌ FAIL |
| R41 | P2b:post | `post1@.set_bits == {}.insert(0)` | ❌ FAIL |
| R42 | P2b:post | `post2@.num_bits >= -8 && post2@.num_bits <= 8` | ❌ FAIL |
| R43-46 | P2b:post | `post2@.num_bits` bisection | ✅ PASS |
| R47 | P2b:post | `post2@.num_bits == 8` | ❌ FAIL |
| R48 | P2b:post | `post2@.set_bits == Set::empty()` | ✅ PASS |
| R49 | P2b:post | `post2@.set_bits.len() == 1` | ❌ FAIL |
| R50-58 | P2b:post | `post2@.set_bits.contains(-8...0)` | ✅ PASS |
| R59 | P2b:post | `post2@.set_bits.contains(1)` | ❌ FAIL |
| R60 | P2b:post | `post2@.set_bits == {}.insert(1)` | ❌ FAIL |
