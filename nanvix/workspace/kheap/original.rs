// Copyright(c) The Maintainers of Nanvix.
// Licensed under the MIT License.

//==================================================================================================
// Imports
//==================================================================================================

#[allow(unused_imports)]
use ::vstd::prelude::*;

// Include specifications.
#[cfg(verus_keep_ghost)]
include!("kheap.spec.rs");
// Include proofs.
#[cfg(verus_keep_ghost)]
include!("kheap.proof.rs");

use crate::collections::Slab;
#[cfg(verus_keep_ghost)]
use crate::collections::SlabView;
use ::alloc::alloc::{
    AllocError,
    GlobalAlloc,
    Layout,
};
use ::arch::mem;
use ::config::constants;
use ::core::ptr;
use ::sys::error::{
    Error,
    ErrorCode,
};

//==================================================================================================
// Constants
//==================================================================================================

#[cfg(not(verus_keep_ghost))]
#[cfg(feature = "hyperlight")]
pub const NUM_OF_SLABS: usize = 10;
#[cfg(not(verus_keep_ghost))]
#[cfg(not(feature = "hyperlight"))]
pub const NUM_OF_SLABS: usize = 7;
#[cfg(not(verus_keep_ghost))]
const SLAB_COUNT: usize = 32;
#[cfg(not(verus_keep_ghost))]
pub const MIN_SLAB_SIZE: usize = SLAB_COUNT * mem::PAGE_SIZE;
#[cfg(not(verus_keep_ghost))]
pub const MIN_HEAP_SIZE: usize = NUM_OF_SLABS * MIN_SLAB_SIZE;

//==================================================================================================
//  Structures
//==================================================================================================

struct ArenaAllocator;

#[repr(align(4096))]
struct HeapStorage {
    memory: [u8; MIN_HEAP_SIZE],
}

::static_assert::assert_eq_align!(HeapStorage, mem::PAGE_SIZE);

static mut HEAP_STORAGE: HeapStorage = HeapStorage {
    memory: [0; MIN_HEAP_SIZE],
};

#[cfg(not(verus_keep_ghost))]
#[derive(Copy, Clone)]
enum SlabSize {
    Slab8 = 8,
    Slab16 = 16,
    Slab32 = 32,
    Slab64 = 64,
    Slab128 = 128,
    Slab256 = 256,
    Slab512 = 512,
    #[cfg(feature = "hyperlight")]
    Slab1024 = 1024,
    #[cfg(feature = "hyperlight")]
    Slab2048 = 2048,
    // FIXME (#1780): investigate what causes allocations >512 bytes under hyperlight
    // and remove these extended slab tiers once the root cause is addressed.
    #[cfg(feature = "hyperlight")]
    Slab4096 = 4096,
}

#[cfg(not(verus_keep_ghost))]
struct Kheap {
    slab_8_bytes: Slab,
    slab_16_bytes: Slab,
    slab_32_bytes: Slab,
    slab_64_bytes: Slab,
    slab_128_bytes: Slab,
    slab_256_bytes: Slab,
    slab_512_bytes: Slab,
    #[cfg(feature = "hyperlight")]
    slab_1024_bytes: Slab,
    #[cfg(feature = "hyperlight")]
    slab_2048_bytes: Slab,
    #[cfg(feature = "hyperlight")]
    slab_4096_bytes: Slab,
}

//==================================================================================================
// Global Variables
//==================================================================================================

static mut HEAP: Option<Kheap> = None;

#[global_allocator]
static mut ALLOCATOR: ArenaAllocator = ArenaAllocator;

//==================================================================================================
// Implementations
//==================================================================================================

