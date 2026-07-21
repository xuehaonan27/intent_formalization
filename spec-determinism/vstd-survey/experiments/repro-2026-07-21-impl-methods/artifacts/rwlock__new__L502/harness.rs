#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::rwlock::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal<V, Pred: RwLockPredicate<V>>(r1: RwLock<V, Pred>, r2: RwLock<V, Pred>) -> bool {
    (r1 == r2)
}

proof fn det_new<V, Pred: RwLockPredicate<V>>(g_neq_tuple: bool, val: V, pred: Pred, r1: RwLock<V, Pred>, r2: RwLock<V, Pred>)
    requires (pred.inv(val)),
    ensures
        ({
            &&& (r1.pred() == pred)
            &&& (r2.pred() == pred)
        }) ==> det_new_equal::<V, Pred>(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}
}

fn main() {}
