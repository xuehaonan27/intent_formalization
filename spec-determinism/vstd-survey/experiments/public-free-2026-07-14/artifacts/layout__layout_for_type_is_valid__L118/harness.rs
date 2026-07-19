#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::layout::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_layout_for_type_is_valid_equal(r1: (), r2: ()) -> bool {
    (r1 == r2)
}

proof fn det_layout_for_type_is_valid<V>(g_neq_tuple: bool, r1: (), r2: ())
    ensures
        ({
            &&& (valid_layout(size_of::<V>() as usize, align_of::<V>() as usize))
            &&& (size_of::<V>() as usize as nat == size_of::<V>())
            &&& (align_of::<V>() as usize as nat == align_of::<V>())
            &&& (align_of::<V>() != 0)
            &&& (size_of::<V>() % align_of::<V>() == 0)
            &&& (valid_layout(size_of::<V>() as usize, align_of::<V>() as usize))
            &&& (size_of::<V>() as usize as nat == size_of::<V>())
            &&& (align_of::<V>() as usize as nat == align_of::<V>())
            &&& (align_of::<V>() != 0)
            &&& (size_of::<V>() % align_of::<V>() == 0)
        }) ==> det_layout_for_type_is_valid_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_layout_for_type_is_valid_equal(r1, r2)); }
}
}

fn main() {}
