#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_set::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_get_equal<Key, 'a>(r1: Option<&'a Key>, r2: Option<&'a Key>) -> bool
    where Key: View + Eq + Hash {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> ((r1->Some_0)@ == (r2->Some_0)@)))
}

proof fn det_get<Key, 'a>(g_r1_is_Some: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2_is_None: bool, g_neq_tuple: bool, self_: &HashSetWithView<Key>, k: &Key, r1: Option<&'a Key>, r2: Option<&'a Key>)
    where Key: View + Eq + Hash
    ensures
        ({
            &&& (match r1 {
                Some(v) => self_@.contains(k@) && v == &k,
                None => !self_@.contains(k@),
            })
            &&& (match r2 {
                Some(v) => self_@.contains(k@) && v == &k,
                None => !self_@.contains(k@),
            })
        }) ==> det_get_equal::<Key>(r1, r2),
{
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_get_equal(r1, r2)); }
}
}

fn main() {}
