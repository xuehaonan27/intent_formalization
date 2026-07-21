#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::float::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_float_cast_equal<To>(r1: To, r2: To) -> bool {
    (r1 == r2)
}

proof fn det_float_cast<From: Copy + IeeeFloatCast<To>, To>(g_neq_tuple: bool, from: From, r1: To, r2: To)
    ensures
        ({
            &&& (float_cast_spec(from, r1))
            &&& (float_cast_spec(from, r2))
        }) ==> det_float_cast_equal::<To>(r1, r2),
{
    if g_neq_tuple { assume(!det_float_cast_equal(r1, r2)); }
}
}

fn main() {}
