#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_set::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal<Key>(r1: HashSetWithView<Key>, r2: HashSetWithView<Key>) -> bool
    where Key: View + Eq + Hash {
    (((r1).view() =~= (r2).view()))
}

proof fn det_new<Key>(g_neq_tuple: bool, r1: HashSetWithView<Key>, r2: HashSetWithView<Key>)
    where Key: View + Eq + Hash
    requires (obeys_key_model::<Key>()), (forall|k1: Key, k2: Key| k1@ == k2@ ==> k1 == k2),
    ensures
        ({
            &&& (r1@ == Set::<<Key as View>::V>::empty())
            &&& (r2@ == Set::<<Key as View>::V>::empty())
        }) ==> det_new_equal::<Key>(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}
}

fn main() {}
