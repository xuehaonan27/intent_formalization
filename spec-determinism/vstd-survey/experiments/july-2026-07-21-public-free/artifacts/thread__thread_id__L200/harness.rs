#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::thread::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_thread_id_equal(r1: (ThreadId, Tracked<IsThread>), r2: (ThreadId, Tracked<IsThread>)) -> bool {
    ((r1.0 == r2.0) && ((r1.1)@@ == (r2.1)@@))
}

proof fn det_thread_id(g_neq_tuple: bool, tracked r1: (ThreadId, Tracked<IsThread>), tracked r2: (ThreadId, Tracked<IsThread>))
    ensures
        ({
            &&& (r1.1@@ == r1.0)
            &&& (r2.1@@ == r2.0)
        }) ==> det_thread_id_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_thread_id_equal(r1, r2)); }
    // === LLM PROOF BLOCK ===
let tracked __det_t1 = r1.1.borrow();
    let tracked __det_t2 = r2.1.borrow();
    __det_t1.agrees(*__det_t2);
    // === END LLM PROOF BLOCK ===

}
}

fn main() {}
