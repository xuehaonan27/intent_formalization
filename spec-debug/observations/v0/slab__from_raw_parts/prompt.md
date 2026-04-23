# Task: close a spec-nondeterminism gap

You are editing a Verus specification file. A determinism checker has
found an input for which two spec-allowed outputs differ. Strengthen the
spec so that the spec-allowed output is uniquely determined (up to the
equivalence relation below), without over-constraining it.

## Function under spec
`slab::from_raw_parts`

## Current `lib.spec.rs`
```rust
// Copyright(c) The Maintainers of Nanvix.
// Licensed under the MIT License.

// Slab - Specifications
//
// This file contains specification functions, SlabView, and View trait for Slab.

verus! {

pub assume_specification<T: core::marker::PointeeSized> [ <*mut T>::is_null ] (ptr: *mut T) -> (result: bool)
    ensures
        result == (ptr as usize == 0),
;

pub assume_specification<T: Sized> [ <*mut T>::wrapping_add ] (p: *mut T, count: usize) -> (result: *mut T)
    ensures
        result as usize == ((p as usize + count * size_of::<T>()) % (usize::MAX + 1)) as usize,
;

pub assume_specification<T: core::marker::PointeeSized>[ <*mut T as core::cmp::PartialOrd>::lt ] (
    p: &*mut T,
    q: &*mut T
) -> (result: bool)
    ensures
        result == ((*p as usize) < (*q as usize)),
;

pub assume_specification<T: core::marker::PointeeSized>[ <*const T as core::cmp::PartialOrd>::lt ] (
    p: &*const T,
    q: &*const T
) -> (result: bool)
    ensures
        result == ((*p as usize) < (*q as usize)),
;

pub assume_specification<T: core::marker::PointeeSized>[ <*const T as core::cmp::PartialOrd>::ge ] (
    p: &*const T,
    q: &*const T
) -> (result: bool)
    ensures
        result == ((*p as usize) >= (*q as usize)),
;

pub assume_specification<T: Sized> [ <*mut T>::add ] (p: *mut T, count: usize) -> (result: *mut T)
    requires
        p as usize + count * size_of::<T>() <= usize::MAX,
        count * size_of::<T>() <= isize::MAX,
    ensures
        result as usize == p as usize + count * size_of::<T>(),
;

pub assume_specification<T: Sized> [ <*const T>::offset_from_unsigned ] (
    p: *const T,
    origin: *const T
) -> (result: usize)
    requires
        p as usize >= origin as usize,
        // The difference must be bounded by isize::MAX, according to
        // https://doc.rust-lang.org/src/core/ptr/const_ptr.rs.html#672-675
        p as usize - origin as usize <= isize::MAX,
        (p as usize - origin as usize) % (size_of::<T>() as int) == 0,
    ensures
        result == (p as usize - origin as usize) / (size_of::<T>() as int),
;

pub axiom fn axiom_align_of_u8_is_1()
    ensures
        vstd::layout::align_of::<u8>() == 1,
;

// A view of the Slab as a set of blocks, each either allocated or freed.
#[verifier::ext_equal]
pub struct SlabView {
    pub block_size: usize,
    pub start_addr: usize,
    pub end_addr: usize,
    pub allocated_addrs: Set<usize>,
    pub free_addrs: Set<usize>,
}

impl SlabView {
    pub open spec fn inv(&self) -> bool {
        &&& self.block_size > 0
        &&& self.start_addr % self.block_size == 0
        &&& self.end_addr % self.block_size == 0
        &&& self.end_addr > self.start_addr
        &&& forall|i| #[trigger] self.allocated_addrs.contains(i) ==> {
            &&& self.start_addr <= i < self.end_addr
            &&& i % self.block_size == 0
        }
        &&& forall|i| #[trigger] self.free_addrs.contains(i) ==> {
            &&& self.start_addr <= i < self.end_addr
            &&& i % self.block_size == 0
        }
        &&& self.allocated_addrs.disjoint(self.free_addrs)
    }
}

}

```

## Determinism check context
The checker expands the spec with this template (ASSUMES is where the
witness below lives):

```rust
proof fn det_from_raw_parts(addr: *mut u8, len: usize, block_size: usize, r1: Result<Slab, Error>, r2: Result<Slab, Error>)
    ensures
        ({
            &&& (match r1 {
                 Ok(slab) => {
                     &&& slab.inv()
                     &&& slab@.block_size == block_size
                     &&& slab@.start_addr >= addr as usize
                     &&& slab@.end_addr <= addr as usize + len
                     &&& slab@.allocated_addrs == Set::<usize>::empty()
                 },
                 Err(e) => {
                     &&& e.code == ErrorCode::InvalidArgument
                     &&& {
                         ||| addr as usize == 0
                         ||| len == 0
                         ||| len >= i32::MAX
                         ||| len > isize::MAX
                         ||| addr as usize + len > usize::MAX
                         ||| block_size == 0
                         ||| block_size >= i32::MAX
                         ||| block_size > (usize::MAX - 1) / (u8::BITS as int)
                         ||| len < block_size * 2
                         ||| addr as usize % block_size != 0
                     }
                 }
             })
            &&& (match r2 {
                 Ok(slab) => {
                     &&& slab.inv()
                     &&& slab@.block_size == block_size
                     &&& slab@.start_addr >= addr as usize
                     &&& slab@.end_addr <= addr as usize + len
                     &&& slab@.allocated_addrs == Set::<usize>::empty()
                 },
                 Err(e) => {
                     &&& e.code == ErrorCode::InvalidArgument
                     &&& {
                         ||| addr as usize == 0
                         ||| len == 0
                         ||| len >= i32::MAX
                         ||| len > isize::MAX
                         ||| addr as usize + len > usize::MAX
                         ||| block_size == 0
                         ||| block_size >= i32::MAX
                         ||| block_size > (usize::MAX - 1) / (u8::BITS as int)
                         ||| len < block_size * 2
                         ||| addr as usize % block_size != 0
                     }
                 }
             })
        }) ==> det_from_raw_parts_equal(r1, r2),
{
{ASSUMES}}
```

The equivalence relation used to decide "same output":

```rust
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_from_raw_parts_equal(r1: Result<Slab, Error>, r2: Result<Slab, Error>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> ((r1->Ok_0)@ == (r2->Ok_0)@)))
}
```

## Witness (committed assumes that demonstrate nondeterminism)
The checker found the following `assume`s consistent with the spec; the
last assume `!det_from_raw_parts_equal(r1, r2)` asserts the two outputs differ.

```text
len == 1
block_size == 1
r1 is Ok
r1->Ok_0@.block_size == 1
r1->Ok_0@.start_addr == 0
r1->Ok_0@.end_addr == 1
r1->Ok_0@.allocated_addrs == Set::<usize>::empty()
r1->Ok_0@.free_addrs == Set::<usize>::empty()
r2 is Ok
r2->Ok_0@.block_size == 1
r2->Ok_0@.start_addr == 0
r2->Ok_0@.end_addr == 1
r2->Ok_0@.allocated_addrs == Set::<usize>::empty()
r2->Ok_0@.free_addrs.len() > 0
r2->Ok_0@.free_addrs.len() == 1
r2->Ok_0@.free_addrs.contains(0)
!det_from_raw_parts_equal(r1, r2)
```

## What to return

Return a single fenced ```rust block containing the **full replacement
contents** of `lib.spec.rs`. Do not include any other prose.

Constraints:
- Keep all existing items; only strengthen the `ensures` of
  `from_raw_parts` (or add whatever minimal new helper items are needed).
- Do not change function signatures.
- Your fix must still be satisfied by a reasonable implementation.
