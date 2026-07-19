#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::hash_map::*;

use std::hash::Hash;
use vstd::std_specs::hash::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_get_equal<Value, 'a>(r1: Option<&'a Value>, r2: Option<&'a Value>) -> bool {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0)))
}

proof fn det_get<Value, 'a>(g_k_eq_empty: bool, g_k_eq_string_1: bool, g_k_eq_string_2: bool, g_r1_is_Some: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2_is_None: bool, g_neq_tuple: bool, self_: &StringHashMap<Value>, k: &str, r1: Option<&'a Value>, r2: Option<&'a Value>)
    ensures
        ({
            &&& (match r1 {
                Some(v) => self_@.contains_key(k@) && *v == self_@[k@],
                None => !self_@.contains_key(k@),
            })
            &&& (match r2 {
                Some(v) => self_@.contains_key(k@) && *v == self_@[k@],
                None => !self_@.contains_key(k@),
            })
        }) ==> det_get_equal::<Value>(r1, r2),
{
    if g_k_eq_empty { assume(k@ == ""@); }
    if g_k_eq_string_1 { assume(k@ == "string 1"@); }
    if g_k_eq_string_2 { assume(k@ == "string 2"@); }
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_get_equal::<Value>(r1, r2)); }
}
}

fn main() {}
