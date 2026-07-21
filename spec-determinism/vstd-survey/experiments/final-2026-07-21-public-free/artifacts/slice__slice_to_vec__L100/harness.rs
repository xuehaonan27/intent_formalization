#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::slice::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_slice_to_vec_equal<T: Copy>(r1: alloc::vec::Vec<T>, r2: alloc::vec::Vec<T>) -> bool {
    ((r1)@ =~= (r2)@)
}

proof fn det_slice_to_vec<T: Copy>(g_slice_leneq: bool, k_slice_leneq: nat, g_slice_lenrng: bool, k_slice_lenrng_lo: nat, k_slice_lenrng_hi: nat, g_r1_leneq: bool, k_r1_leneq: nat, g_r1_lenrng: bool, k_r1_lenrng_lo: nat, k_r1_lenrng_hi: nat, g_r2_leneq: bool, k_r2_leneq: nat, g_r2_lenrng: bool, k_r2_lenrng_lo: nat, k_r2_lenrng_hi: nat, g_neq_tuple: bool, slice: &[T], r1: alloc::vec::Vec<T>, r2: alloc::vec::Vec<T>)
    ensures
        ({
            &&& (r1@ == slice@)
            &&& (r2@ == slice@)
        }) ==> det_slice_to_vec_equal::<T>(r1, r2),
{
    if g_slice_leneq { assume(slice.len() == k_slice_leneq); }
    if g_slice_lenrng { assume(slice.len() >= k_slice_lenrng_lo && slice.len() <= k_slice_lenrng_hi); }
    if g_r1_leneq { assume(r1@.len() == k_r1_leneq); }
    if g_r1_lenrng { assume(r1@.len() >= k_r1_lenrng_lo && r1@.len() <= k_r1_lenrng_hi); }
    if g_r2_leneq { assume(r2@.len() == k_r2_leneq); }
    if g_r2_lenrng { assume(r2@.len() >= k_r2_lenrng_lo && r2@.len() <= k_r2_lenrng_hi); }
    if g_neq_tuple { assume(!det_slice_to_vec_equal::<T>(r1, r2)); }
}
}

fn main() {}
