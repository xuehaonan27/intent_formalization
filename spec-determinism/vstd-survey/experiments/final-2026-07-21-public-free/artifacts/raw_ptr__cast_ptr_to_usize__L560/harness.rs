#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_cast_ptr_to_usize_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}

proof fn det_cast_ptr_to_usize<T: Sized>(g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, ptr: *mut T, r1: usize, r2: usize)
    ensures
        ({
            &&& (r1 == spec_cast_ptr_to_usize(ptr))
            &&& (r2 == spec_cast_ptr_to_usize(ptr))
        }) ==> det_cast_ptr_to_usize_equal(r1, r2),
{
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_cast_ptr_to_usize_equal(r1, r2)); }
}
}

fn main() {}
