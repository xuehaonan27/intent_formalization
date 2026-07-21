#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::std_specs::iter::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_next_equal<'a, I: Iterator>(r1: Option<I::Item>, r2: Option<I::Item>, post1_self_: VerusForLoopWrapper<'a, I>, post2_self_: VerusForLoopWrapper<'a, I>) -> bool {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0)))
    && (post1_self_ == post2_self_)
}

proof fn det_next<'a, I: Iterator>(g_r1_is_Some: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2_is_None: bool, g_neq_tuple: bool, pre_self_: VerusForLoopWrapper<'a, I>, post1_self_: VerusForLoopWrapper<'a, I>, r1: Option<I::Item>, post2_self_: VerusForLoopWrapper<'a, I>, r2: Option<I::Item>)
    requires (pre_self_.wf()),
    ensures
        ({
            &&& (post1_self_.seq() == pre_self_.seq())
            &&& (post1_self_.index() == pre_self_.index() + if r1 is Some { 1int } else { 0 })
            &&& (post1_self_.snapshot == pre_self_.snapshot)
            &&& (post1_self_.init == pre_self_.init)
            &&& (post1_self_.iter.obeys_prophetic_iter_laws() ==> post1_self_.wf())
            &&& (post1_self_.iter.obeys_prophetic_iter_laws() && r1 is None ==>
                post1_self_.snapshot@.will_return_none() && post1_self_.index() == post1_self_.seq().len())
            &&& (post1_self_.iter.obeys_prophetic_iter_laws() ==> (r1 matches Some(r_1) ==>
                r_1 == pre_self_.seq()[pre_self_.index()]))
            &&& (r1 matches Some(i_1) ==> post1_self_.history@ == pre_self_.history@.push(i_1))
            &&& (r1 is None ==> post1_self_.history@ == pre_self_.history@)
            &&& (post1_self_.iter.obeys_prophetic_iter_laws() == pre_self_.iter.obeys_prophetic_iter_laws())
            &&& (post1_self_.iter.obeys_prophetic_iter_laws() ==> post1_self_.iter.will_return_none() == pre_self_.iter.will_return_none())
            &&& (post1_self_.iter.obeys_prophetic_iter_laws() ==> (pre_self_.iter.decrease() is Some <==> post1_self_.iter.decrease() is Some))
            &&& (post1_self_.iter.obeys_prophetic_iter_laws() ==>
            ({
                if pre_self_.iter.remaining().len() > 0 {
                    &&& post1_self_.iter.remaining() == pre_self_.iter.remaining().drop_first()
                    &&& r1 == Some(pre_self_.iter.remaining()[0])
                } else {
                    post1_self_.iter.remaining() == pre_self_.iter.remaining() && r1 == None && post1_self_.iter.will_return_none()
                }
            }))
            &&& (post1_self_.iter.obeys_prophetic_iter_laws() && pre_self_.iter.remaining().len() > 0 && post1_self_.iter.decrease() is Some ==>
                decreases_to!(pre_self_.iter.decrease()->0 => post1_self_.iter.decrease()->0))
            &&& (post2_self_.seq() == pre_self_.seq())
            &&& (post2_self_.index() == pre_self_.index() + if r2 is Some { 1int } else { 0 })
            &&& (post2_self_.snapshot == pre_self_.snapshot)
            &&& (post2_self_.init == pre_self_.init)
            &&& (post2_self_.iter.obeys_prophetic_iter_laws() ==> post2_self_.wf())
            &&& (post2_self_.iter.obeys_prophetic_iter_laws() && r2 is None ==>
                post2_self_.snapshot@.will_return_none() && post2_self_.index() == post2_self_.seq().len())
            &&& (post2_self_.iter.obeys_prophetic_iter_laws() ==> (r2 matches Some(r_2) ==>
                r_2 == pre_self_.seq()[pre_self_.index()]))
            &&& (r2 matches Some(i_2) ==> post2_self_.history@ == pre_self_.history@.push(i_2))
            &&& (r2 is None ==> post2_self_.history@ == pre_self_.history@)
            &&& (post2_self_.iter.obeys_prophetic_iter_laws() == pre_self_.iter.obeys_prophetic_iter_laws())
            &&& (post2_self_.iter.obeys_prophetic_iter_laws() ==> post2_self_.iter.will_return_none() == pre_self_.iter.will_return_none())
            &&& (post2_self_.iter.obeys_prophetic_iter_laws() ==> (pre_self_.iter.decrease() is Some <==> post2_self_.iter.decrease() is Some))
            &&& (post2_self_.iter.obeys_prophetic_iter_laws() ==>
            ({
                if pre_self_.iter.remaining().len() > 0 {
                    &&& post2_self_.iter.remaining() == pre_self_.iter.remaining().drop_first()
                    &&& r2 == Some(pre_self_.iter.remaining()[0])
                } else {
                    post2_self_.iter.remaining() == pre_self_.iter.remaining() && r2 == None && post2_self_.iter.will_return_none()
                }
            }))
            &&& (post2_self_.iter.obeys_prophetic_iter_laws() && pre_self_.iter.remaining().len() > 0 && post2_self_.iter.decrease() is Some ==>
                decreases_to!(pre_self_.iter.decrease()->0 => post2_self_.iter.decrease()->0))
        }) ==> det_next_equal::<I>(r1, r2, post1_self_, post2_self_),
{
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_next_equal::<I>(r1, r2, post1_self_, post2_self_)); }
}
}

fn main() {}
