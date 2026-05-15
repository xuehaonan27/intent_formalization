use vstd::prelude::*;
use vstd::seq_lib::*;

fn main() {}

verus! {

pub fn vec_erase<A>(v: &mut Vec<A>, start: usize, end: usize)
    requires
        start <= end <= old(v).len(),
    ensures
        true,
        v@ == old(v)@.subrange(0, start as int) + old(v)@.subrange(end as int, old(v)@.len() as int),
{
    let mut deleted = 0;
    proof {
        assert_seqs_equal!(v@,
                           old(v)@.subrange(0, start as int) +
                           old(v)@.subrange(start as int + deleted as int,
                                               old(v)@.len() as int));
    }
    while deleted < end - start
        invariant
            start <= end <= old(v)@.len(),
            v@.len() == old(v)@.len() - deleted,
            0 <= deleted <= end - start,
            v@ == old(v)@.subrange(0, start as int) + old(v)@.subrange(start as int + deleted as int, old(v)@.len() as int),
        decreases
            end - start - deleted
    {
        v.remove(start);
        deleted = deleted + 1;
        proof {
            assert_seqs_equal!(v@,
                               old(v)@.subrange(0, start as int) +
                               old(v)@.subrange(start as int + deleted as int,
                                                   old(v)@.len() as int));
        }
    }
}


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_vec_erase_equal<A>(r1: (), r2: (), post1_v: Vec<A>, post2_v: Vec<A>) -> bool {
    (r1 == r2)
    && (post1_v == post2_v)
}

proof fn det_vec_erase<A>(g_start_eq: bool, k_start_eq: int, g_start_rng: bool, k_start_rng_lo: int, k_start_rng_hi: int, g_end_eq: bool, k_end_eq: int, g_end_rng: bool, k_end_rng_lo: int, k_end_rng_hi: int, g_neq_tuple: bool, pre_v: Vec<A>, start: usize, end: usize, post1_v: Vec<A>, r1: (), post2_v: Vec<A>, r2: ())
    requires (start <= end <= pre_v.len()),
    ensures
        ({
            &&& (true)
            &&& (post1_v@ == pre_v@.subrange(0, start as int) + pre_v@.subrange(end as int, pre_v@.len() as int))
            &&& (true)
            &&& (post2_v@ == pre_v@.subrange(0, start as int) + pre_v@.subrange(end as int, pre_v@.len() as int))
        }) ==> det_vec_erase_equal(r1, r2, post1_v, post2_v),
{
    if g_start_eq { assume(start as int == k_start_eq); }
    if g_start_rng { assume(start as int >= k_start_rng_lo && start as int <= k_start_rng_hi); }
    if g_end_eq { assume(end as int == k_end_eq); }
    if g_end_rng { assume(end as int >= k_end_rng_lo && end as int <= k_end_rng_hi); }
    if g_neq_tuple { assume(!det_vec_erase_equal(r1, r2, post1_v, post2_v)); }
}
// === END INJECTED ===

}
