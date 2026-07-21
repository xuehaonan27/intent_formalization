#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::invcell::*;

use vstd::predicate::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal<T, Pred: Predicate<T>>(r1: InvCell<T, Pred>, r2: InvCell<T, Pred>) -> bool {
    (r1 == r2)
}

proof fn det_new<T, Pred: Predicate<T>>(g_neq_tuple: bool, val: T, pred: Pred, r1: InvCell<T, Pred>, r2: InvCell<T, Pred>)
    requires (pred.predicate(val)),
    ensures
        ({
            &&& (r1.predicate() == pred)
            &&& (r2.predicate() == pred)
        }) ==> det_new_equal::<T, Pred>(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal::<T, Pred>(r1, r2)); }
}

}

fn main() {}
