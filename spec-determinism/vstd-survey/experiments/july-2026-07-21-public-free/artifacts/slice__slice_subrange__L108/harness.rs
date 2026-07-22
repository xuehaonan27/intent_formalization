#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::slice::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_slice_subrange_equal<T>(r1: &[T], r2: &[T]) -> bool {
    (r1 =~= r2)
}

proof fn det_slice_subrange<T>(g_slice_leneq: bool, k_slice_leneq: nat, g_slice_lenrng: bool, k_slice_lenrng_lo: nat, k_slice_lenrng_hi: nat, g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_j_eq: bool, k_j_eq: int, g_j_rng: bool, k_j_rng_lo: int, k_j_rng_hi: int, g_r1_leneq: bool, k_r1_leneq: nat, g_r1_lenrng: bool, k_r1_lenrng_lo: nat, k_r1_lenrng_hi: nat, g_r2_leneq: bool, k_r2_leneq: nat, g_r2_lenrng: bool, k_r2_lenrng_lo: nat, k_r2_lenrng_hi: nat, g_neq_tuple: bool, slice: &[T], i: usize, j: usize, r1: &[T], r2: &[T])
    requires (0 <= i <= j <= slice@.len()),
    ensures
        ({
            &&& (r1@ == slice@.subrange(i as int, j as int))
            &&& (r2@ == slice@.subrange(i as int, j as int))
        }) ==> det_slice_subrange_equal::<T>(r1, r2),
{
    if g_slice_leneq { assume(slice.len() == k_slice_leneq); }
    if g_slice_lenrng { assume(slice.len() >= k_slice_lenrng_lo && slice.len() <= k_slice_lenrng_hi); }
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_j_eq { assume(j as int == k_j_eq); }
    if g_j_rng { assume(j as int >= k_j_rng_lo && j as int <= k_j_rng_hi); }
    if g_r1_leneq { assume(r1.len() == k_r1_leneq); }
    if g_r1_lenrng { assume(r1.len() >= k_r1_lenrng_lo && r1.len() <= k_r1_lenrng_hi); }
    if g_r2_leneq { assume(r2.len() == k_r2_leneq); }
    if g_r2_lenrng { assume(r2.len() >= k_r2_lenrng_lo && r2.len() <= k_r2_lenrng_hi); }
    if g_neq_tuple { assume(!det_slice_subrange_equal::<T>(r1, r2)); }
}
}

fn main() {}
