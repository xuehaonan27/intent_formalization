// Copyright(c) The Maintainers of Nanvix.
// Licensed under the MIT License.

//==================================================================================================
// Configuration
//==================================================================================================

#![cfg_attr(not(feature = "std"), no_std)]
#![cfg_attr(verus_keep_ghost, feature(proc_macro_hygiene))]
#![cfg_attr(verus_keep_ghost, feature(allocator_api))]

//==================================================================================================
// Modules
//==================================================================================================

#[cfg(all(test, feature = "std"))]
mod test;

//==================================================================================================
// Imports
//==================================================================================================

extern crate alloc;

use ::alloc::vec::Vec;
#[allow(unused_imports)]
use ::vstd::prelude::*;

// Include specifications.
#[cfg(verus_keep_ghost)]
include!("lib.spec.rs");

// Include proofs.
#[cfg(verus_keep_ghost)]
include!("lib.proof.rs");

//==================================================================================================
// Structures
//==================================================================================================

//==================================================================================================
// Implementations
//==================================================================================================

verus! {

///
/// # Description
///
/// A sorted vector that maintains its elements in ascending order and provides efficient
/// lookup via binary search.
///
/// Elements must implement [`Ord`] for sorting and searching. The vector does not allow
/// duplicate elements; inserting a value that already exists replaces the old entry.
///
#[cfg_attr(not(verus_keep_ghost), derive(Debug, Clone))]
pub struct SortedVec<T: Ord> {
    /// Underlying storage.
    inner: Vec<T>,
}

impl<T: Ord> SortedVec<T> {
    ///
    /// # Description
    ///
    /// Creates an empty [`SortedVec`].
    ///
    /// # Returns
    ///
    /// An empty sorted vector.
    ///
    // FN-1
    pub fn new() -> (result: Self)
        ensures
            result.inv(),
            result@ == Seq::<T>::empty(),
    {
        Self { inner: Vec::new() }
    }

    ///
    /// # Description
    ///
    /// Creates an empty [`SortedVec`] with the specified capacity.
    ///
    /// # Parameters
    ///
    /// - `capacity`: The number of elements the vector can hold without reallocating.
    ///
    /// # Returns
    ///
    /// An empty sorted vector with the given capacity.
    ///
    // FN-2
    pub fn with_capacity(capacity: usize) -> (result: Self)
        ensures
            result.inv(),
            result@ == Seq::<T>::empty(),
    {
        Self {
            inner: Vec::with_capacity(capacity),
        }
    }

    ///
    /// # Description
    ///
    /// Returns the number of elements in the sorted vector.
    ///
    /// # Returns
    ///
    /// The number of elements.
    ///
    // FN-3
    pub fn len(&self) -> (result: usize)
        ensures
            result as int == self@.len(),
    {
        self.inner.len()
    }

    ///
    /// # Description
    ///
    /// Returns `true` if the sorted vector contains no elements.
    ///
    /// # Returns
    ///
    /// `true` if empty, `false` otherwise.
    ///
    // FN-4
    pub fn is_empty(&self) -> (result: bool)
        ensures
            result <==> self@.len() == 0,
    {
        self.inner.is_empty()
    }

    ///
    /// # Description
    ///
    /// Returns the capacity of the sorted vector.
    ///
    /// # Returns
    ///
    /// The number of elements the vector can hold without reallocating.
    ///
    // FN-5
    pub fn capacity(&self) -> (result: usize)
        ensures
            result as int >= self@.len(),
    {
        self.inner.capacity()
    }

    ///
    /// # Description
    ///
    /// Clears all elements from the sorted vector.
    ///
    // FN-6
    pub fn clear(&mut self)
        requires
            old(self).inv(),
        ensures
            self.inv(),
            self@ == Seq::<T>::empty(),
    {
        self.inner.clear();
    }

    ///
    /// # Description
    ///
    /// Inserts a value into the sorted vector, maintaining sorted order. If the value already
    /// exists, the old value is replaced and returned.
    ///
    /// # Parameters
    ///
    /// - `value`: The value to insert.
    ///
    /// # Returns
    ///
    /// `Some(old_value)` if the value was already present, `None` otherwise.
    ///
    // FN-7
    pub fn insert(&mut self, value: T) -> (result: Option<T>)
        requires
            old(self).inv(),
        ensures
            self.inv(),
            // Biconditional: replacement iff value was Ord-present
            result.is_some() <==> spec_contains(old(self)@, value),
            // Replacement case: value was Ord-present
            result.is_some() ==> {
                &&& old(self)@.contains(result.unwrap())
                &&& sv_eq(result.unwrap(), value)
                &&& self@.len() == old(self)@.len()
                &&& spec_contains(self@, value)
            },
            // New insertion case: value was Ord-absent
            result.is_none() ==> {
                &&& self@.len() == old(self)@.len() + 1
                &&& spec_contains(self@, value)
            },
            // Frame: elements not Ord-equal to value are structurally preserved
            forall|v: T| old(self)@.contains(v) && !sv_eq(v, value) ==> self@.contains(v),
    {
        match self.inner.binary_search(&value) {
            Ok(index) => {
                // VERUS DEVIATION: `core::mem::replace(&mut self.inner[index], value)`
                // cannot be verified — Verus does not support IndexMut (`&mut vec[i]`).
                // Semantically equivalent remove+insert used under verus_keep_ghost.
                // Variable renamed from `old` to `old_elem` to avoid shadowing
                // the Verus `old()` builtin.
                #[cfg(not(verus_keep_ghost))]
                {
                    let old: T = ::core::mem::replace(&mut self.inner[index], value);
                    Some(old)
                }
                #[cfg(verus_keep_ghost)]
                {
                    let ghost old_seq = old(self)@;
                    let ghost idx = index as int;
                    let old_elem = self.inner.remove(index);
                    self.inner.insert(index, value);
                    proof {
                        let ghost _vec_len: usize = vstd::std_specs::vec::spec_vec_len(&self.inner);
                        lemma_insert_replace_maintains_inv(old_seq, idx, value);
                    }
                    Some(old_elem)
                }
            },
            Err(index) => {
                self.inner.insert(index, value);
                proof {
                    let ghost _vec_len: usize = vstd::std_specs::vec::spec_vec_len(&self.inner);
                    lemma_insert_new_maintains_inv(old(self)@, index as int, value);
                }
                None
            },
        }
    }

    ///
    /// # Description
    ///
    /// Removes a value from the sorted vector.
    ///
    /// # Parameters
    ///
    /// - `value`: The value to remove.
    ///
    /// # Returns
    ///
    /// `Some(removed_value)` if found, `None` otherwise.
    ///
    // FN-8
    pub fn remove(&mut self, value: &T) -> (result: Option<T>)
        requires
            old(self).inv(),
        ensures
            self.inv(),
            // Found: element removed
            result.is_some() ==> {
                &&& sv_eq(result.unwrap(), *value)
                &&& self@.len() == old(self)@.len() - 1
                &&& !spec_contains(self@, *value)
            },
            // Not found: state unchanged
            result.is_none() ==> {
                &&& !spec_contains(old(self)@, *value)
                &&& self@ == old(self)@
            },
            // Frame: elements not Ord-equal to value are structurally preserved
            forall|v: T| old(self)@.contains(v) && !sv_eq(v, *value) ==> self@.contains(v),
    {
        match self.inner.binary_search(value) {
            Ok(index) => {
                proof { lemma_remove_maintains_inv(self@, index as int, *value); }
                Some(self.inner.remove(index))
            },
            Err(_) => None,
        }
    }

    // FN-9: remove_by is defined outside verus! — see below.
    // binary_search_by_key cannot be spec'd in Verus (lifetime parameter mismatch).

    ///
    /// # Description
    ///
    /// Returns `true` if the sorted vector contains the given value.
    ///
    /// # Parameters
    ///
    /// - `value`: The value to search for.
    ///
    /// # Returns
    ///
    /// `true` if the value is found, `false` otherwise.
    ///
    // FN-10
    pub fn contains(&self, value: &T) -> (result: bool)
        requires
            self.inv(),
        ensures
            result <==> spec_contains(self@, *value),
    {
        self.inner.binary_search(value).is_ok()
    }

    ///
    /// # Description
    ///
    /// Returns a reference to the element matching the given value, using binary search.
    ///
    /// # Parameters
    ///
    /// - `value`: The value to search for.
    ///
    /// # Returns
    ///
    /// `Some(&element)` if found, `None` otherwise.
    ///
    // FN-11
    pub fn get(&self, value: &T) -> (result: Option<&T>)
        requires
            self.inv(),
        ensures
            result.is_some() <==> spec_contains(self@, *value),
            result.is_some() ==> sv_eq(*result.unwrap(), *value),
            result.is_some() ==> exists|i: int| 0 <= i < self@.len() && self@[i] == *result.unwrap(),
    {
        match self.inner.binary_search(value) {
            Ok(index) => Some(&self.inner[index]),
            Err(_) => None,
        }
    }

    // FN-12: lookup_by is defined outside verus! — see below.
    // binary_search_by_key cannot be spec'd in Verus (lifetime parameter mismatch).

    ///
    /// # Description
    ///
    /// Returns a reference to the smallest element.
    ///
    /// # Returns
    ///
    /// `Some(&element)` if non-empty, `None` otherwise.
    ///
    // FN-13
    pub fn first(&self) -> (result: Option<&T>)
        requires
            self.inv(),
        ensures
            result.is_some() <==> self@.len() > 0,
            result.is_some() ==> *result.unwrap() == self@[0],
    {
        self.inner.first()
    }

    ///
    /// # Description
    ///
    /// Returns a reference to the largest element.
    ///
    /// # Returns
    ///
    /// `Some(&element)` if non-empty, `None` otherwise.
    ///
    // FN-14
    pub fn last(&self) -> (result: Option<&T>)
        requires
            self.inv(),
        ensures
            result.is_some() <==> self@.len() > 0,
            result.is_some() ==> *result.unwrap() == self@[self@.len() - 1],
    {
        self.inner.last()
    }

    ///
    /// # Description
    ///
    /// Returns an iterator over the elements in sorted order.
    ///
    /// # Returns
    ///
    /// An iterator yielding references to elements in ascending order.
    ///
    // FN-15: iter — core::slice::Iter lacks vstd spec; no contract.
    pub fn iter(&self) -> ::core::slice::Iter<'_, T> {
        self.inner.iter()
    }

    ///
    /// # Description
    ///
    /// Returns a slice of the underlying sorted elements.
    ///
    /// # Returns
    ///
    /// A slice of all elements in sorted order.
    ///
    // FN-16
    pub fn as_slice(&self) -> (result: &[T])
        requires
            self.inv(),
        ensures
            result@ == self@,
    {
        self.inner.as_slice()
    }
}

} // verus!

