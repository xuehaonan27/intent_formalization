#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::pcell::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal<T: ?Sized>(r1: (PCell<T>, Tracked<PointsTo<T>>), r2: (PCell<T>, Tracked<PointsTo<T>>)) -> bool
    where T: Sized {
    ((r1.0 == r2.0) && (((true) == (true)) && (((r1.1)@).id() == ((r2.1)@).id()) && ((true) ==> (((r1.1)@).value() == ((r2.1)@).value()))))
}

proof fn det_new<T: ?Sized>(g___r1_1____is_init___is_true: bool, g___r1_1____is_init___is_false: bool, g___r1_1____ptr___addr___eq: bool, k___r1_1____ptr___addr___eq: int, g___r1_1____ptr___addr___rng: bool, k___r1_1____ptr___addr___rng_lo: int, k___r1_1____ptr___addr___rng_hi: int, g___r2_1____is_init___is_true: bool, g___r2_1____is_init___is_false: bool, g___r2_1____ptr___addr___eq: bool, k___r2_1____ptr___addr___eq: int, g___r2_1____ptr___addr___rng: bool, k___r2_1____ptr___addr___rng_lo: int, k___r2_1____ptr___addr___rng_hi: int, g_neq_tuple: bool, v: T, r1: (PCell<T>, Tracked<PointsTo<T>>), r2: (PCell<T>, Tracked<PointsTo<T>>))
    where T: Sized
    ensures
        ({
            &&& (r1.1@.id() == r1.0.id() && r1.1@.value() == v)
            &&& (r2.1@.id() == r2.0.id() && r2.1@.value() == v)
        }) ==> det_new_equal::<T>(r1, r2),
{
    if g___r1_1____is_init___is_true { assume((true) == true); }
    if g___r1_1____is_init___is_false { assume((true) == false); }
    if g___r2_1____is_init___is_true { assume((true) == true); }
    if g___r2_1____is_init___is_false { assume((true) == false); }
    if g_neq_tuple { assume(!det_new_equal::<T>(r1, r2)); }
}

}

fn main() {}
