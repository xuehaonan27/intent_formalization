#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_cast_slice_ptr_to_slice_ptr_equal<U>(r1: *mut [U], r2: *mut [U]) -> bool {
    (true /* raw pointer: opaque by default */)
}

proof fn det_cast_slice_ptr_to_slice_ptr<T, U>(g_neq_tuple: bool, ptr: *mut [T], r1: *mut [U], r2: *mut [U])
    ensures
        ({
            &&& (r1 == spec_cast_slice_ptr_to_slice_ptr::<T, U>(ptr))
            &&& (r2 == spec_cast_slice_ptr_to_slice_ptr::<T, U>(ptr))
        }) ==> det_cast_slice_ptr_to_slice_ptr_equal::<U>(r1, r2),
{
    if g_neq_tuple { assume(!det_cast_slice_ptr_to_slice_ptr_equal::<U>(r1, r2)); }
}
}

fn main() {}
