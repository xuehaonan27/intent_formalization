# Bitmap Determinism Check — Binary Search Traces

## Function: `new(number_of_bits) -> Result<Bitmap, Error>`

### Round 0: Full determinism check
```rust
proof fn det_new(number_of_bits, result1, result2)
    ensures Q(nb, result1) && Q(nb, result2) ==> result1 == result2
```
**Result: ❌ FAIL** → nondeterminism exists

### Round 1a: L1 — Both Ok → same bitmap?
```rust
ensures ... && result1 is Ok && result2 is Ok ==> result1 == result2
```
**Result: ❌ FAIL** → two Ok bitmaps can differ

### Round 1b: L1 — Same branch?
```rust
ensures ... ==> (result1 is Ok <==> result2 is Ok)
```
**Result: ❌ FAIL** → one Ok, one Err allowed for same input

### Round 2a: L3 — Narrow input: number_of_bits < 100?
```rust
ensures ... && number_of_bits < 100 ==> (result1 is Ok <==> result2 is Ok)
```
**Result: ❌ FAIL** → trigger in small range

### Round 2b: L3 — Narrow input: number_of_bits == 8?
```rust
ensures ... && number_of_bits == 8 ==> (result1 is Ok <==> result2 is Ok)
```
**Result: ❌ FAIL** → **TRIGGER FOUND: number_of_bits = 8**

### Round 2c: L3 — Control: number_of_bits == 0?
```rust
ensures ... && number_of_bits == 0 ==> (result1 is Ok <==> result2 is Ok)
```
**Result: ✅ PASS** → forced Err (deterministic)

### Final witness
```
Input:  number_of_bits = 8
y1:     Ok(bitmap)    — valid per spec
y2:     Err(...)      — also valid per spec
Gap:    Liveness — spec never guarantees Ok for valid inputs
```

---

## Function: `alloc(&mut self) -> Result<usize, Error>`

### Round 0: Full determinism check
```rust
proof fn det_alloc(pre, post1, post2, result1, result2)
    requires pre.inv()
    ensures Q(pre, post1, result1) && Q(pre, post2, result2) ==> result1 == result2 && post1@ == post2@
```
**Result: ❌ FAIL** → nondeterminism exists

### Round 1: L1 — Same branch?
```rust
ensures ... ==> (result1 is Ok <==> result2 is Ok)
```
**Result: ✅ PASS** → branch is deterministic (is_full() is biconditional)

### Round 2: L1 — Both Ok → same index?
```rust
ensures ... && result1 is Ok && result2 is Ok ==> result1 == result2
```
**Result: ❌ FAIL** → **different free bits can be returned**

### Round 3: L2 — Same index → same post-state?
```rust
ensures ... && result1 is Ok && result2 is Ok && result1 == result2 ==> post1@ == post2@
```
**Result: ✅ PASS** → given same index, post-state is fully determined

### Final witness
```
Input:  pre = any non-full bitmap with ≥2 free bits
y1:     Ok(index_a), post with bit a set
y2:     Ok(index_b), post with bit b set  (a ≠ b)
Gap:    Nondeterministic bit selection — DESIGN CHOICE, not a bug
```

---

## Function: `set(&mut self, index) -> Result<(), Error>`

### Round 0: Full determinism check
```rust
proof fn det_set(pre, index, post1, post2, result1, result2)
    requires pre.inv()
    ensures Q(pre, index, post1, result1) && Q(pre, index, post2, result2) ==> result1 == result2 && post1@ == post2@
```
**Result: ❌ FAIL** → nondeterminism exists

### Round 1: L1 — Same branch?
```rust
ensures ... ==> (result1 is Ok <==> result2 is Ok)
```
**Result: ✅ PASS** → branch deterministic (Err guard: `index >= num_bits || is_bit_set`)

### Round 2: L1 — Both Err → same error code?
```rust
ensures ... && result1 is Err && result2 is Err ==> result1 == result2
```
**Result: ❌ FAIL** → **error code is nondeterministic**

### Final witness
```
Input:  pre = bitmap, index >= num_bits (out of bounds)
y1:     Err(InvalidArgument)   — valid per spec (Err(_) wildcard)
y2:     Err(ResourceBusy)      — also valid per spec
Gap:    Error code unconstrained — Err(_) wildcard allows any ErrorCode
```

---

## Summary

| Function | Rounds | Source of nondeterminism | Gap type |
|----------|--------|------------------------|----------|
| `new` | 6 | Ok vs Err on valid input (nb=8) | **Liveness gap** |
| `alloc` | 3 | Which free bit returned | Design choice |
| `set` | 2 | Error code on Err | **Error wildcard** |

Total Verus calls: 11 (6 + 3 + 2)
All results match previously known findings from LLM-based pipeline.
