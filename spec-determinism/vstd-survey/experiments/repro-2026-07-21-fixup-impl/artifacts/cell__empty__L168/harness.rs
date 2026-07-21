#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_empty_equal<V>(r1: (PCell<V>, Tracked<PointsTo<V>>), r2: (PCell<V>, Tracked<PointsTo<V>>)) -> bool {
    ((r1.0 == r2.0) && ((((r1.1)@).is_init() == ((r2.1)@).is_init()) && (((r1.1)@).id() == ((r2.1)@).id()) && (((r1.1)@).is_init() ==> (((r1.1)@).value() == ((r2.1)@).value()))))
}

proof fn det_empty<V>(g___r1_1____is_init___is_true: bool, g___r1_1____is_init___is_false: bool, g___r1_1____ptr___addr___eq: bool, k___r1_1____ptr___addr___eq: int, g___r1_1____ptr___addr___rng: bool, k___r1_1____ptr___addr___rng_lo: int, k___r1_1____ptr___addr___rng_hi: int, g___r2_1____is_init___is_true: bool, g___r2_1____is_init___is_false: bool, g___r2_1____ptr___addr___eq: bool, k___r2_1____ptr___addr___eq: int, g___r2_1____ptr___addr___rng: bool, k___r2_1____ptr___addr___rng_lo: int, k___r2_1____ptr___addr___rng_hi: int, g_neq_tuple: bool, r1: (PCell<V>, Tracked<PointsTo<V>>), r2: (PCell<V>, Tracked<PointsTo<V>>))
    ensures
        ({
            &&& (r1.1@@ == pcell_points![ r1.0.id() => MemContents::Uninit ])
            &&& (r2.1@@ == pcell_points![ r2.0.id() => MemContents::Uninit ])
        }) ==> det_empty_equal::<V>(r1, r2),
{
    if g___r1_1____is_init___is_true { assume(((r1.1)@).is_init() == true); }
    if g___r1_1____is_init___is_false { assume(((r1.1)@).is_init() == false); }
    if g___r2_1____is_init___is_true { assume(((r2.1)@).is_init() == true); }
    if g___r2_1____is_init___is_false { assume(((r2.1)@).is_init() == false); }
    if g_neq_tuple { assume(!det_empty_equal::<V>(r1, r2)); }
}

}

fn main() {}
