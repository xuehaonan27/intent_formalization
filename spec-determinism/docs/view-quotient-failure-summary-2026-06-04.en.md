# View-quotient determinism — failure case summary (2026-06-04)


## 1. Overview

| # | Function | Why it fails (one sentence) | Suggested fix |
|---|----------|-----------------------------|---------------|
| 1 | [`StaticLinkedList::len`](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L65) (atmosphere) | An ensures clause reads the hidden field `value_list_len` directly, and the function has no `requires` constraining the precondition | Add `requires self.wf()`, or drop the ensures clause that reads the hidden field |
| 2 | [`DelegationMap::get_internal`](../../verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs#L238) (ironkv) | The `glb` component of ensures depends on the internal structure of the hidden field `lows`, and `valid()` allows `lows` to map two distinct keys to the same endpoint | Tighten `valid()` to forbid this redundancy, or rewrite the ensures so that `glb` is also determined by the view |

Both cases have been mechanically confirmed: see the self-contained Verus witnesses under [`spec-determinism/witnesses/`](../witnesses/). Each witness composes the function's `ensures` for two independent calls and asks Verus to discharge the Step-2 obligation; the obligation that should fail does fail with a "postcondition not satisfied" error, while the Step-1 counterpart and the rescued sub-obligations verify.

| witness file | expected outcome (Verus) |
|---|---|
| [`len_witness.rs`](../witnesses/len_witness.rs) | `2 verified, 1 errors` — `step2_len_check` rejects |
| [`get_internal_witness.rs`](../witnesses/get_internal_witness.rs) | `6 verified, 1 errors` — `step2_get_internal_glb_check` rejects; `step2_get_internal_id_check` verifies (id rescued by `id@ == self@[*k]`) |

---

## 2. Case 1: `StaticLinkedList::len`

Source: [`atmosphere/.../free_pages_are_not_mapped.rs`](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs) — struct at [L42](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L42), `len` at [L65](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L65), `view` at [L82](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L82).

### 2.1 Struct

```rust
struct StaticLinkedList<T, N> {
    spec_seq:       Ghost<Seq<T>>,   // view fields = {spec_seq}
    value_list_len: usize,           // hidden
    head, tail, free_head, ...       // hidden
}
spec fn view(self) -> Seq<T> { self.spec_seq@ }
```

### 2.2 Function

```rust
fn len(&self) -> (l: usize)
    ensures
        l == self.value_list_len,            // (E1) directly exposes a hidden field
        self.wf() ==> l == self@.len(),      // (E2) conditional; aligns with the view only under wf
```

The function has **no `requires`**. (E2) is conditional: once the input fails `wf()`, it degenerates to `true`, leaving only (E1), which constrains a hidden field and says nothing about the view side.

### 2.3 Minimal counterexample

Let both `s1` and `s2` have `spec_seq@` equal to the empty sequence, with `value_list_len` set to `0` and `7` respectively; other fields are arbitrary. Neither state satisfies `wf()`, but because there is no precondition enforcing `wf()`, both calls are legal inputs.

- `pre1@ == pre2@ == ε` ✓
- Both satisfy ensures (only (E1) is active; (E2) trivially holds)
- `r1 = 0`, `r2 = 7`; `usize` has no view, so comparison falls back to `==` — fails.

### 2.4 This is a real spec defect

The spec of `len` promises to return `value_list_len`, but that field is garbage in non-wf states. Any caller relying on `len`'s return value without first establishing `self.wf()` is depending on undefined behaviour. The minimal fix is a single `requires self.wf()`: it has no side effects and tightens both (E1) and (E2) at the same time.

---

## 3. Case 2: `DelegationMap::get_internal`

Source: [`ironkv/.../delegation_map_v__impl4__set.rs`](../../verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs) — `StrictlyOrderedMap` at [L120](../../verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs#L120), `DelegationMap` at [L212](../../verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs#L212), `get_internal` at [L238](../../verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs#L238), `KeyIterator` at [L545](../../verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs#L545).

### 3.1 Struct

```rust
struct DelegationMap<K> {
    lows: StrictlyOrderedMap<K>,        // hidden: actual run-length encoding
    m:    Ghost<Map<K, AbstractEndPoint>>,
}
spec fn view(self) -> Map<K, AbstractEndPoint> { self.m@ }
```

### 3.2 Function

```rust
fn get_internal(&self, k: &K) -> (res: (ID, Ghost<KeyIterator<K>>))
    requires self.valid(),
    ensures ({
        let (id, glb) = res;
        &&& id@ == self@[*k]                                          // (E1) view-only
        &&& self.lows.greatest_lower_bound_spec(KI(*k), glb@)         // (E2) reads lows
        &&& id@.valid_physical_address()
    })
```

When comparing return values, `id` has a view, so we compare `id@`; `glb` is wrapped in a `Ghost`, and the inner `KeyIterator` has **no view**, so comparison falls back to structural `==`.

### 3.3 Where the defect lies

The (E2) clause `self.lows.greatest_lower_bound_spec(KI(*k), glb@)` is **a property defined directly on the view-invisible field `self.lows`** — its value depends on the internal structure of `lows`. Two view-equal states can have different `lows`, and therefore produce different `glb` while both satisfying the same ensures clause.

### 3.4 Minimal counterexample

Fix the constant view `m@ = K → ep_x`:

| state | `lows.keys` | `lows@` | `valid()` |
|-------|-------------|---------|:---------:|
| `s1`  | `[K::zero]` | `{K::zero ↦ ep_x}` | ✓ |
| `s2`  | `[K::zero, k₅]` | `{K::zero ↦ ep_x, k₅ ↦ ep_x}` | ✓ |

In `s2`, `K::zero` and `k₅` are distinct keys that both map to `ep_x` — the internal structure of `lows` differs across two view-equal states.

Query `*k = k₆` with `k₅ < k₆`:
- `glb1 = KI::new(K::zero)` (the greatest key in `s1.lows@.dom()` that is `< k₆`)
- `glb2 = KI::new(k₅)` (the greatest key in `s2.lows@.dom()` that is `< k₆`)

`id1@ = id2@ = ep_x` ✓, but `glb1 ≠ glb2` — the `glb` component breaks.

### 3.5 Fixes

- **Strengthen `valid()`**: add a clause requiring adjacent keys in `lows` to map to different endpoints (equivalently, `lows.dom` is the canonical RLE of `m@`). `s2` becomes invalid and the counterexample disappears.
- **Rewrite ensures**: make `glb` derivable from `m@`, e.g. return "the left endpoint of the maximal equal-value run containing `*k`", bypassing the internal structure of `lows`.
