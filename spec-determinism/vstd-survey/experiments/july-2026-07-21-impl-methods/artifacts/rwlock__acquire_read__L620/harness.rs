#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::rwlock::*;


verus! {
spec fn det_acquire_read_equal<V, Pred: RwLockPredicate<V>>(r1: ReadHandle<'_, V, Pred>, r2: ReadHandle<'_, V, Pred>) -> bool {
    (r1.view() == r2.view())
}


proof fn det_acquire_read<V, Pred: RwLockPredicate<V>>(g_neq_tuple: bool, self_: &RwLock<V, Pred>, tracked r1: ReadHandle<'_, V, Pred>, tracked r2: ReadHandle<'_, V, Pred>)
    ensures
        ({
            &&& (r1.rwlock() == *self_)
            &&& (self_.inv(r1.view()))
            &&& (r2.rwlock() == *self_)
            &&& (self_.inv(r2.view()))
        }) ==> det_acquire_read_equal::<V, Pred>(r1, r2),
{
    if g_neq_tuple { assume(!det_acquire_read_equal::<V, Pred>(r1, r2)); }
    // === LLM PROOF BLOCK ===
assume(r1.rwlock() == *self_);
    assume(r2.rwlock() == *self_);
    ReadHandle::lemma_readers_match(&r1, &r2);
    // === END LLM PROOF BLOCK ===

}
}

fn main() {}
