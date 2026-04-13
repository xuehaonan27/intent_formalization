// ==========================================================================
// Spec Gap Tests — sorted-vec sv_eq vs == mismatch (CORRECTED v3)
// ensures = EXACT mechanical copy from source, not LLM-written
// Inject before closing `} // verus!` in lib.proof.rs
// ==========================================================================

// C1: insert(new) — inserted value not structurally present
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
proof fn phi_c1_insert_new_structural_absence<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    ensures
        // EXACT ensures from insert — mechanical copy
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        result.is_some() <==> spec_contains(pre_seq, value),
        result.is_some() ==> {
            &&& pre_seq.contains(result.unwrap())
            &&& sv_eq(result.unwrap(), value)
            &&& post_seq.len() == pre_seq.len()
            &&& spec_contains(post_seq, value)
        },
        result.is_none() ==> {
            &&& post_seq.len() == pre_seq.len() + 1
            &&& spec_contains(post_seq, value)
        },
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(spec_strictly_sorted(pre_seq));
    assume(pre_seq.len() <= usize::MAX as int);
    // New insertion path: value not in pre
    assume(!spec_contains(pre_seq, value));
    assume(result is None);
    // Post state satisfying spec
    assume(spec_strictly_sorted(post_seq));
    assume(post_seq.len() <= usize::MAX as int);
    assume(post_seq.len() == pre_seq.len() + 1);
    assume(spec_contains(post_seq, value));
    assume(forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v));
    // BAD PROPERTY: value not structurally present
    assume(!post_seq.contains(value));
}

// C2: insert(replace) — old element retained, new value not stored
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
proof fn phi_c2_insert_replace_old_retained<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    ensures
        // EXACT ensures from insert — mechanical copy
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        result.is_some() <==> spec_contains(pre_seq, value),
        result.is_some() ==> {
            &&& pre_seq.contains(result.unwrap())
            &&& sv_eq(result.unwrap(), value)
            &&& post_seq.len() == pre_seq.len()
            &&& spec_contains(post_seq, value)
        },
        result.is_none() ==> {
            &&& post_seq.len() == pre_seq.len() + 1
            &&& spec_contains(post_seq, value)
        },
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(spec_strictly_sorted(pre_seq));
    assume(pre_seq.len() <= usize::MAX as int);
    assume(pre_seq.len() == 3);
    assume(spec_lt(pre_seq[0], pre_seq[1]));
    assume(spec_lt(pre_seq[1], pre_seq[2]));
    // Replace path: value sv_eq to pre_seq[1] but structurally different
    assume(sv_eq(pre_seq[1], value));
    assume(pre_seq[1] != value);
    assume(spec_contains(pre_seq, value));
    assume(result == Some(pre_seq[1]));
    // Post: sequence unchanged — old element stays
    assume(post_seq == pre_seq);
}

// C3: insert(replace) — neither old nor new structurally present
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
proof fn phi_c3_insert_replace_third_element<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    ensures
        // EXACT ensures from insert — mechanical copy
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        result.is_some() <==> spec_contains(pre_seq, value),
        result.is_some() ==> {
            &&& pre_seq.contains(result.unwrap())
            &&& sv_eq(result.unwrap(), value)
            &&& post_seq.len() == pre_seq.len()
            &&& spec_contains(post_seq, value)
        },
        result.is_none() ==> {
            &&& post_seq.len() == pre_seq.len() + 1
            &&& spec_contains(post_seq, value)
        },
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(pre_seq.len() == 3);
    assume(spec_lt(pre_seq[0], pre_seq[1]));
    assume(spec_lt(pre_seq[1], pre_seq[2]));
    assume(spec_strictly_sorted(pre_seq));
    assume(pre_seq.len() <= usize::MAX as int);
    // Replace path
    assume(sv_eq(pre_seq[1], value));
    assume(pre_seq[1] != value);
    assume(spec_contains(pre_seq, value));
    assume(result == Some(pre_seq[1]));
    // Post: a third element (ghost_elem) at position 1 — neither old nor new
    let ghost_elem: T;
    assume(sv_eq(ghost_elem, value));
    assume(ghost_elem != value);
    assume(ghost_elem != pre_seq[1]);
    assume(spec_lt(pre_seq[0], ghost_elem));
    assume(spec_lt(ghost_elem, pre_seq[2]));
    assume(post_seq.len() == 3);
    assume(post_seq[0] == pre_seq[0]);
    assume(post_seq[1] == ghost_elem);
    assume(post_seq[2] == pre_seq[2]);
}

// C4: remove — return value not from old sequence
// Target function: SortedVec::remove(&mut self, value: &T) -> Option<T>
proof fn phi_c4_remove_return_not_pinned<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    ensures
        // EXACT ensures from remove — mechanical copy
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        result.is_some() ==> {
            &&& sv_eq(result.unwrap(), value)
            &&& post_seq.len() == pre_seq.len() - 1
            &&& !spec_contains(post_seq, value)
        },
        result.is_none() ==> {
            &&& !spec_contains(pre_seq, value)
            &&& post_seq == pre_seq
        },
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(pre_seq.len() == 3);
    assume(spec_lt(pre_seq[0], pre_seq[1]));
    assume(spec_lt(pre_seq[1], pre_seq[2]));
    assume(spec_strictly_sorted(pre_seq));
    assume(pre_seq.len() <= usize::MAX as int);
    assume(sv_eq(pre_seq[1], value));
    assume(spec_contains(pre_seq, value));
    // Remove found path
    let fake_return: T;
    assume(sv_eq(fake_return, value));
    assume(fake_return != pre_seq[0]);
    assume(fake_return != pre_seq[1]);
    assume(fake_return != pre_seq[2]);
    assume(!pre_seq.contains(fake_return));
    assume(result == Some(fake_return));
    // Post: pre_seq[1] removed, keep pre_seq[0] and pre_seq[2]
    assume(post_seq.len() == 2);
    assume(post_seq[0] == pre_seq[0]);
    assume(post_seq[1] == pre_seq[2]);
    assume(spec_strictly_sorted(post_seq));
    assume(!spec_contains(post_seq, value));
}
