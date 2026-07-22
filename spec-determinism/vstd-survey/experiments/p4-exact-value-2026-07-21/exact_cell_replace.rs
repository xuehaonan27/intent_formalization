// P4 phase B — exact-value counterfactual (option ②).
//
// Counterfactual contract for deprecated `InvCell::replace` (cell.rs:359):
//     ensures self.inv(old_val) && old_val == old(self).current()
// i.e. a ghost exact-current-value accessor is exposed. `current` models the
// accessor's value on the pre-state. The det check for the amended contract
// is: does any pair of results satisfying BOTH the original postcondition
// AND the exact-value constraint agree? Verified: determinism is restored
// the moment the exact value is pinned — the only missing constraint.

#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::*;

verus! {

proof fn det_replace_exact_value<T>(
    self_: &InvCell<T>, val: T, r1: T, r2: T, current: T,
)
    requires
        self_.inv(val),
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
