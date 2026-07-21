#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::std_specs::iter::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal<'a, I: Iterator>(r1: VerusForLoopWrapper<'a, I>, r2: VerusForLoopWrapper<'a, I>) -> bool {
    (r1 == r2)
}

proof fn det_new<'a, I: Iterator>(g__init___is_Some: bool, g__init___is_None: bool, g_neq_tuple: bool, iter: I, init: Ghost<Option<&'a I>>, r1: VerusForLoopWrapper<'a, I>, r2: VerusForLoopWrapper<'a, I>)
    requires (init@ matches Some(i) ==> iter.initial_value_relation(i)),
    ensures
        ({
            &&& (r1.index == 0)
            &&& (r1.snapshot == iter)
            &&& (r1.init == init)
            &&& (r1.iter == iter)
            &&& (r1.history@ == Seq::<I::Item>::empty())
            &&& (r1.wf())
            &&& (r2.index == 0)
            &&& (r2.snapshot == iter)
            &&& (r2.init == init)
            &&& (r2.iter == iter)
            &&& (r2.history@ == Seq::<I::Item>::empty())
            &&& (r2.wf())
        }) ==> det_new_equal::<I>(r1, r2),
{
    if g__init___is_Some { assume((init)@ is Some); }
    if g__init___is_None { assume((init)@ is None); }
    if g_neq_tuple { assume(!det_new_equal::<I>(r1, r2)); }
}
}

fn main() {}
