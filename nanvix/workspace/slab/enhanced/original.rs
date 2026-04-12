// Copyright (c) The Maintainers of Nanvix.
// Licensed under the MIT license.

//==================================================================================================
// Configuration
//==================================================================================================

#![cfg_attr(not(feature = "std"), no_std)]
// To support attributes on statements, e.g., #[verus_spec(invariant ...)] while ...,
// we need `proc_macro_hygiene`.
#![cfg_attr(verus_keep_ghost, feature(proc_macro_hygiene))]

//==================================================================================================
// Modules
//==================================================================================================

#[cfg(all(test, feature = "std"))]
mod test;

//==================================================================================================
// Imports
//==================================================================================================

use ::bitmap::Bitmap;
use ::raw_array::RawArray;
use ::sys::error::{
    Error,
    ErrorCode,
};
use ::vstd::prelude::*;

// Include specifications.
#[cfg(verus_keep_ghost)]
include!("lib.spec.rs");
// Include proofs.
#[cfg(verus_keep_ghost)]
include!("lib.proof.rs");

//==================================================================================================
// Structures
//==================================================================================================

///
/// # Description
///
/// A slab allocator.
///
/// It has the following layout in memory:
///
/// ```text
/// +-------------------+--------------------------------------+
/// | Index Blocks      | Data Blocks                          |
/// +-------------------+--------------------------------------+
/// ```
///
#[verus_verify(external_derive)]
#[derive(Debug)]
pub struct Slab {
    /// An index that keeps track of free blocks.
    index: Bitmap,
    /// Base address of data blocks.
    data_addr: *mut u8,
    /// End of data blocks.
    end_addr: *const u8,
    /// Size of blocks in the slab.
    block_size: usize,
}

//==================================================================================================
// Implementations
//==================================================================================================

