#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::layout::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_layout_for_val_is_valid_equal(r1: (), r2: ()) -> bool {
    (r1 == r2)
}

proof fn det_layout_for_val_is_valid<V: ?Sized>(g_neq_tuple: bool, val: Tracked<&V>, r1: (), r2: ())
    ensures
        ({
            &&& (valid_layout(spec_size_of_val::<V>(val@) as usize, spec_align_of_val::<V>(val@) as usize))
            &&& (spec_size_of_val::<V>(val@) as usize as nat == spec_size_of_val::<V>(val@))
            &&& (spec_align_of_val::<V>(val@) as usize as nat == spec_align_of_val::<V>(val@))
            &&& (spec_align_of_val::<V>(val@) != 0)
            &&& (spec_size_of_val::<V>(val@) % spec_align_of_val::<V>(val@) == 0)
            &&& (valid_layout(spec_size_of_val::<V>(val@) as usize, spec_align_of_val::<V>(val@) as usize))
            &&& (spec_size_of_val::<V>(val@) as usize as nat == spec_size_of_val::<V>(val@))
            &&& (spec_align_of_val::<V>(val@) as usize as nat == spec_align_of_val::<V>(val@))
            &&& (spec_align_of_val::<V>(val@) != 0)
            &&& (spec_size_of_val::<V>(val@) % spec_align_of_val::<V>(val@) == 0)
        }) ==> det_layout_for_val_is_valid_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_layout_for_val_is_valid_equal(r1, r2)); }
}
}

fn main() {}
