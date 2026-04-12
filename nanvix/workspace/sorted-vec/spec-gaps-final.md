# Sorted-Vec Spec Gap Analysis

**Source:** `nanvix-verus/src/libs/sorted-vec/src/`
**Date:** 2026-04-12
**Baseline:** 18 verified, 0 errors (1379 total with vstd)
**With φ tests:** 20 verified, 2 errors (2 φ verified = gaps, 2 φ rejected = spec complete)

## Key Spec Design

- `inv()` = `spec_strictly_sorted(self@) && self@.len() <= usize::MAX`
- `sv_eq(a, b)` = Ord-equality: `!spec_lt(a, b) && !spec_lt(b, a)` (not structural `==`)
- `spec_contains(s, v)` = sv_eq-based membership
- `Seq::contains` = structural `==` membership
- Frame conditions use `Seq::contains` (structural), not `spec_contains` (sv_eq)

---

## Gap 1: `insert` — Duplicate replacement not guaranteed ⬛ MEDIUM

**φ:** `phi_insert_duplicate_old_stays` — **Verus: ✅ verified (gap confirmed)**

**Problem:** When inserting a value that is Ord-equal (`sv_eq`) to an existing element but structurally different (e.g., `KeyValue{key:10, payload:"new"}` vs `KeyValue{key:10, payload:"old"}`), the spec allows the sequence to remain completely unchanged — the old element stays, the new value is never stored.

The body does `mem::replace` (via `Vec::remove` + `Vec::insert`), which replaces the old with the new. But the spec only guarantees:
- `spec_contains(self@, value)` — which is sv_eq-based, so the OLD element satisfies this
- `result.unwrap()` is sv_eq to value and was in `old(self)@` — correctly returns old
- `post.len() == pre.len()` — satisfied trivially by no change

**Impact:** For types where Ord-equality doesn't imply structural equality (like `KeyValue`), callers cannot prove the new payload was stored. The existing Rust test `test_insert_duplicate_replaces` checks this at runtime, but the spec doesn't guarantee it.

**Representative Test:**

```rust
proof fn phi_insert_duplicate_old_stays<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    ensures
        // ... insert's full ensures (mechanically copied) ...
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(pre_seq.len() == 3);
    assume(spec_strictly_sorted(pre_seq));
    assume(sv_eq(pre_seq[1], value));
    assume(pre_seq[1] != value);       // structurally different
    assume(result == Some(pre_seq[1])); // return old element

    // ★ BAD: post_seq unchanged — old element stays
    assume(post_seq == pre_seq);
}
// Verus: ✅ verified — spec allows NOT replacing the old element
```

**Fix:** Add to insert's ensures (duplicate case):
```rust
result.is_some() ==> {
    // existing ...
    &&& self@.contains(value)  // structural: the NEW value is in the sequence
},
```

Or equivalently, for the position where the old element was:
```rust
result.is_some() ==> exists|i: int| 0 <= i < self@.len() && self@[i] == value,
```

---

## Gap 2: `insert` — New insertion allows sv_eq-different element ⬛ LOW-MEDIUM

**φ:** `phi_insert_new_wrong_element` — **Verus: ✅ verified (gap confirmed)**

**Problem:** When inserting a truly new value (not a duplicate), the spec requires `spec_contains(self@, value)` which only guarantees something sv_eq to value exists. A degenerate implementation could store a different element `fake` where `sv_eq(fake, value)` but `fake != value`.

**Impact:** Same as Gap 1 but for new insertions. Caller can't prove the exact value they passed is structurally in the sequence.

**Representative Test:**

```rust
proof fn phi_insert_new_wrong_element<T: Ord>(
    pre_seq: Seq<T>, post_seq: Seq<T>, value: T, result: Option<T>,
)
    ensures /* ... insert's full ensures ... */
{
    assume(spec_lt_is_strict_total_order::<T>());
    assume(pre_seq.len() == 2);
    assume(!spec_contains(pre_seq, value));
    assume(result is None);

    // ★ BAD: insert fake element (sv_eq to value but structurally !=)
    assume(post_seq.len() == 3);
    assume(post_seq[0] == pre_seq[0]);
    assume(sv_eq(post_seq[1], value));
    assume(post_seq[1] != value);       // NOT the value we passed
    assume(post_seq[2] == pre_seq[1]);
}
// Verus: ✅ verified — spec allows storing a different-but-sv_eq element
```

**Fix:** Add to insert's ensures (new case):
```rust
result.is_none() ==> {
    // existing ...
    &&& self@.contains(value)  // structural: exact value is stored
},
```

---

## Non-Gaps (Spec Correctly Rejects)

### `insert` — Returning value instead of old element ✅ BLOCKED

**φ:** `phi_insert_duplicate_return_new` — **Verus: ❌ error (spec complete)**

`pre_seq.contains(result.unwrap())` uses structural equality, so returning `value` (which isn't structurally in pre_seq) violates the postcondition. Good.

### `remove` — Dropping non-matching element ✅ BLOCKED

**φ:** `phi_remove_loses_element` — **Verus: ❌ error (spec complete)**

The frame condition `forall|v| pre_seq.contains(v) && !sv_eq(v, value) ==> post_seq.contains(v)` correctly prevents losing any non-matching element. Good.

---

## Root Cause Analysis

Both gaps stem from the same root cause: **the spec uses `spec_contains` (sv_eq-based) where it should use `Seq::contains` (structural `==`)** to guarantee the exact value is stored.

The frame condition correctly uses `Seq::contains` — that's why it successfully blocks element loss (φ2, φ3). But the "value is present" postcondition uses `spec_contains`, which only guarantees sv_eq membership.

For types where `sv_eq` ≡ `==` (like `i32`), these gaps are invisible. They only manifest for types where Ord-equality is coarser than structural equality (like `KeyValue` where `Ord` compares by key only).

---

## Summary

| # | Target | Gap | Severity | Verified |
|---|--------|-----|----------|----------|
| 1 | `insert` (duplicate) | Old element not replaced | Medium | ✅ φ1 |
| 2 | `insert` (new) | sv_eq-different element stored | Low-med | ✅ φ4 |
| — | `insert` (return value) | Returning non-old element | N/A | ❌ φ2 (blocked) |
| — | `remove` (frame) | Losing non-matching element | N/A | ❌ φ3 (blocked) |
