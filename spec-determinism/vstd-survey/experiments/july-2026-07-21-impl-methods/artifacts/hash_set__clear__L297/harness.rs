#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_set::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_clear_equal(r1: (), r2: (), post1_self_: StringHashSet, post2_self_: StringHashSet) -> bool {
    (r1 == r2)
    && (((post1_self_).view() =~= (post2_self_).view()))
}

proof fn det_clear(g_neq_tuple: bool, pre_self_: StringHashSet, post1_self_: StringHashSet, r1: (), post2_self_: StringHashSet, r2: ())
    ensures
        ({
            &&& (post1_self_@ == Set::<Seq<char>>::empty())
            &&& (post2_self_@ == Set::<Seq<char>>::empty())
        }) ==> det_clear_equal(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_clear_equal(r1, r2, post1_self_, post2_self_)); }
}
}

fn main() {}
