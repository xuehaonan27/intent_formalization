#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::invcell::*;

use vstd::predicate::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_into_inner_equal<T>(r1: T, r2: T) -> bool {
    (r1 == r2)
}

proof fn det_into_inner<T, Pred: Predicate<T>>(g_neq_tuple: bool, self_: InvCell<T, Pred>, r1: T, r2: T)
    ensures
        ({
            &&& (self_.inv(r1))
            &&& (self_.inv(r2))
        }) ==> det_into_inner_equal::<T>(r1, r2),
{
    if g_neq_tuple { assume(!det_into_inner_equal::<T>(r1, r2)); }
}

}

fn main() {}
