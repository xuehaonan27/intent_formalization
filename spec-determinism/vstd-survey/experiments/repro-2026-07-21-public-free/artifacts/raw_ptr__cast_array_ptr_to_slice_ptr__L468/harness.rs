#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_cast_array_ptr_to_slice_ptr_equal<T>(r1: *mut [T], r2: *mut [T]) -> bool {
    (true /* raw pointer: opaque by default */)
}

proof fn det_cast_array_ptr_to_slice_ptr<T, const N: usize>(g_neq_tuple: bool, ptr: *mut [T; N], r1: *mut [T], r2: *mut [T])
    ensures
        ({
            &&& (r1 == spec_cast_array_ptr_to_slice_ptr(ptr))
            &&& (r2 == spec_cast_array_ptr_to_slice_ptr(ptr))
        }) ==> det_cast_array_ptr_to_slice_ptr_equal::<T>(r1, r2),
{
    if g_neq_tuple { assume(!det_cast_array_ptr_to_slice_ptr_equal(r1, r2)); }
}
}

fn main() {}
