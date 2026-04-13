// ==========================================================================
// Spec Gap Tests — sorted-vec (v5 FINAL)
// Uses SortedVec<T> directly. requires/ensures verbatim from source.
// Only change: old(self) → pre, self → post (two immutable snapshots).
// ==========================================================================

// C1: insert(new) — inserted value not structurally present
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
proof fn phi_c1_insert_new_structural_absence<T: Ord>(
    pre: SortedVec<T>, post: SortedVec<T>, value: T, result: Option<T>,
)
    requires
        pre.inv(),
    ensures
        post.inv(),
        result.is_some() <==> spec_contains(pre@, value),
        result.is_some() ==> {
            &&& pre@.contains(result.unwrap())
            &&& sv_eq(result.unwrap(), value)
            &&& post@.len() == pre@.len()
            &&& spec_contains(post@, value)
        },
        result.is_none() ==> {
            &&& post@.len() == pre@.len() + 1
            &&& spec_contains(post@, value)
        },
        forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post@.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    // New insertion path
    assume(!spec_contains(pre@, value));
    assume(result is None);
    // Post state
    assume(post.inv());
    assume(post@.len() == pre@.len() + 1);
    assume(spec_contains(post@, value));
    assume(forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post@.contains(v));
    // BAD PROPERTY: value not structurally present
    assume(!post@.contains(value));
}

// C2: insert(replace) — old element retained, new value not stored
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
proof fn phi_c2_insert_replace_old_retained<T: Ord>(
    pre: SortedVec<T>, post: SortedVec<T>, value: T, result: Option<T>,
)
    requires
        pre.inv(),
    ensures
        post.inv(),
        result.is_some() <==> spec_contains(pre@, value),
        result.is_some() ==> {
            &&& pre@.contains(result.unwrap())
            &&& sv_eq(result.unwrap(), value)
            &&& post@.len() == pre@.len()
            &&& spec_contains(post@, value)
        },
        result.is_none() ==> {
            &&& post@.len() == pre@.len() + 1
            &&& spec_contains(post@, value)
        },
        forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post@.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    // Concrete pre: 3 sorted elements
    assume(pre@.len() == 3);
    assume(spec_lt(pre@[0], pre@[1]));
    assume(spec_lt(pre@[1], pre@[2]));
    // Replace path: value sv_eq to pre@[1] but structurally different
    assume(sv_eq(pre@[1], value));
    assume(pre@[1] != value);
    assume(spec_contains(pre@, value));
    assume(result == Some(pre@[1]));
    // BAD PROPERTY: post unchanged — old element stays, new value not stored
    assume(post@ == pre@);
}

// C3: insert(replace) — neither old nor new structurally present
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
proof fn phi_c3_insert_replace_third_element<T: Ord>(
    pre: SortedVec<T>, post: SortedVec<T>, value: T, result: Option<T>,
)
    requires
        pre.inv(),
    ensures
        post.inv(),
        result.is_some() <==> spec_contains(pre@, value),
        result.is_some() ==> {
            &&& pre@.contains(result.unwrap())
            &&& sv_eq(result.unwrap(), value)
            &&& post@.len() == pre@.len()
            &&& spec_contains(post@, value)
        },
        result.is_none() ==> {
            &&& post@.len() == pre@.len() + 1
            &&& spec_contains(post@, value)
        },
        forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post@.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    // Concrete pre: 3 sorted elements
    assume(pre@.len() == 3);
    assume(spec_lt(pre@[0], pre@[1]));
    assume(spec_lt(pre@[1], pre@[2]));
    // Replace path
    assume(sv_eq(pre@[1], value));
    assume(pre@[1] != value);
    assume(spec_contains(pre@, value));
    assume(result == Some(pre@[1]));
    // BAD PROPERTY: third element — neither old nor new
    let ghost_elem: T;
    assume(sv_eq(ghost_elem, value));
    assume(ghost_elem != value);
    assume(ghost_elem != pre@[1]);
    assume(spec_lt(pre@[0], ghost_elem));
    assume(spec_lt(ghost_elem, pre@[2]));
    assume(post@.len() == 3);
    assume(post@[0] == pre@[0]);
    assume(post@[1] == ghost_elem);
    assume(post@[2] == pre@[2]);
    assume(spec_strictly_sorted(post@));
    assume(spec_contains(post@, value));
}

// C4: remove — return value not from old sequence
// Target function: SortedVec::remove(&mut self, value: &T) -> Option<T>
proof fn phi_c4_remove_return_not_pinned<T: Ord>(
    pre: SortedVec<T>, post: SortedVec<T>, value: T, result: Option<T>,
)
    requires
        pre.inv(),
    ensures
        post.inv(),
        result.is_some() ==> {
            &&& sv_eq(result.unwrap(), value)
            &&& post@.len() == pre@.len() - 1
            &&& !spec_contains(post@, value)
        },
        result.is_none() ==> {
            &&& !spec_contains(pre@, value)
            &&& post@ == pre@
        },
        forall|v: T| pre@.contains(v) && !sv_eq(v, value) ==> post@.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    // Concrete pre: 3 sorted elements
    assume(pre@.len() == 3);
    assume(spec_lt(pre@[0], pre@[1]));
    assume(spec_lt(pre@[1], pre@[2]));
    assume(sv_eq(pre@[1], value));
    assume(spec_contains(pre@, value));
    // Remove found path — return a fabricated value
    let fake_return: T;
    assume(sv_eq(fake_return, value));
    assume(fake_return != pre@[0]);
    assume(fake_return != pre@[1]);
    assume(fake_return != pre@[2]);
    assume(!pre@.contains(fake_return));
    assume(result == Some(fake_return));
    // Post: pre@[1] removed
    assume(post@.len() == 2);
    assume(post@[0] == pre@[0]);
    assume(post@[1] == pre@[2]);
    assume(spec_strictly_sorted(post@));
    assume(!spec_contains(post@, value));
}