#[verus_verify]
impl Slab {
    ///
    /// # Description
    ///
    /// Creates a new slab allocator on the memory region starting at `addr` with `len` bytes and
    /// block size of `block_size` bytes. The slab allocator is initialized with all blocks free.
    ///
    /// # Parameters
    ///
    /// - `addr`: Start address of the memory region.
    /// - `len`: Length of the memory region in bytes.
    /// - `block_size`: Size of blocks in bytes.
    ///
    /// # Returns
    ///
    /// Upon success, a new slab allocator is returned. Upon failure, an error is returned instead
    /// and the memory may be left in an modified state.
    ///
    /// # Safety
    ///
    /// This function is unsafe for the following reasons:
    /// - It assumes that the memory region starting at `addr` with `len` bytes is valid.
    ///
    #[verus_spec(result =>
         ensures
             match result {
                 Ok(slab) => {
                     &&& slab.inv()
                     &&& slab@.block_size == block_size
                     &&& slab@.start_addr >= addr as usize
                     &&& slab@.end_addr <= addr as usize + len
                     &&& slab@.allocated_addrs == Set::<usize>::empty()
                 },
                 Err(e) => e.code == ErrorCode::InvalidArgument,
             },
    )]
    pub unsafe fn from_raw_parts(
        addr: *mut u8,
        len: usize,
        block_size: usize,
    ) -> Result<Slab, Error> {
        // Make sure the address isn't null, e.g., from a failed allocation.
        if addr.is_null() {
            return Err(Error::new(ErrorCode::InvalidArgument, "null pointer"));
        }

        // Check if length is invalid.
        if len == 0 || len >= i32::MAX as usize || len > isize::MAX as usize {
            return Err(Error::new(ErrorCode::InvalidArgument, "invalid slab length"));
        }

        // Check if the memory region wraps around.
        if addr.wrapping_add(len) < addr {
            return Err(Error::new(ErrorCode::InvalidArgument, "wrapping memory region"));
        }

        // Check if the block size is valid.
        // TODO: Make this `const U8_BITS` instead of `let u8_bits` once issue
        // https://github.com/verus-lang/verus/issues/2023 is fixed.
        let u8_bits: usize = u8::BITS as usize;
        if block_size == 0
            || block_size >= i32::MAX as usize
            || block_size > (usize::MAX - 1) / u8_bits
            || block_size > len
        {
            return Err(Error::new(ErrorCode::InvalidArgument, "invalid block size"));
        }

        // Check if `addr` is aligned to `block_size`.
        if !(addr as usize).is_multiple_of(block_size) {
            return Err(Error::new(ErrorCode::InvalidArgument, "unaligned start address"));
        }

        // Compute layout of the slab allocator.
        let total_num_blocks: usize = len / block_size;

        // The number of index blocks (`num_index_blocks`) we need is
        //  `ceil(total_num_blocks / (block_size * u8::BITS + 1))`
        // for the following reason. This condition implies:
        //  `num_index_blocks * (block_size * u8::BITS + 1) >= total_num_blocks`
        // This, in turn, implies that:
        //  `num_index_blocks * block_size * u8::BITS  >= total_num_blocks - num_index_blocks`
        // The left-hand side of this inequality is the number of bits that
        // `num_index_blocks` blocks contain. The right-hand side of this inequality
        // is the number of blocks that aren't index blocks. So, a bitmap occupying
        // `num_index_blocks` blocks can address all the blocks outside of that bitmap.
        let divisor: usize = block_size * u8_bits + 1;
        let num_index_blocks: usize = (total_num_blocks / divisor)
            + if total_num_blocks.is_multiple_of(divisor) {
                0
            } else {
                1
            };
        if num_index_blocks >= total_num_blocks {
            return Err(Error::new(ErrorCode::InvalidArgument, "insufficient blocks for index"));
        }

        proof! { Slab::lemma_can_compute_data_addr(addr, total_num_blocks, num_index_blocks, block_size, len); }
        let data_addr: *mut u8 = addr.add(num_index_blocks * block_size);

        let num_data_blocks: usize = total_num_blocks - num_index_blocks;
        let index_len: usize = (num_data_blocks / u8_bits)
            + if num_data_blocks.is_multiple_of(u8_bits) {
                0
            } else {
                1
            };

        // Instantiate index.
        proof! {
            Slab::lemma_can_create_raw_array(addr, total_num_blocks, num_index_blocks,
                                             num_data_blocks, block_size, len, index_len);
        }
        let storage: RawArray<u8> = RawArray::from_raw_parts(addr, index_len)?;

        proof! {
            assert forall|i| 0 <= i < index_len implies storage@[i] == 0 by {
                raw_array::axiom_u8_zero_is_0(storage@[i]);
            }
        }
        let mut index: Bitmap = Bitmap::from_raw_array(storage)?;

        // NOTE: The index is initialized with all blocks free, thus if we fail beyond this point
        // the memory region is left in a modified state.

        // Initialize index.
        //
        // The uppermost bits of the index may point beyond the end of
        // the allocated region. So, we need to set those bits to mark
        // them "in use" and thereby prevent them from being
        // allocated. Note that there are at most 7 such bits we need
        // to set.
        #[cfg_attr(verus_keep_ghost, verus_spec(
            invariant
                index.inv(),
                index@.num_bits == index_len * u8_bits,
                index@.set_bits == Set::new(|j: int| num_data_blocks <= j < i),
        ))]
        for i in num_data_blocks..(index_len * u8_bits) {
            index.set(i)?;
        }

        let end_addr = addr.add(total_num_blocks * block_size);
        proof! {
            Slab::lemma_from_raw_parts_establishes_inv(
                block_size, data_addr, end_addr, &index,
                addr, len, total_num_blocks, num_index_blocks,
                num_data_blocks, index_len, u8_bits,
            );
        }
        Ok(Slab {
            index,
            data_addr,
            end_addr,
            block_size,
        })
    }

    ///
    /// # Description
    ///
    /// Allocates a block of memory from the slab allocator.
    ///
    /// # Returns
    ///
    /// Upon success, a pointer to the allocated block is returned. Upon failure, an error is
    /// returned instead.
    ///
    #[verus_spec(result =>
        requires
            old(self).inv(),
        ensures
            self.inv(),
            match result {
                Ok(ptr) => {
                    let addr = ptr as usize;
                    &&& old(self)@.free_addrs.contains(addr)
                    &&& addr % self@.block_size == 0
                    &&& self@ == SlabView {
                        allocated_addrs: old(self)@.allocated_addrs.insert(addr),
                        free_addrs: old(self)@.free_addrs.remove(addr),
                        ..old(self)@
                    }
                },
                Err(_) => {
                    &&& old(self)@.free_addrs == Set::<usize>::empty()
                    &&& self@ == old(self)@
                },
            },
    )]
    pub fn allocate(&mut self) -> Result<*mut u8, Error> {
        let block: usize = self.index.alloc()?;

        proof! { self.lemma_allocate_add_is_safe(block); }
        let block_addr: *mut u8 = unsafe { self.data_addr.add(block * self.block_size) };

        proof! { self.lemma_allocate_ok(old(self), block, block_addr as usize); }

        Ok(block_addr)
    }

    ///
    /// # Description
    ///
    /// Frees a block of memory from the slab allocator.
    ///
    /// # Parameters
    ///
    /// - `ptr`: Pointer to the block to free.
    ///
    /// # Returns
    ///
    /// Upon success, `Ok(())` is returned. Upon failure, an error is returned instead.
    ///
    /// # Safety
    ///
    /// This function is unsafe for the following reasons:
    ///
    /// - It uses `offset_from_unsigned`.
    ///
    #[verus_spec(result =>
        requires
            old(self).inv(),
        ensures
            self.inv(),
            match result {
                Ok(()) => {
                    &&& old(self)@.allocated_addrs.contains(ptr as usize)
                    &&& self@ == (SlabView {
                        allocated_addrs: old(self)@.allocated_addrs.remove(ptr as usize),
                        free_addrs: old(self)@.free_addrs.insert(ptr as usize),
                        ..old(self)@
                    })
                },
                Err(_) => {
                    &&& !old(self)@.allocated_addrs.contains(ptr as usize)
                    &&& self@ == old(self)@
                },
            },
    )]
    pub unsafe fn deallocate(&mut self, ptr: *const u8) -> Result<(), Error> {
        // Return an error if the pointer is before or after the data blocks.
        if ptr < self.data_addr as *const u8 || ptr >= self.end_addr {
            return Err(Error::new(ErrorCode::BadAddress, "pointer out of bounds"));
        }

        // Return an error if the pointer isn't at a block boundary.
        if !(ptr as usize).is_multiple_of(self.block_size) {
            return Err(Error::new(ErrorCode::BadAddress, "pointer unaligned"));
        }

        proof! { self.lemma_deallocate_offset_bound(ptr); }

        // Compute the block index.
        let index: usize = unsafe { ptr.offset_from_unsigned(self.data_addr) } / self.block_size;

        proof! { self.lemma_deallocate_index_ok(ptr, index); }

        // Return an error if the block is already free.
        if !self.index.test(index)? {
            return Err(Error::new(ErrorCode::BadAddress, "block is already free"));
        }

        // Free the block.
        self.index.clear(index)?;

        proof! { self.lemma_deallocate_ok(old(self), index, ptr); }

        Ok(())
    }
}
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
// Copyright(c) The Maintainers of Nanvix.
// Licensed under the MIT License.

