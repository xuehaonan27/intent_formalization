# Bitmap Determinism Check — Complete Binary Search Traces (v3 Final)

All traces follow the `spec-determinism` skill protocol:
Phase 1 = narrow input, Phase 2 = narrow output.

## Function: `new(number_of_bits: usize) -> Result<Bitmap, Error>`

Input: `number_of_bits`
Output: `result`

| Round | Phase | Active assumes | Result | Interpretation |
|-------|-------|---------------|--------|---------------|
| R0 | — | (none) | ❌ FAIL | nondeterminism exists |
| R1 | P1: input | `nb < 100` | ❌ FAIL | trigger in [0, 100) |
| R2 | P1: input | `nb == 8` | ❌ FAIL | **input found: nb=8** |
| R3 | P1: input (control) | `nb == 0` | ❌ FAIL | nb=0 also nondeterministic (error code) |
| R4 | P2: output | `nb == 8, r1 is Ok, r2 is Err` | ❌ FAIL | **witness complete** |

**Concrete witness:**
```
x:  number_of_bits = 8
y1: Ok(bitmap)  where bitmap.inv() && bitmap@.num_bits == 8 && bitmap@.is_empty()
y2: Err(e)      where e is any Error
```
**Gap: Liveness — spec allows Err on valid input**

---

## Function: `alloc(&mut self) -> Result<usize, Error>`

Input: `pre: Bitmap`
Output: `(post: Bitmap, result: Result<usize, Error>)`

| Round | Phase | Active assumes | Result | Interpretation |
|-------|-------|---------------|--------|---------------|
| R0 | — | (none) | ❌ FAIL | nondeterminism exists |
| R1 | P1: input | `pre@.num_bits == 8` | ❌ FAIL | 8-bit bitmap triggers |
| R2 | P1: input | `pre@.num_bits == 8, pre@.usage() == 0` | ❌ FAIL | **input found: 8-bit empty** |
| R3 | P2: output | `... + r1==Ok(0), r2==Ok(1)` | ❌ FAIL | **witness complete** |

**Concrete witness:**
```
x:  pre = 8-bit bitmap, all bits free (usage == 0)
y1: (post1, Ok(0))  — allocate bit 0, post1 = {bit 0 set}
y2: (post2, Ok(1))  — allocate bit 1, post2 = {bit 1 set}
```
**Gap: Nondeterministic bit selection — DESIGN CHOICE**

---

## Function: `set(&mut self, index: usize) -> Result<(), Error>`

Input: `(pre: Bitmap, index: usize)`
Output: `(post: Bitmap, result: Result<(), Error>)`

| Round | Phase | Active assumes | Result | Interpretation |
|-------|-------|---------------|--------|---------------|
| R0 | — | (none) | ❌ FAIL | nondeterminism exists |
| R1 | P1: input | `pre@.num_bits == 8` | ❌ FAIL | 8-bit bitmap triggers |
| R2 | P1: input | `pre@.num_bits == 8, index == 10` | ❌ FAIL | **input found: OOB index** |
| R3 | P2: output | `... + r1=Err(InvalidArgument), r2=Err(ResourceBusy)` | ❌ FAIL | **witness complete** |

**Concrete witness:**
```
x:  pre = 8-bit bitmap, index = 10 (out of bounds, ≥ num_bits)
y1: (post1, Err(InvalidArgument))  — post1 == pre (state unchanged)
y2: (post2, Err(ResourceBusy))     — post2 == pre (state unchanged)
```
**Gap: Error code unconstrained — Err(_) wildcard**

---

## Summary

| Function | P1 rounds | P2 rounds | Total | Gap type |
|----------|----------|----------|-------|----------|
| `new` | 3 (R1-R3) | 1 (R4) | 5 | **Liveness** |
| `alloc` | 2 (R1-R2) | 1 (R3) | 4 | Design choice |
| `set` | 2 (R1-R2) | 1 (R3) | 4 | **Error wildcard** |

**Total Verus calls: 13**
