#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::proph::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_resolve_equal(r1: (), r2: ()) -> bool {
    (r1 == r2)
}

proof fn det_resolve<T>(g_neq_tuple: bool, self_: Prophecy<T>, v: &T, r1: (), r2: ())
    where T: Structural
    ensures
        ({
            &&& (self_@ == v)
            &&& (self_@ == v)
        }) ==> det_resolve_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_resolve_equal(r1, r2)); }
}
}

fn main() {}
