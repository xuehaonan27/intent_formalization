use vstd::prelude::*;

fn main() {}

verus!{

// File: spec_t/mmu/defs.rs
macro_rules! bitmask_inc {
    ($low:expr,$high:expr) => {
        (!(!0usize << (($high+1usize)-$low))) << $low
    }
}

#[verifier(external_body)]
pub const MAX_PHYADDR_WIDTH: usize = 52;

pub axiom fn axiom_max_phyaddr_width_facts()
    ensures
        32 <= MAX_PHYADDR_WIDTH <= 52,
;


// File: spec_t/mmu/translation.rs
pub spec const MASK_L1_PG_ADDR_SPEC: usize = bitmask_inc!(30usize, MAX_PHYADDR_WIDTH - 1);

pub fn MASK_L1_PG_ADDR() -> (ret: usize)
    ensures ret == MASK_L1_PG_ADDR_SPEC 
{
    proof {
        axiom_max_phyaddr_width_facts();
    }
    let r = bitmask_inc!(30usize, MAX_PHYADDR_WIDTH - 1);
    r
}

// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_MASK_L1_PG_ADDR_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}

proof fn det_MASK_L1_PG_ADDR(g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, r1: usize, r2: usize)
    ensures
        ({
            &&& (r1 == MASK_L1_PG_ADDR_SPEC)
            &&& (r2 == MASK_L1_PG_ADDR_SPEC)
        }) ==> det_MASK_L1_PG_ADDR_equal(r1, r2),
{
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_MASK_L1_PG_ADDR_equal(r1, r2)); }
}
// === END INJECTED ===

}
