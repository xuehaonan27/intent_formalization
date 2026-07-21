#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_map::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_insert_equal<Key, Value>(r1: (), r2: (), post1_self_: HashMapWithView<Key, Value>, post2_self_: HashMapWithView<Key, Value>) -> bool
    where Key: View + Eq + Hash {
    (r1 == r2)
    && (((post1_self_).view() =~= (post2_self_).view()))
}

proof fn det_insert<Key, Value>(g_neq_tuple: bool, pre_self_: HashMapWithView<Key, Value>, k: Key, v: Value, post1_self_: HashMapWithView<Key, Value>, r1: (), post2_self_: HashMapWithView<Key, Value>, r2: ())
    where Key: View + Eq + Hash
    ensures
        ({
            &&& (post1_self_@ == pre_self_@.insert(k@, v))
            &&& (post2_self_@ == pre_self_@.insert(k@, v))
        }) ==> det_insert_equal::<Key, Value>(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_insert_equal::<Key, Value>(r1, r2, post1_self_, post2_self_)); }
}
}

fn main() {}
