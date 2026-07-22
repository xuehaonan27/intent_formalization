// P4 phase B — exact-value counterfactual (option ②).
// Amended contract for `RwLock::acquire_write` (rwlock.rs:530):
//     ensures ret.1.rwlock() == *self && self.inv(ret.0) && ret.0 == self.current()
// The WriteHandle keeps its opaque identity; the amended equality observes
// only the value component.

#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::rwlock::*;

verus! {

proof fn det_acquire_write_exact_value<V, Pred: RwLockPredicate<V>>(
    self_: &RwLock<V, Pred>,
    r1: (V, WriteHandle<'_, V, Pred>),
    r2: (V, WriteHandle<'_, V, Pred>),
    current: V,
)
    ensures
        ({
            &&& (r1.1.rwlock() == *self_)
            &&& (self_.inv(r1.0))
            &&& (r1.0 == current)
            &&& (r2.1.rwlock() == *self_)
            &&& (self_.inv(r2.0))
            &&& (r2.0 == current)
        }) ==> (r1.0 == r2.0),
{
}

} // verus!

fn main() {}
