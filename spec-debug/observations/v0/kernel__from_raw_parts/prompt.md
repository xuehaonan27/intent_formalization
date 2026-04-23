# Task: close a spec-nondeterminism gap

You are editing a Verus specification file. A determinism checker has
found an input for which two spec-allowed outputs differ. Strengthen the
spec so that the spec-allowed output is uniquely determined (up to the
equivalence relation below), without over-constraining it.

## Function under spec
`kernel::from_raw_parts`

## Current `kheap.spec.rs`
```rust
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

```

## Determinism check context
The checker expands the spec with this template (ASSUMES is where the
witness below lives):

```rust
proof fn det_from_raw_parts(addr: usize, size: usize, r1: Result<Kheap, Error>, r2: Result<Kheap, Error>)
    requires (addr as int + size as int <= usize::MAX as int), (size as int <= isize::MAX as int),
    ensures
        ({
            &&& (match r1 {
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
            })
            &&& (match r2 {
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
            })
        }) ==> det_from_raw_parts_equal(r1, r2),
{
{ASSUMES}}
```

The equivalence relation used to decide "same output":

```rust
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=False, opaque_ok=False
spec fn det_from_raw_parts_equal(r1: Result<Kheap, Error>, r2: Result<Kheap, Error>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> ((r1->Ok_0)@ == (r2->Ok_0)@)) && ((r1 is Err) ==> ((((r1->Err_0.code is OperationNotPermitted) == (r2->Err_0.code is OperationNotPermitted)) && ((r1->Err_0.code is NoSuchEntry) == (r2->Err_0.code is NoSuchEntry)) && ((r1->Err_0.code is NoSuchProcess) == (r2->Err_0.code is NoSuchProcess)) && ((r1->Err_0.code is Interrupted) == (r2->Err_0.code is Interrupted)) && ((r1->Err_0.code is IoErr) == (r2->Err_0.code is IoErr)) && ((r1->Err_0.code is NoSuchDeviceOrAddress) == (r2->Err_0.code is NoSuchDeviceOrAddress)) && ((r1->Err_0.code is TooBig) == (r2->Err_0.code is TooBig)) && ((r1->Err_0.code is InvalidExecutableFormat) == (r2->Err_0.code is InvalidExecutableFormat)) && ((r1->Err_0.code is BadFile) == (r2->Err_0.code is BadFile)) && ((r1->Err_0.code is NoChildProcess) == (r2->Err_0.code is NoChildProcess)) && ((r1->Err_0.code is TryAgain) == (r2->Err_0.code is TryAgain)) && ((r1->Err_0.code is OutOfMemory) == (r2->Err_0.code is OutOfMemory)) && ((r1->Err_0.code is PermissionDenied) == (r2->Err_0.code is PermissionDenied)) && ((r1->Err_0.code is BadAddress) == (r2->Err_0.code is BadAddress)) && ((r1->Err_0.code is NotBlockDevice) == (r2->Err_0.code is NotBlockDevice)) && ((r1->Err_0.code is ResourceBusy) == (r2->Err_0.code is ResourceBusy)) && ((r1->Err_0.code is EntryExists) == (r2->Err_0.code is EntryExists)) && ((r1->Err_0.code is CrossDeviceLink) == (r2->Err_0.code is CrossDeviceLink)) && ((r1->Err_0.code is NoSuchDevice) == (r2->Err_0.code is NoSuchDevice)) && ((r1->Err_0.code is InvalidDirectory) == (r2->Err_0.code is InvalidDirectory)) && ((r1->Err_0.code is IsDirectory) == (r2->Err_0.code is IsDirectory)) && ((r1->Err_0.code is InvalidArgument) == (r2->Err_0.code is InvalidArgument)) && ((r1->Err_0.code is FileTableOVerflow) == (r2->Err_0.code is FileTableOVerflow)) && ((r1->Err_0.code is TooManyOpenFiles) == (r2->Err_0.code is TooManyOpenFiles)) && ((r1->Err_0.code is NotTerminal) == (r2->Err_0.code is NotTerminal)) && ((r1->Err_0.code is TextFileBusy) == (r2->Err_0.code is TextFileBusy)) && ((r1->Err_0.code is FileTooLarge) == (r2->Err_0.code is FileTooLarge)) && ((r1->Err_0.code is NoSpaceOnDevice) == (r2->Err_0.code is NoSpaceOnDevice)) && ((r1->Err_0.code is IllegalSeek) == (r2->Err_0.code is IllegalSeek)) && ((r1->Err_0.code is ReadOnlyFileSystem) == (r2->Err_0.code is ReadOnlyFileSystem)) && ((r1->Err_0.code is TooManyLinks) == (r2->Err_0.code is TooManyLinks)) && ((r1->Err_0.code is BrokenPipe) == (r2->Err_0.code is BrokenPipe)) && ((r1->Err_0.code is MathArgDomainErr) == (r2->Err_0.code is MathArgDomainErr)) && ((r1->Err_0.code is ValueOutOfRange) == (r2->Err_0.code is ValueOutOfRange)) && ((r1->Err_0.code is NoMessageAvailable) == (r2->Err_0.code is NoMessageAvailable)) && ((r1->Err_0.code is IdentifierRemoved) == (r2->Err_0.code is IdentifierRemoved)) && ((r1->Err_0.code is OutOfRangeChannel) == (r2->Err_0.code is OutOfRangeChannel)) && ((r1->Err_0.code is Level2NotSynchronized) == (r2->Err_0.code is Level2NotSynchronized)) && ((r1->Err_0.code is Level3Halted) == (r2->Err_0.code is Level3Halted)) && ((r1->Err_0.code is Level3Reset) == (r2->Err_0.code is Level3Reset)) && ((r1->Err_0.code is InvalidLinkNumber) == (r2->Err_0.code is InvalidLinkNumber)) && ((r1->Err_0.code is InvalidProtocolDriver) == (r2->Err_0.code is InvalidProtocolDriver)) && ((r1->Err_0.code is NoStructAvailable) == (r2->Err_0.code is NoStructAvailable)) && ((r1->Err_0.code is Level2Halted) == (r2->Err_0.code is Level2Halted)) && ((r1->Err_0.code is Deadlock) == (r2->Err_0.code is Deadlock)) && ((r1->Err_0.code is LockNotAvailable) == (r2->Err_0.code is LockNotAvailable)) && ((r1->Err_0.code is InvalidExchange) == (r2->Err_0.code is InvalidExchange)) && ((r1->Err_0.code is InvalidRequestDescriptor) == (r2->Err_0.code is InvalidRequestDescriptor)) && ((r1->Err_0.code is ExchangeFull) == (r2->Err_0.code is ExchangeFull)) && ((r1->Err_0.code is InvalidAnode) == (r2->Err_0.code is InvalidAnode)) && ((r1->Err_0.code is InvalidRequestCode) == (r2->Err_0.code is InvalidRequestCode)) && ((r1->Err_0.code is InvalidSlot) == (r2->Err_0.code is InvalidSlot)) && ((r1->Err_0.code is DeadlockWouldOccur) == (r2->Err_0.code is DeadlockWouldOccur)) && ((r1->Err_0.code is BadFontFormat) == (r2->Err_0.code is BadFontFormat)) && ((r1->Err_0.code is NoStreamDeviceAvailable) == (r2->Err_0.code is NoStreamDeviceAvailable)) && ((r1->Err_0.code is NoDataAvailable) == (r2->Err_0.code is NoDataAvailable)) && ((r1->Err_0.code is TimerExpired) == (r2->Err_0.code is TimerExpired)) && ((r1->Err_0.code is NoStreamResources) == (r2->Err_0.code is NoStreamResources)) && ((r1->Err_0.code is NoNetwork) == (r2->Err_0.code is NoNetwork)) && ((r1->Err_0.code is MissingPackage) == (r2->Err_0.code is MissingPackage)) && ((r1->Err_0.code is RemoteObject) == (r2->Err_0.code is RemoteObject)) && ((r1->Err_0.code is NoLink) == (r2->Err_0.code is NoLink)) && ((r1->Err_0.code is AdvertiseErr) == (r2->Err_0.code is AdvertiseErr)) && ((r1->Err_0.code is MountErr) == (r2->Err_0.code is MountErr)) && ((r1->Err_0.code is CommunicationErr) == (r2->Err_0.code is CommunicationErr)) && ((r1->Err_0.code is ProtocolErr) == (r2->Err_0.code is ProtocolErr)) && ((r1->Err_0.code is MultipleHopAttemped) == (r2->Err_0.code is MultipleHopAttemped)) && ((r1->Err_0.code is InodeRemote) == (r2->Err_0.code is InodeRemote)) && ((r1->Err_0.code is RfsErr) == (r2->Err_0.code is RfsErr)) && ((r1->Err_0.code is InvalidMessage) == (r2->Err_0.code is InvalidMessage)) && ((r1->Err_0.code is InvalidFileType) == (r2->Err_0.code is InvalidFileType)) && ((r1->Err_0.code is NonUniqueName) == (r2->Err_0.code is NonUniqueName)) && ((r1->Err_0.code is InvalidFileDescriptor) == (r2->Err_0.code is InvalidFileDescriptor)) && ((r1->Err_0.code is RemoteAddressChanged) == (r2->Err_0.code is RemoteAddressChanged)) && ((r1->Err_0.code is LibraryAccessErr) == (r2->Err_0.code is LibraryAccessErr)) && ((r1->Err_0.code is InvalidLibraryAccess) == (r2->Err_0.code is InvalidLibraryAccess)) && ((r1->Err_0.code is CorruptedLibSection) == (r2->Err_0.code is CorruptedLibSection)) && ((r1->Err_0.code is ExcessiveLibraryLinkCount) == (r2->Err_0.code is ExcessiveLibraryLinkCount)) && ((r1->Err_0.code is InvalidExecSharedLibrary) == (r2->Err_0.code is InvalidExecSharedLibrary)) && ((r1->Err_0.code is InvalidSysCall) == (r2->Err_0.code is InvalidSysCall)) && ((r1->Err_0.code is DirectoryNotEmpty) == (r2->Err_0.code is DirectoryNotEmpty)) && ((r1->Err_0.code is NameTooLong) == (r2->Err_0.code is NameTooLong)) && ((r1->Err_0.code is SymbolicLinkLoop) == (r2->Err_0.code is SymbolicLinkLoop)) && ((r1->Err_0.code is OperationNotSupportedOnSocket) == (r2->Err_0.code is OperationNotSupportedOnSocket)) && ((r1->Err_0.code is ProtocolFamilyNotSupported) == (r2->Err_0.code is ProtocolFamilyNotSupported)) && ((r1->Err_0.code is ConnectionReset) == (r2->Err_0.code is ConnectionReset)) && ((r1->Err_0.code is NoBufferSpace) == (r2->Err_0.code is NoBufferSpace)) && ((r1->Err_0.code is AddressFamilyNotSupported) == (r2->Err_0.code is AddressFamilyNotSupported)) && ((r1->Err_0.code is BadProtocolType) == (r2->Err_0.code is BadProtocolType)) && ((r1->Err_0.code is NotSocketFile) == (r2->Err_0.code is NotSocketFile)) && ((r1->Err_0.code is ProtocolOptionNotAvailable) == (r2->Err_0.code is ProtocolOptionNotAvailable)) && ((r1->Err_0.code is TransportEndpointShutdown) == (r2->Err_0.code is TransportEndpointShutdown)) && ((r1->Err_0.code is ConnectionRefused) == (r2->Err_0.code is ConnectionRefused)) && ((r1->Err_0.code is AddressInUse) == (r2->Err_0.code is AddressInUse)) && ((r1->Err_0.code is ConnectionAborted) == (r2->Err_0.code is ConnectionAborted)) && ((r1->Err_0.code is NetworkUnreachable) == (r2->Err_0.code is NetworkUnreachable)) && ((r1->Err_0.code is NetworkDown) == (r2->Err_0.code is NetworkDown)) && ((r1->Err_0.code is OperationTimedOut) == (r2->Err_0.code is OperationTimedOut)) && ((r1->Err_0.code is HostDown) == (r2->Err_0.code is HostDown)) && ((r1->Err_0.code is HostUnreachable) == (r2->Err_0.code is HostUnreachable)) && ((r1->Err_0.code is OperationInProgress) == (r2->Err_0.code is OperationInProgress)) && ((r1->Err_0.code is OperationAlreadyInProgress) == (r2->Err_0.code is OperationAlreadyInProgress)) && ((r1->Err_0.code is DestinationAddressRequired) == (r2->Err_0.code is DestinationAddressRequired)) && ((r1->Err_0.code is MessageTooLong) == (r2->Err_0.code is MessageTooLong)) && ((r1->Err_0.code is ProtocolNotSupported) == (r2->Err_0.code is ProtocolNotSupported)) && ((r1->Err_0.code is SocketTypeNotSupported) == (r2->Err_0.code is SocketTypeNotSupported)) && ((r1->Err_0.code is AddressNotAvailable) == (r2->Err_0.code is AddressNotAvailable)) && ((r1->Err_0.code is NetworkReset) == (r2->Err_0.code is NetworkReset)) && ((r1->Err_0.code is TransportEndpointConnected) == (r2->Err_0.code is TransportEndpointConnected)) && ((r1->Err_0.code is TransportEndpointNotConnected) == (r2->Err_0.code is TransportEndpointNotConnected)) && ((r1->Err_0.code is TooManyReferences) == (r2->Err_0.code is TooManyReferences)) && ((r1->Err_0.code is TooManyUsers) == (r2->Err_0.code is TooManyUsers)) && ((r1->Err_0.code is QuotaExceeded) == (r2->Err_0.code is QuotaExceeded)) && ((r1->Err_0.code is StaleHandle) == (r2->Err_0.code is StaleHandle)) && ((r1->Err_0.code is OperationNotSupported) == (r2->Err_0.code is OperationNotSupported)) && ((r1->Err_0.code is MediumNotFound) == (r2->Err_0.code is MediumNotFound)) && ((r1->Err_0.code is IllegalByteSequence) == (r2->Err_0.code is IllegalByteSequence)) && ((r1->Err_0.code is ValueOverflow) == (r2->Err_0.code is ValueOverflow)) && ((r1->Err_0.code is OperationCanceled) == (r2->Err_0.code is OperationCanceled)) && ((r1->Err_0.code is UnrecoverableState) == (r2->Err_0.code is UnrecoverableState)) && ((r1->Err_0.code is DeadOwner) == (r2->Err_0.code is DeadOwner)) && ((r1->Err_0.code is StreamPipeErr) == (r2->Err_0.code is StreamPipeErr))) && (r1->Err_0.reason == r2->Err_0.reason))))
}
```

## Witness (committed assumes that demonstrate nondeterminism)
The checker found the following `assume`s consistent with the spec; the
last assume `!det_from_raw_parts_equal(r1, r2)` asserts the two outputs differ.

```text
addr == 0
size == 0
r1 is Err
r1->Err_0.code is InvalidArgument
r1->Err_0.reason == ""
r2 is Err
r2->Err_0.code is InvalidArgument
r2->Err_0.reason == "string 1"
!det_from_raw_parts_equal(r1, r2)
```

## What to return

Return a single fenced ```rust block containing the **full replacement
contents** of `kheap.spec.rs`. Do not include any other prose.

Constraints:
- Keep all existing items; only strengthen the `ensures` of
  `from_raw_parts` (or add whatever minimal new helper items are needed).
- Do not change function signatures.
- Your fix must still be satisfied by a reasonable implementation.
