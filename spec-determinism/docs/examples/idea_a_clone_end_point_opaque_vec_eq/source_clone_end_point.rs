// Extracted from:
// /home/chentianyu/verus-proof-synthesis/benchmarks/VeruSAGE-Bench/source-projects/
//   ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs
//
// (Lines abridged for clarity; only the items that matter for this example.)

use vstd::prelude::*;

verus! {

pub struct AbstractEndPoint {
    pub id: Seq<u8>,
}

pub struct EndPoint {
    pub id: Vec<u8>,
}

impl EndPoint {
    pub open spec fn view(self) -> AbstractEndPoint {
        AbstractEndPoint { id: self.id@ }
    }

    // The function whose determinism we are checking.
    // Note: `cloned_ep@ == ep@` only constrains the *view* (Seq<u8>),
    // not Vec equality.
    pub fn clone_end_point(ep: &EndPoint) -> (cloned_ep: EndPoint)
        ensures
            cloned_ep@ == ep@,
    {
        unimplemented!()    // real source is `#[verifier(external_body)]`
    }
}

}
