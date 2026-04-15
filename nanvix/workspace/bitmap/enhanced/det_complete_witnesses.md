# Bitmap Determinism — Complete Witnesses (All Fields Concrete)

## Function: `new(number_of_bits: usize) -> Result<Bitmap, Error>`

### Witness (Liveness Gap)

```
INPUT:
  number_of_bits = 8

OUTPUT 1 (y1):
  result = Ok(bitmap) where
    bitmap@ = BitmapView {
      num_bits: 8,
      set_bits: {},          // Set::<int>::empty()
    }
    // derived: usage() = 0, is_empty() = true

OUTPUT 2 (y2):
  result = Err(e)            // e is any Error (unconstrained)

BOTH SATISFY SPEC:
  y1: Ok branch — inv() ✓, num_bits == 8 ✓, is_empty() ✓
  y2: Err branch — spec only says "nb==0 ==> Err, nb>=MAX ==> Err, nb%8!=0 ==> Err"
      nb=8 triggers none of these, but Err is still allowed (no liveness guarantee)
  y1 ≠ y2 ✓

GAP: Liveness — spec never says valid input must succeed
```

---

## Function: `alloc(&mut self) -> Result<usize, Error>`

### Witness (Nondeterministic Bit Selection — Design Choice)

```
INPUT:
  pre@ = BitmapView {
    num_bits: 8,
    set_bits: {},            // Set::<int>::empty()
  }
  // derived: usage() = 0, is_empty() = true, is_full() = false

OUTPUT 1 (y1):
  result = Ok(0)
  post1@ = BitmapView {
    num_bits: 8,
    set_bits: {0},           // Set::<int>::empty().insert(0)
  }
  // derived: usage() = 1

OUTPUT 2 (y2):
  result = Ok(1)
  post2@ = BitmapView {
    num_bits: 8,
    set_bits: {1},           // Set::<int>::empty().insert(1)
  }
  // derived: usage() = 1

BOTH SATISFY SPEC (alloc Ok branch):
  y1: index=0, 0 < num_bits ✓, !pre.is_bit_set(0) ✓, post.is_bit_set(0) ✓,
      frame (all other bits unchanged) ✓, set_bits == {}.insert(0) ✓, usage == 0+1 ✓
  y2: index=1, same checks with bit 1 ✓
  y1 ≠ y2 ✓ (different index AND different post-state)

GAP: Nondeterministic bit selection — DESIGN CHOICE (spec intentionally abstracts over allocation strategy)
```

---

## Function: `set(&mut self, index: usize) -> Result<(), Error>`

### Witness (Error Code Wildcard)

```
INPUT:
  pre@ = BitmapView {
    num_bits: 8,
    set_bits: {},            // Set::<int>::empty()
  }
  // derived: usage() = 0
  index = 10                 // out of bounds (10 >= 8)

OUTPUT 1 (y1):
  result = Err(Error { code: InvalidArgument, ... })
  post1@ = BitmapView {
    num_bits: 8,
    set_bits: {},            // unchanged
  }
  // post1@ == pre@

OUTPUT 2 (y2):
  result = Err(Error { code: ResourceBusy, ... })
  post2@ = BitmapView {
    num_bits: 8,
    set_bits: {},            // unchanged
  }
  // post2@ == pre@

BOTH SATISFY SPEC (set Err branch):
  y1: Err(_) — index(10) >= num_bits(8) ✓, post == pre ✓
  y2: Err(_) — same guard ✓, post == pre ✓
  Err(_) wildcard accepts any ErrorCode
  y1 ≠ y2 ✓ (different error codes)
  post1@ == post2@ (both unchanged) — nondeterminism is ONLY in error code

GAP: Error code unconstrained — Err(_) wildcard allows any ErrorCode
```
