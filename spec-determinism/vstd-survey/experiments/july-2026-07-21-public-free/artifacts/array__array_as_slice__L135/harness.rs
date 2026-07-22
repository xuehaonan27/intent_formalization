#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::array::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_array_as_slice_equal<T>(r1: &[T], r2: &[T]) -> bool {
    (r1 =~= r2)
}

proof fn det_array_as_slice<T, const N: usize>(g_ar_leneq: bool, k_ar_leneq: nat, g_ar_lenrng: bool, k_ar_lenrng_lo: nat, k_ar_lenrng_hi: nat, g_r1_leneq: bool, k_r1_leneq: nat, g_r1_lenrng: bool, k_r1_lenrng_lo: nat, k_r1_lenrng_hi: nat, g_r2_leneq: bool, k_r2_leneq: nat, g_r2_lenrng: bool, k_r2_lenrng_lo: nat, k_r2_lenrng_hi: nat, g_neq_tuple: bool, ar: &[T; N], r1: &[T], r2: &[T])
    ensures
        ({
            &&& (r1 == spec_array_as_slice(ar))
            &&& (ar@ == r1@)
            &&& (r2 == spec_array_as_slice(ar))
            &&& (ar@ == r2@)
        }) ==> det_array_as_slice_equal::<T>(r1, r2),
{
    if g_ar_leneq { assume(ar.len() == k_ar_leneq); }
    if g_ar_lenrng { assume(ar.len() >= k_ar_lenrng_lo && ar.len() <= k_ar_lenrng_hi); }
    if g_r1_leneq { assume(r1.len() == k_r1_leneq); }
    if g_r1_lenrng { assume(r1.len() >= k_r1_lenrng_lo && r1.len() <= k_r1_lenrng_hi); }
    if g_r2_leneq { assume(r2.len() == k_r2_leneq); }
    if g_r2_lenrng { assume(r2.len() >= k_r2_lenrng_lo && r2.len() <= k_r2_lenrng_hi); }
    if g_neq_tuple { assume(!det_array_as_slice_equal::<T>(r1, r2)); }
}
}

fn main() {}
