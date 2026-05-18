// Determinism check that our pipeline generates for `clone_end_point`
// under the current policy (errs_equivalent=True, opaque_ok=False).
//
// Real file with all 100+ guard parameters is in the artifact directory:
//   results-verusage-llmproof/ironkv/artifacts/
//     ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__clone_end_point/
//     llm_proof/det.rs
//
// We elide the per-field/byte guard cluster here for readability — it is
// emitted by schema_search and always evaluates to `assume(false)` only
// when the relevant `g_*` knob is true. When LLM-mode fires, all guards
// are off (no schema variant closed the obligation), so the body of the
// proof fn reduces to whatever the agent writes in the LLM PROOF BLOCK.

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

// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_clone_end_point_equal(r1: EndPoint, r2: EndPoint) -> bool {
    ((r1.id == r2.id))            // <- Vec<u8> *structural* equality
}

proof fn det_clone_end_point(
    // … ~100 boolean/int guard params elided … //
    ep: EndPoint, r1: EndPoint, r2: EndPoint,
)
    ensures
        ({
            &&& (r1@ == ep@)      // <- from clone_end_point's ensures
            &&& (r2@ == ep@)
        }) ==> det_clone_end_point_equal(r1, r2),
{
    // (guard cluster elided — all `if g_* { assume(...) }` lines.
    //  In the LLM-triggering path, every `g_*` is false, so the
    //  body before our marker is observationally a no-op.)

    // === LLM PROOF BLOCK ===
    // What the LLM agent wrote after 5 verus rounds:
    if r1@ == ep@ && r2@ == ep@ {
        assert(r1.id@ == ep.id@);   // ✓  unfolds EndPoint::view
        assert(r2.id@ == ep.id@);   // ✓
        assert(r1.id@ == r2.id@);   // ✓  transitivity on Seq
        assert(r1.id == r2.id);     // ✗  ← verus rejects (see verus_error.txt)
    }
    // === END LLM PROOF BLOCK ===
}

}
