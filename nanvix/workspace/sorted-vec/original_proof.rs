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
