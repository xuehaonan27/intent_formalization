// P4 phase A — machine-checked nondeterminism witness.
//
// Target: deprecated `vstd::cell::InvCell::{replace, get}` (cell.rs:359/378),
// whose postcondition is `ensures self.inv(result)`.
//
// The invariant predicate is a *possible-value* predicate: `inv(v)` holds
// iff `v` is in the cell's `possible_values` ISet, which is built from an
// arbitrary user predicate. Choosing the constant-true predicate makes EVERY
// value admissible. This file proves — inside the actual vstd model — that
// two distinct values satisfy the postcondition, i.e. the spec genuinely
// does not determine the result (audit class C, now machine-established).

#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::*;

verus! {

fn witness_deprecated_invcell_result_not_unique()
{
    // `new(val, Ghost(f))` requires `f(val)` and ensures
    // `forall|v| f(v) <==> cell.inv(v)`. With f = |v| true:
    let cell = InvCell::<u64>::new(0u64, Ghost(|v: u64| true));
    proof {
        // … the postcondition `self.inv(old_val)` of replace/get admits
        // two distinct old values:
        assert(cell.inv(0u64));
        assert(cell.inv(1u64));
        assert(0u64 != 1u64);
        // QED: P(x) ∧ Q(x, 0) ∧ Q(x, 1) ∧ 0 != 1 is achievable, so
        // `ensures self.inv(result)` is genuinely underconstrained.
    }
}

} // verus!

fn main() {}
