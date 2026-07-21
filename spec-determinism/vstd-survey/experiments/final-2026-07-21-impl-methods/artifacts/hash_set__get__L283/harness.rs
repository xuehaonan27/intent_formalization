#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_set::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_get_equal<'a>(r1: Option<&'a String>, r2: Option<&'a String>) -> bool {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> ((r1->Some_0)@ == (r2->Some_0)@)))
}

proof fn det_get<'a>(g_k_eq_empty: bool, g_k_eq_string_1: bool, g_k_eq_string_2: bool, g_r1_is_Some: bool, g_r1__Some_0_eq_empty: bool, g_r1__Some_0_eq_string_1: bool, g_r1__Some_0_eq_string_2: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2__Some_0_eq_empty: bool, g_r2__Some_0_eq_string_1: bool, g_r2__Some_0_eq_string_2: bool, g_r2_is_None: bool, g_neq_tuple: bool, self_: &StringHashSet, k: &str, r1: Option<&'a String>, r2: Option<&'a String>)
    ensures
        ({
            &&& (match r1 {
                Some(v) => self_@.contains(k@) && v@ == k@,
                None => !self_@.contains(k@),
            })
            &&& (match r2 {
                Some(v) => self_@.contains(k@) && v@ == k@,
                None => !self_@.contains(k@),
            })
        }) ==> det_get_equal(r1, r2),
{
    if g_k_eq_empty { assume(k@ == ""@); }
    if g_k_eq_string_1 { assume(k@ == "string 1"@); }
    if g_k_eq_string_2 { assume(k@ == "string 2"@); }
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1__Some_0_eq_empty { assume(r1 is Some); assume(r1->Some_0@ == ""@); }
    if g_r1__Some_0_eq_string_1 { assume(r1 is Some); assume(r1->Some_0@ == "string 1"@); }
    if g_r1__Some_0_eq_string_2 { assume(r1 is Some); assume(r1->Some_0@ == "string 2"@); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2__Some_0_eq_empty { assume(r2 is Some); assume(r2->Some_0@ == ""@); }
    if g_r2__Some_0_eq_string_1 { assume(r2 is Some); assume(r2->Some_0@ == "string 1"@); }
    if g_r2__Some_0_eq_string_2 { assume(r2 is Some); assume(r2->Some_0@ == "string 2"@); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_get_equal(r1, r2)); }
}
}

fn main() {}
