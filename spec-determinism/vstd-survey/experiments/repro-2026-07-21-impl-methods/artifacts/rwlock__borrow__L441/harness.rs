#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::rwlock::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_borrow_equal<V>(r1: &V, r2: &V) -> bool {
    (r1 == r2)
}

proof fn det_borrow<'a, V, Pred: RwLockPredicate<V>>(g_neq_tuple: bool, self_: &ReadHandle<'a, V, Pred>, r1: &V, r2: &V)
    ensures
        ({
            &&& (r1 == self_.view())
            &&& (r2 == self_.view())
        }) ==> det_borrow_equal::<V>(r1, r2),
{
    if g_neq_tuple { assume(!det_borrow_equal(r1, r2)); }
}
}

fn main() {}
