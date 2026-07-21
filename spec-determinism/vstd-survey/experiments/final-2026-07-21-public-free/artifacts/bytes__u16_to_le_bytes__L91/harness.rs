#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::bytes::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_u16_to_le_bytes_equal(r1: alloc::vec::Vec<u8>, r2: alloc::vec::Vec<u8>) -> bool {
    ((r1)@ =~= (r2)@)
}

proof fn det_u16_to_le_bytes(g_x_eq: bool, k_x_eq: int, g_x_rng: bool, k_x_rng_lo: int, k_x_rng_hi: int, g_r1_leneq: bool, k_r1_leneq: nat, g_r1_lenrng: bool, k_r1_lenrng_lo: nat, k_r1_lenrng_hi: nat, g_r1__0__eq: bool, k_r1__0__eq: int, g_r1__0__rng: bool, k_r1__0__rng_lo: int, k_r1__0__rng_hi: int, g_r1__1__eq: bool, k_r1__1__eq: int, g_r1__1__rng: bool, k_r1__1__rng_lo: int, k_r1__1__rng_hi: int, g_r1__2__eq: bool, k_r1__2__eq: int, g_r1__2__rng: bool, k_r1__2__rng_lo: int, k_r1__2__rng_hi: int, g_r1__3__eq: bool, k_r1__3__eq: int, g_r1__3__rng: bool, k_r1__3__rng_lo: int, k_r1__3__rng_hi: int, g_r1__4__eq: bool, k_r1__4__eq: int, g_r1__4__rng: bool, k_r1__4__rng_lo: int, k_r1__4__rng_hi: int, g_r1__5__eq: bool, k_r1__5__eq: int, g_r1__5__rng: bool, k_r1__5__rng_lo: int, k_r1__5__rng_hi: int, g_r1__6__eq: bool, k_r1__6__eq: int, g_r1__6__rng: bool, k_r1__6__rng_lo: int, k_r1__6__rng_hi: int, g_r1__7__eq: bool, k_r1__7__eq: int, g_r1__7__rng: bool, k_r1__7__rng_lo: int, k_r1__7__rng_hi: int, g_r2_leneq: bool, k_r2_leneq: nat, g_r2_lenrng: bool, k_r2_lenrng_lo: nat, k_r2_lenrng_hi: nat, g_r2__0__eq: bool, k_r2__0__eq: int, g_r2__0__rng: bool, k_r2__0__rng_lo: int, k_r2__0__rng_hi: int, g_r2__1__eq: bool, k_r2__1__eq: int, g_r2__1__rng: bool, k_r2__1__rng_lo: int, k_r2__1__rng_hi: int, g_r2__2__eq: bool, k_r2__2__eq: int, g_r2__2__rng: bool, k_r2__2__rng_lo: int, k_r2__2__rng_hi: int, g_r2__3__eq: bool, k_r2__3__eq: int, g_r2__3__rng: bool, k_r2__3__rng_lo: int, k_r2__3__rng_hi: int, g_r2__4__eq: bool, k_r2__4__eq: int, g_r2__4__rng: bool, k_r2__4__rng_lo: int, k_r2__4__rng_hi: int, g_r2__5__eq: bool, k_r2__5__eq: int, g_r2__5__rng: bool, k_r2__5__rng_lo: int, k_r2__5__rng_hi: int, g_r2__6__eq: bool, k_r2__6__eq: int, g_r2__6__rng: bool, k_r2__6__rng_lo: int, k_r2__6__rng_hi: int, g_r2__7__eq: bool, k_r2__7__eq: int, g_r2__7__rng: bool, k_r2__7__rng_lo: int, k_r2__7__rng_hi: int, g_neq_tuple: bool, x: u16, r1: alloc::vec::Vec<u8>, r2: alloc::vec::Vec<u8>)
    ensures
        ({
            &&& (r1@ == spec_u16_to_le_bytes(x))
            &&& (r1@.len() == 2)
            &&& (r2@ == spec_u16_to_le_bytes(x))
            &&& (r2@.len() == 2)
        }) ==> det_u16_to_le_bytes_equal(r1, r2),
{
    if g_x_eq { assume(x as int == k_x_eq); }
    if g_x_rng { assume(x as int >= k_x_rng_lo && x as int <= k_x_rng_hi); }
    if g_r1_leneq { assume(r1@.len() == k_r1_leneq); }
    if g_r1_lenrng { assume(r1@.len() >= k_r1_lenrng_lo && r1@.len() <= k_r1_lenrng_hi); }
    if g_r1__0__eq { assume(r1@[0] as int == k_r1__0__eq); }
    if g_r1__0__rng { assume(r1@[0] as int >= k_r1__0__rng_lo && r1@[0] as int <= k_r1__0__rng_hi); }
    if g_r1__1__eq { assume(r1@[1] as int == k_r1__1__eq); }
    if g_r1__1__rng { assume(r1@[1] as int >= k_r1__1__rng_lo && r1@[1] as int <= k_r1__1__rng_hi); }
    if g_r1__2__eq { assume(r1@[2] as int == k_r1__2__eq); }
    if g_r1__2__rng { assume(r1@[2] as int >= k_r1__2__rng_lo && r1@[2] as int <= k_r1__2__rng_hi); }
    if g_r1__3__eq { assume(r1@[3] as int == k_r1__3__eq); }
    if g_r1__3__rng { assume(r1@[3] as int >= k_r1__3__rng_lo && r1@[3] as int <= k_r1__3__rng_hi); }
    if g_r1__4__eq { assume(r1@[4] as int == k_r1__4__eq); }
    if g_r1__4__rng { assume(r1@[4] as int >= k_r1__4__rng_lo && r1@[4] as int <= k_r1__4__rng_hi); }
    if g_r1__5__eq { assume(r1@[5] as int == k_r1__5__eq); }
    if g_r1__5__rng { assume(r1@[5] as int >= k_r1__5__rng_lo && r1@[5] as int <= k_r1__5__rng_hi); }
    if g_r1__6__eq { assume(r1@[6] as int == k_r1__6__eq); }
    if g_r1__6__rng { assume(r1@[6] as int >= k_r1__6__rng_lo && r1@[6] as int <= k_r1__6__rng_hi); }
    if g_r1__7__eq { assume(r1@[7] as int == k_r1__7__eq); }
    if g_r1__7__rng { assume(r1@[7] as int >= k_r1__7__rng_lo && r1@[7] as int <= k_r1__7__rng_hi); }
    if g_r2_leneq { assume(r2@.len() == k_r2_leneq); }
    if g_r2_lenrng { assume(r2@.len() >= k_r2_lenrng_lo && r2@.len() <= k_r2_lenrng_hi); }
    if g_r2__0__eq { assume(r2@[0] as int == k_r2__0__eq); }
    if g_r2__0__rng { assume(r2@[0] as int >= k_r2__0__rng_lo && r2@[0] as int <= k_r2__0__rng_hi); }
    if g_r2__1__eq { assume(r2@[1] as int == k_r2__1__eq); }
    if g_r2__1__rng { assume(r2@[1] as int >= k_r2__1__rng_lo && r2@[1] as int <= k_r2__1__rng_hi); }
    if g_r2__2__eq { assume(r2@[2] as int == k_r2__2__eq); }
    if g_r2__2__rng { assume(r2@[2] as int >= k_r2__2__rng_lo && r2@[2] as int <= k_r2__2__rng_hi); }
    if g_r2__3__eq { assume(r2@[3] as int == k_r2__3__eq); }
    if g_r2__3__rng { assume(r2@[3] as int >= k_r2__3__rng_lo && r2@[3] as int <= k_r2__3__rng_hi); }
    if g_r2__4__eq { assume(r2@[4] as int == k_r2__4__eq); }
    if g_r2__4__rng { assume(r2@[4] as int >= k_r2__4__rng_lo && r2@[4] as int <= k_r2__4__rng_hi); }
    if g_r2__5__eq { assume(r2@[5] as int == k_r2__5__eq); }
    if g_r2__5__rng { assume(r2@[5] as int >= k_r2__5__rng_lo && r2@[5] as int <= k_r2__5__rng_hi); }
    if g_r2__6__eq { assume(r2@[6] as int == k_r2__6__eq); }
    if g_r2__6__rng { assume(r2@[6] as int >= k_r2__6__rng_lo && r2@[6] as int <= k_r2__6__rng_hi); }
    if g_r2__7__eq { assume(r2@[7] as int == k_r2__7__eq); }
    if g_r2__7__rng { assume(r2@[7] as int >= k_r2__7__rng_lo && r2@[7] as int <= k_r2__7__rng_hi); }
    if g_neq_tuple { assume(!det_u16_to_le_bytes_equal(r1, r2)); }
}
}

fn main() {}
