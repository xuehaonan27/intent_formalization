#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::rwlock::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_acquire_read_equal<V, Pred: RwLockPredicate<V>>(r1: ReadHandle<'_, V, Pred>, r2: ReadHandle<'_, V, Pred>) -> bool {
    (r1 == r2)
}

proof fn det_acquire_read<V, Pred: RwLockPredicate<V>>(g_neq_tuple: bool, self_: &RwLock<V, Pred>, r1: ReadHandle<'_, V, Pred>, r2: ReadHandle<'_, V, Pred>)
    ensures
        ({
            &&& (r1.rwlock() == *self_)
            &&& (self_.inv(r1.view()))
            &&& (r2.rwlock() == *self_)
            &&& (self_.inv(r2.view()))
        }) ==> det_acquire_read_equal::<V, Pred>(r1, r2),
{
    if g_neq_tuple { assume(!det_acquire_read_equal::<V, Pred>(r1, r2)); }
}
}

fn main() {}