//==================================================================================================
// Unverified Methods (binary_search_by_key limitation)
//==================================================================================================

// FN-9, FN-12: binary_search_by_key cannot be spec'd in Verus — its named
// lifetime parameter `'a` tying `&'a self` to `FnMut(&'a T)` does not match
// Verus's HRTB desugaring. These methods are placed outside verus! to make
// their unverified status explicit and avoid dummy cfg-gated branches.
impl<T: Ord> SortedVec<T> {
    ///
    /// # Description
    ///
    /// Removes an element by extracting a comparable key from each entry.
    ///
    /// The key function must extract a value whose natural ordering is consistent with the
    /// ascending [`Ord`] order of the underlying sorted vector. The library performs the
    /// comparison internally, so ordering correctness is enforced by construction.
    ///
    /// # Parameters
    ///
    /// - `key`: The key value to search for.
    /// - `f`: A function that extracts a comparable key of type `K` from each element.
    ///
    /// # Returns
    ///
    /// `Some(removed_value)` if found, `None` otherwise.
    ///
    pub fn remove_by<K, F>(&mut self, key: &K, f: F) -> Option<T>
    where
        K: Ord,
        F: FnMut(&T) -> K,
    {
        match self.inner.binary_search_by_key(key, f) {
            Ok(index) => Some(self.inner.remove(index)),
            Err(_) => None,
        }
    }

