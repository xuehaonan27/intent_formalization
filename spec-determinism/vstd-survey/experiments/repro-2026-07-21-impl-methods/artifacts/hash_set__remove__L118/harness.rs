#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_set::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_remove_equal<Key>(r1: bool, r2: bool, post1_self_: HashSetWithView<Key>, post2_self_: HashSetWithView<Key>) -> bool
    where Key: View + Eq + Hash {
    (r1 == r2)
    && (((post1_self_).view() =~= (post2_self_).view()))
}

proof fn det_remove<Key>(g_r1_is_true: bool, g_r1_is_false: bool, g_r2_is_true: bool, g_r2_is_false: bool, g_neq_tuple: bool, pre_self_: HashSetWithView<Key>, k: &Key, post1_self_: HashSetWithView<Key>, r1: bool, post2_self_: HashSetWithView<Key>, r2: bool)
    where Key: View + Eq + Hash
    ensures
        ({
            &&& (post1_self_@ == pre_self_@.remove(k@) && r1 == pre_self_@.contains(k@))
            &&& (post2_self_@ == pre_self_@.remove(k@) && r2 == pre_self_@.contains(k@))
        }) ==> det_remove_equal::<Key>(r1, r2, post1_self_, post2_self_),
{
    if g_r1_is_true { assume(r1 == true); }
    if g_r1_is_false { assume(r1 == false); }
    if g_r2_is_true { assume(r2 == true); }
    if g_r2_is_false { assume(r2 == false); }
    if g_neq_tuple { assume(!det_remove_equal(r1, r2, post1_self_, post2_self_)); }
}
}

fn main() {}
