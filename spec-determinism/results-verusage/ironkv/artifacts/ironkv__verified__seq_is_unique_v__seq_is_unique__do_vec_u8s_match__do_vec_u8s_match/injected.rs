use vstd::prelude::*;

fn main() {}

verus! {

    pub fn do_vec_u8s_match(e1: &Vec<u8>, e2: &Vec<u8>) -> (eq: bool)
        ensures
            eq == (e1@ == e2@)
    {
        if e1.len() != e2.len() {
            assert (e1@.len() != e2@.len());
            assert (e1@ != e2@);
            return false;
        }

        let mut i: usize = 0;
        while i < e1.len()
            invariant
                0 <= i,
                i <= e1.len(),
                e1.len() == e2.len(),
                forall |j: int| 0 <= j && j < i ==> e1@[j] == e2@[j]
            decreases
                e1.len() - i
        {
            if e1[i] != e2[i] {
                return false;
            }
            i += 1;
        }
        proof {
            assert(e1@=~=e2@);
        }
        return true;
    }


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_do_vec_u8s_match_equal(r1: bool, r2: bool) -> bool {
    (r1 == r2)
}

proof fn det_do_vec_u8s_match(g_r1_is_true: bool, g_r1_is_false: bool, g_r2_is_true: bool, g_r2_is_false: bool, g_neq_tuple: bool, e1: Vec<u8>, e2: Vec<u8>, r1: bool, r2: bool)
    ensures
        ({
            &&& (r1 == (e1@ == e2@))
            &&& (r2 == (e1@ == e2@))
        }) ==> det_do_vec_u8s_match_equal(r1, r2),
{
    if g_r1_is_true { assume(r1 == true); }
    if g_r1_is_false { assume(r1 == false); }
    if g_r2_is_true { assume(r2 == true); }
    if g_r2_is_false { assume(r2 == false); }
    if g_neq_tuple { assume(!det_do_vec_u8s_match_equal(r1, r2)); }
}
// === END INJECTED ===

}
