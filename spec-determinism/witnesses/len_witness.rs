// View-quotient determinism witness for StaticLinkedList::len
//
// Models the relevant fragment of the spec from
//   verusage/source-projects/atmosphere/verified/allocator/
//     allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs
//
// The proof obligation `step2_len_check` should FAIL verification, confirming
// that len's spec is not view-quotient deterministic.
// `step1_len_check` should pass (the existing concrete-input check).

use vstd::prelude::*;

fn main() {}

verus! {

pub struct SLL<T> {
    pub spec_seq: Ghost<Seq<T>>,
    pub value_list_len: usize,
}

impl<T> SLL<T> {
    pub open spec fn view(&self) -> Seq<T> { self.spec_seq@ }

    #[verifier::external_body]
    pub closed spec fn wf(&self) -> bool { unimplemented!() }
}

// Step 1: concrete-input determinism for len.
// Inputs are equal (s1 == s2). Both returns satisfy ensures of len.
// Expected: VERIFIES.
proof fn step1_len_check<T>(s1: SLL<T>, s2: SLL<T>, r1: usize, r2: usize)
    requires
        s1 == s2,
        r1 == s1.value_list_len,
        s1.wf() ==> r1 == s1@.len(),
        r2 == s2.value_list_len,
        s2.wf() ==> r2 == s2@.len(),
    ensures r1 == r2,
{
}

// Step 2: view-quotient determinism for len.
// Inputs only have to agree on view (s1@ == s2@), not on hidden fields.
// Expected: FAILS — value_list_len can differ between view-equal states.
proof fn step2_len_check<T>(s1: SLL<T>, s2: SLL<T>, r1: usize, r2: usize)
    requires
        s1@ == s2@,
        r1 == s1.value_list_len,
        s1.wf() ==> r1 == s1@.len(),
        r2 == s2.value_list_len,
        s2.wf() ==> r2 == s2@.len(),
    ensures r1 == r2,
{
}

// Step 2 with the proposed fix `requires self.wf()`.
// Now the (E2) clause is unconditional, tying r to self@.len().
// Expected: VERIFIES.
proof fn step2_len_check_fixed<T>(s1: SLL<T>, s2: SLL<T>, r1: usize, r2: usize)
    requires
        s1.wf(),
        s2.wf(),
        s1@ == s2@,
        r1 == s1.value_list_len,
        r1 == s1@.len(),
        r2 == s2.value_list_len,
        r2 == s2@.len(),
    ensures r1 == r2,
{
}

}
