#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::simple_pptr::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal<V>(r1: (PPtr<V>, Tracked<PointsTo<V>>), r2: (PPtr<V>, Tracked<PointsTo<V>>)) -> bool {
    ((r1.0 == r2.0) && ((((r1.1)@).is_init() == ((r2.1)@).is_init()) && (((r1.1)@).pptr().addr() == ((r2.1)@).pptr().addr()) && (((r1.1)@).is_init() ==> (((r1.1)@).value() == ((r2.1)@).value()))))
}

proof fn det_new<V>(g___r1_1____is_init___is_true: bool, g___r1_1____is_init___is_false: bool, g___r1_1____ptr___addr___eq: bool, k___r1_1____ptr___addr___eq: int, g___r1_1____ptr___addr___rng: bool, k___r1_1____ptr___addr___rng_lo: int, k___r1_1____ptr___addr___rng_hi: int, g___r2_1____is_init___is_true: bool, g___r2_1____is_init___is_false: bool, g___r2_1____ptr___addr___eq: bool, k___r2_1____ptr___addr___eq: int, g___r2_1____ptr___addr___rng: bool, k___r2_1____ptr___addr___rng_lo: int, k___r2_1____ptr___addr___rng_hi: int, g_neq_tuple: bool, v: V, r1: (PPtr<V>, Tracked<PointsTo<V>>), r2: (PPtr<V>, Tracked<PointsTo<V>>))
    ensures
        ({
            &&& (r1.1@.pptr() == r1.0)
            &&& (r1.1@.mem_contents() == MemContents::Init(v))
            &&& (r2.1@.pptr() == r2.0)
            &&& (r2.1@.mem_contents() == MemContents::Init(v))
        }) ==> det_new_equal::<V>(r1, r2),
{
    if g___r1_1____is_init___is_true { assume(((r1.1)@).is_init() == true); }
    if g___r1_1____is_init___is_false { assume(((r1.1)@).is_init() == false); }
    if g___r1_1____ptr___addr___eq { assume(((r1.1)@).pptr().addr() as int == k___r1_1____ptr___addr___eq); }
    if g___r1_1____ptr___addr___rng { assume(((r1.1)@).pptr().addr() as int >= k___r1_1____ptr___addr___rng_lo && ((r1.1)@).pptr().addr() as int <= k___r1_1____ptr___addr___rng_hi); }
    if g___r2_1____is_init___is_true { assume(((r2.1)@).is_init() == true); }
    if g___r2_1____is_init___is_false { assume(((r2.1)@).is_init() == false); }
    if g___r2_1____ptr___addr___eq { assume(((r2.1)@).pptr().addr() as int == k___r2_1____ptr___addr___eq); }
    if g___r2_1____ptr___addr___rng { assume(((r2.1)@).pptr().addr() as int >= k___r2_1____ptr___addr___rng_lo && ((r2.1)@).pptr().addr() as int <= k___r2_1____ptr___addr___rng_hi); }
    if g_neq_tuple { assume(!det_new_equal::<V>(r1, r2)); }
}
}

fn main() {}
