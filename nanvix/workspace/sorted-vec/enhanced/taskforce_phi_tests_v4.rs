// ==========================================================================
// Spec Gap Tests — sorted-vec (v4 FINAL)
// requires + ensures = EXACT mechanical copy from source
// Mapping: old(self)@ → pre_seq, self@ → post_seq, inv() expanded inline
// ==========================================================================

// C1: insert(new) — inserted value not structurally present
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
proof fn phi_c1_insert_new_structural_absence<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    requires
        // old(self).inv()
        spec_strictly_sorted(pre_seq),
        pre_seq.len() <= usize::MAX as int,
    ensures
        // self.inv()
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        // result.is_some() <==> spec_contains(old(self)@, value)
        result.is_some() <==> spec_contains(pre_seq, value),
        // result.is_some() ==> { ... }
        result.is_some() ==> {
            &&& pre_seq.contains(result.unwrap())
            &&& sv_eq(result.unwrap(), value)
            &&& post_seq.len() == pre_seq.len()
            &&& spec_contains(post_seq, value)
        },
        // result.is_none() ==> { ... }
        result.is_none() ==> {
            &&& post_seq.len() == pre_seq.len() + 1
            &&& spec_contains(post_seq, value)
        },
        // forall frame
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    // New insertion path
    assume(!spec_contains(pre_seq, value));
    assume(result is None);
    // Post state
    assume(spec_strictly_sorted(post_seq));
    assume(post_seq.len() <= usize::MAX as int);
    assume(post_seq.len() == pre_seq.len() + 1);
    assume(spec_contains(post_seq, value));
    assume(forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v));
    // BAD PROPERTY
    assume(!post_seq.contains(value));
}

// C2: insert(replace) — old element retained, new value not stored
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
proof fn phi_c2_insert_replace_old_retained<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    requires
        // old(self).inv()
        spec_strictly_sorted(pre_seq),
        pre_seq.len() <= usize::MAX as int,
    ensures
        // self.inv()
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        // result.is_some() <==> spec_contains(old(self)@, value)
        result.is_some() <==> spec_contains(pre_seq, value),
        // result.is_some() ==> { ... }
        result.is_some() ==> {
            &&& pre_seq.contains(result.unwrap())
            &&& sv_eq(result.unwrap(), value)
            &&& post_seq.len() == pre_seq.len()
            &&& spec_contains(post_seq, value)
        },
        // result.is_none() ==> { ... }
        result.is_none() ==> {
            &&& post_seq.len() == pre_seq.len() + 1
            &&& spec_contains(post_seq, value)
        },
        // forall frame
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    // Concrete pre: 3 sorted elements
    assume(pre_seq.len() == 3);
    assume(spec_lt(pre_seq[0], pre_seq[1]));
    assume(spec_lt(pre_seq[1], pre_seq[2]));
    // Replace path: value sv_eq to pre_seq[1] but structurally different
    assume(sv_eq(pre_seq[1], value));
    assume(pre_seq[1] != value);
    assume(spec_contains(pre_seq, value));
    assume(result == Some(pre_seq[1]));
    // BAD PROPERTY: post unchanged — old element stays, new value not stored
    assume(post_seq == pre_seq);
}

// C3: insert(replace) — neither old nor new structurally present
// Target function: SortedVec::insert(&mut self, value: T) -> Option<T>
proof fn phi_c3_insert_replace_third_element<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    requires
        // old(self).inv()
        spec_strictly_sorted(pre_seq),
        pre_seq.len() <= usize::MAX as int,
    ensures
        // self.inv()
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        // result.is_some() <==> spec_contains(old(self)@, value)
        result.is_some() <==> spec_contains(pre_seq, value),
        // result.is_some() ==> { ... }
        result.is_some() ==> {
            &&& pre_seq.contains(result.unwrap())
            &&& sv_eq(result.unwrap(), value)
            &&& post_seq.len() == pre_seq.len()
            &&& spec_contains(post_seq, value)
        },
        // result.is_none() ==> { ... }
        result.is_none() ==> {
            &&& post_seq.len() == pre_seq.len() + 1
            &&& spec_contains(post_seq, value)
        },
        // forall frame
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    // Concrete pre: 3 sorted elements
    assume(pre_seq.len() == 3);
    assume(spec_lt(pre_seq[0], pre_seq[1]));
    assume(spec_lt(pre_seq[1], pre_seq[2]));
    // Replace path
    assume(sv_eq(pre_seq[1], value));
    assume(pre_seq[1] != value);
    assume(spec_contains(pre_seq, value));
    assume(result == Some(pre_seq[1]));
    // BAD PROPERTY: third element — neither old nor new
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
    assume(spec_strictly_sorted(post_seq));
    assume(spec_contains(post_seq, value));
}

// C4: remove — return value not from old sequence
// Target function: SortedVec::remove(&mut self, value: &T) -> Option<T>
proof fn phi_c4_remove_return_not_pinned<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    requires
        // old(self).inv()
        spec_strictly_sorted(pre_seq),
        pre_seq.len() <= usize::MAX as int,
    ensures
        // self.inv()
        spec_strictly_sorted(post_seq),
        post_seq.len() <= usize::MAX as int,
        // result.is_some() ==> { ... }
        result.is_some() ==> {
            &&& sv_eq(result.unwrap(), value)
            &&& post_seq.len() == pre_seq.len() - 1
            &&& !spec_contains(post_seq, value)
        },
        // result.is_none() ==> { ... }
        result.is_none() ==> {
            &&& !spec_contains(pre_seq, value)
            &&& post_seq == pre_seq
        },
        // forall frame
        forall|v: T| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v),
{
    assume(spec_lt_is_strict_total_order::<T>());
    // Concrete pre: 3 sorted elements
    assume(pre_seq.len() == 3);
    assume(spec_lt(pre_seq[0], pre_seq[1]));
    assume(spec_lt(pre_seq[1], pre_seq[2]));
    assume(sv_eq(pre_seq[1], value));
    assume(spec_contains(pre_seq, value));
    // Remove found path — return a fabricated value
    let fake_return: T;
    assume(sv_eq(fake_return, value));
    assume(fake_return != pre_seq[0]);
    assume(fake_return != pre_seq[1]);
    assume(fake_return != pre_seq[2]);
    assume(!pre_seq.contains(fake_return));
    assume(result == Some(fake_return));
    // Post: pre_seq[1] removed
    assume(post_seq.len() == 2);
    assume(post_seq[0] == pre_seq[0]);
    assume(post_seq[1] == pre_seq[2]);
    assume(spec_strictly_sorted(post_seq));
    assume(!spec_contains(post_seq, value));
}
