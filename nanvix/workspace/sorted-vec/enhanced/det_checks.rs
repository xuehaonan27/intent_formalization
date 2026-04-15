// ==========================================================================
// Determinism Checks — Spec Nondeterminism Detection
// If Verus FAILS → nondeterminism found → spec incomplete
// If Verus PASSES → spec is deterministic for this function
// ==========================================================================

// DET-1: insert determinism — same input, same pre-state → same result + post-state?
proof fn det_insert<T: Ord>(
    pre: SortedVec<T>, post1: SortedVec<T>, post2: SortedVec<T>,
    value: T, result1: Option<T>, result2: Option<T>,
)
    requires
        pre.inv(),
    ensures
        // If both satisfy insert's ensures...
        (
            // post1 satisfies insert spec
            post1.inv()
            && (result1.is_some() <==> spec_contains(pre@, value))
            && (result1.is_some() ==> {
                &&& pre@.contains(result1.unwrap())
                &&& sv_eq(result1.unwrap(), value)
                &&& post1@.len() == pre@.len()
                &&& spec_contains(post1@, value)
            })
            && (result1.is_none() ==> {
                &&& post1@.len() == pre@.len() + 1
                &&& spec_contains(post1@, value)
            })
            && (forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post1@.contains(v))

            // post2 also satisfies insert spec
            && post2.inv()
            && (result2.is_some() <==> spec_contains(pre@, value))
            && (result2.is_some() ==> {
                &&& pre@.contains(result2.unwrap())
                &&& sv_eq(result2.unwrap(), value)
                &&& post2@.len() == pre@.len()
                &&& spec_contains(post2@, value)
            })
            && (result2.is_none() ==> {
                &&& post2@.len() == pre@.len() + 1
                &&& spec_contains(post2@, value)
            })
            && (forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post2@.contains(v))
        )
        // ...then they must be identical
        ==> (result1 == result2 && post1@ == post2@)
{
    // Empty body — let SMT try to prove
}

// DET-2: remove determinism
proof fn det_remove<T: Ord>(
    pre: SortedVec<T>, post1: SortedVec<T>, post2: SortedVec<T>,
    value: T, result1: Option<T>, result2: Option<T>,
)
    requires
        pre.inv(),
    ensures
        (
            // post1 satisfies remove spec
            post1.inv()
            && (result1.is_some() ==> {
                &&& sv_eq(result1.unwrap(), value)
                &&& post1@.len() == pre@.len() - 1
                &&& !spec_contains(post1@, value)
            })
            && (result1.is_none() ==> {
                &&& !spec_contains(pre@, value)
                &&& post1@ == pre@
            })
            && (forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post1@.contains(v))

            // post2 also satisfies remove spec
            && post2.inv()
            && (result2.is_some() ==> {
                &&& sv_eq(result2.unwrap(), value)
                &&& post2@.len() == pre@.len() - 1
                &&& !spec_contains(post2@, value)
            })
            && (result2.is_none() ==> {
                &&& !spec_contains(pre@, value)
                &&& post2@ == pre@
            })
            && (forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post2@.contains(v))
        )
        ==> (result1 == result2 && post1@ == post2@)
{
    // Empty body — let SMT try to prove
}
