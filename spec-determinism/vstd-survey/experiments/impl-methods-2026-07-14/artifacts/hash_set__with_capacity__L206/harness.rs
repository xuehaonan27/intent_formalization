#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_set::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_with_capacity_equal(r1: StringHashSet, r2: StringHashSet) -> bool {
    (((r1).view() =~= (r2).view()))
}

proof fn det_with_capacity(g_capacity_eq: bool, k_capacity_eq: int, g_capacity_rng: bool, k_capacity_rng_lo: int, k_capacity_rng_hi: int, g_neq_tuple: bool, capacity: usize, r1: StringHashSet, r2: StringHashSet)
    ensures
        ({
            &&& (r1@ == Set::<Seq<char>>::empty())
            &&& (r2@ == Set::<Seq<char>>::empty())
        }) ==> det_with_capacity_equal(r1, r2),
{
    if g_capacity_eq { assume(capacity as int == k_capacity_eq); }
    if g_capacity_rng { assume(capacity as int >= k_capacity_rng_lo && capacity as int <= k_capacity_rng_hi); }
    if g_neq_tuple { assume(!det_with_capacity_equal(r1, r2)); }
}
}

fn main() {}
