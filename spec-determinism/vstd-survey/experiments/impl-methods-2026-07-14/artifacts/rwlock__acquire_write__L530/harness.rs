#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::rwlock::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_acquire_write_equal<V, Pred: RwLockPredicate<V>>(r1: (V, WriteHandle<'_, V, Pred>), r2: (V, WriteHandle<'_, V, Pred>)) -> bool {
    ((r1.0 == r2.0) && (r1.1 == r2.1))
}

proof fn det_acquire_write<V, Pred: RwLockPredicate<V>>(g_neq_tuple: bool, self_: &RwLock<V, Pred>, r1: (V, WriteHandle<'_, V, Pred>), r2: (V, WriteHandle<'_, V, Pred>))
    ensures
        ({
            &&& (({
                let val = r1.0;
                let write_handle = r1.1;
                &&& write_handle.rwlock() == *self_
                &&& self_.inv(val)
            }))
            &&& (({
                let val = r2.0;
                let write_handle = r2.1;
                &&& write_handle.rwlock() == *self_
                &&& self_.inv(val)
            }))
        }) ==> det_acquire_write_equal::<V, Pred>(r1, r2),
{
    if g_neq_tuple { assume(!det_acquire_write_equal::<V, Pred>(r1, r2)); }
}
}

fn main() {}
