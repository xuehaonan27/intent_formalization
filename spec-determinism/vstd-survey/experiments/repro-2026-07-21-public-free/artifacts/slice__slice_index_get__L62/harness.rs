#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::slice::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_slice_index_get_equal<T>(r1: &T, r2: &T) -> bool {
    (r1 == r2)
}

proof fn det_slice_index_get<T>(g_slice_leneq: bool, k_slice_leneq: nat, g_slice_lenrng: bool, k_slice_lenrng_lo: nat, k_slice_lenrng_hi: nat, g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_neq_tuple: bool, slice: &[T], i: usize, r1: &T, r2: &T)
    requires (0 <= i < slice.view().len()),
    ensures
        ({
            &&& (*r1 == slice@.index(i as int))
            &&& (*r2 == slice@.index(i as int))
        }) ==> det_slice_index_get_equal::<T>(r1, r2),
{
    if g_slice_leneq { assume(slice.len() == k_slice_leneq); }
    if g_slice_lenrng { assume(slice.len() >= k_slice_lenrng_lo && slice.len() <= k_slice_lenrng_hi); }
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_neq_tuple { assume(!det_slice_index_get_equal(r1, r2)); }
}
}

fn main() {}
