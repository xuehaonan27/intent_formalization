// P4 phase B — exact-value counterfactual (option ②).
// Amended contract for `cell::invcell::InvCell::into_inner` (invcell.rs:155):
//     ensures self.inv(val) && val == self.current()

#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::invcell::*;
use vstd::predicate::*;

verus! {

proof fn det_into_inner_exact_value<T, Pred: Predicate<T>>(
    self_: InvCell<T, Pred>, r1: T, r2: T, current: T,
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
