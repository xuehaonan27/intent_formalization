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
spec fn det_va_4k_range_valid_equal(r1: bool, r2: bool) -> bool {
    (r1 == r2)
}

proof fn det_va_4k_range_valid(g_va_eq: bool, k_va_eq: int, g_va_rng: bool, k_va_rng_lo: int, k_va_rng_hi: int, g_len_eq: bool, k_len_eq: int, g_len_rng: bool, k_len_rng_lo: int, k_len_rng_hi: int, g_r1_is_true: bool, g_r1_is_false: bool, g_r2_is_true: bool, g_r2_is_false: bool, g_neq_tuple: bool, va: usize, len: usize, r1: bool, r2: bool)
    requires (va_4k_valid(va)),
    ensures
        ({
            &&& (spec_va_4k_range_valid(va, len) == r1)
            &&& (spec_va_4k_range_valid(va, len) == r2)
        }) ==> det_va_4k_range_valid_equal(r1, r2),
{
    if g_va_eq { assume(va as int == k_va_eq); }
    if g_va_rng { assume(va as int >= k_va_rng_lo && va as int <= k_va_rng_hi); }
    if g_len_eq { assume(len as int == k_len_eq); }
    if g_len_rng { assume(len as int >= k_len_rng_lo && len as int <= k_len_rng_hi); }
    if g_r1_is_true { assume(r1 == true); }
    if g_r1_is_false { assume(r1 == false); }
    if g_r2_is_true { assume(r2 == true); }
    if g_r2_is_false { assume(r2 == false); }
    if g_neq_tuple { assume(!det_va_4k_range_valid_equal(r1, r2)); }
}
// === END INJECTED ===

}