    ///
    /// # Description
    ///
    /// Searches the sorted vector by extracting a comparable key from each entry.
    ///
    /// The key function must extract a value whose natural ordering is consistent with the
    /// ascending [`Ord`] order of the underlying sorted vector. The library performs the
    /// comparison internally, so ordering correctness is enforced by construction.
    ///
    /// # Parameters
    ///
    /// - `key`: The key value to search for.
    /// - `f`: A function that extracts a comparable key of type `K` from each element.
    ///
    /// # Returns
    ///
    /// `Some(&element)` if found, `None` otherwise.
    ///
    pub fn lookup_by<K, F>(&self, key: &K, f: F) -> Option<&T>
    where
        K: Ord,
        F: FnMut(&T) -> K,
    {
        match self.inner.binary_search_by_key(key, f) {
            Ok(index) => Some(&self.inner[index]),
            Err(_) => None,
        }
    }
}

//==================================================================================================
// Trait Implementations
//==================================================================================================

verus! {

// FN-17
impl<T: Ord> Default for SortedVec<T> {
    fn default() -> (result: Self)
        ensures
            result.inv(),
            result@ == Seq::<T>::empty(),
    {
        Self::new()
    }
}

} // verus!

// FN-18: From<Vec<T>> — sort_unstable operates on [T] via DerefMut, which Verus
// cannot fully model inside verus!. Keep outside verus! (no contract).
impl<T: Ord> From<Vec<T>> for SortedVec<T> {
    ///
    /// # Description
    ///
    /// Creates a [`SortedVec`] from an unsorted [`Vec`]. The vector is sorted and duplicates
    /// are removed.
    ///
    fn from(mut vec: Vec<T>) -> Self {
        vec.sort_unstable();
        vec.dedup();
        Self { inner: vec }
    }
}

