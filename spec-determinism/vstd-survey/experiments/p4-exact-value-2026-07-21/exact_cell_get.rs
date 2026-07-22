// P4 phase B — exact-value counterfactual (option ②).
// Amended contract for deprecated `InvCell::get` (cell.rs:378):
//     ensures self.inv(val) && val == self.current()

#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::*;

verus! {

proof fn det_get_exact_value<T: Copy>(
    self_: &InvCell<T>, r1: T, r2: T, current: T,
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
