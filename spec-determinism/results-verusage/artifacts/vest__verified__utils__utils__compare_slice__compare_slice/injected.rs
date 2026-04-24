use vstd::prelude::*;
use vstd::slice::slice_index_get;

fn main() {}

verus!{

// File: src/utils.rs
pub fn compare_slice<'a, 'b>(x: &'a [u8], y: &'a [u8]) -> (res: bool)
    ensures
        res == (x@ =~= y@),
{
    if x.len() != y.len() {
        assert(x@.len() != y@.len());
        return false;
    }
    for i in 0..x.len()
        invariant
            0 <= i <= x.len(),
            x.len() == y.len(),
            forall|j: int| 0 <= j < i ==> x@[j] == y@[j],
    {
        if slice_index_get(x, i) != slice_index_get(y, i) {
            assert(x@[i as int] != y@[i as int]);
            return false;
        }
    }
    proof {
        assert(x@ =~= y@);
    }
    true
}



// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_compare_slice_equal(r1: bool, r2: bool) -> bool {
    (r1 == r2)
}

proof fn det_compare_slice(g_r1_is_true: bool, g_r1_is_false: bool, g_r2_is_true: bool, g_r2_is_false: bool, g_neq_tuple: bool, x: &[u8], y: &[u8], r1: bool, r2: bool)
    ensures
        ({
            &&& (r1 == (x@ =~= y@))
            &&& (r2 == (x@ =~= y@))
        }) ==> det_compare_slice_equal(r1, r2),
{
    if g_r1_is_true { assume(r1 == true); }
    if g_r1_is_false { assume(r1 == false); }
    if g_r2_is_true { assume(r2 == true); }
    if g_r2_is_false { assume(r2 == false); }
    if g_neq_tuple { assume(!det_compare_slice_equal(r1, r2)); }
}
// === END INJECTED ===

}
