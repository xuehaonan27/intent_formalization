# Findings — what the witnesses tell us about nanvix's specs

This document walks through each of the 14 target functions and
classifies its determinism result as one of:

- **Tight** — the spec genuinely pins down the output; R0-deterministic
  is the right answer.
- **Loose-by-design** — nondeterministic, and this is the spec
  author's intent (e.g. allocator freedom to pick any free slot).
- **Missing ensures** — nondeterministic because the spec has a real
  gap that a conforming implementation could exploit to misbehave.
- **Unverified** — the tool could not reach a verdict (e.g. the
  target crate won't compile).

Each row is followed by the actual witness excerpt the tool produced
and, where relevant, a concrete suggestion for tightening the spec.

The equality policy for every row is the auto-generated one captured
in `results/artifacts/<crate>__<fn>/det_spec.json` (`equal_fn_def`).
Some are `errs_equivalent=True` (both-`Err` is equivalent regardless
of error code/reason) and some are `errs_equivalent=False` (every
field of every error must match).

---

## Summary

| # | Function | Rounds | Verdict |
|---|---|---:|---|
| 1 | `bitmap::number_of_bits`      |    1 | **Tight** |
| 2 | `bitmap::new`                 |   20 | **Missing ensures** (Err code unconstrained) |
| 3 | `bitmap::from_raw_array`      |    1 | **Tight** (modulo errs-equivalent policy) |
| 4 | `bitmap::alloc`               |   65 | **Loose-by-design** (allocator picks free bit) |
| 5 | `bitmap::alloc_range`         |   72 | **Loose-by-design** (allocator picks free range) |
| 6 | `bitmap::set`                 |    1 | **Tight** |
| 7 | `bitmap::clear`               |    1 | **Tight** |
| 8 | `bitmap::test`                |    1 | **Tight** |
| 9 | `slab::from_raw_parts`        |   67 | **Missing ensures** (start/end/free_addrs under-specified) |
| 10 | `slab::allocate`             |   94 | **Loose-by-design** (allocator picks free addr) |
| 11 | `slab::deallocate`           |    1 | **Tight** |
| 12 | `kernel::from_raw_parts`     |   65 | **Missing ensures** (Err reason string unconstrained) |
| 13 | `kernel::allocate`           | 3567 | **Loose-by-design** (allocator picks free addr; huge context) |
| 14 | `kernel::deallocate`         |    1 | **Tight** |
| 15 | `kernel::layout_to_allocator` |   — | **Unverified** (pre-existing stale `Slab1024` artifact; tool cannot compile the module) |

**Tight: 7.  Loose-by-design: 4.  Missing ensures: 3.  Unverified: 1.**

Three of the 14 functions have real, actionable spec gaps that a
future tightening of the spec could close. The other nondeterminism
results match the author's intent (allocators).

---

## Detailed findings

### 1. `bitmap::number_of_bits` — **Tight**

Spec: `ensures r == self_@.num_bits`. Two runs on the same input must
return the same `num_bits`. R0 unsat is correct.

### 2. `bitmap::new` — **Missing ensures**

Witness:

```
number_of_bits == 8
r1 is Ok
r1->Ok_0@.num_bits == 8
r1->Ok_0@.set_bits == Set::<int>::empty()
r2 is Err
r2->Err_0.code is OperationNotPermitted
r2->Err_0.reason == ""
```

The spec (`lib.rs:88–99`) says

```
number_of_bits == 0 ==> result is Err,
number_of_bits >= u32::MAX ==> result is Err,
number_of_bits % (u8::BITS as usize) != 0 ==> result is Err,
```

plus structural ensures on `Ok`. It says nothing about **which error
code** to return, nor does it have a forward direction for valid
inputs. A conforming impl is therefore allowed to return
`Err(OperationNotPermitted)` on a perfectly valid `number_of_bits == 8`
— which the witness exhibits.

The actual implementation only ever returns `Err(InvalidArgument,
"invalid length" | "length must be a multiple of 8")` (via the
length-check branches) or `RawArray::new`'s OOM propagation. Tightening
the spec to match that is a local edit:

```rust
result matches Err(e) ==> e.code is InvalidArgument
```

and, optionally, require the specific reasons for each branch if they
are part of the intended interface contract.

### 3. `bitmap::from_raw_array` — **Tight**

R0 unsat. On `Ok(bitmap)` the spec uniquely pins
`bitmap@.num_bits`, `bitmap@.is_empty()`, and every
`is_bit_set(i)`. The `errs_equivalent=True` policy treats two
different errors as equal. Under that policy the spec is tight; if
the policy were changed to `errs_equivalent=False` we would likely
see a `bitmap::new`-style gap.

### 4. `bitmap::alloc` — **Loose-by-design**

Witness:

```
pre_self_@.num_bits == 8
pre_self_@.set_bits == Set::<int>::empty()
r1 is Ok, r1->Ok_0 == 0
r2 is Ok, r2->Ok_0 == 1
post1_self_@.set_bits.contains(0)
post2_self_@.set_bits.contains(1)
```

The spec says `Ok(index)` must satisfy `0 <= index < num_bits` and
`!pre@.is_bit_set(index)` — i.e. "some free bit". It deliberately
does not commit to a specific bit. Two runs on an all-zero bitmap
can legitimately return `0` and `1`. **Intended underdetermination.**

### 5. `bitmap::alloc_range` — **Loose-by-design**

Same pattern as `alloc`: spec asks for some free contiguous range of
length `size`; witness picks `start=0` vs `start=1`.

### 6–8. `bitmap::set` / `clear` / `test` — **Tight**

All three pin down the post-state exactly on both `Ok` and `Err`
branches (e.g. `post_self_@.set_bits == pre.set_bits.insert(index)`),
and the `errs_equivalent=True` policy absorbs any error-detail
divergence. R0 unsat is the right answer.

### 9. `slab::from_raw_parts` — **Missing ensures**

Witness:

```
len == 1, block_size == 1
r1 is Ok, r1->Ok_0@.block_size == 1
r1->Ok_0@.start_addr == 0, r1->Ok_0@.end_addr == 1
r1->Ok_0@.free_addrs == Set::<usize>::empty()
r2 is Ok, (same block_size/start/end/allocated)
r2->Ok_0@.free_addrs.len() == 1
r2->Ok_0@.free_addrs.contains(0)
```

On `Ok`, the spec pins:

- `slab@.block_size == block_size` ✓
- `slab@.allocated_addrs == empty` ✓
- `slab@.start_addr >= addr` (only a **bound**)
- `slab@.end_addr <= addr + len` (only a **bound**)
- **nothing about `free_addrs`**

Two conforming runs are free to pick any `start_addr` in `[addr, addr+len]`,
any `end_addr` in `[0, addr+len]` (subject to invariants), and
**any free_addrs set they like**. The witness is a concrete example:
one run leaves `free_addrs` empty; the other fills it with `{0}`.

This is a real spec bug. A freshly constructed slab should
deterministically have `free_addrs = { start, start + block_size,
start + 2·block_size, ..., < end }` — which is exactly what the impl
computes. Suggested fixes:

```rust
&&& slab@.start_addr == addr as usize  // pin exact start
&&& slab@.end_addr   == spec_end(addr, len, block_size)
&&& slab@.free_addrs == spec_block_aligned_range(slab@.start_addr,
                                                 slab@.end_addr,
                                                 block_size)
```

(Depending on how the real start/end are computed from alignment,
`spec_end` and `spec_block_aligned_range` already exist in the
proof helpers or need to be added.)

### 10. `slab::allocate` — **Loose-by-design**

Witness picks addr 0 in run 1 and addr 1 in run 2 from a
two-element `free_addrs`. Spec commits to "some address in
`free_addrs`, aligned to `block_size`", then pins the exact
post-state given that choice. Classic allocator freedom.

### 11. `slab::deallocate` — **Tight**

R0 unsat. On `Ok`: `post@ == SlabView { allocated_addrs:
pre@.allocated_addrs.remove(ptr), free_addrs:
pre@.free_addrs.insert(ptr), ..pre@ }`. On `Err`: `post@ == pre@`.
Both are exact.

### 12. `kernel::from_raw_parts` — **Missing ensures**

Witness:

```
addr == 0, size == 0
r1 is Err, r1->Err_0.code is InvalidArgument, r1->Err_0.reason == ""
r2 is Err, r2->Err_0.code is InvalidArgument, r2->Err_0.reason == "string 1"
!det_from_raw_parts_equal(r1, r2)
```

This function's equal_fn is generated with `errs_equivalent=False`
(because it has structural per-code `Err` specs), so `reason`
divergence matters. Spec pins `e.code == ErrorCode::InvalidArgument`
but says nothing about `e.reason`, which is a `String`. Two runs
with the same input can legitimately return different human-readable
reasons under this spec — flagged correctly by the tool.

This is a minor but real gap. If `Err.reason` is part of the contract
(other callers branch on its content), it should be pinned:

```rust
Err(e) => {
    &&& e.code == ErrorCode::InvalidArgument
    &&& e.reason == spec_invalid_reason(addr, size)  // or a fixed string
}
```

If `reason` is purely for debugging, the equality policy should be
switched to ignore it (`errs_equivalent_on_code = True`), which would
move this row from "missing ensures" to "intentional".

### 13. `kernel::allocate` — **Loose-by-design** (with very large context)

116-assume witness. The interesting part:

```
pre_self_@.slabs[6].free_addrs.len() == 1  // only slab[6] has any free blocks
r1 is Ok, r2 is Ok
post1_self_@.slabs[6].allocated_addrs.len() == 1
post1_self_@.slabs[6].free_addrs.len() == 1   (originally 1; picked one, but not the same as r2's)
post2_self_@.slabs[6].allocated_addrs.len() == 1
post2_self_@.slabs[6].free_addrs.len() == 1
!det_allocate_equal(r1, r2, post1, post2)
```

The actual source of nondeterminism is ~10 assumes: "two Ok results,
both valid under spec, picked different ptrs from `slabs[6].free_addrs`."
The other ~105 are structural setup pinning down the seven-slab
layout (block_size 8,16,32,64,128,256,512; start/end; empty sets)
to produce a well-defined heap. This is just how `Kheap.inv()`
requires the full slab array to be fixed before we can vary the
free address inside one slab.

Same flavor as `bitmap::alloc` and `slab::allocate`: the allocator
is permitted to pick any free address. The spec is tight in every
dimension *except* "which free slot" — which is intentional.

### 14. `kernel::deallocate` — **Tight**

R0 unsat. `post@ == pre@.spec_deallocate(idx, ptr)` on `Ok`;
`post@ == pre@` on `Err`. Exact.

### 15. `kernel::layout_to_allocator` — **Unverified**

Pre-existing issue: `src/kernel/src/mm/kheap.proof.rs:370` references
a `Slab1024` variant that no longer exists in `AllocSlabIndex` (see
the `verus_error` stderr in `results/full_run.json`). The `det_fn`
never compiles, so the tool cannot run a determinism check. Nothing
to conclude about the spec itself. Recommended action: remove
`Slab1024` references from the proof module, then re-run the tool.

---

## What this tells us

- **The tool finds real gaps.** Three of the 14 functions have spec
  bugs that a determinism check surfaced — `bitmap::new`'s error code
  being unconstrained, `slab::from_raw_parts`'s `start_addr` /
  `end_addr` / `free_addrs` being unconstrained, and
  `kernel::from_raw_parts`'s error `reason` being unconstrained.
  These are the kinds of defects that escape pure functional-
  correctness review because the spec is structurally "about" the
  `Ok` path.

- **The "pass" verdicts are meaningful.** For all seven R0-deterministic
  rows, the ensures uniquely fix the output on every reachable
  branch (Ok and Err, modulo the `errs_equivalent` policy). The tool
  is not rubber-stamping trivial specs.

- **Allocator nondeterminism is a known design pattern.** Four of
  the "fail" rows are exactly this: the spec commits to "some
  valid free slot" and refuses to say which, to preserve impl
  freedom. These rows are not bugs. If a caller depends on a
  specific allocation order, the fix is at the call site (add an
  additional `ensures`), not in the allocator.

- **The slab-from-raw-parts gap is the highest-value finding.** It
  is the only case where the output of a **constructor** is
  structurally underspecified. Any client code that reads
  `slab@.free_addrs` immediately after construction could reason
  incorrectly about the slab's initial state.

## Next actions (ordered by value)

1. Tighten `slab::from_raw_parts` to pin `start_addr`, `end_addr`,
   `free_addrs` — highest signal of a real spec gap.
2. Tighten `bitmap::new` to pin the error code on each failure branch.
3. Decide whether `kernel::from_raw_parts`'s `Err.reason` is part of
   the contract — either pin it or switch the policy.
4. Fix the stale `Slab1024` artifact in `kheap.proof.rs` so
   `layout_to_allocator` becomes verifiable.
