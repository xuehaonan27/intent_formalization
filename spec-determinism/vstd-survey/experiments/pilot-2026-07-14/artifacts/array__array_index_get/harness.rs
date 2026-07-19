#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::array::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_array_index_get_equal<T>(r1: &T, r2: &T) -> bool {
    (r1 == r2)
}

proof fn det_array_index_get<T, const N: usize>(g_ar_leneq: bool, k_ar_leneq: nat, g_ar_lenrng: bool, k_ar_lenrng_lo: nat, k_ar_lenrng_hi: nat, g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_neq_tuple: bool, ar: &[T; N], i: usize, r1: &T, r2: &T)
    requires (0 <= i < N),
    ensures
        ({
            &&& (*r1 == ar@.index(i as int))
            &&& (*r2 == ar@.index(i as int))
        }) ==> det_array_index_get_equal::<T>(r1, r2),
{
    if g_ar_leneq { assume(ar.len() == k_ar_leneq); }
    if g_ar_lenrng { assume(ar.len() >= k_ar_lenrng_lo && ar.len() <= k_ar_lenrng_hi); }
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_neq_tuple { assume(!det_array_index_get_equal::<T>(r1, r2)); }
}
}

fn main() {}
