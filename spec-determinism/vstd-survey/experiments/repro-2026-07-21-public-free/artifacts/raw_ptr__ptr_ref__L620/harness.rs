#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_ptr_ref_equal<T>(r1: &T, r2: &T) -> bool {
    (r1 == r2)
}

proof fn det_ptr_ref<T>(g__perm__is_init___is_true: bool, g__perm__is_init___is_false: bool, g__perm__addr___eq: bool, k__perm__addr___eq: int, g__perm__addr___rng: bool, k__perm__addr___rng_lo: int, k__perm__addr___rng_hi: int, g_neq_tuple: bool, ptr: *const T, perm: &PointsTo<T>, r1: &T, r2: &T)
    requires (perm.ptr() == ptr), (perm.is_init()),
    ensures
        ({
            &&& (r1 == perm.value())
            &&& (r2 == perm.value())
        }) ==> det_ptr_ref_equal::<T>(r1, r2),
{
    if g__perm__is_init___is_true { assume((perm).is_init() == true); }
    if g__perm__is_init___is_false { assume((perm).is_init() == false); }
    if g__perm__addr___eq { assume((perm).addr() as int == k__perm__addr___eq); }
    if g__perm__addr___rng { assume((perm).addr() as int >= k__perm__addr___rng_lo && (perm).addr() as int <= k__perm__addr___rng_hi); }
    if g_neq_tuple { assume(!det_ptr_ref_equal(r1, r2)); }
}
}

fn main() {}