verus! {

impl Kheap {
    // FN-2: Construct a Kheap by partitioning a raw memory region into slabs.
    unsafe fn from_raw_parts(addr: usize, size: usize) -> (result: Result<Kheap, Error>)
        requires
            // SAF-1: region must not wrap around address space
            addr as int + size as int <= usize::MAX as int,
            // SAF-2: total size must fit in isize for pointer arithmetic
            size as int <= isize::MAX as int,
        ensures
            match result {
                Ok(heap) => {
                    let slab_size = size as int / NUM_OF_SLABS as int;
                    // FN-2b: heap invariant holds
                    &&& heap.inv()
                    // FN-2c: all slabs start fully unallocated
                    &&& forall|i: int| 0 <= i < NUM_OF_SLABS as int ==>
                        (#[trigger] heap@.slabs[i]).allocated_addrs == Set::<usize>::empty()
                    // FN-2e: each slab is contained within its partition
                    &&& forall|i: int| 0 <= i < NUM_OF_SLABS as int ==> {
                        &&& (#[trigger] heap@.slabs[i]).start_addr >= addr as int + i * slab_size
                        &&& heap@.slabs[i].end_addr <= addr as int + (i + 1) * slab_size
                    }
                    // FN-2g (forward): success implies preconditions held
                    &&& addr as int % PAGE_SIZE as int == 0
                    &&& size >= MIN_HEAP_SIZE
                    &&& size as int % MIN_HEAP_SIZE as int == 0
                }
                Err(e) => {
                    // FN-2f: error code
                    &&& e.code == ErrorCode::InvalidArgument
                }
            },
    {
        // Check if start address is not page aligned.
        // VERUS DEVIATION: mem::PAGE_SIZE cfg-gated — defined outside verus! {} block
        if !addr.is_multiple_of({
            #[cfg(not(verus_keep_ghost))]
            { mem::PAGE_SIZE }
            #[cfg(verus_keep_ghost)]
            { PAGE_SIZE }
        }) {
            return Err(Error::new(ErrorCode::InvalidArgument, "unaligned start address"));
        }

        // Check if size is less than minimum heap size.
        if size < MIN_HEAP_SIZE {
            return Err(Error::new(
                ErrorCode::InvalidArgument,
                "heap size is less than minimum heap size",
            ));
        }

        // Check if size is not a multiple of the minimum heap size.
        if !size.is_multiple_of(MIN_HEAP_SIZE) {
            return Err(Error::new(
                ErrorCode::InvalidArgument,
                "size is not a multiple of the minimum heap size",
            ));
        }

        // VERUS DEVIATION: addr as *mut u8 unsupported — Verus lacks usize-to-pointer cast
        let heap_start_addr: *mut u8 = {
            #[cfg(not(verus_keep_ghost))]
            { addr as *mut u8 }
            #[cfg(verus_keep_ghost)]
            { usize_to_mut_ptr(addr) }
        };
        let slab_size: usize = size / NUM_OF_SLABS;
        #[cfg(not(verus_keep_ghost))]
        info!("heap size: {} MB", size / constants::MEGABYTE);
        #[cfg(not(verus_keep_ghost))]
        info!("slab size: {} KB", slab_size / constants::KILOBYTE);
        proof {
            broadcast use vstd::std_specs::control_flow::group_control_flow_axioms;
            assert(size_of::<u8>() == 1) by {
                broadcast use vstd::layout::layout_of_primitives;
            };
            vstd::arithmetic::div_mod::lemma_fundamental_div_mod(size as int, NUM_OF_SLABS as int);
            vstd::arithmetic::div_mod::lemma_mod_pos_bound(size as int, NUM_OF_SLABS as int);
            assert(slab_size as int * NUM_OF_SLABS as int <= size as int);
            assert(heap_start_addr as usize == addr);
            assert(1 * slab_size as int <= size as int);
            assert(2 * slab_size as int <= size as int);
            assert(3 * slab_size as int <= size as int);
            assert(4 * slab_size as int <= size as int);
            assert(5 * slab_size as int <= size as int);
            assert(6 * slab_size as int <= size as int);
        }
        Ok(Kheap {
            slab_8_bytes: Slab::from_raw_parts(
                heap_start_addr,
                slab_size,
                SlabSize::Slab8 as usize,
            )?,
            slab_16_bytes: Slab::from_raw_parts(
                heap_start_addr.add(slab_size),
                slab_size,
                SlabSize::Slab16 as usize,
            )?,
            slab_32_bytes: Slab::from_raw_parts(
                heap_start_addr.add(2 * slab_size),
                slab_size,
                SlabSize::Slab32 as usize,
            )?,
            slab_64_bytes: Slab::from_raw_parts(
                heap_start_addr.add(3 * slab_size),
                slab_size,
                SlabSize::Slab64 as usize,
            )?,
            slab_128_bytes: Slab::from_raw_parts(
                heap_start_addr.add(4 * slab_size),
                slab_size,
                SlabSize::Slab128 as usize,
            )?,
            slab_256_bytes: Slab::from_raw_parts(
                heap_start_addr.add(5 * slab_size),
                slab_size,
                SlabSize::Slab256 as usize,
            )?,
            slab_512_bytes: Slab::from_raw_parts(
                heap_start_addr.add(6 * slab_size),
                slab_size,
                SlabSize::Slab512 as usize,
            )?,
            #[cfg(feature = "hyperlight")]
            slab_1024_bytes: Slab::from_raw_parts(
                heap_start_addr.add(7 * slab_size),
                slab_size,
                SlabSize::Slab1024 as usize,
            )?,
            #[cfg(feature = "hyperlight")]
            slab_2048_bytes: Slab::from_raw_parts(
                heap_start_addr.add(8 * slab_size),
                slab_size,
                SlabSize::Slab2048 as usize,
            )?,
            #[cfg(feature = "hyperlight")]
            slab_4096_bytes: Slab::from_raw_parts(
                heap_start_addr.add(9 * slab_size),
                slab_size,
                SlabSize::Slab4096 as usize,
            )?,
        })
    }

    // FN-3: Allocate a block from the slab matching layout.size().
    unsafe fn allocate(&mut self, layout: Layout) -> (result: Result<*mut u8, AllocError>)
        requires
            // FN-3a
            old(self).inv(),
        ensures
            // FN-3e: invariant preserved
            self.inv(),
            match result {
                Ok(ptr) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-3b: address was free in the correct slab
                    &&& opt_idx.is_some()
                    &&& old(self)@.slabs[opt_idx.unwrap()].free_addrs.contains(ptr as usize)
                    // FN-3c: pointer is block-aligned
                    &&& ptr as usize % old(self)@.slabs[opt_idx.unwrap()].block_size == 0
                    // FN-3d: exact state transition
                    &&& self@ == old(self)@.spec_allocate(opt_idx.unwrap(), ptr as usize)
                }
                Err(_) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-3g: state preserved on error
                    &&& self@ == old(self)@
                    // FN-3f: error iff size unsupported or slab exhausted
                    &&& (opt_idx.is_none()
                        || old(self)@.slabs[opt_idx.unwrap()].free_addrs
                            == Set::<usize>::empty())
                }
            },
    {
        proof {
            broadcast use vstd::std_specs::control_flow::group_control_flow_axioms;
        }
        // VERUS DEVIATION: |_| → |_e| — Verus requires named variables in closure params
        match Kheap::layout_to_allocator(&layout)? {
            SlabSize::Slab8 => self.slab_8_bytes.allocate().map_err(|_e| AllocError),
            SlabSize::Slab16 => self.slab_16_bytes.allocate().map_err(|_e| AllocError),
            SlabSize::Slab32 => self.slab_32_bytes.allocate().map_err(|_e| AllocError),
            SlabSize::Slab64 => self.slab_64_bytes.allocate().map_err(|_e| AllocError),
            SlabSize::Slab128 => self.slab_128_bytes.allocate().map_err(|_e| AllocError),
            SlabSize::Slab256 => self.slab_256_bytes.allocate().map_err(|_e| AllocError),
            SlabSize::Slab512 => self.slab_512_bytes.allocate().map_err(|_e| AllocError),
            #[cfg(feature = "hyperlight")]
            SlabSize::Slab1024 => self.slab_1024_bytes.allocate().map_err(|_e| AllocError),
            #[cfg(feature = "hyperlight")]
            SlabSize::Slab2048 => self.slab_2048_bytes.allocate().map_err(|_e| AllocError),
            #[cfg(feature = "hyperlight")]
            SlabSize::Slab4096 => self.slab_4096_bytes.allocate().map_err(|_e| AllocError),
        }
    }

    // FN-4: Return a previously-allocated block to its slab.
    unsafe fn deallocate(&mut self, ptr: *mut u8, layout: Layout) -> (result: Result<(), AllocError>)
        requires
            // FN-4a
            old(self).inv(),
        ensures
            // FN-4d: invariant preserved
            self.inv(),
            match result {
                Ok(()) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-4b: pointer was allocated in the correct slab
                    &&& opt_idx.is_some()
                    &&& old(self)@.slabs[opt_idx.unwrap()].allocated_addrs.contains(ptr as usize)
                    // FN-4c: exact state transition
                    &&& self@ == old(self)@.spec_deallocate(opt_idx.unwrap(), ptr as usize)
                }
                Err(_) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-4f: state preserved on error
                    &&& self@ == old(self)@
                    // FN-4e: error iff size unsupported or ptr not allocated
                    &&& (opt_idx.is_none()
                        || !old(self)@.slabs[opt_idx.unwrap()].allocated_addrs
                            .contains(ptr as usize))
                }
            },
    {
        proof {
            broadcast use vstd::std_specs::control_flow::group_control_flow_axioms;
        }
        // VERUS DEVIATION: |_| → |_e| — Verus requires named variables in closure params
        match Kheap::layout_to_allocator(&layout)? {
            SlabSize::Slab8 => self.slab_8_bytes.deallocate(ptr).map_err(|_e| AllocError),
            SlabSize::Slab16 => self.slab_16_bytes.deallocate(ptr).map_err(|_e| AllocError),
            SlabSize::Slab32 => self.slab_32_bytes.deallocate(ptr).map_err(|_e| AllocError),
            SlabSize::Slab64 => self.slab_64_bytes.deallocate(ptr).map_err(|_e| AllocError),
            SlabSize::Slab128 => self.slab_128_bytes.deallocate(ptr).map_err(|_e| AllocError),
            SlabSize::Slab256 => self.slab_256_bytes.deallocate(ptr).map_err(|_e| AllocError),
            SlabSize::Slab512 => self.slab_512_bytes.deallocate(ptr).map_err(|_e| AllocError),
            #[cfg(feature = "hyperlight")]
            SlabSize::Slab1024 => self.slab_1024_bytes.deallocate(ptr).map_err(|_e| AllocError),
            #[cfg(feature = "hyperlight")]
            SlabSize::Slab2048 => self.slab_2048_bytes.deallocate(ptr).map_err(|_e| AllocError),
            #[cfg(feature = "hyperlight")]
            SlabSize::Slab4096 => self.slab_4096_bytes.deallocate(ptr).map_err(|_e| AllocError),
        }
    }

    // FN-1: Pure routing function. Maps layout size to slab tier.
    pub fn layout_to_allocator(layout: &Layout) -> (result: Result<SlabSize, AllocError>)
        ensures
            match result {
                Ok(ss) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(*layout) as int);
                    // FN-1a: size is supported
                    &&& opt_idx.is_some()
                    // FN-1b: the matching slab tier is large enough
                    &&& block_sizes()[opt_idx.unwrap()] >= spec_layout_size(*layout) as int
                    // FN-1c: returned SlabSize corresponds to the correct index
                    &&& opt_idx.unwrap() == spec_slab_size_to_index(ss)
                    // FN-1c strengthened: tightest fit — all smaller tiers are too small
                    &&& forall|j: int| 0 <= j < opt_idx.unwrap() ==>
                        block_sizes()[j] < spec_layout_size(*layout) as int
                }
                // FN-1d: error iff size is unsupported
                Err(_) => spec_slab_for_size(spec_layout_size(*layout) as int).is_none(),
            },
    {
        match layout.size() {
            1..=8 => Ok(SlabSize::Slab8),
            9..=16 => Ok(SlabSize::Slab16),
            17..=32 => Ok(SlabSize::Slab32),
            33..=64 => Ok(SlabSize::Slab64),
            65..=128 => Ok(SlabSize::Slab128),
            129..=256 => Ok(SlabSize::Slab256),
            257..=512 => Ok(SlabSize::Slab512),
            #[cfg(feature = "hyperlight")]
            513..=1024 => Ok(SlabSize::Slab1024),
            #[cfg(feature = "hyperlight")]
            1025..=2048 => Ok(SlabSize::Slab2048),
            #[cfg(feature = "hyperlight")]
            2049..=4096 => Ok(SlabSize::Slab4096),
            _ => Err(AllocError),
        }
    }
}

} // verus!

