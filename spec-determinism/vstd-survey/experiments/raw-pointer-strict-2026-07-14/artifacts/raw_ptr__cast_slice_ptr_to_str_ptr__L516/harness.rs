#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_cast_slice_ptr_to_str_ptr_equal(r1: *mut str, r2: *mut str) -> bool {
    (r1 == r2)
}

proof fn det_cast_slice_ptr_to_str_ptr<T>(g_neq_tuple: bool, ptr: *mut [T], r1: *mut str, r2: *mut str)
    ensures
        ({
            &&& (r1 == spec_cast_slice_ptr_to_str_ptr::<T>(ptr))
            &&& (r2 == spec_cast_slice_ptr_to_str_ptr::<T>(ptr))
        }) ==> det_cast_slice_ptr_to_str_ptr_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_cast_slice_ptr_to_str_ptr_equal(r1, r2)); }
}
}

fn main() {}
