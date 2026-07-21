#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::thread::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_join_equal<Ret>(r1: Result<Ret, ()>, r2: Result<Ret, ()>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> (r1->Ok_0 == r2->Ok_0)))
}

proof fn det_join<Ret>(g_r1_is_Ok: bool, g_r1_is_Err: bool, g_r2_is_Ok: bool, g_r2_is_Err: bool, g_neq_tuple: bool, self_: JoinHandle<Ret>, r1: Result<Ret, ()>, r2: Result<Ret, ()>)
    ensures
        ({
            &&& (match r1 {
                Result::Ok(r) => self_.predicate(r),
                Result::Err(_) => true,
            })
            &&& (match r2 {
                Result::Ok(r) => self_.predicate(r),
                Result::Err(_) => true,
            })
        }) ==> det_join_equal::<Ret>(r1, r2),
{
    if g_r1_is_Ok { assume(r1 is Ok); }
    if g_r1_is_Err { assume(r1 is Err); }
    if g_r2_is_Ok { assume(r2 is Ok); }
    if g_r2_is_Err { assume(r2 is Err); }
    if g_neq_tuple { assume(!det_join_equal(r1, r2)); }
}
}

fn main() {}
