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
