// P4 phase B — exact-value counterfactual (option ②).
// Amended contract for `cell::invcell::InvCell::replace` (invcell.rs:123):
//     ensures self.inv(old_val) && old_val == old(self).current()

#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::invcell::*;
use vstd::predicate::*;

verus! {

proof fn det_replace_exact_value<T, Pred: Predicate<T>>(
    self_: &InvCell<T, Pred>, val: T, r1: T, r2: T, current: T,
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
