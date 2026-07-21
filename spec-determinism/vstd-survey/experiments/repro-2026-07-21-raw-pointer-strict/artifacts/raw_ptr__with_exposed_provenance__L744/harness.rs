#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_with_exposed_provenance_equal<T: Sized>(r1: *mut T, r2: *mut T) -> bool {
    (((r1).view() =~= (r2).view()))
}

proof fn det_with_exposed_provenance<T: Sized>(g_addr_eq: bool, k_addr_eq: int, g_addr_rng: bool, k_addr_rng_lo: int, k_addr_rng_hi: int, g_neq_tuple: bool, addr: usize, provenance: IsExposed, r1: *mut T, r2: *mut T)
    ensures
        ({
            &&& (r1 == ptr_mut_from_data::<T>(
            PtrData::<T> { addr: addr, provenance: provenance@, metadata: () },
        ))
            &&& (r2 == ptr_mut_from_data::<T>(
            PtrData::<T> { addr: addr, provenance: provenance@, metadata: () },
        ))
        }) ==> det_with_exposed_provenance_equal::<T>(r1, r2),
{
    if g_addr_eq { assume(addr as int == k_addr_eq); }
    if g_addr_rng { assume(addr as int >= k_addr_rng_lo && addr as int <= k_addr_rng_hi); }
    if g_neq_tuple { assume(!det_with_exposed_provenance_equal(r1, r2)); }
}
}

fn main() {}
