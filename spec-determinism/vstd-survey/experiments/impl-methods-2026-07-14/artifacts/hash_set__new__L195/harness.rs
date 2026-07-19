#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_set::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal(r1: StringHashSet, r2: StringHashSet) -> bool {
    (((r1).view() =~= (r2).view()))
}

proof fn det_new(g_neq_tuple: bool, r1: StringHashSet, r2: StringHashSet)
    ensures
        ({
            &&& (r1@ == Set::<Seq<char>>::empty())
            &&& (r2@ == Set::<Seq<char>>::empty())
        }) ==> det_new_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}
}

fn main() {}
