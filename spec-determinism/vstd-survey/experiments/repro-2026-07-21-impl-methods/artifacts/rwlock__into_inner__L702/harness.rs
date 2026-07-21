#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::rwlock::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_into_inner_equal<V>(r1: V, r2: V) -> bool {
    (r1 == r2)
}

proof fn det_into_inner<V, Pred: RwLockPredicate<V>>(g_neq_tuple: bool, self_: RwLock<V, Pred>, r1: V, r2: V)
    ensures
        ({
            &&& (self_.inv(r1))
            &&& (self_.inv(r2))
        }) ==> det_into_inner_equal::<V>(r1, r2),
{
    if g_neq_tuple { assume(!det_into_inner_equal(r1, r2)); }
}
}

fn main() {}
