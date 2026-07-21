#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::bytes::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_u16_from_le_bytes_equal(r1: u16, r2: u16) -> bool {
    (r1 == r2)
}

proof fn det_u16_from_le_bytes(g_s_leneq: bool, k_s_leneq: nat, g_s_lenrng: bool, k_s_lenrng_lo: nat, k_s_lenrng_hi: nat, g_s_0__eq: bool, k_s_0__eq: int, g_s_0__rng: bool, k_s_0__rng_lo: int, k_s_0__rng_hi: int, g_s_1__eq: bool, k_s_1__eq: int, g_s_1__rng: bool, k_s_1__rng_lo: int, k_s_1__rng_hi: int, g_s_2__eq: bool, k_s_2__eq: int, g_s_2__rng: bool, k_s_2__rng_lo: int, k_s_2__rng_hi: int, g_s_3__eq: bool, k_s_3__eq: int, g_s_3__rng: bool, k_s_3__rng_lo: int, k_s_3__rng_hi: int, g_s_4__eq: bool, k_s_4__eq: int, g_s_4__rng: bool, k_s_4__rng_lo: int, k_s_4__rng_hi: int, g_s_5__eq: bool, k_s_5__eq: int, g_s_5__rng: bool, k_s_5__rng_lo: int, k_s_5__rng_hi: int, g_s_6__eq: bool, k_s_6__eq: int, g_s_6__rng: bool, k_s_6__rng_lo: int, k_s_6__rng_hi: int, g_s_7__eq: bool, k_s_7__eq: int, g_s_7__rng: bool, k_s_7__rng_lo: int, k_s_7__rng_hi: int, g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, s: &[u8], r1: u16, r2: u16)
    requires (s@.len() == 2),
    ensures
        ({
            &&& (r1 == spec_u16_from_le_bytes(s@))
            &&& (r2 == spec_u16_from_le_bytes(s@))
        }) ==> det_u16_from_le_bytes_equal(r1, r2),
{
    if g_s_leneq { assume(s.len() == k_s_leneq); }
    if g_s_lenrng { assume(s.len() >= k_s_lenrng_lo && s.len() <= k_s_lenrng_hi); }
    if g_s_0__eq { assume(s[0] as int == k_s_0__eq); }
    if g_s_0__rng { assume(s[0] as int >= k_s_0__rng_lo && s[0] as int <= k_s_0__rng_hi); }
    if g_s_1__eq { assume(s[1] as int == k_s_1__eq); }
    if g_s_1__rng { assume(s[1] as int >= k_s_1__rng_lo && s[1] as int <= k_s_1__rng_hi); }
    if g_s_2__eq { assume(s[2] as int == k_s_2__eq); }
    if g_s_2__rng { assume(s[2] as int >= k_s_2__rng_lo && s[2] as int <= k_s_2__rng_hi); }
    if g_s_3__eq { assume(s[3] as int == k_s_3__eq); }
    if g_s_3__rng { assume(s[3] as int >= k_s_3__rng_lo && s[3] as int <= k_s_3__rng_hi); }
    if g_s_4__eq { assume(s[4] as int == k_s_4__eq); }
    if g_s_4__rng { assume(s[4] as int >= k_s_4__rng_lo && s[4] as int <= k_s_4__rng_hi); }
    if g_s_5__eq { assume(s[5] as int == k_s_5__eq); }
    if g_s_5__rng { assume(s[5] as int >= k_s_5__rng_lo && s[5] as int <= k_s_5__rng_hi); }
    if g_s_6__eq { assume(s[6] as int == k_s_6__eq); }
    if g_s_6__rng { assume(s[6] as int >= k_s_6__rng_lo && s[6] as int <= k_s_6__rng_hi); }
    if g_s_7__eq { assume(s[7] as int == k_s_7__eq); }
    if g_s_7__rng { assume(s[7] as int >= k_s_7__rng_lo && s[7] as int <= k_s_7__rng_hi); }
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_u16_from_le_bytes_equal(r1, r2)); }
}
}

fn main() {}
