#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_set::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_clear_equal<Key>(r1: (), r2: (), post1_self_: HashSetWithView<Key>, post2_self_: HashSetWithView<Key>) -> bool
    where Key: View + Eq + Hash {
    (r1 == r2)
    && (((post1_self_).view() =~= (post2_self_).view()))
}

proof fn det_clear<Key>(g_neq_tuple: bool, pre_self_: HashSetWithView<Key>, post1_self_: HashSetWithView<Key>, r1: (), post2_self_: HashSetWithView<Key>, r2: ())
    where Key: View + Eq + Hash
    ensures
        ({
            &&& (post1_self_@ == Set::<<Key as View>::V>::empty())
            &&& (post2_self_@ == Set::<<Key as View>::V>::empty())
        }) ==> det_clear_equal::<Key>(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_clear_equal::<Key>(r1, r2, post1_self_, post2_self_)); }
}
}

fn main() {}
