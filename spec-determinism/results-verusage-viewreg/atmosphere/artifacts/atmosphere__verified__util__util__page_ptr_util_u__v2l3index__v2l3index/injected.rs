use vstd::prelude::*;

fn main() {}

verus!{

pub type L3Index = usize;

// File: util/page_ptr_util_u.rs
pub open spec fn spec_va_4k_valid(va: usize) -> bool {
    (va & (!MEM_4k_MASK) as usize == 0) && (va as u64 >> 39u64 & 0x1ffu64)
        >= KERNEL_MEM_END_L4INDEX as u64
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_va_4k_valid))]
pub fn va_4k_valid(va: usize) -> (ret: bool)
    ensures
        ret == spec_va_4k_valid(va),
{
    unimplemented!()
}


pub open spec fn spec_va_2m_valid(va: usize) -> bool {
    (va & (!MEM_2m_MASK) as usize == 0) && (va as u64 >> 39u64 & 0x1ffu64)
        >= KERNEL_MEM_END_L4INDEX as u64
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_va_2m_valid))]
pub fn va_2m_valid(va: usize) -> (ret: bool)
    ensures
        ret == spec_va_2m_valid(va),
{
    unimplemented!()
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_va_2m_valid))]
pub fn va_1g_valid(va: usize) -> (ret: bool)
    ensures
        ret == spec_va_1g_valid(va),
{
    unimplemented!()
}

pub open spec fn spec_va_1g_valid(va: usize) -> bool {
    (va & (!MEM_1g_MASK) as usize == 0) && (va as u64 >> 39u64 & 0x1ffu64)
        >= KERNEL_MEM_END_L4INDEX as u64
}


pub open spec fn spec_v2l3index(va: usize) -> L3Index {
    (va >> 30 & 0x1ff) as usize
}

#[verifier(when_used_as_spec(spec_v2l3index))]
pub fn v2l3index(va: usize) -> (ret: L3Index)
    requires
        va_4k_valid(va) || va_2m_valid(va) || va_1g_valid(va),
    ensures
        ret == spec_v2l3index(va),
        ret <= 0x1ff,
{
    assert((va as u64 >> 30u64 & 0x1ffu64) as usize <= 0x1ff) by (bit_vector);
    (va as u64 >> 30u64 & 0x1ffu64) as usize
}


// File: define.rs
pub const KERNEL_MEM_END_L4INDEX: usize = 1;

pub const MEM_4k_MASK: u64 = 0x0000_ffff_ffff_f000;

pub const MEM_2m_MASK: u64 = 0x0000_ffff_ffe0_0000;

pub const MEM_1g_MASK: u64 = 0x0000_fffc_0000_0000;


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_v2l3index_equal(r1: L3Index, r2: L3Index) -> bool {
    ((r1 == r2))
}

proof fn det_v2l3index(g_va_eq: bool, k_va_eq: int, g_va_rng: bool, k_va_rng_lo: int, k_va_rng_hi: int, g_neq_tuple: bool, va: usize, r1: L3Index, r2: L3Index)
    requires (va_4k_valid(va) || va_2m_valid(va) || va_1g_valid(va)),
    ensures
        ({
            &&& (r1 == spec_v2l3index(va))
            &&& (r1 <= 0x1ff)
            &&& (r2 == spec_v2l3index(va))
            &&& (r2 <= 0x1ff)
        }) ==> det_v2l3index_equal(r1, r2),
{
    if g_va_eq { assume(va as int == k_va_eq); }
    if g_va_rng { assume(va as int >= k_va_rng_lo && va as int <= k_va_rng_hi); }
    if g_neq_tuple { assume(!det_v2l3index_equal(r1, r2)); }
}
// === END INJECTED ===

}
