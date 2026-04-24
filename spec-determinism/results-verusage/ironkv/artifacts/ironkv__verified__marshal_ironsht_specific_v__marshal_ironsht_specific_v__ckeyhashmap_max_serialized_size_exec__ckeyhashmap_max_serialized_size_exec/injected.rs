extern crate verus_builtin_macros as builtin_macros;
use vstd::bytes::*;
use vstd::map::*;
use vstd::modes::*;
use vstd::multiset::*;
use vstd::prelude::*;
use vstd::seq::*;
use vstd::seq_lib::*;
use vstd::set::*;
use vstd::slice::*;
use vstd::*;

fn main() {}

verus! {
    #[verifier::opaque]
    pub open spec fn ckeyhashmap_max_serialized_size() -> usize {
        0x100000
    }

    pub fn ckeyhashmap_max_serialized_size_exec() -> (r: usize)
        ensures r == ckeyhashmap_max_serialized_size()
    {
        reveal(ckeyhashmap_max_serialized_size);
        0x100000
    }


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_ckeyhashmap_max_serialized_size_exec_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}

proof fn det_ckeyhashmap_max_serialized_size_exec(g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, r1: usize, r2: usize)
    ensures
        ({
            &&& (r1 == ckeyhashmap_max_serialized_size())
            &&& (r2 == ckeyhashmap_max_serialized_size())
        }) ==> det_ckeyhashmap_max_serialized_size_exec_equal(r1, r2),
{
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_ckeyhashmap_max_serialized_size_exec_equal(r1, r2)); }
}
// === END INJECTED ===

}
