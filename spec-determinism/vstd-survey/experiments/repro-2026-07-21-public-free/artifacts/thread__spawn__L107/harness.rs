#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::thread::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_spawn_equal<F, Ret>(r1: JoinHandle<Ret>, r2: JoinHandle<Ret>) -> bool
    where F: FnOnce() -> Ret, F: Send + 'static, Ret: Send + 'static {
    (r1 == r2)
}

proof fn det_spawn<F, Ret>(g_neq_tuple: bool, f: F, r1: JoinHandle<Ret>, r2: JoinHandle<Ret>)
    where F: FnOnce() -> Ret,
    F: Send + 'static,
    Ret: Send + 'static,
    requires (f.requires(())),
    ensures
        ({
            &&& (forall|ret: Ret| #[trigger] r1.predicate(ret) ==> f.ensures((), ret))
            &&& (forall|ret: Ret| #[trigger] r2.predicate(ret) ==> f.ensures((), ret))
        }) ==> det_spawn_equal::<F, Ret>(r1, r2),
{
    if g_neq_tuple { assume(!det_spawn_equal(r1, r2)); }
}
}

fn main() {}
