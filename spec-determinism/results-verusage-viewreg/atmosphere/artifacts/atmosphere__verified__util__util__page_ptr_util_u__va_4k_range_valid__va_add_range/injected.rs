use vstd::prelude::*;

fn main() {}

verus!{

// File: util/page_ptr_util_u.rs
	#[verifier::external_body]
#[verifier(when_used_as_spec(spec_va_4k_valid))]
pub fn va_4k_valid(va: usize) -> (ret: bool)
    ensures
        ret == spec_va_4k_valid(va),
	{
		unimplemented!()
	}

pub open spec fn spec_va_4k_range_valid(va: usize, len: usize) -> bool {
    forall|i: usize|
        #![trigger spec_va_add_range(va, i)]
        0 <= i < len ==> spec_va_4k_valid(spec_va_add_range(va, i))
}

#[verifier(when_used_as_spec(spec_va_4k_range_valid))]
pub fn va_4k_range_valid(va: usize, len: usize) -> (ret: bool)
    requires
        va_4k_valid(va),
    ensures
        spec_va_4k_range_valid(va, len) == ret,
{
    for idx in iter: 0..len
        invariant
            va_4k_valid(va),
            forall|i: usize|
                #![trigger spec_va_add_range(va, i)]
                0 <= i < idx ==> spec_va_4k_valid(spec_va_add_range(va, i)),
    {
        if va_4k_valid(va_add_range(va, idx)) == false {
            return false;
        }
    }
    true
}

pub open spec fn spec_va_4k_valid(va: usize) -> bool {
    (va & (!MEM_4k_MASK) as usize == 0) && (va as u64 >> 39u64 & 0x1ffu64)
        >= KERNEL_MEM_END_L4INDEX as u64
}

pub open spec fn spec_va_add_range(va: usize, i: usize) -> usize {
    (va + (i * 4096)) as usize
}

	#[verifier::external_body]
#[verifier(external_body)]
pub fn va_add_range(va: usize, i: usize) -> (ret: usize)
    ensures
        ret == spec_va_add_range(va, i),
        i != 0 ==> ret != va,
	{
		unimplemented!()
	}


// File: define.rs
pub const KERNEL_MEM_END_L4INDEX: usize = 1;

pub const MEM_4k_MASK: u64 = 0x0000_ffff_ffff_f000;



// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_va_add_range_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}

proof fn det_va_add_range(g_va_eq: bool, k_va_eq: int, g_va_rng: bool, k_va_rng_lo: int, k_va_rng_hi: int, g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, va: usize, i: usize, r1: usize, r2: usize)
    ensures
        ({
            &&& (r1 == spec_va_add_range(va, i))
            &&& (i != 0 ==> r1 != va)
            &&& (r2 == spec_va_add_range(va, i))
            &&& (i != 0 ==> r2 != va)
        }) ==> det_va_add_range_equal(r1, r2),
{
    if g_va_eq { assume(va as int == k_va_eq); }
    if g_va_rng { assume(va as int >= k_va_rng_lo && va as int <= k_va_rng_hi); }
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_va_add_range_equal(r1, r2)); }
}
// === END INJECTED ===

}
