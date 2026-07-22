#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_map::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_with_capacity_equal<Key, Value>(r1: HashMapWithView<Key, Value>, r2: HashMapWithView<Key, Value>) -> bool
    where Key: View + Eq + Hash {
    (((r1).view() =~= (r2).view()))
}

proof fn det_with_capacity<Key, Value>(g_capacity_eq: bool, k_capacity_eq: int, g_capacity_rng: bool, k_capacity_rng_lo: int, k_capacity_rng_hi: int, g_neq_tuple: bool, capacity: usize, r1: HashMapWithView<Key, Value>, r2: HashMapWithView<Key, Value>)
    where Key: View + Eq + Hash
    requires (obeys_key_model::<Key>()), (forall|k1: Key, k2: Key| k1@ == k2@ ==> k1 == k2),
    ensures
        ({
            &&& (r1@ == Map::<<Key as View>::V, Value>::empty())
            &&& (r2@ == Map::<<Key as View>::V, Value>::empty())
        }) ==> det_with_capacity_equal::<Key, Value>(r1, r2),
{
    if g_capacity_eq { assume(capacity as int == k_capacity_eq); }
    if g_capacity_rng { assume(capacity as int >= k_capacity_rng_lo && capacity as int <= k_capacity_rng_hi); }
    if g_neq_tuple { assume(!det_with_capacity_equal::<Key, Value>(r1, r2)); }
}
}

fn main() {}