// Slab - Proofs
//
// This file contains lemmas and proof functions for Slab.

verus! {

impl View for Slab {
    type V = SlabView;

    closed spec fn view(&self) -> SlabView {
        let bitmap_view = self.index@;
        let data_addr_as_int = self.data_addr as usize as int;
        let set_bits = Set::<int>::new(|i: int| 0 <= i < self.num_data_blocks() && bitmap_view.is_bit_set(i));
        let free_bits = Set::<int>::new(|i: int| 0 <= i < self.num_data_blocks() && !bitmap_view.is_bit_set(i));
        SlabView {
            block_size: self.block_size,
            start_addr: self.data_addr as usize,
            end_addr: self.end_addr as usize,
            allocated_addrs: set_bits.map(|i: int| (data_addr_as_int + i * self.block_size) as usize),
            free_addrs: free_bits.map(|i: int| (data_addr_as_int + i * self.block_size) as usize),
        }
    }
}

impl Slab {
    pub open spec fn inv(&self) -> bool {
        &&& self@.inv()
        &&& self.internal_inv()
    }

    pub closed spec fn num_data_blocks(&self) -> usize {
        ((self.end_addr as usize - self.data_addr as usize) / (self.block_size as int)) as usize
    }

    pub closed spec fn internal_inv(&self) -> bool {
        &&& self.block_size > 0
        &&& self.index.inv()
        &&& self.index@.num_bits >= self.num_data_blocks()
        &&& (self.data_addr as usize) < (self.end_addr as usize) <= usize::MAX
        &&& self.data_addr as usize % self.block_size == 0
        &&& self.block_size > 0
        &&& (self.end_addr as usize - self.data_addr as usize) % (self.block_size as int) == 0
        &&& (self.end_addr as usize - self.data_addr as usize) <= isize::MAX
        &&& forall|i: int| self.num_data_blocks() as int <= i < self.index@.num_bits as int
                ==> self.index@.is_bit_set(i)
    }

    proof fn lemma_can_compute_data_addr(
        addr: *mut u8,
        total_num_blocks: usize,
        num_index_blocks: usize,
        block_size: usize,
        len: usize
    )
        requires
            ((addr as usize) + len * size_of::<u8>()) % (usize::MAX + 1) >= addr as usize,
            len <= isize::MAX,
            block_size > 0,
            total_num_blocks == len / block_size,
            num_index_blocks < total_num_blocks,
        ensures
            num_index_blocks * block_size < total_num_blocks * block_size <= len,
            (addr as usize) + (total_num_blocks * block_size) * size_of::<u8>()
                + vstd::layout::align_of::<u8>() - 1 <= usize::MAX,
            (num_index_blocks * block_size) * size_of::<u8>() <= isize::MAX,
            (addr as usize) + len * size_of::<u8>() <= usize::MAX,
    {
        axiom_align_of_u8_is_1();
        assert(size_of::<u8>() == 1);
        assert(num_index_blocks * block_size < total_num_blocks * block_size <= len) by (nonlinear_arith)
            requires
                block_size > 0,
                total_num_blocks == len / block_size,
                num_index_blocks < total_num_blocks,
        ;
        assert(num_index_blocks * block_size * size_of::<u8>() == num_index_blocks * block_size);
        assert((addr as usize) + (total_num_blocks * block_size) * size_of::<u8>() ==
               (addr as usize) + (total_num_blocks * block_size));
        assert(len * 1 == len);
        assert((addr as usize) + len <= usize::MAX) by (nonlinear_arith)
            requires
                ((addr as usize) + len) % (usize::MAX + 1) >= addr as usize,
        ;
        assert((addr as usize) + (total_num_blocks * block_size) * size_of::<u8>() <= usize::MAX);
    }

    proof fn lemma_can_create_raw_array(
        addr: *mut u8,
        total_num_blocks: usize,
        num_index_blocks: usize,
        num_data_blocks: usize,
        block_size: usize,
        len: usize,
        index_len: usize,
    )
        requires
            ((addr as usize) + len * size_of::<u8>()) % (usize::MAX + 1) >= addr as usize,
            block_size > 0,
            total_num_blocks == len / block_size,
            num_index_blocks < total_num_blocks,
            num_data_blocks == total_num_blocks - num_index_blocks,
            index_len == (num_data_blocks / (u8::BITS as usize))
                + if num_data_blocks.is_multiple_of(u8::BITS as usize) {
                    0int
                } else {
                    1int
                },
        ensures
            addr as usize + index_len * size_of::<u8>() + align_of::<u8>() - 1 <= usize::MAX,
    {
        axiom_align_of_u8_is_1();
        assert(size_of::<u8>() == 1);
        assert(addr as usize + index_len * size_of::<u8>() + align_of::<u8>() - 1 == addr as usize + index_len);
        assert((addr as usize) + len <= usize::MAX) by (nonlinear_arith)
            requires
                ((addr as usize) + len * size_of::<u8>()) % (usize::MAX + 1) >= addr as usize,
        ;
    }

    /// Proves that a freshly constructed Slab satisfies its invariant.
    proof fn lemma_from_raw_parts_establishes_inv(
        block_size: usize,
        data_addr: *mut u8,
        end_addr: *const u8,
        index: &Bitmap,
        addr: *mut u8,
        len: usize,
        total_num_blocks: usize,
        num_index_blocks: usize,
        num_data_blocks: usize,
        index_len: usize,
        U8_BITS: usize,
    )
        requires
            U8_BITS == u8::BITS as usize,
            len <= isize::MAX,
            block_size > 0,
            block_size < i32::MAX,
            num_data_blocks >= 1,
            num_data_blocks == total_num_blocks - num_index_blocks,
            num_index_blocks < total_num_blocks,
            total_num_blocks == len / block_size,
            data_addr as usize == addr as usize + num_index_blocks * block_size,
            end_addr as usize == addr as usize + total_num_blocks * block_size,
            addr as usize % block_size == 0,
            addr as usize + len * size_of::<u8>() <= usize::MAX,
            index.inv(),
            index@.num_bits == index_len * U8_BITS,
            index@.set_bits == Set::new(|j: int| num_data_blocks <= j < index_len * U8_BITS),
            index_len == (num_data_blocks / U8_BITS) + if num_data_blocks % U8_BITS == 0 { 0int } else { 1int },
        ensures
            ({
                let slab = Slab { index: *index, data_addr, end_addr, block_size };
                &&& slab@.block_size == slab.block_size
                &&& slab@.start_addr >= addr as usize
                &&& slab@.end_addr <= addr as usize + len
                &&& slab@.allocated_addrs == Set::<usize>::empty()
                &&& slab.inv()
            })
    {
        assert(size_of::<u8>() == 1);

        let slab = Slab { index: *index, data_addr, end_addr, block_size };

        // Prove internal_inv().

        vstd::arithmetic::mul::lemma_mul_is_commutative(total_num_blocks as int, slab.block_size as int);

        assert(total_num_blocks * slab.block_size <= len) by {
            vstd::arithmetic::div_mod::lemma_fundamental_div_mod(len as int, slab.block_size as int);
        }

        assert(num_index_blocks * slab.block_size + num_data_blocks * slab.block_size ==
               total_num_blocks * slab.block_size) by {
            vstd::arithmetic::mul::lemma_mul_is_distributive_add_other_way(
                slab.block_size as int,
                num_index_blocks as int,
                num_data_blocks as int
            );
        }

        assert(slab.data_addr as usize % slab.block_size == 0) by {
            vstd::arithmetic::div_mod::lemma_mod_multiples_vanish(
                num_index_blocks as int, addr as usize as int, slab.block_size as int
            );
            vstd::arithmetic::mul::lemma_mul_is_commutative(
                num_index_blocks as int, slab.block_size as int
            );
        }

        // Establish that end_addr - data_addr == num_data_blocks * block_size.
        assert(slab.end_addr as usize - slab.data_addr as usize == num_data_blocks * slab.block_size);

        // Establish num_data_blocks() == num_data_blocks (needed for choose witnesses below).
        assert(slab.num_data_blocks() == num_data_blocks) by {
            vstd::arithmetic::div_mod::lemma_div_by_multiple(
                num_data_blocks as int, slab.block_size as int,
            );
            vstd::arithmetic::mul::lemma_mul_is_commutative(
                num_data_blocks as int, slab.block_size as int,
            );
        }

        // (end_addr - data_addr) == num_data_blocks * block_size, and block_size divides it.
        assert(slab.end_addr as usize - slab.data_addr as usize == num_data_blocks * slab.block_size);
        assert((slab.end_addr as usize - slab.data_addr as usize) % (slab.block_size as int) == 0) by {
            vstd::arithmetic::div_mod::lemma_mod_multiples_basic(
                num_data_blocks as int, slab.block_size as int,
            );
            vstd::arithmetic::mul::lemma_mul_is_commutative(
                num_data_blocks as int, slab.block_size as int,
            );
        }

        // data_addr < end_addr (since num_data_blocks >= 1 and block_size > 0).
        assert(num_data_blocks * slab.block_size > 0) by (nonlinear_arith)
            requires num_data_blocks >= 1int, slab.block_size >= 1;
        assert((slab.data_addr as usize) < (slab.end_addr as usize));

        // (end_addr - data_addr) <= isize::MAX.
        assert((slab.end_addr as usize - slab.data_addr as usize) <= isize::MAX);

        assert(slab.internal_inv());

        // Prove slab@.inv() (SlabView::inv()).

        assert(slab@.end_addr % slab@.block_size == 0) by {
            vstd::arithmetic::div_mod::lemma_mod_multiples_vanish(
                slab.num_data_blocks() as int,
                slab.data_addr as usize as int,
                slab.block_size as int,
            );
            vstd::arithmetic::mul::lemma_mul_is_commutative(
                slab.num_data_blocks() as int, slab.block_size as int,
            );
        }

        assert(slab@.end_addr > slab@.start_addr) by {
            assert(num_data_blocks * slab.block_size > 0) by (nonlinear_arith)
                requires
                    num_data_blocks >= 1,
                    slab.block_size >= 1,
            ;
        }

        // After construction, no bits < num_data_blocks are set, so allocated_addrs is empty.
        assert(slab.index@.set_bits =~= Set::new(|k: int| num_data_blocks <= k < index_len * U8_BITS));
        assert forall|i: int| slab.num_data_blocks() as int <= i < slab.index@.num_bits as int
            implies slab.index@.is_bit_set(i) by {}
        assert forall|j: int| 0 <= j < slab.num_data_blocks() implies !slab.index@.is_bit_set(j) by {}
        assert(slab@.allocated_addrs =~= Set::<usize>::empty());

        assert forall|a: usize| slab@.allocated_addrs.contains(a) implies
            slab@.start_addr <= a < slab@.end_addr && a as usize % slab@.block_size == 0 by {}

        assert forall|a: usize| slab@.free_addrs.contains(a) implies
            slab@.start_addr <= a < slab@.end_addr && a % slab@.block_size == 0 by {
            let data_addr_as_int = slab.data_addr as usize as int;
            let free_bits = Set::<int>::new(|i: int| 0 <= i < slab.num_data_blocks() && !slab.index@.is_bit_set(i));
            let j = choose|j: int| free_bits.contains(j) && a == (data_addr_as_int + j * slab.block_size) as usize;
            assert(j * slab.block_size < num_data_blocks * slab.block_size) by (nonlinear_arith)
                requires 0 <= j < num_data_blocks as int, slab.block_size >= 1;
            // Overflow bound: data_addr + j * bs < data_addr + num_data_blocks * bs <= usize::MAX.
            assert(num_index_blocks * slab.block_size + num_data_blocks * slab.block_size ==
                   total_num_blocks * slab.block_size) by {
                vstd::arithmetic::mul::lemma_mul_is_distributive_add_other_way(
                    slab.block_size as int, num_index_blocks as int, num_data_blocks as int);
            }
            assert(total_num_blocks * slab.block_size <= len) by {
                vstd::arithmetic::div_mod::lemma_fundamental_div_mod(len as int, slab.block_size as int);
            }
            assert(a % slab.block_size == 0) by {
                vstd::arithmetic::mul::lemma_mul_is_commutative(j, slab.block_size as int);
                vstd::arithmetic::div_mod::lemma_mod_multiples_vanish(j, data_addr_as_int, slab.block_size as int);
            }
        }

        assert(slab@.allocated_addrs.disjoint(slab@.free_addrs));
    }

    /// Proves that the address mapping is injective: distinct block indices
    /// within [0, num_data_blocks) produce distinct addresses.
    proof fn lemma_addr_injective(
        data_addr: *mut u8,
        num_data_blocks: usize,
        block_size: usize,
        block: usize,
    )
        requires
            block_size > 0,
            block < num_data_blocks,
            data_addr as usize + num_data_blocks * block_size <= usize::MAX,
        ensures
            forall|i: int|
                0 <= i < (num_data_blocks as int) && i != (block as int)
                ==> #[trigger] ((data_addr as usize as int + i * (block_size as int)) as usize)
                    != ((data_addr as usize as int + (block as int) * (block_size as int)) as usize),
    {
        let da = data_addr as usize as int;
        let bs = block_size as int;
        let ndb = num_data_blocks as int;
        let bi = block as int;
        assert forall|i: int|
            0 <= i < ndb && i != bi
            implies
            #[trigger] ((da + i * bs) as usize) != ((da + bi * bs) as usize) by {
            assert(i * bs != bi * bs)
                by (nonlinear_arith) requires i != bi, bs > 0;
            assert(i * bs < ndb * bs)
                by (nonlinear_arith) requires 0 <= i, i < ndb, bs > 0;
            assert(bi * bs < ndb * bs)
                by (nonlinear_arith) requires 0 <= bi, bi < ndb, bs > 0;
        }
    }

    /// Proves that a set bit within the data range implies the
    /// corresponding address is in `allocated_addrs`.
    proof fn lemma_set_bit_implies_allocated(&self, i: int)
        requires
            self.internal_inv(),
            self.block_size > 0,
            0 <= i < self.num_data_blocks(),
            self.index@.is_bit_set(i),
        ensures
            self@.allocated_addrs.contains(
                (self.data_addr as usize as int + i * self.block_size) as usize,
            ),
    {
        assert(Set::<int>::new(
            |j: int| 0 <= j < self.num_data_blocks() && self.index@.is_bit_set(j)
        ).contains(i));
    }

    /// Proves that an unset bit within the data range implies the
    /// corresponding address is in `free_addrs`.
    proof fn lemma_unset_bit_implies_free(&self, i: int)
        requires
            self.internal_inv(),
            self.block_size > 0,
            0 <= i < self.num_data_blocks(),
            !self.index@.is_bit_set(i),
        ensures
            self@.free_addrs.contains(
                (self.data_addr as usize as int + i * self.block_size) as usize,
            ),
    {
        assert(Set::<int>::new(
            |j: int| 0 <= j < self.num_data_blocks() && !self.index@.is_bit_set(j)
        ).contains(i));
    }

    /// Proves that membership in `allocated_addrs` implies a set bit.
    proof fn lemma_allocated_implies_set_bit(&self, a: usize) -> (i: int)
        requires
            self.internal_inv(),
        ensures
            self@.allocated_addrs.contains(a) ==> {
                &&& 0 <= i < self.num_data_blocks()
                &&& self.index@.is_bit_set(i)
                &&& a == (self.data_addr as usize as int + i * self.block_size) as usize
            },
    {
        if self@.allocated_addrs.contains(a) {
            choose|i: int| 0 <= i < self.num_data_blocks()
                && self.index@.is_bit_set(i)
                && a == (self.data_addr as usize as int + i * self.block_size) as usize
        }
        else {
            0
        }
    }

    /// Proves that membership in `free_addrs` implies an unset bit.
    proof fn lemma_free_implies_unset_bit(&self, a: usize) -> (i: int)
        requires
            self.internal_inv(),
            self@.free_addrs.contains(a),
        ensures
            0 <= i < self.num_data_blocks(),
            !self.index@.is_bit_set(i),
            a == (self.data_addr as usize as int + i * self.block_size) as usize,
    {
        choose|i: int| 0 <= i < self.num_data_blocks()
            && !self.index@.is_bit_set(i)
            && a == (self.data_addr as usize as int + i * self.block_size) as usize
    }

    /// Proves that the pointer addition in `allocate` is OK to do.
    proof fn lemma_allocate_add_is_safe(
        &self,
        block: usize,
    )
        requires
            self.block_size > 0,
            block < (self.end_addr as usize - self.data_addr as usize) / (self.block_size as int),
            (self.end_addr as usize - self.data_addr as usize) % (self.block_size as int) == 0,
         ensures
            self.data_addr as usize + block * self.block_size < self.end_addr as usize,
            size_of::<u8>() == 1,
    {
        assert(self.data_addr as usize + block * self.block_size < self.end_addr as usize) by (nonlinear_arith)
            requires
                self.block_size > 0,
                block < (self.end_addr as usize - self.data_addr as usize) / (self.block_size as int),
                (self.end_addr as usize - self.data_addr as usize) % (self.block_size as int) == 0,
           ;
    }

    /// Proves the postconditions of `allocate` in the success case:
    /// the returned address was free, allocated_addrs gains it,
    /// free_addrs loses it, and the invariant is preserved.
    proof fn lemma_allocate_ok(
        self: &Slab,
        old_self: &Slab,
        block: usize,
        addr: usize,
    )
        requires
            old_self.inv(),
            // Bitmap alloc postconditions.
            self.index.inv(),
            0 <= block < old_self.index@.num_bits,
            !old_self.index@.is_bit_set(block as int),
            self.index@.is_bit_set(block as int),
            self.index@.num_bits == old_self.index@.num_bits,
            forall|i: int| 0 <= i < self.index@.num_bits && i != block as int
                ==> self.index@.is_bit_set(i) == old_self.index@.is_bit_set(i),
            // Frame: non-index fields unchanged.
            self.data_addr == old_self.data_addr,
            self.num_data_blocks() == old_self.num_data_blocks(),
            self.block_size == old_self.block_size,
            self.end_addr == old_self.end_addr,
            // block < num_data_blocks (from sentinel invariant).
            block < old_self.num_data_blocks(),
            // addr == data_addr + block * block_size.
            addr == old_self.data_addr as usize + block * old_self.block_size,
        ensures
            self.inv(),
            old_self@.free_addrs.contains(addr),
            self@.allocated_addrs == old_self@.allocated_addrs.insert(addr),
            self@.free_addrs == old_self@.free_addrs.remove(addr),
            self@.block_size == old_self@.block_size,
            self@.start_addr == old_self@.start_addr,
            self@.end_addr == old_self@.end_addr,
    {
        let bi = block as int;

        old_self.lemma_unset_bit_implies_free(bi);

        // Establish self.internal_inv() so we can call lemmas on self.
        // The sentinel bits (>= num_data_blocks) are unchanged since block < num_data_blocks.
        assert forall|i: int| self.num_data_blocks() as int <= i < self.index@.num_bits as int
            implies self.index@.is_bit_set(i) by {
            assert(i != block as int);
        };

        // Pre-compute overflow bound needed inside the quantifier and for lemma_addr_injective.
        assert(self.data_addr as usize + self.num_data_blocks() * self.block_size <= usize::MAX) by {
            vstd::arithmetic::div_mod::lemma_fundamental_div_mod(
                (self.end_addr as usize - self.data_addr as usize) as int, self.block_size as int
            );
            vstd::arithmetic::mul::lemma_mul_is_commutative(
                self.num_data_blocks() as int, self.block_size as int
            );
        }

        assert(self.internal_inv());

        self.lemma_set_bit_implies_allocated(bi);

        // allocated_addrs == old.insert(addr).
        assert forall|a: usize|
            #[trigger] self@.allocated_addrs.contains(a)
                || old_self@.allocated_addrs.insert(addr).contains(a)
            implies
            self@.allocated_addrs.contains(a)
                && old_self@.allocated_addrs.insert(addr).contains(a) by {
            if self@.allocated_addrs.contains(a) {
                let j = self.lemma_allocated_implies_set_bit(a);
                if j != bi { old_self.lemma_set_bit_implies_allocated(j); }
            }
            if old_self@.allocated_addrs.insert(addr).contains(a) && a != addr {
                let j = old_self.lemma_allocated_implies_set_bit(a);
                self.lemma_set_bit_implies_allocated(j);
            }
        }
        assert(self@.allocated_addrs =~= old_self@.allocated_addrs.insert(addr));

        // free_addrs == old.remove(addr).
        Slab::lemma_addr_injective(
            self.data_addr, self.num_data_blocks(), self.block_size, block,
        );
        assert forall|a: usize|
            #[trigger] self@.free_addrs.contains(a)
                || old_self@.free_addrs.remove(addr).contains(a)
            implies
            self@.free_addrs.contains(a)
                && old_self@.free_addrs.remove(addr).contains(a) by {
            if self@.free_addrs.contains(a) {
                let j = self.lemma_free_implies_unset_bit(a);
                old_self.lemma_unset_bit_implies_free(j);
            }
            if old_self@.free_addrs.remove(addr).contains(a) {
                let j = old_self.lemma_free_implies_unset_bit(a);
                self.lemma_unset_bit_implies_free(j);
            }
        }
        assert(self@.free_addrs =~= old_self@.free_addrs.remove(addr));
    }

    /// Proves the precondition of `offset_from_unsigned` for an allocated address:
    /// the offset from `data_addr` to the address fits in `isize`.
    proof fn lemma_deallocate_offset_bound(&self, ptr: *const u8)
        requires
            self.inv(),
            ptr as usize >= self.data_addr as usize,
        ensures
            (ptr as usize - self.data_addr as usize) % (size_of::<u8>() as int) == 0,
            self@.allocated_addrs.contains(ptr as usize) ==> ptr as usize - self.data_addr as usize <= isize::MAX,
    {
        let addr = ptr as usize;
        if self@.allocated_addrs.contains(addr) {
            let block_idx = self.lemma_allocated_implies_set_bit(addr);
            assert(block_idx * self.block_size < self.num_data_blocks() * self.block_size) by (nonlinear_arith)
                requires 0 <= block_idx, block_idx < self.num_data_blocks(), self.block_size > 0;
        }
    }

    /// Proves that the index computed as `(ptr - data_addr) / block_size`
    /// is in range, has its bit set, and maps back to `addr`.
    proof fn lemma_deallocate_index_ok(&self, ptr: *const u8, index: usize)
        requires
            self.inv(),
            ptr as usize >= self.data_addr as usize,
            (ptr as usize) < self.end_addr as usize,
            index == (ptr as usize - self.data_addr as usize) / (self.block_size as int) / (size_of::<u8>() as int),
            (ptr as usize) % self.block_size == 0,
        ensures
            index < self.num_data_blocks(),
            ptr as usize == self.data_addr as usize + index * self.block_size,
            self@.allocated_addrs.contains(ptr as usize) ==> self.index@.is_bit_set(index as int),
    {
        assert(index == (ptr as usize - self.data_addr as usize) / (self.block_size as int)) by (nonlinear_arith)
            requires
                index == (ptr as usize - self.data_addr as usize) / (self.block_size as int) / 1,
        ;

        let addr = ptr as usize;
        // Step 1: Prove (addr - data_addr) % block_size == 0.
        assert((addr - self.data_addr as usize) % self.block_size as int == 0) by {
            let q = self.data_addr as usize as int / self.block_size as int;
            vstd::arithmetic::div_mod::lemma_fundamental_div_mod(self.data_addr as int, self.block_size as int);
            vstd::arithmetic::mul::lemma_mul_is_commutative(self.block_size as int, q);
            vstd::arithmetic::div_mod::lemma_mod_multiples_vanish(-q, addr as int, self.block_size as int);
            vstd::arithmetic::mul::lemma_mul_unary_negation(q as int, self.block_size as int);
        }

        // Step 2: From div/mod and remainder == 0, derive addr == data_addr + index * block_size.
        vstd::arithmetic::div_mod::lemma_fundamental_div_mod(addr - self.data_addr as usize, self.block_size as int);
        vstd::arithmetic::mul::lemma_mul_is_commutative(index as int, self.block_size as int);

        // Step 3: From addr < end_addr, derive index < num_data_blocks.
        // end_addr - data_addr == num_data_blocks() * block_size (from internal_inv divisibility).
        let bs = self.block_size as int;
        let ndb = self.num_data_blocks() as int;
        let idx = index as int;
        // addr == data_addr + index * block_size, addr < end_addr == data_addr + ndb * bs.
        assert(ndb * bs == self.end_addr as usize - self.data_addr as usize) by {
            vstd::arithmetic::div_mod::lemma_fundamental_div_mod(
                (self.end_addr as usize - self.data_addr as usize) as int, self.block_size as int
            );
            vstd::arithmetic::mul::lemma_mul_is_commutative(ndb, bs);
        }
        assert(idx * bs < ndb * bs);
        assert(idx < ndb) by (nonlinear_arith)
            requires idx * bs < ndb * bs, bs > 0;

        if self@.allocated_addrs.contains(addr) {
            let block_idx = self.lemma_allocated_implies_set_bit(addr);
            let bi = block_idx;
            assert(bi * bs < ndb * bs) by (nonlinear_arith)
                requires 0 <= bi, bi < ndb, bs > 0;
            vstd::arithmetic::div_mod::lemma_div_by_multiple(block_idx, self.block_size as int);
            vstd::arithmetic::mul::lemma_mul_is_commutative(block_idx, self.block_size as int);
        }
    }

    /// Proves the postconditions of `deallocate` in the success case:
    /// the given address was allocated, allocated_addrs loses it,
    /// free_addrs gains it, and the invariant is preserved.
    proof fn lemma_deallocate_ok(
        self: &Slab,
        old_self: &Slab,
        block: usize,
        ptr: *const u8,
    )
        requires
            old_self.inv(),
            // Bitmap clear postconditions.
            self.index.inv(),
            0 <= block < old_self.index@.num_bits,
            old_self.index@.is_bit_set(block as int),
            !self.index@.is_bit_set(block as int),
            self.index@.num_bits == old_self.index@.num_bits,
            forall|i: int| 0 <= i < self.index@.num_bits && i != block as int
                ==> self.index@.is_bit_set(i) == old_self.index@.is_bit_set(i),
            // Frame: non-index fields unchanged.
            self.data_addr == old_self.data_addr,
            self.num_data_blocks() == old_self.num_data_blocks(),
            self.block_size == old_self.block_size,
            self.end_addr == old_self.end_addr,
            // block < num_data_blocks (from sentinel invariant).
            block < old_self.num_data_blocks(),
            // ptr == data_addr + block * block_size.
            ptr as usize == old_self.data_addr as usize + block * old_self.block_size,
        ensures
            self.inv(),
            old_self@.allocated_addrs.contains(ptr as usize),
            self@.allocated_addrs == old_self@.allocated_addrs.remove(ptr as usize),
            self@.free_addrs == old_self@.free_addrs.insert(ptr as usize),
            self@.block_size == old_self@.block_size,
            self@.start_addr == old_self@.start_addr,
            self@.end_addr == old_self@.end_addr,
    {
        let addr = ptr as usize;
        let bi = block as int;

        old_self.lemma_set_bit_implies_allocated(bi);

        // Establish self.internal_inv() so we can call lemmas on self.
        // The sentinel bits (>= num_data_blocks) are unchanged since block < num_data_blocks.
        assert forall|i: int| self.num_data_blocks() as int <= i < self.index@.num_bits as int
            implies self.index@.is_bit_set(i) by {
            assert(i != block as int);
        };

        self.lemma_unset_bit_implies_free(bi);

        // Establish overflow bound for lemma_addr_injective.
        assert(self.data_addr as usize + self.num_data_blocks() * self.block_size <= usize::MAX) by {
            vstd::arithmetic::div_mod::lemma_fundamental_div_mod(
                (self.end_addr as usize - self.data_addr as usize) as int, self.block_size as int
            );
            vstd::arithmetic::mul::lemma_mul_is_commutative(
                self.num_data_blocks() as int, self.block_size as int
            );
        }
        Slab::lemma_addr_injective(
            self.data_addr, self.num_data_blocks(), self.block_size, block,
        );

        // allocated_addrs == old.remove(addr).
        assert forall|a: usize|
            #[trigger] self@.allocated_addrs.contains(a)
                || old_self@.allocated_addrs.remove(addr).contains(a)
            implies
            self@.allocated_addrs.contains(a)
                && old_self@.allocated_addrs.remove(addr).contains(a) by {
            if self@.allocated_addrs.contains(a) {
                let j = self.lemma_allocated_implies_set_bit(a);
                old_self.lemma_set_bit_implies_allocated(j);
            }
            if old_self@.allocated_addrs.remove(addr).contains(a) {
                let j = old_self.lemma_allocated_implies_set_bit(a);
                self.lemma_set_bit_implies_allocated(j);
            }
        }
        assert(self@.allocated_addrs =~= old_self@.allocated_addrs.remove(addr));

        // free_addrs == old.insert(addr).
        assert forall|a: usize|
            #[trigger] self@.free_addrs.contains(a)
                || old_self@.free_addrs.insert(addr).contains(a)
            implies
            self@.free_addrs.contains(a)
                && old_self@.free_addrs.insert(addr).contains(a) by {
            if self@.free_addrs.contains(a) {
                let j = self.lemma_free_implies_unset_bit(a);
                if j != bi { old_self.lemma_unset_bit_implies_free(j); }
            }
            if old_self@.free_addrs.insert(addr).contains(a) && a != addr {
                let j = old_self.lemma_free_implies_unset_bit(a);
                self.lemma_unset_bit_implies_free(j);
            }
        }
        assert(self@.free_addrs =~= old_self@.free_addrs.insert(addr));
    }
}

}
