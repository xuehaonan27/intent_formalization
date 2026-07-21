#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_map::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_remove_equal<Key, Value>(r1: Option<Value>, r2: Option<Value>, post1_self_: HashMapWithView<Key, Value>, post2_self_: HashMapWithView<Key, Value>) -> bool
    where Key: View + Eq + Hash {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0)))
    && (((post1_self_).view() =~= (post2_self_).view()))
}

proof fn det_remove<Key, Value>(g_r1_is_Some: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2_is_None: bool, g_neq_tuple: bool, pre_self_: HashMapWithView<Key, Value>, k: &Key, post1_self_: HashMapWithView<Key, Value>, r1: Option<Value>, post2_self_: HashMapWithView<Key, Value>, r2: Option<Value>)
    where Key: View + Eq + Hash
    ensures
        ({
            &&& (match r1 {
                Some(v) => pre_self_@.contains_key(k@) && v == pre_self_@[k@] && post1_self_@
                    == pre_self_@.remove(k@),
                None => !pre_self_@.contains_key(k@) && post1_self_@ == pre_self_@,
            })
            &&& (match r2 {
                Some(v) => pre_self_@.contains_key(k@) && v == pre_self_@[k@] && post2_self_@
                    == pre_self_@.remove(k@),
                None => !pre_self_@.contains_key(k@) && post2_self_@ == pre_self_@,
            })
        }) ==> det_remove_equal::<Key, Value>(r1, r2, post1_self_, post2_self_),
{
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_remove_equal(r1, r2, post1_self_, post2_self_)); }
}
}

fn main() {}
