#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::raw_ptr::*;

use vstd::layout::*;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_expose_provenance_equal(r1: Tracked<IsExposed>, r2: Tracked<IsExposed>) -> bool {
    ((r1)@@ == (r2)@@)
}

proof fn det_expose_provenance<T: Sized>(g_neq_tuple: bool, m: *mut T, r1: Tracked<IsExposed>, r2: Tracked<IsExposed>)
    ensures
        ({
            &&& (r1@@ == m@.provenance)
            &&& (r2@@ == m@.provenance)
        }) ==> det_expose_provenance_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_expose_provenance_equal(r1, r2)); }
}
}

fn main() {}
