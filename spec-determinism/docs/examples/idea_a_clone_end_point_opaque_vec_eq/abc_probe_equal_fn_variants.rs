// A/B/C probe: three candidate equal-fn shapes for `clone_end_point`,
// all run through Verus to demonstrate the actual root cause of the
// Case 1 failure.
//
// Variant A is what our pipeline emits today (FAILS).
// Variants B and C are what the pipeline *would* emit if either
// (B) codegen's SEQ branch consulted the extracted `spec_view`, or
// (C) the extractor populated `EndPoint.spec_view` so the STRUCT
//     branch fired its "nested view" fallback `({lhs})@ == ({rhs})@`.
// Both B and C pass with empty proof bodies — no LLM needed.

use vstd::prelude::*;

fn main() {}

verus! {

pub struct AbstractEndPoint { pub id: Seq<u8> }
pub struct EndPoint { pub id: Vec<u8> }

impl EndPoint {
    pub open spec fn view(self) -> AbstractEndPoint {
        AbstractEndPoint { id: self.id@ }
    }
}

// A — what `_build_equal_fn` actually emits today.
//     codegen/gen_det.py line 1184 (SEQ branch) ignores
//     `ty.spec_view` and emits raw `lhs == rhs`.
spec fn det_equal_A(r1: EndPoint, r2: EndPoint) -> bool {
    (r1.id == r2.id)
}

// B — what the SEQ branch should emit when `ty.spec_view` is set
//     (we extracted Vec<u8>.spec_view = Seq<u8> already; codegen
//     just doesn't read it for SEQ).
spec fn det_equal_B(r1: EndPoint, r2: EndPoint) -> bool {
    (r1.id@ == r2.id@)
}

// C — what the STRUCT branch would emit if the extractor populated
//     `EndPoint.spec_view` from `impl EndPoint { spec fn view }`.
//     Line 1327-1332 fallback: `({lhs})@ == ({rhs})@`.
spec fn det_equal_C(r1: EndPoint, r2: EndPoint) -> bool {
    (r1@ == r2@)
}

proof fn det_A(ep: EndPoint, r1: EndPoint, r2: EndPoint)
    ensures (r1@ == ep@ && r2@ == ep@) ==> det_equal_A(r1, r2),
{ /* expect: FAIL — postcondition not satisfied */ }

proof fn det_B(ep: EndPoint, r1: EndPoint, r2: EndPoint)
    ensures (r1@ == ep@ && r2@ == ep@) ==> det_equal_B(r1, r2),
{ /* expect: pass with empty body */ }

proof fn det_C(ep: EndPoint, r1: EndPoint, r2: EndPoint)
    ensures (r1@ == ep@ && r2@ == ep@) ==> det_equal_C(r1, r2),
{ /* expect: pass with empty body */ }

}
