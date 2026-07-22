#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::pcell_maybe_uninit::*;

use vstd::raw_ptr::MemContents;

verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_read_equal<V>(r1: V, r2: V) -> bool
    where V: Copy {
    (r1 == r2)
}

proof fn det_read<V>(g__perm__is_init___is_true: bool, g__perm__is_init___is_false: bool, g__perm__ptr___addr___eq: bool, k__perm__ptr___addr___eq: int, g__perm__ptr___addr___rng: bool, k__perm__ptr___addr___rng_lo: int, k__perm__ptr___addr___rng_hi: int, g_neq_tuple: bool, self_: &PCell<V>, perm: &PointsTo<V>, r1: V, r2: V)
    where V: Copy
    requires (self_.id() == perm.id()), (perm.is_init()),
    ensures
        ({
            &&& (r1 == perm.value())
            &&& (r2 == perm.value())
        }) ==> det_read_equal::<V>(r1, r2),
{
    if g__perm__is_init___is_true { assume((perm).is_init() == true); }
    if g__perm__is_init___is_false { assume((perm).is_init() == false); }
    if g_neq_tuple { assume(!det_read_equal::<V>(r1, r2)); }
}

}

fn main() {}
