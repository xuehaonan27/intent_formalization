#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_allocate_equal(r1: (
    *mut u8,
    Tracked<PointsToRaw>,
    Tracked<Dealloc>,
), r2: (
    *mut u8,
    Tracked<PointsToRaw>,
    Tracked<Dealloc>,
)) -> bool {
    ((true /* raw pointer: opaque by default */) && (true /* PointsToRaw permission: opaque */) && ((r1.2)@@ == (r2.2)@@))
}

proof fn det_allocate(g_size_eq: bool, k_size_eq: int, g_size_rng: bool, k_size_rng_lo: int, k_size_rng_hi: int, g_align_eq: bool, k_align_eq: int, g_align_rng: bool, k_align_rng_lo: int, k_align_rng_hi: int, g_neq_tuple: bool, size: usize, align: usize, r1: (
    *mut u8,
    Tracked<PointsToRaw>,
    Tracked<Dealloc>,
), r2: (
    *mut u8,
    Tracked<PointsToRaw>,
    Tracked<Dealloc>,
))
    requires (valid_layout(size, align)), (size != 0),
    ensures
        ({
            &&& (r1.1@.is_range(r1.0.addr() as int, size as int))
            &&& (r1.0.addr() + size <= usize::MAX + 1)
            &&& (r1.2@@ == (DeallocData {
            addr: r1.0.addr(),
            size: size as nat,
            align: align as nat,
            provenance: r1.1@.provenance(),
        }))
            &&& (r1.0.addr() as int % align as int == 0)
            &&& (r1.0@.provenance == r1.1@.provenance())
            &&& (r2.1@.is_range(r2.0.addr() as int, size as int))
            &&& (r2.0.addr() + size <= usize::MAX + 1)
            &&& (r2.2@@ == (DeallocData {
            addr: r2.0.addr(),
            size: size as nat,
            align: align as nat,
            provenance: r2.1@.provenance(),
        }))
            &&& (r2.0.addr() as int % align as int == 0)
            &&& (r2.0@.provenance == r2.1@.provenance())
        }) ==> det_allocate_equal(r1, r2),
{
    if g_size_eq { assume(size as int == k_size_eq); }
    if g_size_rng { assume(size as int >= k_size_rng_lo && size as int <= k_size_rng_hi); }
    if g_align_eq { assume(align as int == k_align_eq); }
    if g_align_rng { assume(align as int >= k_align_rng_lo && align as int <= k_align_rng_hi); }
    if g_neq_tuple { assume(!det_allocate_equal(r1, r2)); }
}
}

fn main() {}
