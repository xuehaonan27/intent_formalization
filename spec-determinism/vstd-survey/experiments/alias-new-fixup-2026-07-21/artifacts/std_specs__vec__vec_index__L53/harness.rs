#![allow(unused_imports)]
#![feature(allocator_api)]
extern crate alloc;
use vstd::prelude::*;
use vstd::std_specs::vec::*;

use alloc::alloc::Allocator;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_vec_index_equal<T>(r1: &T, r2: &T) -> bool {
    (r1 == r2)
}

proof fn det_vec_index<T, A: Allocator>(g_vec_leneq: bool, k_vec_leneq: nat, g_vec_lenrng: bool, k_vec_lenrng_lo: nat, k_vec_lenrng_hi: nat, g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_neq_tuple: bool, vec: &Vec<T, A>, i: usize, r1: &T, r2: &T)
    requires (i < vec.view().len()),
    ensures
        ({
            &&& (*r1 == vec.view().index(i as int))
            &&& (*r2 == vec.view().index(i as int))
        }) ==> det_vec_index_equal::<T>(r1, r2),
{
    if g_vec_leneq { assume(vec@.len() == k_vec_leneq); }
    if g_vec_lenrng { assume(vec@.len() >= k_vec_lenrng_lo && vec@.len() <= k_vec_lenrng_hi); }
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_neq_tuple { assume(!det_vec_index_equal::<T>(r1, r2)); }
}
}

fn main() {}
