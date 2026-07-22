#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::*;


verus! {
spec fn det_new_equal<V>(r1: (PCell<V>, Tracked<PointsTo<V>>), r2: (PCell<V>, Tracked<PointsTo<V>>)) -> bool {
    (((r1.1)@).is_init() == ((r2.1)@).is_init())
    && (((r1.1)@).is_init() ==> (((r1.1)@).value() == ((r2.1)@).value()))
}


proof fn det_new<V>(g___r1_1____is_init___is_true: bool, g___r1_1____is_init___is_false: bool, g___r1_1____ptr___addr___eq: bool, k___r1_1____ptr___addr___eq: int, g___r1_1____ptr___addr___rng: bool, k___r1_1____ptr___addr___rng_lo: int, k___r1_1____ptr___addr___rng_hi: int, g___r2_1____is_init___is_true: bool, g___r2_1____is_init___is_false: bool, g___r2_1____ptr___addr___eq: bool, k___r2_1____ptr___addr___eq: int, g___r2_1____ptr___addr___rng: bool, k___r2_1____ptr___addr___rng_lo: int, k___r2_1____ptr___addr___rng_hi: int, g_neq_tuple: bool, v: V, r1: (PCell<V>, Tracked<PointsTo<V>>), r2: (PCell<V>, Tracked<PointsTo<V>>))
    ensures
        ({
            &&& (r1.1@@ == pcell_points! [ r1.0.id() => MemContents::Init(v) ])
            &&& (r2.1@@ == pcell_points! [ r2.0.id() => MemContents::Init(v) ])
        }) ==> det_new_equal::<V>(r1, r2),
{
    if g___r1_1____is_init___is_true { assume(((r1.1)@).is_init() == true); }
    if g___r1_1____is_init___is_false { assume(((r1.1)@).is_init() == false); }
    if g___r2_1____is_init___is_true { assume(((r2.1)@).is_init() == true); }
    if g___r2_1____is_init___is_false { assume(((r2.1)@).is_init() == false); }
    if g_neq_tuple { assume(!det_new_equal::<V>(r1, r2)); }
}

}

fn main() {}
