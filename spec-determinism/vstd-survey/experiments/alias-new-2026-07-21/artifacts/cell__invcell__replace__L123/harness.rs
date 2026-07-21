#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::invcell::*;

use vstd::predicate::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_replace_equal<T>(r1: T, r2: T) -> bool {
    (r1 == r2)
}

proof fn det_replace<T, Pred: Predicate<T>>(g_neq_tuple: bool, self_: &InvCell<T, Pred>, val: T, r1: T, r2: T)
    requires (self_.inv(val)),
    ensures
        ({
            &&& (self_.inv(r1))
            &&& (self_.inv(r2))
        }) ==> det_replace_equal::<T>(r1, r2),
{
    if g_neq_tuple { assume(!det_replace_equal::<T>(r1, r2)); }
}

}

fn main() {}
