#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_map::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_remove_equal<Value>(r1: (), r2: (), post1_self_: StringHashMap<Value>, post2_self_: StringHashMap<Value>) -> bool {
    (r1 == r2)
    && (((post1_self_).view() =~= (post2_self_).view()))
}

proof fn det_remove<Value>(g_k_eq_empty: bool, g_k_eq_string_1: bool, g_k_eq_string_2: bool, g_neq_tuple: bool, pre_self_: StringHashMap<Value>, k: &str, post1_self_: StringHashMap<Value>, r1: (), post2_self_: StringHashMap<Value>, r2: ())
    ensures
        ({
            &&& (post1_self_@ == pre_self_@.remove(k@))
            &&& (post2_self_@ == pre_self_@.remove(k@))
        }) ==> det_remove_equal::<Value>(r1, r2, post1_self_, post2_self_),
{
    if g_k_eq_empty { assume(k@ == ""@); }
    if g_k_eq_string_1 { assume(k@ == "string 1"@); }
    if g_k_eq_string_2 { assume(k@ == "string 2"@); }
    if g_neq_tuple { assume(!det_remove_equal(r1, r2, post1_self_, post2_self_)); }
}
}

fn main() {}
