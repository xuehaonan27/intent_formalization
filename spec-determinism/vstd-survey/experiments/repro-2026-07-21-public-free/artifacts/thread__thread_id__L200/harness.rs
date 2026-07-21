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

proof fn det_thread_id(g_neq_tuple: bool, r1: (ThreadId, Tracked<IsThread>), r2: (ThreadId, Tracked<IsThread>))
    ensures
        ({
            &&& (r1.1@@ == r1.0)
            &&& (r2.1@@ == r2.0)
        }) ==> det_thread_id_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_thread_id_equal(r1, r2)); }
}
}

fn main() {}
