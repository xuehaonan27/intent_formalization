#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_cast_ptr_to_thin_ptr_equal<U: Sized>(r1: *mut U, r2: *mut U) -> bool {
    (r1 == r2)
}

proof fn det_cast_ptr_to_thin_ptr<T: ?Sized, U: Sized>(g_neq_tuple: bool, ptr: *mut T, r1: *mut U, r2: *mut U)
    ensures
        ({
            &&& (r1 == spec_cast_ptr_to_thin_ptr::<T, U>(ptr))
            &&& (r2 == spec_cast_ptr_to_thin_ptr::<T, U>(ptr))
        }) ==> det_cast_ptr_to_thin_ptr_equal::<U>(r1, r2),
{
    if g_neq_tuple { assume(!det_cast_ptr_to_thin_ptr_equal::<U>(r1, r2)); }
}
}

fn main() {}
