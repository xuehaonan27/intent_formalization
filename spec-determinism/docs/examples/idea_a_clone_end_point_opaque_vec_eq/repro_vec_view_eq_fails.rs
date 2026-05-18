// Minimal reproducer the agent constructed (described in its rationale)
// to confirm that `v1@ == v2@ ==> v1 == v2` is *not* derivable for
// Vec<u8> in Verus spec mode.
//
// Save as a stand-alone Verus file. `verus repro_vec_view_eq_fails.rs`
// should reject `lemma_view_eq_implies_eq` with `assertion failed` on
// the `ensures` line.

use vstd::prelude::*;

fn main() {}

verus! {

// This lemma is FALSE in Verus's spec semantics, because Vec is
// `external_body` and its `PartialEq`/`==` is not axiomatized in
// terms of the underlying Seq view. The verifier cannot close the
// postcondition.
proof fn lemma_view_eq_implies_eq(a: Vec<u8>, b: Vec<u8>)
    requires a@ == b@,
    ensures  a == b,    // <- expect: postcondition not satisfied
{
}

// In contrast, the symmetric direction is trivially true (PartialEq
// on Vec is determined enough to unfold to its argument):
proof fn lemma_eq_implies_view_eq(a: Vec<u8>, b: Vec<u8>)
    requires a == b,
    ensures  a@ == b@,
{
}

}
