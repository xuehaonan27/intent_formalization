#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_map::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_clear_equal<Value>(r1: (), r2: (), post1_self_: StringHashMap<Value>, post2_self_: StringHashMap<Value>) -> bool {
    (r1 == r2)
    && (((post1_self_).view() =~= (post2_self_).view()))
}

proof fn det_clear<Value>(g_neq_tuple: bool, pre_self_: StringHashMap<Value>, post1_self_: StringHashMap<Value>, r1: (), post2_self_: StringHashMap<Value>, r2: ())
    ensures
        ({
            &&& (post1_self_@ == Map::<Seq<char>, Value>::empty())
            &&& (post2_self_@ == Map::<Seq<char>, Value>::empty())
        }) ==> det_clear_equal::<Value>(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_clear_equal(r1, r2, post1_self_, post2_self_)); }
}
}

fn main() {}
