// P4 phase A — machine-checked nondeterminism witness.
//
// Target: `vstd::cell::invcell::InvCell::{replace, get, into_inner}`
// (invcell.rs:123/139/155), postcondition `ensures self.inv(result)`.
//
// `inv(v)` is open and delegates to the user-chosen `Pred`:
//     inv(v) = self.predicate().predicate(v)
// Instantiating `Pred` with the constant-true spec_fn admits every value.
// Machine-checked proof that two distinct results satisfy the contract.

#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::invcell::*;
use vstd::predicate::*;

verus! {

fn witness_invcell_result_not_unique()
{
    // vstd's blanket impl makes `spec_fn(T) -> bool` a `Predicate<T>`.
    // `new(val, Ghost(pred))` requires `pred.predicate(val)` and ensures
    // `cell.predicate() == pred`.
    let cell = InvCell::<u64, spec_fn(u64) -> bool>::new(0u64, Ghost(|v: u64| true));
    proof {
        // inv is an open spec fn: inv(v) = predicate().predicate(v) = true.
        assert(cell.inv(0u64));
        assert(cell.inv(1u64));
        assert(0u64 != 1u64);
        // QED: replace/get/into_inner's `ensures self.inv(result)` admits
        // two distinct results — genuine underconstraint, machine-established.
    }
}

} // verus!

fn main() {}
