#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_map::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_is_empty_equal(r1: bool, r2: bool) -> bool {
    (r1 == r2)
}

proof fn det_is_empty<Key, Value>(g_r1_is_true: bool, g_r1_is_false: bool, g_r2_is_true: bool, g_r2_is_false: bool, g_neq_tuple: bool, self_: &HashMapWithView<Key, Value>, r1: bool, r2: bool)
    where Key: View + Eq + Hash
    ensures
        ({
            &&& (r1 == self_@.is_empty())
            &&& (r2 == self_@.is_empty())
        }) ==> det_is_empty_equal(r1, r2),
{
    if g_r1_is_true { assume(r1 == true); }
    if g_r1_is_false { assume(r1 == false); }
    if g_r2_is_true { assume(r2 == true); }
    if g_r2_is_false { assume(r2 == false); }
    if g_neq_tuple { assume(!det_is_empty_equal(r1, r2)); }
}
}

fn main() {}
