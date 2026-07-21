#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::pcell::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_into_inner_equal<T: ?Sized>(r1: T, r2: T) -> bool
    where T: Sized {
    (r1 == r2)
}

proof fn det_into_inner<T: ?Sized>(g__perm__is_init___is_true: bool, g__perm__is_init___is_false: bool, g__perm__ptr___addr___eq: bool, k__perm__ptr___addr___eq: int, g__perm__ptr___addr___rng: bool, k__perm__ptr___addr___rng_lo: int, k__perm__ptr___addr___rng_hi: int, g_neq_tuple: bool, self_: PCell<T>, perm: PointsTo<T>, r1: T, r2: T)
    where T: Sized
    requires (self_.id() == perm.id()),
    ensures
        ({
            &&& (r1 == *perm.value())
            &&& (r2 == *perm.value())
        }) ==> det_into_inner_equal::<T>(r1, r2),
{
    if g__perm__is_init___is_true { assume(true) == true); }
    if g__perm__is_init___is_false { assume(true) == false); }
    if g_neq_tuple { assume(!det_into_inner_equal::<T>(r1, r2)); }
}

}

fn main() {}
