#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_cast_str_ptr_to_slice_ptr_equal<T>(r1: *mut [T], r2: *mut [T]) -> bool {
    (r1 == r2)
}

proof fn det_cast_str_ptr_to_slice_ptr<T>(g_neq_tuple: bool, ptr: *mut str, r1: *mut [T], r2: *mut [T])
    ensures
        ({
            &&& (r1 == spec_cast_str_ptr_to_slice_ptr::<T>(ptr))
            &&& (r2 == spec_cast_str_ptr_to_slice_ptr::<T>(ptr))
        }) ==> det_cast_str_ptr_to_slice_ptr_equal::<T>(r1, r2),
{
    if g_neq_tuple { assume(!det_cast_str_ptr_to_slice_ptr_equal(r1, r2)); }
}
}

fn main() {}
