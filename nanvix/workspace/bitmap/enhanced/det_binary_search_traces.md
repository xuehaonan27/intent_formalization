# Bitmap Determinism Check — Complete Binary Search Traces (v2)

## Function: `new(number_of_bits) -> Result<Bitmap, Error>`

| Round | Query | Constraint | Result | Interpretation |
|-------|-------|-----------|--------|---------------|
| R0 | det_new | (none) | ❌ FAIL | nondeterminism exists |
| R1a | det_new_r1a | result1 is Ok && result2 is Ok | ❌ FAIL | two Ok bitmaps can differ |
| R1b | det_new_r1b | (none, check branch agreement) | ❌ FAIL | Ok+Err both allowed |
| R2a | det_new_r2a | number_of_bits < 100 | ❌ FAIL | trigger in [0,100) |
| R2b | det_new_r2b | number_of_bits == 8 | ❌ FAIL | **trigger at 8** |
| R2c | det_new_r2c | number_of_bits == 0 | ✅ PASS | forced Err, deterministic |

**Concrete witness:**
```
x:  number_of_bits = 8  (valid: >0, <u32::MAX, %8==0)
y1: Ok(bitmap)           — valid per spec
y2: Err(InvalidArgument) — also valid per spec
Gap: Liveness — spec never guarantees Ok for valid inputs
```

---

## Function: `alloc(&mut self) -> Result<usize, Error>`

| Round | Query | Constraint | Result | Interpretation |
|-------|-------|-----------|--------|---------------|
| R0 | det_alloc | (none) | ❌ FAIL | nondeterminism exists |
| R1 | det_alloc_r1_branch | check branch agreement | ✅ PASS | Ok/Err deterministic |
| R2 | det_alloc_r2_index | both Ok → same index? | ❌ FAIL | index nondeterministic |
| R3 | det_alloc_r3 | pre@.num_bits==8, pre@.usage()==0 | ❌ FAIL | trigger: 8-bit empty bitmap |
| R4 | det_alloc_r4 | result1==Ok(0), result2==Ok(1) | ❌ FAIL | **concrete witness valid** |

**Concrete witness:**
```
x:  pre = 8-bit bitmap, all bits free (usage==0)
y1: Ok(0), post = {bit 0 set, rest free}
y2: Ok(1), post = {bit 1 set, rest free}
Gap: Nondeterministic bit selection — DESIGN CHOICE
```

---

## Function: `set(&mut self, index) -> Result<(), Error>`

| Round | Query | Constraint | Result | Interpretation |
|-------|-------|-----------|--------|---------------|
| R0 | det_set | (none) | ❌ FAIL | nondeterminism exists |
| R1 | det_set_r1_branch | check branch agreement | ✅ PASS | Ok/Err deterministic |
| R2 | det_set_r2_err_code | both Err → same code? | ❌ FAIL | error code nondeterministic |
| R3 | det_set_r3 | pre@.num_bits==8, index==10 | ❌ FAIL | trigger: OOB index |
| R4 | det_set_r4 | y1=Err(InvalidArgument), y2=Err(ResourceBusy) | ❌ FAIL | **concrete witness valid** |

**Concrete witness:**
```
x:  pre = 8-bit bitmap, index = 10 (out of bounds)
y1: Err(InvalidArgument) — valid per spec (Err(_) wildcard)
y2: Err(ResourceBusy)    — also valid per spec
Gap: Error code unconstrained — Err(_) allows any ErrorCode
```

---

## Summary

| Function | Total rounds | Nondeterminism source | Concrete witness | Gap type |
|----------|-------------|----------------------|-----------------|----------|
| `new` | 6 | Ok vs Err on nb=8 | nb=8, y1=Ok, y2=Err | **Liveness** |
| `alloc` | 5 | index choice on empty bitmap | pre=empty 8-bit, y1=Ok(0), y2=Ok(1) | Design choice |
| `set` | 5 | error code on OOB | pre=8-bit, idx=10, y1=InvalidArgument, y2=ResourceBusy | **Error wildcard** |

**Total Verus calls: 16**
All concrete witnesses match previously known findings from LLM-based pipeline.
