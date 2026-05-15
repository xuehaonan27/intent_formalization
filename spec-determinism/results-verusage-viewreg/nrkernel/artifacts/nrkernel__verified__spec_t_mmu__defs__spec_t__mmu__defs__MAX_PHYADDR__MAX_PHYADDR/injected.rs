use vstd::prelude::*;

fn main() {}

verus!{

global size_of usize == 8;

// File: spec_t/mmu/defs.rs
#[verifier::external_body]
pub const MAX_PHYADDR_WIDTH: usize = 52;

#[verifier::external_body]
pub proof fn axiom_max_phyaddr_width_facts()
    ensures
        32 <= MAX_PHYADDR_WIDTH <= 52,
{
		unimplemented!()
}

pub spec const MAX_PHYADDR_SPEC: usize = ((1usize << MAX_PHYADDR_WIDTH) - 1usize) as usize;

pub fn MAX_PHYADDR() -> (ret: usize)
    ensures ret == MAX_PHYADDR_SPEC 
{
    proof {
        axiom_max_phyaddr_width_facts();
    }
    assert(1usize << 32 == 0x100000000) by (compute);
    assert(forall|m:usize,n:usize|  n < m < 64 ==> 1usize << n < 1usize << m) by (bit_vector);
    let r = (1usize << MAX_PHYADDR_WIDTH) - 1usize;
    r
}

// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_MAX_PHYADDR_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}

proof fn det_MAX_PHYADDR(g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, r1: usize, r2: usize)
    ensures
        ({
            &&& (r1 == MAX_PHYADDR_SPEC)
            &&& (r2 == MAX_PHYADDR_SPEC)
        }) ==> det_MAX_PHYADDR_equal(r1, r2),
{
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_MAX_PHYADDR_equal(r1, r2)); }
}
// === END INJECTED ===

}
