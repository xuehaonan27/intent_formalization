use vstd::prelude::*;
use vstd::slice::slice_index_get;

fn main() {}

verus!{

// File: src/utils.rs
pub open spec fn seq_splice(data: Seq<u8>, pos: usize, v: Seq<u8>) -> Seq<u8>
    recommends
        pos + v.len() <= data.len(),
{
    data.take(pos as int) + v + data.skip(pos + v.len() as int)
}

pub fn set_range<'a>(data: &mut Vec<u8>, i: usize, input: &[u8])
    requires
        0 <= i + input@.len() <= old(data)@.len() <= usize::MAX,
    ensures
        data@.len() == old(data)@.len()
        && data@ == seq_splice(old(data)@, i, input@),
{
    // data[i..i + input.len()].copy_from_slice(input);
    let mut j = 0;
    while j < input.len()
        invariant
            data@.len() == old(data)@.len(),
            forall|k| 0 <= k < i ==> data@[k] == old(data)@[k],
            forall|k| i + input@.len() <= k < data@.len() ==> data@[k] == old(data)@[k],
            0 <= i <= i + j <= i + input@.len() <= data@.len() <= usize::MAX,
            forall|k| 0 <= k < j ==> data@[i + k] == input@[k],
        decreases input@.len() - j,
    {
        data.set(i + j, *slice_index_get(input, j));
        j = j + 1
    }
    assert(data@ =~= old(data)@.subrange(0, i as int).add(input@).add(
        old(data)@.subrange(i + input@.len(), data@.len() as int),
    ))
}



// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_set_range_equal(r1: (), r2: (), post1_data: Vec<u8>, post2_data: Vec<u8>) -> bool {
    (r1 == r2)
    && (post1_data == post2_data)
}

proof fn det_set_range(g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_neq_tuple: bool, pre_data: Vec<u8>, i: usize, input: &[u8], post1_data: Vec<u8>, r1: (), post2_data: Vec<u8>, r2: ())
    requires (0 <= i + input@.len() <= pre_data@.len() <= usize::MAX),
    ensures
        ({
            &&& (post1_data@.len() == pre_data@.len()
        && post1_data@ == seq_splice(pre_data@, i, input@))
            &&& (post2_data@.len() == pre_data@.len()
        && post2_data@ == seq_splice(pre_data@, i, input@))
        }) ==> det_set_range_equal(r1, r2, post1_data, post2_data),
{
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_neq_tuple { assume(!det_set_range_equal(r1, r2, post1_data, post2_data)); }
}
// === END INJECTED ===

}
