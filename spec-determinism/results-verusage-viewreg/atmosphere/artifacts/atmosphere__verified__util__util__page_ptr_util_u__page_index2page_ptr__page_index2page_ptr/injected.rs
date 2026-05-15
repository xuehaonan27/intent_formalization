use vstd::prelude::*;

fn main() {}

verus!{

// File: lemma/lemma_t.rs
	#[verifier::external_body]
#[verifier(external_body)]
pub proof fn lemma_usize_u64(x: u64)
    ensures
        x as usize as u64 == x,
	{
		unimplemented!()
	}


// File: util/page_ptr_util_u.rs
pub open spec fn spec_page_index2page_ptr(i: usize) -> usize
    recommends
        page_index_valid(i),
{
    (i * 4096) as usize
}

#[verifier(when_used_as_spec(spec_page_index2page_ptr))]
pub fn page_index2page_ptr(i: usize) -> (ret: usize)
    requires
        0 <= i < NUM_PAGES,
    ensures
        ret == spec_page_index2page_ptr(i),
{
    proof {
        lemma_usize_u64(MAX_USIZE);
    }
    i * 4096usize
}

pub open spec fn page_index_valid(index: usize) -> bool {
    (0 <= index < NUM_PAGES)
}


// File: define.rs
pub const NUM_PAGES: usize = 2 * 1024 * 1024;

pub const MAX_USIZE: u64 = 31 * 1024 * 1024 * 1024;



// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_page_index2page_ptr_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}

proof fn det_page_index2page_ptr(g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, i: usize, r1: usize, r2: usize)
    requires (0 <= i < NUM_PAGES),
    ensures
        ({
            &&& (r1 == spec_page_index2page_ptr(i))
            &&& (r2 == spec_page_index2page_ptr(i))
        }) ==> det_page_index2page_ptr_equal(r1, r2),
{
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_page_index2page_ptr_equal(r1, r2)); }
}
// === END INJECTED ===

}
