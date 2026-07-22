// P4 phase B — exact-value counterfactual (option ②).
// Amended contract for `RwLock::into_inner` (rwlock.rs:702):
//     ensures self.inv(v) && v == self.current()

#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::rwlock::*;

verus! {

proof fn det_into_inner_exact_value<V, Pred: RwLockPredicate<V>>(
    self_: RwLock<V, Pred>, r1: V, r2: V, current: V,
)
    ensures
        ({
            &&& (self_.inv(r1))
            &&& (r1 == current)
            &&& (self_.inv(r2))
            &&& (r2 == current)
        }) ==> (r1 == r2),
{
}

} // verus!

fn main() {}
