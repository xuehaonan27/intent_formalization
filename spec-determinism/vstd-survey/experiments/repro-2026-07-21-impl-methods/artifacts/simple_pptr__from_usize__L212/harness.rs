#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::simple_pptr::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_from_usize_equal<V>(r1: PPtr<V>, r2: PPtr<V>) -> bool {
    (r1 == r2)
}

proof fn det_from_usize<V>(g_u_eq: bool, k_u_eq: int, g_u_rng: bool, k_u_rng_lo: int, k_u_rng_hi: int, g_neq_tuple: bool, u: usize, r1: PPtr<V>, r2: PPtr<V>)
    ensures
        ({
            &&& (u == r1.addr())
            &&& (u == r2.addr())
        }) ==> det_from_usize_equal::<V>(r1, r2),
{
    if g_u_eq { assume(u as int == k_u_eq); }
    if g_u_rng { assume(u as int >= k_u_rng_lo && u as int <= k_u_rng_hi); }
    if g_neq_tuple { assume(!det_from_usize_equal(r1, r2)); }
}
}

fn main() {}
