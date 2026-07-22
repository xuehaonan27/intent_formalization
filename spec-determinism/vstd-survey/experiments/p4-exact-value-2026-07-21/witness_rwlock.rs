// P4 phase A — machine-checked nondeterminism witness.
//
// Target: `vstd::rwlock::RwLock::{acquire_write, into_inner}`
// (rwlock.rs:530/702). acquire_write's returned value `ret.0` and
// into_inner's returned value are constrained only by `self.inv(v)`,
// which is open and delegates to the user-chosen `RwLockPredicate`:
//     inv(v) = self.pred().inv(v)
// A constant-true predicate admits every value. Machine-checked proof
// that two distinct results satisfy the contract.

#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::rwlock::*;

verus! {

fn witness_rwlock_result_not_unique()
{
    // vstd's own examples construct RwLock with a spec_fn predicate
    // (rwlock.rs:282). With the constant-true predicate:
    let lock = RwLock::<u64, spec_fn(u64) -> bool>::new(0u64, Ghost(|v: u64| true));
    proof {
        // rwlock::inv is open: inv(v) = pred().inv(v) = true.
        assert(lock.inv(0u64));
        assert(lock.inv(1u64));
        assert(0u64 != 1u64);
        // QED: `self.inv(ret.0)` / `self.inv(v)` admit two distinct results —
        // genuine underconstraint, machine-established.
    }
}

} // verus!

fn main() {}
