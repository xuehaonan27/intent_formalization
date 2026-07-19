#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_set::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_reserve_equal<Key>(r1: (), r2: (), post1_self_: HashSetWithView<Key>, post2_self_: HashSetWithView<Key>) -> bool
    where Key: View + Eq + Hash {
    (r1 == r2)
    && (((post1_self_).view() =~= (post2_self_).view()))
}

proof fn det_reserve<Key>(g_additional_eq: bool, k_additional_eq: int, g_additional_rng: bool, k_additional_rng_lo: int, k_additional_rng_hi: int, g_neq_tuple: bool, pre_self_: HashSetWithView<Key>, additional: usize, post1_self_: HashSetWithView<Key>, r1: (), post2_self_: HashSetWithView<Key>, r2: ())
    where Key: View + Eq + Hash
    ensures
        ({
            &&& (post1_self_@ == pre_self_@)
            &&& (post2_self_@ == pre_self_@)
        }) ==> det_reserve_equal::<Key>(r1, r2, post1_self_, post2_self_),
{
    if g_additional_eq { assume(additional as int == k_additional_eq); }
    if g_additional_rng { assume(additional as int >= k_additional_rng_lo && additional as int <= k_additional_rng_hi); }
    if g_neq_tuple { assume(!det_reserve_equal::<Key>(r1, r2, post1_self_, post2_self_)); }
}
}

fn main() {}