unsafe impl GlobalAlloc for ArenaAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let heap = ptr::addr_of_mut!(HEAP);
        if let Some(heap) = &mut *heap {
            match heap.allocate(layout) {
                Ok(ptr) => ptr,
                Err(_) => {
                    error!("allocation failed (layout={:?})", layout);
                    core::ptr::null_mut()
                },
            }
        } else {
            error!("heap is not initialized");
            core::ptr::null_mut()
        }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        let heap = ptr::addr_of_mut!(HEAP);
        if let Some(heap) = &mut *heap {
            if let Err(e) = heap.deallocate(ptr, layout) {
                error!("deallocation failed (layout={:?}): {:?}", layout, e);
            }
        }
    }
}

//==================================================================================================
// Standalone Functions
//==================================================================================================

pub unsafe fn init() -> Result<(), Error> {
    info!("initializing the kernel heap...");

    HEAP = Some(Kheap::from_raw_parts(
        HEAP_STORAGE.memory.as_ptr() as usize,
        HEAP_STORAGE.memory.len(),
    )?);

    Ok(())
}

verus! {

//==================================================================================================
// Constants (mirrors of exec constants for Verus visibility)
//==================================================================================================

#[cfg(feature = "hyperlight")]
pub const NUM_OF_SLABS: usize = 10;
#[cfg(not(feature = "hyperlight"))]
pub const NUM_OF_SLABS: usize = 7;
pub const SLAB_COUNT: usize = 32;
// PAGE_SIZE = 4096 (from arch::mem)
pub const PAGE_SIZE: usize = 4096;
pub const MIN_SLAB_SIZE: usize = SLAB_COUNT * PAGE_SIZE;
pub const MIN_HEAP_SIZE: usize = NUM_OF_SLABS * MIN_SLAB_SIZE;

//==================================================================================================
// Type Definitions (mirrors for Verus visibility)
//==================================================================================================

#[derive(Copy, Clone)]
pub(crate) enum SlabSize {
    Slab8 = 8,
    Slab16 = 16,
    Slab32 = 32,
    Slab64 = 64,
    Slab128 = 128,
    Slab256 = 256,
    Slab512 = 512,
    #[cfg(feature = "hyperlight")]
    Slab1024 = 1024,
    #[cfg(feature = "hyperlight")]
    Slab2048 = 2048,
    #[cfg(feature = "hyperlight")]
    Slab4096 = 4096,
}

pub(crate) struct Kheap {
    slab_8_bytes: Slab,
    slab_16_bytes: Slab,
    slab_32_bytes: Slab,
    slab_64_bytes: Slab,
    slab_128_bytes: Slab,
    slab_256_bytes: Slab,
    slab_512_bytes: Slab,
    #[cfg(feature = "hyperlight")]
    slab_1024_bytes: Slab,
    #[cfg(feature = "hyperlight")]
    slab_2048_bytes: Slab,
    #[cfg(feature = "hyperlight")]
    slab_4096_bytes: Slab,
}

//==================================================================================================
// External Type Specifications
//==================================================================================================

// Layout from core::alloc — opaque, no field access needed.
#[verifier::external_type_specification]
#[verifier::external_body]
pub struct ExLayout(Layout);

// AllocError from core::alloc — unit struct, transparent.
#[verifier::external_type_specification]
pub struct ExAllocError(AllocError);

// Error from sys::error — transparent (public fields).
#[verifier::external_type_specification]
pub struct ExError(Error);

// ErrorCode from sys::error — match upstream: transparent.
#[verifier::external_type_specification]
pub struct ExErrorCode(ErrorCode);

//==================================================================================================
// Assume Specifications (Human-Approved)
//==================================================================================================

/// Uninterpreted spec function for Layout::size().
pub uninterp spec fn spec_layout_size(layout: Layout) -> usize;

/// Layout::size() accessor.
pub assume_specification[ Layout::size ](layout: &Layout) -> (result: usize)
    ensures result == spec_layout_size(*layout),
;

/// Error::new constructor.
pub assume_specification[ Error::new ](code: ErrorCode, reason: &'static str) -> (result: Error)
    ensures
        result.code == code,
;

/// core::ptr::null_mut — result is the null pointer.
/// Helper to convert usize to *mut u8 (Verus doesn't support `as *mut u8` cast).
#[verifier::external_body]
fn usize_to_mut_ptr(addr: usize) -> (result: *mut u8)
    ensures result as usize == addr,
{
    addr as *mut u8
}

/// <*mut u8>::with_addr — not needed, using usize_to_mut_ptr instead.
/// usize::is_multiple_of — already in vstd, visible cross-crate.

//==================================================================================================
// Spec Constants
//==================================================================================================

/// Maximum allocation size supported by the heap.
#[cfg(not(feature = "hyperlight"))]
pub open spec fn max_slab_size() -> int { 512 }

#[cfg(feature = "hyperlight")]
pub open spec fn max_slab_size() -> int { 4096 }

/// Maps a SlabSize enum value to its slab index.
#[cfg(not(feature = "hyperlight"))]
pub closed spec fn spec_slab_size_to_index(ss: SlabSize) -> int {
    match ss {
        SlabSize::Slab8 => 0,
        SlabSize::Slab16 => 1,
        SlabSize::Slab32 => 2,
        SlabSize::Slab64 => 3,
        SlabSize::Slab128 => 4,
        SlabSize::Slab256 => 5,
        SlabSize::Slab512 => 6,
    }
}

#[cfg(feature = "hyperlight")]
pub closed spec fn spec_slab_size_to_index(ss: SlabSize) -> int {
    match ss {
        SlabSize::Slab8 => 0,
        SlabSize::Slab16 => 1,
        SlabSize::Slab32 => 2,
        SlabSize::Slab64 => 3,
        SlabSize::Slab128 => 4,
        SlabSize::Slab256 => 5,
        SlabSize::Slab512 => 6,
        SlabSize::Slab1024 => 7,
        SlabSize::Slab2048 => 8,
        SlabSize::Slab4096 => 9,
    }
}

/// The expected block size for each slab index.
#[cfg(not(feature = "hyperlight"))]
pub open spec fn block_sizes() -> Seq<int> {
    seq![8int, 16, 32, 64, 128, 256, 512]
}

#[cfg(feature = "hyperlight")]
pub open spec fn block_sizes() -> Seq<int> {
    seq![8int, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
}

/// Maps allocation size to slab index. Mirrors layout_to_allocator logic.
/// Returns None for unsupported sizes (0 or > max).
#[cfg(not(feature = "hyperlight"))]
pub open spec fn spec_slab_for_size(size: int) -> Option<int> {
    if 1 <= size <= 8 { Some(0int) }
    else if 9 <= size <= 16 { Some(1int) }
    else if 17 <= size <= 32 { Some(2int) }
    else if 33 <= size <= 64 { Some(3int) }
    else if 65 <= size <= 128 { Some(4int) }
    else if 129 <= size <= 256 { Some(5int) }
    else if 257 <= size <= 512 { Some(6int) }
    else { None }
}

#[cfg(feature = "hyperlight")]
pub open spec fn spec_slab_for_size(size: int) -> Option<int> {
    if 1 <= size <= 8 { Some(0int) }
    else if 9 <= size <= 16 { Some(1int) }
    else if 17 <= size <= 32 { Some(2int) }
    else if 33 <= size <= 64 { Some(3int) }
    else if 65 <= size <= 128 { Some(4int) }
    else if 129 <= size <= 256 { Some(5int) }
    else if 257 <= size <= 512 { Some(6int) }
    else if 513 <= size <= 1024 { Some(7int) }
    else if 1025 <= size <= 2048 { Some(8int) }
    else if 2049 <= size <= 4096 { Some(9int) }
    else { None }
}

//==================================================================================================
// KheapView — Abstract State
//==================================================================================================

/// Abstract view of the kernel heap as a sequence of slab views.
#[verifier::ext_equal]
pub struct KheapView {
    pub slabs: Seq<SlabView>,
}

impl KheapView {
    /// Structural invariant covering TYPE-1, TYPE-2, TYPE-3.
    pub open spec fn inv(&self) -> bool {
        // TYPE-1: Correct number of slabs
        &&& self.slabs.len() == NUM_OF_SLABS as int
        // TYPE-1: Each slab satisfies its own invariant
        &&& forall|i: int| 0 <= i < self.slabs.len() ==>
            (#[trigger] self.slabs[i]).inv()
        // TYPE-2: Slab regions are contiguous and non-overlapping
        &&& forall|i: int| 0 <= i < self.slabs.len() - 1 ==>
            (#[trigger] self.slabs[i]).end_addr <= self.slabs[i + 1].start_addr
        // TYPE-3: Block sizes match the expected power-of-two sequence
        &&& forall|i: int| 0 <= i < self.slabs.len() ==>
            (#[trigger] self.slabs[i]).block_size == block_sizes()[i]
    }

    /// Union of all allocated addresses across all slabs.
    pub open spec fn all_allocated(&self) -> Set<usize> {
        Set::new(|addr: usize| exists|i: int|
            0 <= i < self.slabs.len()
            && (#[trigger] self.slabs[i]).allocated_addrs.contains(addr))
    }

    /// Union of all free addresses across all slabs.
    pub open spec fn all_free(&self) -> Set<usize> {
        Set::new(|addr: usize| exists|i: int|
            0 <= i < self.slabs.len()
            && (#[trigger] self.slabs[i]).free_addrs.contains(addr))
    }

    /// State transition: allocate addr from slab at idx (FN-3d).
    pub open spec fn spec_allocate(self, idx: int, addr: usize) -> KheapView {
        KheapView {
            slabs: self.slabs.update(idx, SlabView {
                allocated_addrs: self.slabs[idx].allocated_addrs.insert(addr),
                free_addrs: self.slabs[idx].free_addrs.remove(addr),
                ..self.slabs[idx]
            }),
        }
    }

    /// State transition: deallocate addr back to slab at idx (FN-4c).
    pub open spec fn spec_deallocate(self, idx: int, addr: usize) -> KheapView {
        KheapView {
            slabs: self.slabs.update(idx, SlabView {
                allocated_addrs: self.slabs[idx].allocated_addrs.remove(addr),
                free_addrs: self.slabs[idx].free_addrs.insert(addr),
                ..self.slabs[idx]
            }),
        }
    }
}

//==================================================================================================
// View Implementation for Kheap
//==================================================================================================

impl View for Kheap {
    type V = KheapView;

    #[cfg(not(feature = "hyperlight"))]
    closed spec fn view(&self) -> KheapView {
        KheapView {
            slabs: seq![
                self.slab_8_bytes@,
                self.slab_16_bytes@,
                self.slab_32_bytes@,
                self.slab_64_bytes@,
                self.slab_128_bytes@,
                self.slab_256_bytes@,
                self.slab_512_bytes@,
            ],
        }
    }

    #[cfg(feature = "hyperlight")]
    closed spec fn view(&self) -> KheapView {
        KheapView {
            slabs: seq![
                self.slab_8_bytes@,
                self.slab_16_bytes@,
                self.slab_32_bytes@,
                self.slab_64_bytes@,
                self.slab_128_bytes@,
                self.slab_256_bytes@,
                self.slab_512_bytes@,
                self.slab_1024_bytes@,
                self.slab_2048_bytes@,
                self.slab_4096_bytes@,
            ],
        }
    }
}

//==================================================================================================
// Kheap Invariant
//==================================================================================================

impl Kheap {
    pub open spec fn inv(&self) -> bool {
        &&& self@.inv()
        &&& self.concrete_inv()
    }

    #[cfg(not(feature = "hyperlight"))]
    pub closed spec fn concrete_inv(&self) -> bool {
        &&& self.slab_8_bytes.inv()
        &&& self.slab_16_bytes.inv()
        &&& self.slab_32_bytes.inv()
        &&& self.slab_64_bytes.inv()
        &&& self.slab_128_bytes.inv()
        &&& self.slab_256_bytes.inv()
        &&& self.slab_512_bytes.inv()
    }

    #[cfg(feature = "hyperlight")]
    pub closed spec fn concrete_inv(&self) -> bool {
        &&& self.slab_8_bytes.inv()
        &&& self.slab_16_bytes.inv()
        &&& self.slab_32_bytes.inv()
        &&& self.slab_64_bytes.inv()
        &&& self.slab_128_bytes.inv()
        &&& self.slab_256_bytes.inv()
        &&& self.slab_512_bytes.inv()
        &&& self.slab_1024_bytes.inv()
        &&& self.slab_2048_bytes.inv()
        &&& self.slab_4096_bytes.inv()
    }
}

} // verus!

verus! {

//==================================================================================================
// Helper Lemmas
//==================================================================================================

/// Helper: regions are ordered across non-consecutive slabs (by transitivity).
proof fn lemma_regions_ordered(kv: &KheapView, i: int, j: int)
    requires
        kv.inv(),
        0 <= i < j < kv.slabs.len(),
    ensures
        kv.slabs[i].end_addr <= kv.slabs[j].start_addr,
    decreases j - i,
{
    if j == i + 1 {
        // Direct from kv.inv(): consecutive pair
    } else {
        lemma_regions_ordered(kv, i, j - 1);
        // IH: kv.slabs[i].end_addr <= kv.slabs[j-1].start_addr
        // kv.slabs[j-1].inv(): start_addr < end_addr
        // kv.inv() consecutive: kv.slabs[j-1].end_addr <= kv.slabs[j].start_addr
        // Chain: slabs[i].end_addr <= slabs[j-1].start_addr < slabs[j-1].end_addr <= slabs[j].start_addr
    }
}

//==================================================================================================
// Proof Bodies
//==================================================================================================

/// MOD-3: Cross-slab disjointness follows from TYPE-2 (region disjointness)
/// and SlabView::inv() (addresses lie within [start_addr, end_addr)).
proof fn lemma_kheap_inv_implies_cross_slab_disjointness(kv: &KheapView)
    requires kv.inv(),
    ensures
        // MOD-1: allocated sets disjoint across slabs
        forall|i: int, j: int| 0 <= i < j < kv.slabs.len() ==>
            kv.slabs[i].allocated_addrs.disjoint(kv.slabs[j].allocated_addrs),
        // MOD-2: free sets disjoint across slabs
        forall|i: int, j: int| 0 <= i < j < kv.slabs.len() ==>
            kv.slabs[i].free_addrs.disjoint(kv.slabs[j].free_addrs),
        // MOD-3 (full): allocated/free cross-disjoint
        forall|i: int, j: int| 0 <= i < j < kv.slabs.len() ==>
            kv.slabs[i].allocated_addrs.disjoint(kv.slabs[j].free_addrs),
{
    assert forall|i: int, j: int| 0 <= i < j < kv.slabs.len() implies
        kv.slabs[i].allocated_addrs.disjoint(kv.slabs[j].allocated_addrs)
    by {
        lemma_regions_ordered(kv, i, j);
        // slabs[i].end_addr <= slabs[j].start_addr
        // Any addr in slab i: addr < slabs[i].end_addr
        // Any addr in slab j: addr >= slabs[j].start_addr
        // So no overlap
    };
    assert forall|i: int, j: int| 0 <= i < j < kv.slabs.len() implies
        kv.slabs[i].free_addrs.disjoint(kv.slabs[j].free_addrs)
    by {
        lemma_regions_ordered(kv, i, j);
    };
    assert forall|i: int, j: int| 0 <= i < j < kv.slabs.len() implies
        kv.slabs[i].allocated_addrs.disjoint(kv.slabs[j].free_addrs)
    by {
        lemma_regions_ordered(kv, i, j);
    };
}

/// spec_slab_for_size maps to a valid index with correct block size bound.
proof fn lemma_slab_for_size_valid(size: int)
    requires spec_slab_for_size(size).is_some(),
    ensures
        0 <= spec_slab_for_size(size).unwrap() < NUM_OF_SLABS as int,
        block_sizes()[spec_slab_for_size(size).unwrap()] >= size,
{
    // spec_slab_for_size and block_sizes are open specs — automatic
}

/// LIVE-5: Allocate-then-deallocate round-trip restores abstract state.
proof fn lemma_alloc_dealloc_round_trip(kv: KheapView, idx: int, addr: usize)
    requires
        kv.inv(),
        0 <= idx < kv.slabs.len(),
        kv.slabs[idx].free_addrs.contains(addr),
    ensures
        kv.spec_allocate(idx, addr).spec_deallocate(idx, addr) == kv,
{
    let slab = kv.slabs[idx];
    // addr is in free, so not in allocated (disjoint from SlabView::inv)
    assert(!slab.allocated_addrs.contains(addr));

    let after_alloc = kv.spec_allocate(idx, addr);
    let after_dealloc = after_alloc.spec_deallocate(idx, addr);

    // Show the slab at idx is restored
    assert(slab.allocated_addrs.insert(addr).remove(addr) =~= slab.allocated_addrs);
    assert(slab.free_addrs.remove(addr).insert(addr) =~= slab.free_addrs);

    // Show slabs sequence is restored
    assert(after_dealloc.slabs =~= kv.slabs);
    assert(after_dealloc =~= kv);
}

/// MOD-5: Allocation conservation — union of allocated+free is preserved
/// across spec_allocate.
proof fn lemma_allocate_conserves(kv: KheapView, idx: int, addr: usize)
    requires
        kv.inv(),
        0 <= idx < kv.slabs.len(),
        kv.slabs[idx].free_addrs.contains(addr),
    ensures
        forall|j: int| 0 <= j < kv.slabs.len() ==>
            (#[trigger] kv.slabs[j]).allocated_addrs.union(kv.slabs[j].free_addrs)
                == kv.spec_allocate(idx, addr).slabs[j].allocated_addrs.union(
                       kv.spec_allocate(idx, addr).slabs[j].free_addrs),
{
    let new_kv = kv.spec_allocate(idx, addr);
    assert forall|j: int| 0 <= j < kv.slabs.len() implies
        (#[trigger] kv.slabs[j]).allocated_addrs.union(kv.slabs[j].free_addrs)
            == new_kv.slabs[j].allocated_addrs.union(new_kv.slabs[j].free_addrs)
    by {
        if j == idx {
            let old_slab = kv.slabs[idx];
            assert(!old_slab.allocated_addrs.contains(addr));
            // allocated.insert(addr) ∪ free.remove(addr) =~= allocated ∪ free
            assert(old_slab.allocated_addrs.insert(addr).union(old_slab.free_addrs.remove(addr))
                =~= old_slab.allocated_addrs.union(old_slab.free_addrs));
        } else {
            // Unchanged
        }
    };
}

/// MOD-5: Deallocation conservation.
proof fn lemma_deallocate_conserves(kv: KheapView, idx: int, addr: usize)
    requires
        kv.inv(),
        0 <= idx < kv.slabs.len(),
        kv.slabs[idx].allocated_addrs.contains(addr),
    ensures
        forall|j: int| 0 <= j < kv.slabs.len() ==>
            (#[trigger] kv.slabs[j]).allocated_addrs.union(kv.slabs[j].free_addrs)
                == kv.spec_deallocate(idx, addr).slabs[j].allocated_addrs.union(
                       kv.spec_deallocate(idx, addr).slabs[j].free_addrs),
{
    let new_kv = kv.spec_deallocate(idx, addr);
    assert forall|j: int| 0 <= j < kv.slabs.len() implies
        (#[trigger] kv.slabs[j]).allocated_addrs.union(kv.slabs[j].free_addrs)
            == new_kv.slabs[j].allocated_addrs.union(new_kv.slabs[j].free_addrs)
    by {
        if j == idx {
            let old_slab = kv.slabs[idx];
            assert(!old_slab.free_addrs.contains(addr));
            assert(old_slab.allocated_addrs.remove(addr).union(old_slab.free_addrs.insert(addr))
                =~= old_slab.allocated_addrs.union(old_slab.free_addrs));
        } else {
            // Unchanged
        }
    };
}

//==================================================================================================
// Strengthening Lemmas
//==================================================================================================

/// FN-1c strengthened: spec_slab_for_size selects the tightest-fitting slab.
/// All smaller slab tiers have block sizes strictly less than the requested size.
proof fn lemma_slab_for_size_tightest_fit(size: int)
    requires spec_slab_for_size(size).is_some(),
    ensures ({
        let idx = spec_slab_for_size(size).unwrap();
        &&& (idx > 0 ==> block_sizes()[idx - 1] < size)
        &&& (idx > 1 ==> block_sizes()[idx - 2] < size)
        &&& block_sizes()[idx] >= size
    }),
{
}

/// TYPE-3 strengthened: block_sizes() is strictly monotonically increasing.
proof fn lemma_block_sizes_strictly_increasing()
    ensures
        forall|i: int| #![trigger block_sizes()[i]]
            0 <= i < (block_sizes().len() - 1) ==>
            block_sizes()[i] < block_sizes()[i + 1],
{
}

/// spec_slab_for_size is total over the supported range [1, max_slab_size()].
proof fn lemma_slab_for_size_total(size: int)
    requires 1 <= size <= max_slab_size(),
    ensures spec_slab_for_size(size).is_some(),
{
}

/// MOD-4: No allocation at address zero (conditional on base address).
/// If the heap was constructed from a non-zero base address, no slab
/// contains address 0 in either its allocated or free sets.
/// The base address is non-zero at runtime because HEAP_STORAGE is a
/// static with linker-assigned address > 0, but this is a runtime fact
/// that cannot be expressed as a Verus axiom.
proof fn lemma_no_null_address(kv: &KheapView, base_addr: int, slab_size: int)
    requires
        kv.inv(),
        base_addr > 0,
        slab_size > 0,
        forall|i: int| 0 <= i < kv.slabs.len() ==>
            (#[trigger] kv.slabs[i]).start_addr >= base_addr + i * slab_size,
    ensures
        forall|i: int| 0 <= i < kv.slabs.len() ==> {
            &&& !(#[trigger] kv.slabs[i]).allocated_addrs.contains(0usize)
            &&& !kv.slabs[i].free_addrs.contains(0usize)
        },
{
    assert forall|i: int| 0 <= i < kv.slabs.len() implies {
        &&& !(#[trigger] kv.slabs[i]).allocated_addrs.contains(0usize)
        &&& !kv.slabs[i].free_addrs.contains(0usize)
    } by {
        // start_addr >= base_addr + i * slab_size >= base_addr > 0
        // SlabView::inv: all addresses in [start_addr, end_addr), so >= start_addr > 0
        // Therefore 0 is not in any slab's address sets
        let slab = kv.slabs[i];
        assert(slab.start_addr >= base_addr + i * slab_size);
        assert(slab.start_addr > 0);
    };
}

/// LIVE-1 (conditional): For init()-standard parameters (size = MIN_HEAP_SIZE,
/// non-zero base), none of the Slab::from_raw_parts error conditions hold
/// for any slab index.
///
/// The Slab spec provides a bidirectional error clause:
///   Err(e) ==> (addr==0 || len==0 || len>=i32::MAX || len>isize::MAX
///               || addr+len>usize::MAX || block_size==0 || block_size>=i32::MAX
///               || block_size>(usize::MAX-1)/8 || len<block_size*2
///               || addr%block_size!=0)
/// By contrapositive: ¬(any error condition) ==> Ok.
///
/// Remaining architecture assumptions (requires parameters):
/// - base_addr > 0: HEAP_STORAGE is a static; linker guarantees non-zero address.
/// - usize::MAX >= 8 * max_slab_size() + 1: true on all ≥16-bit platforms.
/// - MIN_HEAP_SIZE <= isize::MAX: true on all ≥32-bit platforms.
proof fn lemma_slab_construction_feasible(
    base_addr: int,
    slab_idx: int,
)
    requires
        base_addr > 0,
        base_addr % PAGE_SIZE as int == 0,
        base_addr + MIN_HEAP_SIZE as int <= usize::MAX as int,
        MIN_HEAP_SIZE as int <= isize::MAX as int,
        0 <= slab_idx < NUM_OF_SLABS as int,
        usize::MAX as int >= 8 * max_slab_size() + 1,
    ensures ({
        let slab_size = MIN_SLAB_SIZE as int;
        let slab_addr = base_addr + slab_idx * slab_size;
        let block_size = block_sizes()[slab_idx];
        // Negation of ALL Slab::from_raw_parts error conditions:
        &&& slab_addr != 0
        &&& slab_size > 0
        &&& slab_size < i32::MAX as int
        &&& slab_size <= isize::MAX as int
        &&& slab_addr + slab_size <= usize::MAX as int
        &&& block_size > 0
        &&& block_size < i32::MAX as int
        &&& block_size <= (usize::MAX as int - 1) / 8
        &&& slab_size >= block_size * 2
        &&& slab_addr % block_size == 0
    }),
{
    let slab_size: int = MIN_SLAB_SIZE as int;
    let slab_addr: int = base_addr + slab_idx * slab_size;
    let block_size: int = block_sizes()[slab_idx];

    // slab_addr > 0: base_addr > 0, slab_idx >= 0, slab_size > 0
    assert(slab_addr > 0);

    // MIN_SLAB_SIZE = SLAB_COUNT * PAGE_SIZE = 32 * 4096 = 131072
    assert(slab_size > 0);
    assert(slab_size < i32::MAX as int);

    // slab_size <= isize::MAX: MIN_SLAB_SIZE <= MIN_HEAP_SIZE <= isize::MAX
    assert(MIN_SLAB_SIZE as int <= MIN_HEAP_SIZE as int);

    // slab_addr + slab_size <= usize::MAX:
    //   = base_addr + (slab_idx + 1) * slab_size
    //   <= base_addr + NUM_OF_SLABS * slab_size = base_addr + MIN_HEAP_SIZE
    //   <= usize::MAX
    assert(NUM_OF_SLABS as int * MIN_SLAB_SIZE as int == MIN_HEAP_SIZE as int);

    // block_size > 0 and < i32::MAX (max is max_slab_size() <= 4096)
    assert(block_size > 0);
    assert(max_slab_size() < i32::MAX as int);
    assert(block_size <= max_slab_size());

    // block_size <= (usize::MAX - 1) / 8:
    //   usize::MAX - 1 >= 8 * max_slab_size() >= 8 * block_size
    //   By div monotonicity: (usize::MAX-1)/8 >= (8*block_size)/8 = block_size
    assert(usize::MAX as int - 1 >= 8 * block_size);
    vstd::arithmetic::div_mod::lemma_div_is_ordered(
        8 * block_size,
        usize::MAX as int - 1,
        8,
    );
    vstd::arithmetic::div_mod::lemma_div_multiples_vanish(block_size, 8);

    // slab_size >= block_size * 2: 131072 >= 2 * max_slab_size()
    assert(slab_size >= max_slab_size() * 2);

    // slab_addr % block_size == 0 via modular transitivity:
    // (a) PAGE_SIZE % block_size == 0 — case-split on slab_idx for concrete block sizes
    #[cfg(not(feature = "hyperlight"))]
    {
        assert(PAGE_SIZE as int % block_size == 0) by {
            if slab_idx == 0 { }      // 4096 % 8 = 0
            else if slab_idx == 1 { }  // 4096 % 16 = 0
            else if slab_idx == 2 { }  // 4096 % 32 = 0
            else if slab_idx == 3 { }  // 4096 % 64 = 0
            else if slab_idx == 4 { }  // 4096 % 128 = 0
            else if slab_idx == 5 { }  // 4096 % 256 = 0
            else { }                   // 4096 % 512 = 0
        };
    }
    #[cfg(feature = "hyperlight")]
    {
        assert(PAGE_SIZE as int % block_size == 0) by {
            if slab_idx == 0 { }
            else if slab_idx == 1 { }
            else if slab_idx == 2 { }
            else if slab_idx == 3 { }
            else if slab_idx == 4 { }
            else if slab_idx == 5 { }
            else if slab_idx == 6 { }
            else if slab_idx == 7 { }
            else if slab_idx == 8 { }
            else { }
        };
    }

    // (b) base_addr % block_size == 0 (from base_addr % PAGE_SIZE == 0)
    //     PAGE_SIZE = block_size * (PAGE_SIZE / block_size)
    //     lemma_mod_mod: (base_addr % (block_size * b)) % block_size == base_addr % block_size
    let b = PAGE_SIZE as int / block_size;
    vstd::arithmetic::div_mod::lemma_fundamental_div_mod(PAGE_SIZE as int, block_size);
    assert(PAGE_SIZE as int == block_size * b);
    vstd::arithmetic::div_mod::lemma_mod_mod(base_addr, block_size, b);
    assert(base_addr % block_size == 0);

    // (c) (slab_idx * slab_size) % block_size == 0
    //     MIN_SLAB_SIZE = SLAB_COUNT * PAGE_SIZE, and we showed PAGE_SIZE % block_size == 0
    vstd::arithmetic::div_mod::lemma_mod_multiples_basic(SLAB_COUNT as int, PAGE_SIZE as int);
    assert((SLAB_COUNT as int * PAGE_SIZE as int) % PAGE_SIZE as int == 0);
    let b2 = PAGE_SIZE as int / block_size;
    vstd::arithmetic::div_mod::lemma_mod_mod(MIN_SLAB_SIZE as int, block_size, b2);
    assert(MIN_SLAB_SIZE as int % block_size == 0);
    vstd::arithmetic::div_mod::lemma_mul_mod_noop_right(slab_idx, slab_size, block_size);
    assert((slab_idx * slab_size) % block_size == 0);

    // (d) slab_addr = base_addr + slab_idx * slab_size, both 0 mod block_size
    vstd::arithmetic::div_mod::lemma_add_mod_noop(
        base_addr,
        slab_idx * slab_size,
        block_size,
    );
    assert(slab_addr % block_size == 0);
}

} // verus!
