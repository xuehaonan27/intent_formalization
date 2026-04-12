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
