// ==========================================================================
// Spec Gap Tests — sorted-vec sv_eq vs == mismatch
// Inject before closing `} // verus!` in lib.proof.rs
//
// Pattern: ensures = EXACT function ensures (the spec under test)
//          body = assume() witness including bad property
// Verified = gap (spec allows bad scenario)
// Error = spec rejects bad scenario (no gap)
// ==========================================================================

// C1: insert(new) — inserted value not structurally present
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
// Bad property: !post_seq.contains(value) — value absent structurally despite spec_contains
proof fn phi_c1_insert_new_structural_absence<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T,
)
    ensures
        // inv
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        // result.is_none() path (new insertion)
        !spec_contains(pre_seq, value),
        post_seq.len() == pre_seq.len() + 1,
        spec_contains(post_seq, value),
        // frame
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(spec_strictly_sorted(pre_seq));
    assume(pre_seq.len() <= usize::MAX as int);
    assume(spec_strictly_sorted(post_seq));
    assume(post_seq.len() <= usize::MAX as int);
    assume(!spec_contains(pre_seq, value));
    assume(post_seq.len() == pre_seq.len() + 1);
    assume(spec_contains(post_seq, value));
    assume(forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v));
    // BAD PROPERTY: value not structurally in post_seq
    assume(!post_seq.contains(value));
}

// C2: insert(replace) — old element retained, new value not stored
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
// Bad property: !post_seq.contains(value) — new value absent, old stays
proof fn phi_c2_insert_replace_old_retained<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: T,
)
    ensures
        // inv
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        // result.is_some() path (replace)
        spec_contains(pre_seq, value),
        pre_seq.contains(result),
        sv_eq(result, value),
        post_seq.len() == pre_seq.len(),
        spec_contains(post_seq, value),
        // frame
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(spec_strictly_sorted(pre_seq));
    assume(pre_seq.len() <= usize::MAX as int);
    assume(spec_strictly_sorted(post_seq));
    assume(post_seq.len() <= usize::MAX as int);
    assume(spec_contains(pre_seq, value));
    assume(pre_seq.contains(result));
    assume(sv_eq(result, value));
    assume(post_seq.len() == pre_seq.len());
    assume(spec_contains(post_seq, value));
    assume(forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v));
    // BAD PROPERTY: new value not structurally present, old element still there
    assume(!post_seq.contains(value));
    assume(post_seq.contains(result));
}

// C3: insert(replace) — neither old nor new present, third sv_eq element
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
// Bad property: neither value nor result present, phantom sv_eq element instead
proof fn phi_c3_insert_replace_third_element<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: T, phantom: T,
)
    ensures
        // inv
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        // result.is_some() path (replace)
        spec_contains(pre_seq, value),
        pre_seq.contains(result),
        sv_eq(result, value),
        post_seq.len() == pre_seq.len(),
        spec_contains(post_seq, value),
        // frame
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(spec_strictly_sorted(pre_seq));
    assume(pre_seq.len() <= usize::MAX as int);
    assume(spec_strictly_sorted(post_seq));
    assume(post_seq.len() <= usize::MAX as int);
    assume(spec_contains(pre_seq, value));
    assume(pre_seq.contains(result));
    assume(sv_eq(result, value));
    assume(post_seq.len() == pre_seq.len());
    assume(spec_contains(post_seq, value));
    assume(forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v));
    // BAD PROPERTY: neither old nor new present; third sv_eq element instead
    assume(!post_seq.contains(value));
    assume(!post_seq.contains(result));
    assume(sv_eq(phantom, value));
    assume(phantom != value);
    assume(phantom != result);
    assume(post_seq.contains(phantom));
}

// C4: remove — return value not from old sequence
// Target function: SortedVec::remove(&mut self, value: &T) -> Option<T>
// Bad property: !pre_seq.contains(result) — result was never stored
proof fn phi_c4_remove_return_not_pinned<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: T,
)
    ensures
        // inv
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        // result.is_some() path (found)
        sv_eq(result, value),
        post_seq.len() == pre_seq.len() - 1,
        !spec_contains(post_seq, value),
        // frame
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(spec_strictly_sorted(pre_seq));
    assume(pre_seq.len() <= usize::MAX as int);
    assume(spec_strictly_sorted(post_seq));
    assume(post_seq.len() <= usize::MAX as int);
    assume(spec_contains(pre_seq, value));
    assume(sv_eq(result, value));
    assume(post_seq.len() == pre_seq.len() - 1);
    assume(!spec_contains(post_seq, value));
    assume(forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v));
    // BAD PROPERTY: result was never in the old sequence
    assume(!pre_seq.contains(result));
}
