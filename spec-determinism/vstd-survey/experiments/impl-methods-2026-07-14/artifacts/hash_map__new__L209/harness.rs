#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_map::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal<Value>(r1: StringHashMap<Value>, r2: StringHashMap<Value>) -> bool {
    (((r1).view() =~= (r2).view()))
}

proof fn det_new<Value>(g_neq_tuple: bool, r1: StringHashMap<Value>, r2: StringHashMap<Value>)
    ensures
        ({
            &&& (r1@ == Map::<Seq<char>, Value>::empty())
            &&& (r2@ == Map::<Seq<char>, Value>::empty())
        }) ==> det_new_equal::<Value>(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal::<Value>(r1, r2)); }
}
}

fn main() {}
