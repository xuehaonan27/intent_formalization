#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::pcell::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_replace_equal<T: ?Sized>(r1: T, r2: T, post1_perm: PointsTo<T>, post2_perm: PointsTo<T>) -> bool
    where T: Sized {
    (r1 == r2)
    && (((true) == (true)) && ((post1_perm).id() == (post2_perm).id()) && ((true) ==> ((post1_perm).value() == (post2_perm).value())))
}

proof fn det_replace<T: ?Sized>(g__pre_perm__is_init___is_true: bool, g__pre_perm__is_init___is_false: bool, g__pre_perm__ptr___addr___eq: bool, k__pre_perm__ptr___addr___eq: int, g__pre_perm__ptr___addr___rng: bool, k__pre_perm__ptr___addr___rng_lo: int, k__pre_perm__ptr___addr___rng_hi: int, g__post1_perm__is_init___is_true: bool, g__post1_perm__is_init___is_false: bool, g__post1_perm__ptr___addr___eq: bool, k__post1_perm__ptr___addr___eq: int, g__post1_perm__ptr___addr___rng: bool, k__post1_perm__ptr___addr___rng_lo: int, k__post1_perm__ptr___addr___rng_hi: int, g__post2_perm__is_init___is_true: bool, g__post2_perm__is_init___is_false: bool, g__post2_perm__ptr___addr___eq: bool, k__post2_perm__ptr___addr___eq: int, g__post2_perm__ptr___addr___rng: bool, k__post2_perm__ptr___addr___rng_lo: int, k__post2_perm__ptr___addr___rng_hi: int, g_neq_tuple: bool, self_: &PCell<T>, pre_perm: PointsTo<T>, in_v: T, post1_perm: PointsTo<T>, r1: T, post2_perm: PointsTo<T>, r2: T)
    where T: Sized
    requires (self_.id() == pre_perm.id()),
    ensures
        ({
            &&& (post1_perm.id() == pre_perm.id())
            &&& (post1_perm.value() == in_v)
            &&& (r1 == pre_perm.value())
            &&& (post2_perm.id() == pre_perm.id())
            &&& (post2_perm.value() == in_v)
            &&& (r2 == pre_perm.value())
        }) ==> det_replace_equal::<T>(r1, r2, post1_perm, post2_perm),
{
    if g__pre_perm__is_init___is_true { assume((true) == true); }
    if g__pre_perm__is_init___is_false { assume((true) == false); }
    if g__post1_perm__is_init___is_true { assume((true) == true); }
    if g__post1_perm__is_init___is_false { assume((true) == false); }
    if g__post2_perm__is_init___is_true { assume((true) == true); }
    if g__post2_perm__is_init___is_false { assume((true) == false); }
    if g_neq_tuple { assume(!det_replace_equal::<T>(r1, r2, post1_perm, post2_perm)); }
}

}

fn main() {}
