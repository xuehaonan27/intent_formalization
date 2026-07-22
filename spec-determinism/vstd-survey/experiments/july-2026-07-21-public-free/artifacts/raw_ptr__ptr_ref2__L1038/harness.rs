#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_ptr_ref2_equal<'a, T>(r1: SharedReference<
    'a,
    T,
>, r2: SharedReference<
    'a,
    T,
>) -> bool {
    (r1 == r2)
}

proof fn det_ptr_ref2<'a, T>(g__perm__is_init___is_true: bool, g__perm__is_init___is_false: bool, g__perm__ptr___addr___eq: bool, k__perm__ptr___addr___eq: int, g__perm__ptr___addr___rng: bool, k__perm__ptr___addr___rng_lo: int, k__perm__ptr___addr___rng_hi: int, g_neq_tuple: bool, ptr: *const T, perm: &PointsTo<T>, r1: SharedReference<
    'a,
    T,
>, r2: SharedReference<
    'a,
    T,
>)
    requires (perm.ptr() == ptr), (perm.is_init()),
    ensures
        ({
            &&& (r1.value() == perm.value())
            &&& (r1.ptr().addr() == ptr.addr())
            &&& (r1.ptr()@.metadata == ptr@.metadata)
            &&& (r2.value() == perm.value())
            &&& (r2.ptr().addr() == ptr.addr())
            &&& (r2.ptr()@.metadata == ptr@.metadata)
        }) ==> det_ptr_ref2_equal::<T>(r1, r2),
{
    if g__perm__is_init___is_true { assume((perm).is_init() == true); }
    if g__perm__is_init___is_false { assume((perm).is_init() == false); }
    if g__perm__ptr___addr___eq { assume((perm).ptr().addr() as int == k__perm__ptr___addr___eq); }
    if g__perm__ptr___addr___rng { assume((perm).ptr().addr() as int >= k__perm__ptr___addr___rng_lo && (perm).ptr().addr() as int <= k__perm__ptr___addr___rng_hi); }
    if g_neq_tuple { assume(!det_ptr_ref2_equal::<T>(r1, r2)); }
}
}

fn main() {}
