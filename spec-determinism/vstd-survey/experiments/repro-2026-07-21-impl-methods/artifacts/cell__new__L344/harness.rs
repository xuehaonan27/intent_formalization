#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal<T>(r1: InvCell<T>, r2: InvCell<T>) -> bool {
    (r1 == r2)
}

proof fn det_new<T>(g_neq_tuple: bool, val: T, f: spec_fn(T) -> bool, r1: InvCell<T>, r2: InvCell<T>)
    requires (f(val)),
    ensures
        ({
            &&& (forall|v| f(v) <==> r1.inv(v))
            &&& (forall|v| f(v) <==> r2.inv(v))
        }) ==> det_new_equal::<T>(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}

}

fn main() {}