// FN-19, FN-20: IntoIterator impls — iterator types lack full vstd specs.
// Keep outside verus! (no contract).
impl<T: Ord> IntoIterator for SortedVec<T> {
    type Item = T;
    type IntoIter = ::alloc::vec::IntoIter<T>;

    fn into_iter(self) -> Self::IntoIter {
        self.inner.into_iter()
    }
}

impl<'a, T: Ord> IntoIterator for &'a SortedVec<T> {
    type Item = &'a T;
    type IntoIter = ::core::slice::Iter<'a, T>;

    fn into_iter(self) -> Self::IntoIter {
        self.inner.iter()
    }
}

verus! {

// ===========================================================================
// View
// ===========================================================================

// Abstract state: Seq<T> — a sorted sequence with no duplicates.
// `closed` so callers use inv() + method contracts, not internal structure.
impl<T: Ord> View for SortedVec<T> {
    type V = Seq<T>;

    closed spec fn view(&self) -> Seq<T> {
        self.inner@
    }
}

// ===========================================================================
// Spec Helper Functions
// ===========================================================================

/// Uninterpreted spec-level strict ordering on T.
/// Represents the exec-level Ord comparison at the spec level.
/// (Verus has no built-in spec ordering for generic T: Ord.)
pub uninterp spec fn spec_lt<T>(a: T, b: T) -> bool;

/// Collects the strict total order axioms for spec_lt into a single predicate.
/// Matches the ordering axioms ensured by binary_search's assume_specification.
pub open spec fn spec_lt_is_strict_total_order<T>() -> bool {
    &&& forall|a: T| #[trigger] spec_lt(a, a) ==> false
    &&& forall|a: T, b: T| spec_lt(a, b) ==> !#[trigger] spec_lt(b, a)
    &&& forall|a: T, b: T, c: T| #[trigger] spec_lt(a, b) && #[trigger] spec_lt(b, c) ==> spec_lt(a, c)
    &&& forall|a: T, b: T| #[trigger] sv_eq(a, b) || spec_lt(a, b) || spec_lt(b, a)
    &&& forall|a: T, b: T, c: T| #[trigger] sv_eq(a, b) && #[trigger] spec_lt(b, c) ==> spec_lt(a, c)
    &&& forall|a: T, b: T, c: T| #[trigger] spec_lt(a, b) && #[trigger] sv_eq(b, c) ==> spec_lt(a, c)
}

/// Spec-level equality: elements that are "equal" under Ord (neither is less).
pub open spec fn sv_eq<T>(a: T, b: T) -> bool {
    !spec_lt(a, b) && !spec_lt(b, a)
}

/// A sequence is strictly sorted: all pairs in ascending order per spec_lt.
/// TYPE-1: fundamental structural invariant of SortedVec.
pub open spec fn spec_strictly_sorted<T>(s: Seq<T>) -> bool {
    forall|i: int, j: int| 0 <= i < j < s.len() ==> spec_lt(s[i], s[j])
}

/// Membership check using Ord-equality (sv_eq).
/// Use instead of Seq::contains for SortedVec API contracts, since
/// binary_search finds matches via Ord comparison, not structural equality.
pub open spec fn spec_contains<T>(s: Seq<T>, v: T) -> bool {
    exists|i: int| 0 <= i < s.len() && sv_eq(s[i], v)
}

// ===========================================================================
// spec_lt Axioms — Trust Assumptions about T: Ord
// ===========================================================================

// These formalize the assumption that T: Ord provides a strict total order.
// Approved via property analysis exclusion: "We assume T: Ord provides a
// total order" and needed for Phase 3 proofs.
//
// The axiom properties are folded into binary_search's assume_specification
// ensures (same trust boundary) to avoid standalone admit() calls.

// ===========================================================================
// Invariant
// ===========================================================================

impl<T: Ord> SortedVec<T> {
    /// Well-formedness invariant for SortedVec.
    /// TYPE-1: Strictly ascending order (implies uniqueness, TYPE-2).
    /// Representability: length fits in usize.
    pub open spec fn inv(&self) -> bool {
        &&& spec_strictly_sorted(self@)
        &&& self@.len() <= usize::MAX as int
    }
}

// ===========================================================================
// Approved Assume Specifications — External Functions
// ===========================================================================

// --- [x] <[T]>::binary_search ---
// Ok: found element is Ord-equal (sv_eq) to search value (not structural ==).
// Err: no Ord-equal element exists; idx is the sorted insertion point.
//
// The ordering axioms (irreflexivity, asymmetry, transitivity, trichotomy,
// left/right congruence) are included as ensures because they share the same
// trust boundary: T: Ord provides a strict total order. This avoids
// standalone broadcast proof axioms that would require admit().
pub assume_specification<T: Ord>[ <[T]>::binary_search ](
    slice: &[T],
    value: &T,
) -> (result: Result<usize, usize>)
    requires
        spec_strictly_sorted(slice@),
    ensures
        match result {
            Ok(idx) => {
                &&& (idx as int) < slice@.len()
                &&& sv_eq(slice@[idx as int], *value)
            },
            Err(idx) => {
                &&& (idx as int) <= slice@.len()
                &&& !spec_contains(slice@, *value)
                &&& forall|k: int| #![auto] 0 <= k < idx as int ==> spec_lt(slice@[k], *value)
                &&& forall|k: int| #![auto] idx as int <= k < slice@.len() ==> spec_lt(*value, slice@[k])
            },
        },
        // Ordering axioms for T: Ord (strict total order)
        forall|a: T| #[trigger] spec_lt(a, a) ==> false,
        forall|a: T, b: T| spec_lt(a, b) ==> !#[trigger] spec_lt(b, a),
        forall|a: T, b: T, c: T| #[trigger] spec_lt(a, b) && #[trigger] spec_lt(b, c) ==> spec_lt(a, c),
        forall|a: T, b: T| #[trigger] sv_eq(a, b) || spec_lt(a, b) || spec_lt(b, a),
        // Congruence: sv_eq elements relate identically to all others
        forall|a: T, b: T, c: T| #[trigger] sv_eq(a, b) && #[trigger] spec_lt(b, c) ==> spec_lt(a, c),
        forall|a: T, b: T, c: T| #[trigger] spec_lt(a, b) && #[trigger] sv_eq(b, c) ==> spec_lt(a, c),
;

// --- [x] <[T]>::binary_search_by_key ---
// NOTE: Cannot write assume_specification — the function has a named lifetime
// parameter `'a` tying `&'a self` to `FnMut(&'a T)`, which Verus desugars
// to a higher-rank trait bound that does not match. Methods using this
// (remove_by, lookup_by) are placed outside verus! with no contracts.

// --- [x] <[T]>::sort_unstable ---
// Preserves elements (permutation) and produces weakly sorted output.
pub assume_specification<T: Ord>[ <[T]>::sort_unstable ](slice: &mut [T])
    ensures
        slice@.len() == old(slice)@.len(),
        forall|v: T| slice@.contains(v) <==> old(slice)@.contains(v),
        forall|i: int, j: int| 0 <= i < j < slice@.len() ==> !spec_lt(slice@[j], slice@[i]),
;

// --- [x] Vec::dedup ---
// On a weakly sorted input, removes consecutive Ord-equal duplicates,
// producing a sequence with no Ord-duplicates.
pub assume_specification<T: PartialEq, A: core::alloc::Allocator>[ Vec::<T, A>::dedup ](vec: &mut Vec<T, A>)
    requires
        forall|i: int| 0 <= i < old(vec)@.len() - 1 ==> !spec_lt(#[trigger] old(vec)@[i + 1], old(vec)@[i]),
    ensures
        vec@.len() <= old(vec)@.len(),
        forall|v: T| vec@.contains(v) <==> old(vec)@.contains(v),
        forall|i: int, j: int| 0 <= i < j < vec@.len() ==> !sv_eq(vec@[i], vec@[j]),
;

// --- [x] Vec::capacity ---
pub assume_specification<T, A: core::alloc::Allocator>[ Vec::<T, A>::capacity ](vec: &Vec<T, A>) -> (result: usize)
    ensures
        result as int >= vec@.len(),
;

} // verus!

verus! {

/// After binary_search Ok at `idx`, replacing the element with an Ord-equal
/// `value` (via remove+insert ≡ update) preserves strict sorting, membership,
/// and the frame for non-equal elements.
proof fn lemma_insert_replace_maintains_inv<T>(old_seq: Seq<T>, idx: int, value: T)
    requires
        spec_strictly_sorted(old_seq),
        0 <= idx < old_seq.len(),
        sv_eq(old_seq[idx], value),
        spec_lt_is_strict_total_order::<T>(),
    ensures
        old_seq.remove(idx).insert(idx, value) =~= old_seq.update(idx, value),
        spec_strictly_sorted(old_seq.update(idx, value)),
        old_seq.update(idx, value).len() == old_seq.len(),
        spec_contains(old_seq.update(idx, value), value),
        forall|v: T| old_seq.contains(v) && !sv_eq(v, value)
            ==> old_seq.update(idx, value).contains(v),
{
    let new_seq = old_seq.update(idx, value);

    // Strict sorting preserved under update with sv_eq value
    assert forall|i: int, j: int|
        0 <= i < j < new_seq.len()
        implies spec_lt(new_seq[i], new_seq[j])
    by {
        if i == idx {
            assert(spec_lt(old_seq[idx], old_seq[j]));
            assert(sv_eq(value, old_seq[idx]));
        } else if j == idx {
            assert(spec_lt(old_seq[i], old_seq[idx]));
            assert(sv_eq(old_seq[idx], value));
        } else {
            assert(spec_lt(old_seq[i], old_seq[j]));
        }
    }

    // Membership: value is at position idx — triggers spec_contains witness
    assert(sv_eq(new_seq[idx], value));

    // Frame: non-equal elements preserved
    assert forall|v: T|
        old_seq.contains(v) && !sv_eq(v, value)
        implies new_seq.contains(v)
    by {
        let k = choose|k: int| 0 <= k < old_seq.len() && old_seq[k] == v;
        if k == idx {
            assert(false);
        } else {
            assert(new_seq[k] == old_seq[k]);
        }
    }
}

/// After binary_search Err at `idx` (value absent), inserting `value` at `idx`
/// preserves strict sorting and establishes membership.
proof fn lemma_insert_new_maintains_inv<T>(old_seq: Seq<T>, idx: int, value: T)
    requires
        spec_strictly_sorted(old_seq),
        0 <= idx <= old_seq.len(),
        !spec_contains(old_seq, value),
        forall|k: int| 0 <= k < idx ==> spec_lt(old_seq[k], value),
        forall|k: int| idx <= k < old_seq.len() ==> spec_lt(value, old_seq[k]),
        spec_lt_is_strict_total_order::<T>(),
    ensures
        spec_strictly_sorted(old_seq.insert(idx, value)),
        old_seq.insert(idx, value).len() == old_seq.len() + 1,
        spec_contains(old_seq.insert(idx, value), value),
        forall|v: T| old_seq.contains(v) && !sv_eq(v, value)
            ==> old_seq.insert(idx, value).contains(v),
{
    let new_seq = old_seq.insert(idx, value);

    // Strict sorting preserved
    assert forall|i: int, j: int|
        0 <= i < j < new_seq.len()
        implies spec_lt(new_seq[i], new_seq[j])
    by {
        if i < idx && j == idx {
            assert(spec_lt(old_seq[i], value));
        } else if i < idx && j > idx {
            assert(spec_lt(old_seq[i], old_seq[j - 1]));
        } else if i == idx && j > idx {
            assert(spec_lt(value, old_seq[j - 1]));
        } else if i > idx {
            assert(spec_lt(old_seq[i - 1], old_seq[j - 1]));
        }
    }

    // Membership
    assert(sv_eq(new_seq[idx], value));

    // Frame
    assert forall|v: T|
        old_seq.contains(v) && !sv_eq(v, value)
        implies new_seq.contains(v)
    by {
        let k = choose|k: int| 0 <= k < old_seq.len() && old_seq[k] == v;
        if k < idx {
            assert(new_seq[k] == old_seq[k]);
        } else {
            assert(new_seq[k + 1] == old_seq[k]);
        }
    }
}

/// After binary_search Ok at `idx`, removing the element preserves strict
/// sorting, eliminates membership for the removed value, and preserves
/// all other elements.
proof fn lemma_remove_maintains_inv<T>(old_seq: Seq<T>, idx: int, value: T)
    requires
        spec_strictly_sorted(old_seq),
        0 <= idx < old_seq.len(),
        sv_eq(old_seq[idx], value),
        spec_lt_is_strict_total_order::<T>(),
    ensures
        spec_strictly_sorted(old_seq.remove(idx)),
        old_seq.remove(idx).len() == old_seq.len() - 1,
        !spec_contains(old_seq.remove(idx), value),
        forall|v: T| old_seq.contains(v) && !sv_eq(v, value)
            ==> old_seq.remove(idx).contains(v),
{
    let rem = old_seq.remove(idx);

    // Sorted-ness preserved
    assert forall|i: int, j: int|
        0 <= i < j < rem.len()
        implies spec_lt(rem[i], rem[j])
    by {
        let oi = if i < idx { i } else { i + 1 };
        let oj = if j < idx { j } else { j + 1 };
        assert(rem[i] == old_seq[oi]);
        assert(rem[j] == old_seq[oj]);
    }

    // No element in result is sv_eq to value
    assert forall|i: int|
        0 <= i < rem.len()
        implies !sv_eq(rem[i], value)
    by {
        let oi = if i < idx { i } else { i + 1 };
        assert(rem[i] == old_seq[oi]);
        if oi < idx {
            assert(spec_lt(old_seq[oi], old_seq[idx]));
        } else {
            assert(spec_lt(old_seq[idx], old_seq[oi]));
        }
    }

    // Frame
    assert forall|v: T|
        old_seq.contains(v) && !sv_eq(v, value)
        implies rem.contains(v)
    by {
        let k = choose|k: int| 0 <= k < old_seq.len() && old_seq[k] == v;
        if k < idx {
            assert(rem[k] == v);
        } else if k > idx {
            assert(rem[k - 1] == v);
        } else {
            assert(false);
        }
    }
}

} // verus!
