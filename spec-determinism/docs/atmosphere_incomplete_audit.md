# Atmosphere `incomplete` per-case audit

Total: **29 entries** across **14 unique fn templates**.
All carry `permitted_reason=permissive_or`, traced to the closed spec fn `page_is_mapped`
which uses `|||` for set-membership disjunction:

```rust
pub open spec fn page_is_mapped(&self, p: PagePtr) -> bool {
    ||| self.mapped_pages_4k().contains(p)
    ||| self.mapped_pages_2m().contains(p)
    ||| self.mapped_pages_1g().contains(p)
}
```
This `|||` is pure boolean disjunction (deterministic).
The `permissive_or` detector hit the right verdict (`incomplete`) for the wrong syntactic reason.

**Two real non-determinism patterns:**
- **Pattern A — allocation choice**: ensures only constrains `ret` to lie in a non-singleton set. Any element is legal.
- **Pattern B — `Seq` ordering free**: ensures pins `Set`-level view but underlying field is `StaticLinkedList<T,N>` whose `View=Seq<T>` — order of insert/remove is unspecified.

**Pattern A is further split:**
- **A0** = spec bug: ensures fails to pin `ret ∈ old.free_pages_*`; admits pathological impl returning a non-free page (e.g. overwrites mapped page). Must be fixed in the spec.
- **A1** = symmetric alloc choice: with `|free_pages_*|≥2`, multiple legal alloc choices give different but symmetric post-states. Can be folded via a choice-equivalence extension to `det_equal`.

A1 is implicitly excluded by any one of three ret-pinning mechanisms:
1. Explicit `contains(ret)` clause;
2. `Tracked<PagePerm*>` returned for `ret` (linear-resource forces ret ∈ free perm pool);
3. `self.free_pages_*.len() == old.len() - 1` combined with `wf.free_pages_*.unique()` (Seq=Set cardinality, proof by contradiction).

---

## A0 verdicts (genuine spec bugs — KEEP for fix)

| fn | entries | A0 source | A1 also | Witness |
|---|---:|---|---|---|
| `alloc_and_map_2m` | 1 | No `contains(ret)`, no `len()-1`, no `Tracked<PagePerm2m>` returned — admits "overwrite already-mapped 2m page" | ✅ | §`alloc_and_map_2m` below: full witness with `page_array[0]=Free2m, page_array[1]=Mapped2m`, Impl A returns p0, Impl B returns p1 |
| `merged_4k_to_2m` | 1 | ensures references **neither** `target_ptr` **nor** `target_page_idx`; only `.len() ==` counts on `free_pages_4k/2m`; admits impl that ignores target and merges any 2m-aligned all-Free4k block | ✅ | §`merged_4k_to_2m` below: full witness with two free 2m-blocks at indices 0 and 512, Impl A merges block at 0, Impl B merges block at 512 |
| `remove_io_mapping_4k_helper1` | 1 | ensures completely omits `page_array[idx].state`, `mapped_pages_4k()`, `free_pages_4k()`, `page_perms_4k`; wf is biconditional state↔set but allows any consistent assignment; admits impl that recycles target into Free4k rather than Unavailable4k | ✅ | §`remove_io_mapping_4k_helper1` below: full witness with Impl A choosing Unavailable4k vs Impl B choosing Free4k via proof-block ghost write |

**Total A0**: 3 entries (out of 29).

## Pattern A `A1-only` verdicts (no spec bug, only symmetric alloc choice)

| fn | entries | Ret-pinning mechanism |
|---|---:|---|
| `alloc_page_4k` | 8 | Explicit `contains(ret.0)` + LEN-1 + Tracked `PagePerm4k` |
| `alloc_page_4k_for_new_container` | 2 | Explicit `contains(ret.0)` + LEN-1 + Tracked `PagePerm4k` |
| `alloc_page_2m` | 1 | Tracked `PagePerm2m` returned (linear perm forces ret ∈ free perm pool); no explicit `contains` clause but perm linearity implies it |
| `alloc_and_map_4k` | 2 | LEN-1 + `!old.page_is_mapped(ret)` + `!old.allocated_pages_4k().contains(ret)` ⇒ ret ∈ old.free_pages_4k (proof by contradiction) |
| `alloc_and_map_io_4k` | 2 | LEN-1 + `!old.page_is_mapped(ret)` + `!old.allocated_pages_4k().contains(ret)` ⇒ same |

**Total Pattern A1-only**: 15 entries. Excludable via `det_equal` choice-equivalence.

---

## ⚠️ Cross-cutting observation: setter vs public-API ensures inconsistency

**Worth raising with the spec author.**

In every `impl2__*.rs` file we audited, the file contains both:

1. **Low-level setters** (marked `#[verifier(external_body)]`, e.g. `set_state`, `set_io_mapping`, `set_mapping`, `set_ref_count`, `set_owning_container`, `set_rev_pointer`): their ensures use **field-level `==`** equality on every state field they don't touch — including `self.free_pages_4k == old(self).free_pages_4k` (Seq-level equality), plus all ghost / tracked maps.

2. **Public APIs that compose these setters** (e.g. `add_io_mapping_4k`, `add_mapping_4k`, `alloc_and_map_4k`, `free_page_4k`, `merged_4k_to_2m`): their ensures use the **closed spec fn `=~=`** comparison, i.e. `self.free_pages_4k() =~= old(self).free_pages_4k()` (Set-level equality, where `free_pages_4k()` is `closed spec fn → Set<PagePtr> = self.free_pages_4k@.to_set()`).

### Example: `add_io_mapping_4k.rs` lines 580-583 vs 801-815

```rust
// Public API add_io_mapping_4k.ensures (line 580-583):
self.free_pages_4k.len() == old(self).free_pages_4k.len(),  // field .len() — Seq
self.free_pages_4k() =~= old(self).free_pages_4k(),         // closed spec fn — Set
self.free_pages_2m() =~= old(self).free_pages_2m(),         // Set
self.free_pages_1g() =~= old(self).free_pages_1g(),         // Set

// Underlying setter set_io_mapping.ensures (line 801-815):
self.free_pages_4k == old(self).free_pages_4k,    // field == — Seq order PINNED
self.free_pages_2m == old(self).free_pages_2m,    // Seq order PINNED
self.free_pages_1g == old(self).free_pages_1g,    // Seq order PINNED
self.allocated_pages_4k == old(self).allocated_pages_4k,   // Ghost<Set>: full eq
self.mapped_pages_4k    == old(self).mapped_pages_4k,
self.page_perms_4k      == old(self).page_perms_4k,         // Tracked<Map>: full eq
self.container_map_4k   == old(self).container_map_4k,
// ... all 12+ ghost/tracked fields with ==
```

### Implication

- The **actual impl** of `add_io_mapping_4k` is constrained — it can only modify state through these setters, which preserve `free_pages_4k` at Seq level (and even at ghost-map identity level for the perms/containers).
- The **public spec** of `add_io_mapping_4k`, however, only relays Set-level preservation to the verifier and to callers. It silently **weakens** what its own implementation provably guarantees.
- Our det check therefore sees admissible "passive B-Seq permutation" of `free_pages_*` — purely because the public ensures is weaker than the setter ensures, **not** because any real impl could permute the list.

### Open question for the developer

1. **Is the weak public ensures intentional?** (e.g., to allow future impls that don't go through these setters, or to keep proof obligations lighter)
2. **Or is it accidental** — should the public API ensures simply mirror the setters, i.e. write `self.free_pages_4k == old(self).free_pages_4k` (Seq) instead of `self.free_pages_4k() =~= old(self).free_pages_4k()` (Set)?
3. **If accidental**: tightening the public ensures to `==` would directly close the "B-Seq passive" non-determinism without any det_equal extension. The same applies to `add_mapping_4k`, `add_io_mapping_4k`, the `remove_*_helper*` family, and possibly more.

Affected functions (use weak `=~=` Set ensures where the underlying setter gives strong `==` Seq):
- `add_io_mapping_4k`
- `add_mapping_4k`
- `remove_io_mapping_4k_helper1`
- `remove_mapping_4k_helper1/2/3`
- `free_page_4k`
- `alloc_and_map_4k`, `alloc_and_map_io_4k`, `alloc_and_map_2m`
- `alloc_page_4k`, `alloc_page_4k_for_new_container`, `alloc_page_2m`
- `merged_4k_to_2m`

(i.e., essentially every public API in `page_allocator_spec_impl::impl2`.)

### Why this matters for our paper / claims

If the answer is "should be `==`", then the **"B-Seq" bucket in our atmosphere taxonomy is largely an authoring artifact, not a real spec design choice**. The "incomplete" classification persists for these cases at the spec level, but the fix is mechanical (s/=~=/==/ in ensures) rather than requiring a det_equal extension.

The **A0 bugs** (`alloc_and_map_2m`, `merged_4k_to_2m`) remain genuine spec design issues regardless — they involve missing constraints that tightening `=~=` to `==` would NOT fix.

---

## `alloc_and_map_2m`  — Pattern **A**  (1 entry)

**Preliminary verdict**: `real` non-determinism.  
**Underconstrained element**: Same: `old(self).free_pages_2m().contains(ret)`.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_2m.rs`

```rust
    pub fn alloc_and_map_2m(&mut self, pcid: Pcid, va: VAddr, c_ptr: ContainerPtr) -> (ret: PagePtr)
        requires
            old(self).wf(),
            old(self).free_pages_2m.len() > 0,
            old(self).container_map_2m@.dom().contains(c_ptr),
        ensures
            self.wf(),
            // self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_2m() =~= old(self).free_pages_2m().remove(ret),
            self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_1g() =~= old(self).free_pages_1g(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            self.mapped_pages_4k() =~= old(self).mapped_pages_4k(),
            self.mapped_pages_2m() =~= old(self).mapped_pages_2m().insert(ret),
            self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
            forall|p: PagePtr|
                self.page_is_mapped(p) && p != ret ==> self.page_mappings(p) =~= old(
                    self,
                ).page_mappings(p) && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            self.page_mappings(ret) =~= Set::<(Pcid, VAddr)>::empty().insert((pcid, va)),
            self.page_io_mappings(ret) =~= Set::<(IOid, VAddr)>::empty(),
    {
```

**Audit notes**:

`alloc_and_map_2m`'s ensures has **two independent sources of non-determinism**:

**A0 (spec bug — missing `contains(ret)` constraint)**: unlike its sibling
`alloc_page_4k` which explicitly says `old(self).free_pages_4k().contains(ret.0)`,
`alloc_and_map_2m` has **no such clause** for `ret`. The only constraint linking
`ret` to `old.free_pages_2m` is `self.free_pages_2m() =~= old.free_pages_2m().remove(ret)`,
which is consistent both when `ret ∈ old.free_pages_2m` and when `ret ∉ old.free_pages_2m`
(`.remove(ret)` is a no-op in the latter case). This allows an `Impl B` to
return a ptr that's **already mapped** in `old(self)`, overwriting its mapping
entry rather than consuming from the free pool.

**A1 (symmetric alloc choice)**: even assuming `ret ∈ old.free_pages_2m`,
if `|old.free_pages_2m| ≥ 2`, any element is a legal choice and produces
distinct (but symmetric) post-states. Under a "choice-equivalence" extension
to `det_equal`, A1 alone could be normalized away.

**Concrete witness for A0** (same `old(self)` input, two legal post-states):

Setup `old(self)` with `NUM_PAGES = 4`:

| idx | addr | state       | mappings              | io_mappings | ref_count | owning_container |
|-----|------|-------------|-----------------------|-------------|-----------|------------------|
| 0   | p0   | Free2m      | ∅                     | ∅           | 0         | None             |
| 1   | p1   | Mapped2m    | {(pcid_x, va_x)}      | ∅           | 1         | Some(c0)         |
| 2   | p2   | Unavailable | ∅                     | ∅           | 0         | None             |
| 3   | p3   | Unavailable | ∅                     | ∅           | 0         | None             |

Derived views:
- `old.free_pages_2m@ = [p0]`  (satisfies `len() > 0`)
- `old.mapped_pages_2m@ = {p1}`
- `old.allocated_pages_2m@ = ∅`
- `old.page_perms_2m@.dom() = {p0, p1}`
- `old.container_map_2m@ ⊇ {c0 ↦ …}`
- All 4k / 1g sets empty (wf-consistent)

`old.wf()` holds. Call `alloc_and_map_2m(self, pcid, va, c0)` with `(pcid, va) ≠ (pcid_x, va_x)`.

**Impl A** (natural — allocates from free): returns `ret = p0`.

Post-state changes:
- `page_array@[0].state` → `Mapped2m`; `mappings` → `{(pcid, va)}`; `ref_count` → 1; `owning_container` → `Some(c0)`
- `page_array@[1]` unchanged
- `free_pages_2m@` = `[]`; `mapped_pages_2m@` = `{p0, p1}`

**Impl B** (spec-permitted but pathological — overwrites already-mapped page):
returns `ret = p1`.

Post-state changes:
- `page_array@[1].mappings` overwritten to `{(pcid, va)}`; `io_mappings` overwritten to `∅`; state remains `Mapped2m`; `ref_count` stays 1; `owning_container` stays `Some(c0)`
- `page_array@[0]` unchanged
- `free_pages_2m@` = `[p0]` (unchanged); `mapped_pages_2m@` = `{p1}` (unchanged)

**Ensures verification for Impl B**:

| ensures clause                                                     | LHS                  | RHS                                    | ✓ |
|--------------------------------------------------------------------|----------------------|----------------------------------------|---|
| `self.free_pages_2m() =~= old.free_pages_2m().remove(ret)`         | `{p0}`               | `{p0}.remove(p1) = {p0}`               | ✓ |
| `self.mapped_pages_2m() =~= old.mapped_pages_2m().insert(ret)`     | `{p1}`               | `{p1}.insert(p1) = {p1}`               | ✓ |
| `self.page_mappings(ret) =~= {(pcid, va)}`                         | `{(pcid, va)}`       | `{(pcid, va)}`                         | ✓ |
| `self.page_io_mappings(ret) =~= ∅`                                 | `∅`                  | `∅`                                    | ✓ |
| `forall p, page_is_mapped(p) ∧ p ≠ ret ⇒ mappings preserved`       | only `p1` mapped, `p1 = ret` excluded | vacuous            | ✓ |
| `free_pages_4k/1g, allocated_*, mapped_4k/1g =~= old.*`             | all unchanged        | all `=~= old.*`                        | ✓ |

`self.wf()` per sub-invariant:

| sub-invariant                          | check                                                              | ✓ |
|----------------------------------------|--------------------------------------------------------------------|---|
| `mapped_pages_2m_wf`                   | `p1 ∈ mapped_pages_2m` ∧ `page_array[1].state == Mapped2m`         | ✓ |
| `free_pages_2m_wf`                     | `p0 ∈ free_pages_2m` ∧ `page_array[0].state == Free2m`             | ✓ |
| `mapped_pages_have_reference_counter`  | `ref_count[1] = 1 = |mappings|(1) + |io_mappings|(0)`              | ✓ |
| `container_wf` (mapped ⇒ owner Some)   | `page_array[1].owning_container = Some(c0)`                        | ✓ |
| `perm_wf` (`dom = mapped + free`)       | `dom = {p1} ∪ {p0} = {p0, p1}` (same as old)                       | ✓ |
| `page_array_wf` (addr / finite)        | all addrs / finiteness unchanged                                   | ✓ |

→ both Impl A and Impl B satisfy the ensures starting from the same input.

**Observable post-state difference**:

| field                       | Impl A's `self`         | Impl B's `self`         |
|-----------------------------|-------------------------|-------------------------|
| `ret` (return value)        | `p0`                    | `p1`                    |
| `free_pages_2m`             | `[]`                    | `[p0]`                  |
| `mapped_pages_2m`           | `{p0, p1}`              | `{p1}`                  |
| `page_array[0].state`       | `Mapped2m`              | `Free2m`                |
| `page_array[0].mappings`    | `{(pcid, va)}`          | `∅`                     |
| `page_array[1].mappings`    | `{(pcid_x, va_x)}`      | `{(pcid, va)}`          |

These are observationally distinct under `det_seq_equal`/`det_set_equal` —
even an "alloc-choice-equivalence" relaxation of `det_equal` would not
merge them (different cardinalities for `free`/`mapped`).

**Confirmed verdict**: ✅ **real non-determinism (Pattern A0 + A1)**.

- **A0** is a genuine spec bug — the `alloc_and_map_2m` contract should add
  `old(self).free_pages_2m().contains(ret)` (mirroring `alloc_page_4k`'s line 627).
  Once A0 is fixed, only A1 remains.
- **A1** is symmetric alloc choice — addressable in `det_equal` via a
  "choice-equivalence" extension if we want to suppress this class of
  "non-determinism".


## `alloc_and_map_4k`  — Pattern **A**  (2 entries)

**Preliminary verdict**: `real` non-determinism.  
**Underconstrained element**: Returns a chosen ptr `ret` constrained by `old(self).free_pages_4k().contains(ret)`; freedom of allocation choice.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_4k.rs`
- `verified/kernel/kernel__create_and_map_pages__impl0__alloc_and_map.rs`

```rust
    pub fn alloc_and_map_4k(&mut self, pcid: Pcid, va: VAddr, c_ptr: ContainerPtr) -> (ret: PagePtr)
        requires
            old(self).wf(),
            old(self).free_pages_4k.len() > 0,
            old(self).container_map_4k@.dom().contains(c_ptr),
        ensures
            self.wf(),
            // self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_2m() =~= old(self).free_pages_2m(),
            self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret),
            self.free_pages_1g() =~= old(self).free_pages_1g(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            self.mapped_pages_4k() =~= old(self).mapped_pages_4k().insert(ret),
            self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
            self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
            forall|p: PagePtr|
                #![trigger self.page_is_mapped(p)]
                #![trigger self.page_mappings(p)]
                self.page_is_mapped(p) && p != ret ==> self.page_mappings(p) =~= old(
                    self,
                ).page_mappings(p) && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            self.page_mappings(ret) =~= Set::<(Pcid, VAddr)>::empty().insert((pcid, va)),
            self.page_mappings(ret).contains((pcid, va)),
            self.page_io_mappings(ret) =~= Set::<(IOid, VAddr)>::empty(),
            old(self).allocated_pages_4k().contains(ret) == false,
            page_ptr_valid(ret),
            old(self).container_map_4k@.dom() =~= self.container_map_4k@.dom(),
            old(self).container_map_2m@.dom() =~= self.container_map_2m@.dom(),
            old(self).container_map_1g@.dom() =~= self.container_map_1g@.dom(),
            forall|p: PagePtr| #![auto] self.page_is_mapped(p) <== old(self).page_is_mapped(p),
            !old(self).page_is_mapped(ret),
            self.page_is_mapped(ret),
            self.free_pages_4k.len() == old(self).free_pages_4k.len() - 1,
            forall|c: ContainerPtr|
                #![auto]
                self.container_map_4k@.dom().contains(c) && c_ptr != c
                    ==> self.get_container_owned_pages(c) =~= old(self).get_container_owned_pages(
                    c,
                ),
            self.get_container_owned_pages(c_ptr) =~= old(self).get_container_owned_pages(
                c_ptr,
            ).insert(ret),
    {
```

**Audit notes**:

Compared to `alloc_and_map_2m`, this fn carries **substantially stronger
ensures**. The most relevant additional clauses for pinning `ret`:

| line | clause                                                                |
|------|-----------------------------------------------------------------------|
| 623  | `old(self).allocated_pages_4k().contains(ret) == false`               |
| 624  | `page_ptr_valid(ret)`                                                 |
| 625  | `old(self).container_map_4k@.dom() =~= self.container_map_4k@.dom()`  |
| 629  | `!old(self).page_is_mapped(ret)` (i.e. not in any `mapped_pages_*`)   |
| 630  | `self.page_is_mapped(ret)`                                            |
| 631  | `self.free_pages_4k.len() == old(self).free_pages_4k.len() - 1`       |
| 638  | `self.get_container_owned_pages(c_ptr) =~= old.*.insert(ret)`         |

**Does A0 (missing `contains(ret)`) apply here?** No. The clause
`old.allocated_pages_4k().contains(ret) == false`, the absence of `ret` in any
`mapped_pages_*`, and the `len()` constraint on line 631 **collectively force**
`ret ∈ old(self).free_pages_4k()`. Proof by contradiction:

> Assume `ret ∉ old.free_pages_4k()`. Then
> `old.free_pages_4k().remove(ret) = old.free_pages_4k()` (no-op), so the
> ensures `self.free_pages_4k() =~= old.free_pages_4k().remove(ret)` gives
> `self.free_pages_4k() =~= old.free_pages_4k()` (Set view equal). By the
> `wf()` invariant `free_pages_4k.unique()` (from `free_pages_4k_wf`), the
> underlying Seq has no duplicates, so `Seq.len == Set.len`. Therefore
> `self.free_pages_4k.len() == old.free_pages_4k.len()`. This contradicts
> line 631. ∎

So `ret ∈ old.free_pages_4k()` is implicitly guaranteed. **No A0 bug**.

**Only A1 (symmetric alloc choice) remains**:

Setup `old(self)` with `old.free_pages_4k@ = [p0, p1]` (two free 4k pages,
plus the necessary 4k state machinery to satisfy `wf()`), `c0 ∈ container_map_4k@.dom()`.

| field | old |
|---|---|
| `page_array@[0]` | `{ state: Free4k, mappings: ∅, io_mappings: ∅, ref_count: 0 }` |
| `page_array@[1]` | `{ state: Free4k, mappings: ∅, io_mappings: ∅, ref_count: 0 }` |
| `free_pages_4k@` | `[p0, p1]` (Seq, unique) |
| `mapped_pages_4k@`, `allocated_pages_4k@` | `∅` |
| `container_map_4k@.dom()` | `{c0}` |
| `get_container_owned_pages(c0)` | `∅` (or some 4k baseline set) |

**Impl A**: `ret = p0`, mutates `page_array[0]` to Mapped4k with mappings = `{(pcid,va)}`.  
**Impl B**: `ret = p1`, mutates `page_array[1]` analogously.

Each Impl is fully determined by its choice of ret. Both satisfy all 17 ensures (verified by symmetry — the only mutated index is `idx(ret)`, and every set/seq view changes consistently with whichever ret was picked). The post-states differ in:

| field                    | Impl A      | Impl B      |
|--------------------------|-------------|-------------|
| `ret`                    | `p0`        | `p1`        |
| `free_pages_4k`          | `[p1]`      | `[p0]`      |
| `mapped_pages_4k`        | `{p0}`      | `{p1}`      |
| `page_array[0].state`    | `Mapped4k`  | `Free4k`    |
| `page_array[1].state`    | `Free4k`    | `Mapped4k`  |
| `get_container_owned_pages(c0)` | `{p0}` | `{p1}` |

**Confirmed verdict**: ✅ **real non-determinism (Pattern A1 only)**.

The classifier is correct, but a "choice-equivalence" extension to `det_equal`
that quotients allocation outcomes by `ret`-symmetry would suppress this
class of non-determinism (treating it as deterministic-up-to-allocator-choice).

Comparison with `alloc_and_map_2m`: that fn additionally has A0 (missing
`contains(ret)`) — it admits the pathological "overwrite already-mapped
page" interpretation. `alloc_and_map_4k` does not.


---

## `alloc_and_map_io_4k`  — Pattern **A1-only**  (2 entries)

**Preliminary verdict**: `real` non-determinism (A1 symmetric choice only — no A0 bug).  
**Underconstrained element**: which page is chosen when `|free_pages_4k| ≥ 2`.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_io_4k.rs`
- `verified/kernel/kernel__create_and_map_pages__impl0__alloc_and_map_io.rs`

```rust
    pub fn alloc_and_map_io_4k(&mut self, ioid: IOid, va: VAddr, c_ptr: ContainerPtr) -> (ret:
        PagePtr)
        requires
            old(self).wf(),
            old(self).free_pages_4k.len() > 0,
            old(self).container_map_4k@.dom().contains(c_ptr),
        ensures
            self.wf(),
            // self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_2m() =~= old(self).free_pages_2m(),
            self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret),
            self.free_pages_1g() =~= old(self).free_pages_1g(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            self.mapped_pages_4k() =~= old(self).mapped_pages_4k().insert(ret),
            self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
            self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
            forall|p: PagePtr|
                #![trigger self.page_is_mapped(p)]
                #![trigger self.page_mappings(p)]
                self.page_is_mapped(p) && p != ret ==> self.page_io_mappings(p) =~= old(
                    self,
                ).page_io_mappings(p),
            forall|p: PagePtr|
                #![trigger self.page_is_mapped(p)]
                #![trigger self.page_mappings(p)]
                self.page_is_mapped(p) ==> self.page_mappings(p) =~= old(self).page_mappings(p),
            self.page_mappings(ret) =~= Set::<(Pcid, VAddr)>::empty(),
            self.page_io_mappings(ret) =~= Set::<(IOid, VAddr)>::empty().insert((ioid, va)),
            self.page_io_mappings(ret).contains((ioid, va)),
            old(self).allocated_pages_4k().contains(ret) == false,
            page_ptr_valid(ret),
            old(self).container_map_4k@.dom() =~= self.container_map_4k@.dom(),
            old(self).container_map_2m@.dom() =~= self.container_map_2m@.dom(),
            old(self).container_map_1g@.dom() =~= self.container_map_1g@.dom(),
            forall|p: PagePtr| #![auto] self.page_is_mapped(p) <== old(self).page_is_mapped(p),
            !old(self).page_is_mapped(ret),
            self.page_is_mapped(ret),
            self.free_pages_4k.len() == old(self).free_pages_4k.len() - 1,
            forall|c: ContainerPtr|
                #![auto]
                self.container_map_4k@.dom().contains(c) && c_ptr != c
                    ==> self.get_container_owned_pages(c) =~= old(self).get_container_owned_pages(
                    c,
                ),
            self.get_container_owned_pages(c_ptr) =~= old(self).get_container_owned_pages(
                c_ptr,
            ).insert(ret),
    {
```

**Audit notes**: Twin of `alloc_and_map_4k` for IO mappings. Same ret-pinning by `LEN-1 + !old.page_is_mapped(ret) + !old.allocated_pages_4k().contains(ret)` (proof by contradiction: if `ret ∉ old.free_pages_4k`, then `.remove(ret)` is no-op, Set views equal, by `free_pages_4k.unique()` Seq lens equal, contradicting `len() == old.len() - 1`). No A0.

**Confirmed verdict**: ✅ **A1-only** (symmetric alloc choice — excludable via `det_equal` choice-equivalence).


---

## `alloc_page_2m`  — Pattern **A1-only**  (1 entry)

**Preliminary verdict**: `real` non-determinism (A1 only — no A0 bug, ret pinned by Tracked perm linearity).  
**Underconstrained element**: which 2m page is chosen when `|free_pages_2m| ≥ 2`.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_2m.rs`

```rust
    pub fn alloc_page_2m(&mut self) -> (ret: (PagePtr, Tracked<PagePerm2m>))
        requires
            old(self).wf(),
            old(self).free_pages_2m.len() > 0,
        ensures
            self.wf(),
            self.free_pages_4k() =~= old(self).free_pages_4k(),
            // self.free_pages_2m() =~= old(self).free_pages_2m(),
            self.free_pages_2m() =~= old(self).free_pages_2m().remove(ret.0),
            self.free_pages_1g() =~= old(self).free_pages_1g(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m().insert(ret.0),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            self.mapped_pages_4k() =~= old(self).mapped_pages_4k(),
            self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
            self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
            old(self).container_map_4k@.dom() =~= self.container_map_4k@.dom(),
            old(self).container_map_2m@.dom() =~= self.container_map_2m@.dom(),
            old(self).container_map_1g@.dom() =~= self.container_map_1g@.dom(),
            forall|p: PagePtr|
                self.page_is_mapped(p) ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                    && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            ret.0 == ret.1@.addr(),
            ret.1@.is_init(),
    {
```

**Audit notes**: Unlike `alloc_and_map_2m`, this fn returns `Tracked<PagePerm2m>`. The `perm_wf` invariant binds `page_perms_2m@.dom() = mapped + free.to_set()`, and `Tracked` is a linear resource — the impl cannot conjure a new perm. So `ret.0` is forced to be drawn from a perm in `page_perms_2m@.dom()`, and the post-state ensures only allows `ret.0 ∈ free_pages_2m` (since allocated is preserved via `insert(ret.0)` only). Therefore no A0.

**Confirmed verdict**: ✅ **A1-only** (symmetric alloc choice — excludable via `det_equal` choice-equivalence).


---

## `alloc_page_4k`  — Pattern **A1-only**  (8 entries)

**Preliminary verdict**: `real` non-determinism (A1 only — no A0 bug, ret explicitly pinned).  
**Underconstrained element**: which 4k page is chosen when `|free_pages_4k| ≥ 2`.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_4k.rs`
- `verified/kernel/kernel__mem_util__impl0__create_entry.rs`
- `verified/kernel/kernel__mem_util__impl0__create_iommu_table_entry.rs`
- `verified/kernel/kernel__syscall_new_container__impl0__syscall_new_container_with_endpoint.rs`
- `verified/kernel/kernel__syscall_new_proc__impl0__syscall_new_proc_with_endpoint.rs`
- `verified/kernel/kernel__syscall_new_proc_with_iommu__impl0__syscall_new_proc_with_endpoint_iommu.rs`
- `verified/kernel/kernel__syscall_new_thread__impl0__syscall_new_thread.rs`
- `verified/kernel/kernel__syscall_new_thread_with_endpoint__impl0__syscall_new_thread_with_endpoint.rs`

```rust
    pub fn alloc_page_4k(&mut self) -> (ret: (PagePtr, Tracked<PagePerm4k>))
        requires
            old(self).wf(),
            old(self).free_pages_4k.len() > 0,
        ensures
            self.wf(),
            // self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_2m() =~= old(self).free_pages_2m(),
            self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret.0),
            self.free_pages_1g() =~= old(self).free_pages_1g(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k().insert(ret.0),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            self.mapped_pages_4k() =~= old(self).mapped_pages_4k(),
            self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
            self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
            old(self).container_map_4k@.dom() =~= self.container_map_4k@.dom(),
            old(self).container_map_2m@.dom() =~= self.container_map_2m@.dom(),
            old(self).container_map_1g@.dom() =~= self.container_map_1g@.dom(),
            forall|p: PagePtr|
                self.page_is_mapped(p) ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                    && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            ret.1@.is_init(),
            ret.1@.addr() == ret.0,
            old(self).allocated_pages_4k().contains(ret.0) == false,
            forall|c: ContainerPtr|
                #![trigger self.get_container_owned_pages(c)]
                self.container_map_4k@.dom().contains(c) ==> self.get_container_owned_pages(c)
                    =~= old(self).get_container_owned_pages(c),
            page_ptr_valid(ret.0),
            old(self).free_pages_4k().contains(ret.0),
            forall|p: PagePtr| #![auto] self.page_is_mapped(p) == old(self).page_is_mapped(p),
            self.free_pages_4k.len() == old(self).free_pages_4k.len() - 1,
    {
```

**Audit notes**: Strongest possible ret pinning: explicit `old(self).free_pages_4k().contains(ret.0)` clause + `len() == old.len() - 1` + Tracked `PagePerm4k`. All three mechanisms redundantly forbid A0. The only freedom is which free page to pick.

**Confirmed verdict**: ✅ **A1-only** (symmetric alloc choice — excludable via `det_equal` choice-equivalence).


---

## `alloc_page_4k_for_new_container`  — Pattern **A1-only**  (2 entries)

**Preliminary verdict**: `real` non-determinism (A1 only — same pinning as `alloc_page_4k`).  
**Underconstrained element**: Same shape as `alloc_page_4k`; `ret.0` ∈ `old.free_pages_4k()` only.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_4k_for_new_container.rs`
- `verified/kernel/kernel__syscall_new_container__impl0__syscall_new_container_with_endpoint.rs`

```rust
    pub fn alloc_page_4k_for_new_container(&mut self) -> (ret: (PagePtr, Tracked<PagePerm4k>))
        requires
            old(self).wf(),
            old(self).free_pages_4k.len() > 0,
        ensures
            self.wf(),
            // self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_2m() =~= old(self).free_pages_2m(),
            self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret.0),
            self.free_pages_1g() =~= old(self).free_pages_1g(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k().insert(ret.0),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            self.mapped_pages_4k() =~= old(self).mapped_pages_4k(),
            self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
            self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
            self.container_map_4k@ =~= old(self).container_map_4k@.insert(ret.0, Set::empty()),
            old(self).container_map_2m@.insert(ret.0, Set::empty()) =~= self.container_map_2m@,
            old(self).container_map_1g@.insert(ret.0, Set::empty()) =~= self.container_map_1g@,
            forall|p: PagePtr|
                self.page_is_mapped(p) ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                    && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            ret.1@.is_init(),
            ret.1@.addr() == ret.0,
            old(self).allocated_pages_4k().contains(ret.0) == false,
            forall|c: ContainerPtr|
                #![trigger self.get_container_owned_pages(c)]
                old(self).container_map_4k@.dom().contains(c) ==> self.get_container_owned_pages(c)
                    =~= old(self).get_container_owned_pages(c),
            page_ptr_valid(ret.0),
            old(self).free_pages_4k().contains(ret.0),
            forall|p: PagePtr| #![auto] self.page_is_mapped(p) == old(self).page_is_mapped(p),
            self.free_pages_4k.len() == old(self).free_pages_4k.len() - 1,
            self.get_container_owned_pages(ret.0) == Set::<PagePtr>::empty(),
    {
```

**Audit notes**: Same triple-redundant pinning as `alloc_page_4k`. The wrinkle here is that the fn also `insert(ret.0, Set::empty())` into all three `container_map_*@`, but those maps have value type `Set<PagePtr>` (deterministic), so no Seq freedom is introduced.

**Confirmed verdict**: ✅ **A1-only** (symmetric alloc choice — excludable via `det_equal` choice-equivalence).


---

## `add_io_mapping_4k`  — Pattern **B**  (1 entry)

**Preliminary verdict**: `real (suspect)` non-determinism.  
**Underconstrained element**: Same: `page_io_mappings(target_ptr).insert((ioid,va))` pins Set view; underlying seq free.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k.rs`

```rust
    pub fn add_io_mapping_4k(&mut self, target_ptr: PagePtr, ioid: IOid, va: VAddr)
        requires
            old(self).wf(),
            old(self).mapped_pages_4k().contains(target_ptr),
            old(self).page_io_mappings(target_ptr).contains((ioid, va)) == false,
            old(self).page_mappings(target_ptr).len() + old(self).page_io_mappings(target_ptr).len()
                < usize::MAX,
        ensures
            self.wf(),
            self.free_pages_4k.len() == old(self).free_pages_4k.len(),
            self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_2m() =~= old(self).free_pages_2m(),
            self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_1g() =~= old(self).free_pages_1g(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            self.mapped_pages_4k() =~= old(self).mapped_pages_4k(),
            self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
            self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
            forall|p: PagePtr|
                #![trigger self.page_is_mapped(p)]
                #![trigger self.page_mappings(p)]
                self.page_is_mapped(p) && p != target_ptr ==> self.page_mappings(p) =~= old(
                    self,
                ).page_mappings(p) && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
             self.page_io_mappings(target_ptr) =~= old(self).page_io_mappings(target_ptr).insert(
                (ioid, va),
            ),
            self.page_io_mappings(target_ptr).len() =~= old(self).page_io_mappings(target_ptr).len() + 1,
            self.page_io_mappings(target_ptr).contains((ioid, va)),
            self.page_mappings(target_ptr) =~= old(self).page_mappings(target_ptr),
            self.container_map_4k@.dom() =~= old(self).container_map_4k@.dom(),
            forall|p: PagePtr| #![auto] self.page_is_mapped(p) <==> old(self).page_is_mapped(p),
            forall|c: ContainerPtr|
                #![auto]
                self.container_map_4k@.dom().contains(c) ==> self.get_container_owned_pages(c)
                    =~= old(self).get_container_owned_pages(c),
    {
```

**Audit notes**:

#### 函数的真实意图（自然语言）

`add_io_mapping_4k(target_ptr, ioid, va)` 给已经被映射的 4k 页 `target_ptr` 追加一条 IO 映射 `(ioid, va)`。可以把 `page_io_mappings(p)` 想成 "页 p 当前被哪些 (IOid, VAddr) 拿去做 IO 映射"。precondition 要求 target_ptr 已经在 Mapped4k 池里、且 `(ioid, va)` 还不在它的 io_mappings 集合里。完成后只有 target_ptr 那一格的 `io_mappings@` 集合增加一项，`mappings@`、ref_count 也连带更新；free / allocated / 别的 mapped 页一概不动。

#### 这里的"incompleteness"在哪？

跟 `free_page_4k` 那种典型 B-Seq 不同—— `page_io_mappings(p)` 返回 `Set<(IOid, VAddr)>`，底层 `io_mappings: Ghost<Set<...>>` **本身就是 Set**，没有 Vec/Seq。所以 io_mappings 这一层是完全确定的。

非确定性来自两处：

**(1) free_pages_{4k,2m,1g} 的 passive B-Seq 自由**

ensures 用 `=~=` Set 等式钉死了三个 free 池：

```rust
self.free_pages_4k() =~= old(self).free_pages_4k(),   // Set 等
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
```

但底层 `StaticLinkedList` 的 `@` 视图是 `Seq<PagePtr>`，**Set 等式不约束 Seq 顺序**。函数语义上根本没碰这些池，但 spec 没禁止 impl 顺手把链表重洗一遍。

`free_pages_4k_wf` 要求 `page_array[i].rev_pointer == free_pages_4k.get_node_ref(addr)`，所以如果 impl 重洗链表，每个 Free4k 页的 `rev_pointer` 必须同步更新。**rev_pointer 不在 ensures 里**，这种联动重洗合规。

**(2) Mapped4k 页的 `is_io_page` / `rev_pointer` floating**

对 Mapped4k 页 `target_ptr`，下面两个 page_array 字段 **任何 wf invariant 都不约束**：

- `is_io_page`：wf 只对 Free4k 要求 `== false`、对 Merged2m/Merged1g 要求 match parent。Mapped4k 不约束。
- `rev_pointer`：wf 只对 Free4k 与链表节点同步要求。Mapped4k 不在链表，任意值都合规。

由于 `page_array` 是 `pub` 字段，det check 比较所有 Page 字段——这两个字段差异会让检查 SAT。这更像 "Pattern C：不可观测公开字段" 而不是 B-Seq。

#### Witness 草图（B-Seq passive）

`old.free_pages_4k@ = [p1, p2, p3, p4]`，`page_array[idx_k].rev_pointer = k` for free pages。`target_ptr` 是某个独立的 Mapped4k 页。

- **Impl A**: 只改 `page_array[idx_target].io_mappings@.insert((ioid,va))` 和 `ref_count++`。`free_pages_4k@` 不动。
- **Impl B**: 同样添加 io mapping，**额外**把 `free_pages_4k@` 重排成 `[p3, p1, p4, p2]`，同步更新 `page_array[idx_k].rev_pointer` 匹配新链表位置。

两个 impl 都满足 ensures（Set view 都 = `{p1,p2,p3,p4}`，wf 也满足），但 `page_array` 和 `free_pages_4k` 的 Seq 视图都不同 → det check SAT。

#### 分类与修法

| 自由度 | 类别 | 修法 |
|---|---|---|
| `free_pages_{4k,2m,1g}` Seq permutation (rev_pointer 联动) | **B-Seq passive** | det_equal 在 free_pages_* 字段上用 `.to_set()` 比较 |
| Mapped4k 的 `is_io_page` / `rev_pointer` | C-Field-unspecified | 加 wf 钉死，或 det_equal 对这些字段 ignore（对 Mapped4k 页） |

**Confirmed verdict**: ✅ **B-Seq passive + minor C-Field**（无 A0，target_ptr/ioid/va 在 ensures 里绑得很死，io_mappings Set 精确钉死）。可由 det_equal 扩展折叠，不是 spec bug。

**⚠️ See the "setter vs public-API ensures inconsistency" section near the top of this doc.** Same file (`add_io_mapping_4k.rs` line 771 `set_io_mapping`) contains a setter that uses `self.free_pages_4k == old(self).free_pages_4k` (Seq-level) while this public API only writes `self.free_pages_4k() =~= old(self).free_pages_4k()` (Set-level). If the public ensures were tightened to mirror the setter, the "B-Seq passive" issue here would disappear entirely. **Question for developer.**

**Spec typo (作者疏忽佐证)**: line 580 和 line 582 是同一句 `self.free_pages_4k() =~= old(self).free_pages_4k()`（重复了），第二句应该是想写 `free_pages_2m`。同样的 typo 也出现在 `add_mapping_4k.rs` line 580/582。佐证这部分 ensures 是 copy-paste 拼装出来的，未细审。

### Sibling: `add_mapping_4k`  (1 entry)

**完全同构的孪生函数**。区别只在它操作 `page_mappings`（`Set<(Pcid, VAddr)>`）而非 `page_io_mappings`，并通过 `set_ref_count` + `set_mapping` 这两个 setter 改状态（同文件 setter 也用 Seq 级 `==`，line 754, 805）。

Files:
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__add_mapping_4k.rs`
- `verified/kernel/kernel__create_and_share_pages__impl0__share_mapping.rs`

```rust
    pub fn add_mapping_4k(&mut self, target_ptr: PagePtr, pcid: Pcid, va: VAddr)
        requires
            old(self).wf(),
            old(self).mapped_pages_4k().contains(target_ptr),
            old(self).page_mappings(target_ptr).contains((pcid, va)) == false,
            old(self).page_mappings(target_ptr).len() + old(self).page_io_mappings(target_ptr).len()
                < usize::MAX,
        ensures
            self.wf(),
            self.free_pages_4k.len() == old(self).free_pages_4k.len(),
            self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_2m() =~= old(self).free_pages_2m(),
            self.free_pages_4k() =~= old(self).free_pages_4k(),
            self.free_pages_1g() =~= old(self).free_pages_1g(),
            // ... (allocated/mapped Set 视图全部 =~= 保留, 镜像 add_io_mapping_4k)
            self.page_mappings(target_ptr) =~= old(self).page_mappings(target_ptr).insert((pcid, va)),
            self.page_mappings(target_ptr).len() =~= old(self).page_mappings(target_ptr).len() + 1,
            self.page_mappings(target_ptr).contains((pcid, va)),
            self.page_io_mappings(target_ptr) =~= old(self).page_io_mappings(target_ptr),
            // ... (container_map dom 保留, get_container_owned_pages 各容器保留)
    {
```

**对称结构核对**：

| 维度 | `add_io_mapping_4k` | `add_mapping_4k` |
|---|---|---|
| 目标 page | `target_ptr`（输入，requires `mapped_pages_4k().contains(...)`） | 同 |
| 插入条目 | `(ioid, va)`（输入） | `(pcid, va)`（输入） |
| 核心 ensures | `page_io_mappings(target_ptr) =~= old.insert((ioid,va))` | `page_mappings(target_ptr) =~= old.insert((pcid,va))` |
| 其他 page 的 mapping/io_mapping | 均 `=~=` 保留 | 同 |
| free_pages_4k/2m/1g | Set `=~=` + len `==`（line 580-584） | 同（line 579-583） |
| Allocated/Mapped 3 size / Container map dom | `=~=` 保留 | 同 |
| impl 路径 | `set_ref_count` + `set_io_mapping` | `set_ref_count` + `set_mapping` |
| 底层 setter ensures（同文件） | `self.free_pages_4k == old.free_pages_4k`（Seq） | 同（line 754, 805） |

**Confirmed verdict**: ✅ **B-Seq passive + minor C-Field**（无 A0，分类与 `add_io_mapping_4k` 同源）。同样可由 `det_equal` 折叠；同样若 setter-vs-public 的 `==` vs `=~=` 不一致被发现是作者疏忽，则改 public ensures 即可消除自由度。


---

## `free_page_4k`  — Pattern **B**  (5 entrys)

**Preliminary verdict**: `real` non-determinism.  
**Underconstrained element**: ensures pins `Set` view: `self.free_pages_4k() =~= old.insert(target_ptr)`. Field is `StaticLinkedList` whose `View=Seq<T>` (ordered). Push position is free.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__free_page_4k.rs`
- `verified/kernel/kernel__kernel_drop_endpoint__impl0__kernel_drop_endpoint.rs`
- `verified/kernel/kernel__kernel_kill_proc__impl0__helper_kernel_kill_proc_non_root.rs`
- `verified/kernel/kernel__kernel_kill_proc__impl0__helper_kernel_kill_proc_root.rs`
- `verified/kernel/kernel__kernel_kill_thread__impl0__kernel_kill_thread.rs`

```rust
    pub fn free_page_4k(&mut self, target_ptr: PagePtr, Tracked(target_perm): Tracked<PagePerm4k>)
        requires
            old(self).wf(),
            old(self).allocated_pages_4k().contains(target_ptr),
            target_ptr == target_perm.addr(),
            target_perm.is_init(),
            old(self).container_map_4k@.dom().contains(target_ptr) == false,
            old(self).container_map_2m@.dom().contains(target_ptr) == false,
            old(self).container_map_1g@.dom().contains(target_ptr) == false,
        ensures
            self.wf(),
            self.free_pages_4k() =~= old(self).free_pages_4k().insert(target_ptr),
            self.free_pages_2m() =~= old(self).free_pages_2m(),
            self.free_pages_1g() =~= old(self).free_pages_1g(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k().remove(target_ptr),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            self.mapped_pages_4k() =~= old(self).mapped_pages_4k(),
            self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
            self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
            forall|p: PagePtr|
                self.page_is_mapped(p) ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                    && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            old(self).container_map_4k@.dom() =~= self.container_map_4k@.dom(),
            old(self).container_map_2m@.dom() =~= self.container_map_2m@.dom(),
            old(self).container_map_1g@.dom() =~= self.container_map_1g@.dom(),
            forall|c: ContainerPtr|
                #![trigger self.get_container_owned_pages(c)]
                self.container_map_4k@.dom().contains(c) ==> self.get_container_owned_pages(c)
                    =~= old(self).get_container_owned_pages(c),
            forall|p: PagePtr| #![auto] self.page_is_mapped(p) == old(self).page_is_mapped(p),
    {
```

**Audit notes**:

- **No alloc choice (A0/A1 absent)**: `target_ptr` is an input arg, `target_perm: Tracked<PagePerm4k>` is consumed linearly → exactly one page is freed, no choice of which.
- **Set-level ensures fully pin observable state**: `self.free_pages_4k() =~= old.insert(target_ptr)`, `allocated_pages_4k =~= old.remove(target_ptr)`, all other set views frozen, all mappings frozen, all container-owned-pages frozen.
- **Seq-level freedom on `free_pages_4k@`**:
  - **Insertion position free**: spec doesn't say push-front / push-back / sorted. All positions yield identical `Set::to_set()`.
  - **Existing-element permutation free**: even `old@ = [p1,p2,p3]` → `self@ = [p3, target_ptr, p2, p1]` satisfies set ensures + `wf.free_pages_4k.unique()` (the only Seq-level constraint).
- **`wf` does NOT pin Seq order**: `free_pages_4k_wf` only requires `wf() + unique() + forward/backward` (page_array[i].state == Free4k iff i ∈ free_pages_4k@), all `Set`-level.

**Class**: **B-Seq permutation freedom** (insertion position + arbitrary reorder of existing).

**How to fold**: extend `det_*_equal` to compare `free_pages_*: StaticLinkedList<...>` via `field@.to_set()` rather than structural Seq equality. The set-equality is what the spec already guarantees; our check is just over-strict at Seq level.

**Confirmed verdict**: ✅ **B-Seq-only** (excludable via `det_equal` set-view extension on `free_pages_*` fields).

**Preliminary verdict**: `TBD` non-determinism.  
**Underconstrained element**: Bulk-move 4k pages into 2m page; ensures pins set views, Seq orderings unspecified.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__merged_4k_to_2m.rs`

```rust
    pub fn merged_4k_to_2m(&mut self, target_ptr: PagePtr, target_page_idx: usize)
        requires
            old(self).wf(),
            target_page_idx + 512 <= NUM_PAGES,
            forall|i:int|
                #![trigger old(self).page_array[i]]
                target_page_idx<=i<target_page_idx + 512 
                ==> 
                old(self).page_array[i].state == PageState::Free4k
                &&
                old(self).page_array[i].is_io_page == false,
            old(self).free_pages_2m().len() < NUM_PAGES,
            page_ptr_2m_valid(page_index2page_ptr(target_page_idx)),
            old(self).free_pages_4k().len() >= 512,
        ensures
            self.wf(),
            forall|p: PagePtr|
                self.page_is_mapped(p) ==> self.page_mappings(p) =~= old(
                    self,
                ).page_mappings(p) && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            self.container_map_2m@ =~= old(self).container_map_2m@,
            self.container_map_1g@ =~= old(self).container_map_1g@,
            self.container_map_4k@ =~= old(self).container_map_4k@,
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            self.free_pages_4k().len() == old(self).free_pages_4k().len() - 512,
            self.free_pages_2m().len() == old(self).free_pages_2m().len() + 1,
            self.free_pages_1g().len() == old(self).free_pages_1g().len(),
    {
```

**Audit notes**:

**Critical observation**: `ensures` references **neither** `target_ptr` **nor** `target_page_idx`. Compare with `free_page_4k`'s ensures `self.free_pages_4k() =~= old.free_pages_4k().insert(target_ptr)` which directly binds the input.

#### 函数的真实意图（自然语言）

在 x86-64 page allocator 里，2 MiB 大页在物理布局上就是 **512 个连续、对齐的 4 KiB 小页**。`merged_4k_to_2m(target_ptr, target_page_idx)` 名字直译就是 "把 4k 合并为 2m"，它的工作是：

1. 拿到调用方指定的一段地址 —— `target_page_idx` 指明起始的 4k 页索引，`target_ptr` 指明对应物理地址；
2. 这一段必须正好是 **连续 512 个 4k 页，全部当前处于 Free4k 状态**（precondition 已保证）；
3. 把这 512 个 4k 页从 "free 4k 池" 取走，"合并" 成一个 Free2m 大页放进 "free 2m 池"；
4. 同时把 page_array 状态更新：那 512 个槽位里，第一个变成 `Free2m`（代表新大页 head），剩下 511 个变成 `Merged2m`（代表"我已经被并到大页里了，作为 head 的子页"）；
5. ghost 层的 perm 相应地把 512 份 4k 权限收回、铸出 1 份 2m 权限。

类比内存分配器里的 "buddy 合并"——把一连串小块合成一个大块。`target_ptr` / `target_page_idx` 这两个参数的存在就是为了告诉函数 **合并哪一段**。

#### Spec 里缺了什么（自然语言）

正确的 spec 应该说："**调用方指定哪个范围，函数就改哪个范围**"。但实际 ensures 完全没这种话，它只说三件事：

1. `wf()` 还成立；
2. 已映射、已分配、各 container 持有的页，原样不动；
3. **数量级变化**：4k free 池少 512、2m free 池多 1、1g free 池不变。

**两个至关重要的空白**：

- ensures 里 **从头到尾不出现 `target_ptr` 也不出现 `target_page_idx`** —— 两个输入参数对函数的承诺没有任何约束力；
- `free_pages_4k()` / `free_pages_2m()` 都只被 "len 减少多少 / 增加多少" 这种**计数式约束**钉住，**没有用 `=~=` 写 "集合变成 old 删掉这 512 个 / 加上 target 那一个" 这种内容式约束**。

也就是说，spec 等于在告诉 verifier：
> "请确认调用结束后，4k free 池少了 512 个元素、2m free 池多了 1 个元素，invariant 保持。至于少掉的是哪 512 个、多出来的是哪一个，我不在乎。"

这就允许一种荒谬但合规的实现：调用方说 "请把地址 X 开始那段合并"，实现回头却把另一段已经全 free 的连续区域合并了，把 X 那段原封不动留着。verifier 检查每条 ensures 都成立，所以接受。但调用方完全得不到自己想要的语义——`target_ptr` 参数被白白浪费了。

一句话总结：
> `merged_4k_to_2m` **应该**是"把调用方指定的那 512 个连续 free 4k 页升级成一个 free 2m 大页"，但 spec **实际**只说了"4k free 池少 512、2m free 池多 1"，**完全没说少的是哪 512、多的是哪一个**，把函数最关键的 input-output 绑定关系给漏掉了。

#### Spec 的形式化分析

`merged_4k_to_2m` only constrains:
- `wf()` preserved
- All `container_map_*@`, `allocated_pages_*()` preserved (set-level)
- Mappings preserved for pages in `self.page_is_mapped(...)`
- Three `len()` counts: 4k decreases by 512, 2m increases by 1, 1g unchanged

**No `=~=` set-view equality** on `free_pages_{4k,2m,1g}()`. Combined with no reference to inputs, the spec admits an impl that completely ignores `target_ptr` and merges **any** 2m-aligned 512-block of Free4k pages.

#### A0 Witness (same `old(self)`, two legal post-states)

**Setup** (assume `NUM_PAGES ≥ 1024`):

| index range | old.page_array[i].state | is_io_page |
|---|---|---|
| `0 .. 512` | `Free4k` | `false` |
| `512 .. 1024` | `Free4k` | `false` |
| `1024 .. NUM_PAGES` | `Unavailable4k` | `false` |

- `target_page_idx = 0`, `target_ptr = page_index2page_ptr(0)`
- `old.free_pages_4k@.to_set() = {addr_0, …, addr_1023}`, `len() = 1024`
- `old.free_pages_2m@ = []`, `len() = 0`
- All `mapped_*@`, `allocated_*@`, `container_map_*@` empty
- `page_perms_4k@.dom() = {addr_0, …, addr_1023}` (forced by `perm_wf`), `page_perms_2m@.dom() = {}`

Preconditions verified: `target_page_idx+512 ≤ NUM_PAGES`, `page_array[0..512]=Free4k, !io`, `free_pages_2m.len()=0 < NUM_PAGES`, `page_ptr_2m_valid(addr_0)` (0 is 2m-aligned), `free_pages_4k.len()=1024 ≥ 512`, `wf()` (all relevant invariants vacuous since no mapped/allocated/merged state).

**Impl A** — merges target block as intended:

| field | post-state |
|---|---|
| `page_array[0].state` | `Free2m` |
| `page_array[1..512].state` | `Merged2m` |
| `page_array[512..1024].state` | unchanged (`Free4k`) |
| `free_pages_4k@.to_set()` | `{addr_512, …, addr_1023}` (len 512) |
| `free_pages_2m@.to_set()` | `{addr_0}` (len 1) |
| `page_perms_4k@.dom()` | `{addr_512, …, addr_1023}` |
| `page_perms_2m@.dom()` | `{addr_0}` |

**Impl B** — merges the *alternate* 2m-aligned block, completely ignoring `target_ptr`:

| field | post-state |
|---|---|
| `page_array[0..512].state` | unchanged (`Free4k`) |
| `page_array[512].state` | `Free2m` |
| `page_array[513..1024].state` | `Merged2m` |
| `free_pages_4k@.to_set()` | `{addr_0, …, addr_511}` (len 512) |
| `free_pages_2m@.to_set()` | `{addr_512}` (len 1) |
| `page_perms_4k@.dom()` | `{addr_0, …, addr_511}` |
| `page_perms_2m@.dom()` | `{addr_512}` |

#### Ensures verification (Impl B)

| ensures clause | check | OK |
|---|---|---|
| `self.wf()` | see wf table below | ✅ |
| `forall p: page_is_mapped(p) ==> mappings preserved` | self has no mapped page (none in old), vacuous | ✅ |
| `container_map_{4k,2m,1g}@` preserved | Impl B doesn't touch container_map | ✅ |
| `allocated_pages_{4k,2m,1g}()` preserved | all empty, unchanged | ✅ |
| `free_pages_4k.len == old - 512` | 1024 − 512 = 512 | ✅ |
| `free_pages_2m.len == old + 1` | 0 + 1 = 1 | ✅ |
| `free_pages_1g.len` unchanged | both 0 | ✅ |

#### wf sub-invariants (Impl B)

| wf component | check | OK |
|---|---|---|
| `free_pages_4k_wf` | forward: `page_array[0..512]=Free4k` → in `{addr_0..addr_511}` ✓; backward ✓; `unique()` ✓ | ✅ |
| `free_pages_2m_wf` | forward: `page_array[512]=Free2m` → `addr_512 ∈ free_pages_2m@` ✓; backward ✓; `unique()` ✓ | ✅ |
| `merged_pages_wf` | `i ∈ [513,1024)` with state `Merged2m` → `truncate_2m(i) = 512`, `page_array[512].state = Free2m ∈ {Mapped2m,Free2m,Allocated2m,Unavailable2m}` ✓; `i` not 2m-valid (513..1023 not divisible by 512) ✓; `is_io_page` both false ✓ | ✅ |
| `hugepages_wf` | `i=512` (2m-valid, `Free2m`) → `∀ j` in 512's 2m range, `page_array[j] = Merged2m` ✓; `i=0` (2m-valid, `Free4k`) → antecedent state ∉ {Mapped2m,…} so vacuous ✓ | ✅ |
| `mapped_pages_*_wf` | all `mapped_*@` empty, no Mapped state, vacuous | ✅ |
| `allocated_pages_*_wf` | all empty, vacuous | ✅ |
| `mapped_pages_have_reference_counter` | all `ref_count == 0`, all states ∉ Mapped*; `mappings.len()+io_mappings.len() = 0` | ✅ |
| `container_wf` | all `container_map_*@` empty; no Mapped state in page_array, vacuous | ✅ |
| `perm_wf` | `page_perms_4k@.dom() = {} + {addr_0..addr_511} = mapped_4k + free_4k.to_set()` ✓; `page_perms_2m@.dom() = {} + {addr_512}` ✓; linearity: 512 4k-perms consumed, 1 2m-perm produced (the impl owns the transfer) ✓ | ✅ |

#### Observable difference

| observation | Impl A | Impl B |
|---|---|---|
| `self.free_pages_2m@.to_set()` | `{addr_0}` | `{addr_512}` |
| `self.free_pages_4k@.to_set()` | `{addr_512..addr_1023}` | `{addr_0..addr_511}` |
| `self.page_array[0].state` | `Free2m` | `Free4k` |
| `self.page_array[1].state` | `Merged2m` | `Free4k` |
| `self.page_array[512].state` | `Free4k` | `Free2m` |
| `self.page_array[513].state` | `Free4k` | `Merged2m` |
| `target_ptr` honored? | **yes** (merges block at 0) | **no** (merges block at 512) |

Same `old(self)`, same `(target_ptr, target_page_idx)`, two completely different post-states, both satisfy all ensures and `wf()`. → **A0 spec bug confirmed**.

#### Suggested spec fix

Add a clause binding the input to the post-state, e.g.:

```rust
// The new 2m page is exactly target_ptr:
self.free_pages_2m() =~= old(self).free_pages_2m().insert(target_ptr),
// And the 512 removed 4k pages are exactly target's range:
self.free_pages_4k() =~= old(self).free_pages_4k().difference(
    Set::new(|p: PagePtr| exists|i:int|
        target_page_idx <= i < target_page_idx + 512 && p == page_index2page_ptr(i as usize))
),
// And the page_array state transitions are pinned to the target range:
forall|i:int| target_page_idx < i < target_page_idx + 512
    ==> self.page_array[i].state == PageState::Merged2m,
self.page_array[target_page_idx as int].state == PageState::Free2m,
```

Once those clauses are added, the only residual freedom is **B-Seq insertion position** of `addr_target` in `free_pages_2m@` and of the removed entries in `free_pages_4k@` — same shape as `free_page_4k`'s remainder.

**Confirmed verdict**: ✅ **A0 (spec bug) + residual B-Seq** (excludable via `det_equal` set-view extension after spec fix).


---

## `remove_io_mapping_4k_helper1`  — Pattern **B**  (1 entry)

**Preliminary verdict**: `TBD` non-determinism.  
**Underconstrained element**: Similar removal helper for io mappings.

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_io_mapping_4k_helper1.rs`

```rust
    fn remove_io_mapping_4k_helper1(&mut self, target_ptr: PagePtr, ioid: IOid, va: VAddr)
        requires
            old(self).wf(),
            old(self).mapped_pages_4k().contains(target_ptr),
            old(self).page_io_mappings(target_ptr).contains((ioid, va)),
            old(self).page_array@[page_ptr2page_index(target_ptr) as int].is_io_page == true,
            old(self).page_array@[page_ptr2page_index(target_ptr) as int].ref_count == 1,
        ensures
            self.wf(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            forall|p: PagePtr|
                self.page_is_mapped(p) && p != target_ptr ==> self.page_mappings(p) =~= old(
                    self,
                ).page_mappings(p) && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            self.page_mappings(target_ptr) =~= old(self).page_mappings(target_ptr),
            self.page_io_mappings(target_ptr) =~= old(self).page_io_mappings(target_ptr).remove(
                (ioid, va),
            ),
            // self.container_map_4k@ =~= old(self).container_map_4k@,
            self.container_map_2m@ =~= old(self).container_map_2m@,
            self.container_map_1g@ =~= old(self).container_map_1g@,
            self.container_map_4k@ =~= old(self).container_map_4k@.insert(
                old(self).page_array@[page_ptr2page_index(
                    target_ptr,
                ) as int].owning_container.unwrap(),
                old(self).container_map_4k@[old(self).page_array@[page_ptr2page_index(
                    target_ptr,
                ) as int].owning_container.unwrap()].remove(target_ptr),
            ),
    {
```

**Audit notes**:

### 函数语义
私有 helper（无 `pub`），由 `remove_io_mapping_4k` 在 `ref_count == 1` 时调用：删除 `target_ptr` 这个 Mapped4k 页上唯一的 (ioid, va) io-mapping，并把页面回收。requires 保证：

- `target_ptr` 当前在 `mapped_pages_4k` 里且状态 `Mapped4k`
- 已存在 `(ioid, va) ∈ page_io_mappings(target_ptr)`
- `is_io_page == true`（"删的就是 io 映射"）
- `ref_count == 1`（结合 `mapped_pages_have_reference_counter`，即 mappings.len()+io_mappings.len()==1；又 `(ioid,va) ∈ io_mappings`，所以 mappings=∅, io_mappings={(ioid,va)}）

当前 impl 走的步骤（line 591-606）：
1. `set_ref_count(idx, 0)`
2. `set_io_mapping(idx, Ghost(Set::empty()))`
3. `set_state(idx, PageState::Unavailable4k)` —— **选择 Unavailable4k**
4. `set_owning_container(idx, None)`
5. `proof { self.mapped_pages_4k@ = self.mapped_pages_4k@.remove(target_ptr); }`
6. `proof { self.container_map_4k@ = self.container_map_4k@.insert(c, old[c].remove(target_ptr)); }`
7. `tracked_remove(target_ptr)` from `page_perms_4k`（perm 从 dom 移走，drop 掉）

### 关键观察：每个 PageState 类需要一个 "anchor"，而 Free4k 没有

helper1 的 ensures 通过几个 set/map view 间接锁定了大部分页面归属，但**漏掉了 Free pool 的锚定**。这是 incompleteness 的真正根源。

**Anchor 表**（PageAllocator 的 wf 子条款都是 ⇔ 双向约束，所以钉死任一方向的 set view 就等于钉死 state）：

| PageState 类 | helper1 ensures 里的 anchor | 间接钉死什么 |
|---|---|---|
| Mapped4k | `container_map_4k =~= old.insert(c, old[c].remove(target_ptr))` | 经 `container_wf` 双向（line 466-470 + 487-495）⇒ `mapped_pages_4k@` 锁死为 `old \ {target_ptr}` |
| Mapped2m/1g | `container_map_2m/1g =~= old` | 同上，⇒ `mapped_pages_2m/1g@` 不变 |
| Allocated4k/2m/1g | `allocated_pages_4k/2m/1g() =~= old` | 经 `allocated_pages_*_wf` 双向 ⇒ `state==Allocated*k` 的 page 集合不变 |
| **Free4k** | ❌ **无 anchor** | `free_pages_4k_wf` 双向**只能与 spec 本身一致**，但 ensures 没钉死 `free_pages_4k()` 任何一边 |
| **Free2m/1g** | ❌ **无 anchor** | 同上 |
| Merged2m/1g, Pagetable, Io, Unavailable* | ❌ 无 anchor | 这些 state 没有对应的 set/map view，wf 完全沉默 |

所以 helper1 ensures 对 target_ptr 之外的所有 "非 Mapped、非 Allocated" 4k 页都**没有任何约束**——这些页的 state 可以在 `{Free4k, Unavailable4k, Pagetable, Io}`（及对应 2m/1g state 的 4k-aligned 投影）之间任意翻转，只要 `free_pages_4k_wf` 这条对剩下的页一致即可。

### 主要 witness：Impl E "私自缩减 free pool"

最干净地展示 incompleteness 的 impl：除了正常回收 target_ptr 之外，**额外**把某个无关的 Free4k 页 `q` 从 free 池里悄悄删掉。

**初始 σ_0**（`NUM_PAGES = 1024`，target_ptr = page_index2page_ptr(0)，输入 ioid=I, va=V，owning_container = c；额外选一个 q = page_index2page_ptr(2) 作为"被偷"的 Free4k 页）：
- `page_array[0]`: `{ state: Mapped4k, addr: tp, is_io_page: true, rev_pointer: r₀, ref_count: 1, owning_container: Some(c), mappings: ∅, io_mappings: {(I,V)} }`
- `page_array[2]` (= q): `{ state: Free4k, addr: q_addr, is_io_page: false, rev_pointer: rq, ref_count: 0, owning_container: None, mappings: ∅, io_mappings: ∅ }`
- 其他页: 全部 `Unavailable4k`
- `mapped_pages_4k@ = {tp}`; `free_pages_4k@ = [q_addr]`; `allocated_pages_4k@ = ∅`
- `page_perms_4k@.dom() = {tp, q_addr}`
- `container_map_4k = {c → {tp}}`

**Impl A (current code)** — 只动 target_ptr：
- `page_array[0]`: `{ state: Unavailable4k, is_io_page: true, ref_count: 0, owning_container: None, mappings: ∅, io_mappings: ∅, ... }`
- `page_array[2]`: 不变（仍 Free4k）
- `mapped_pages_4k@ = ∅`; `free_pages_4k@ = [q_addr]`（不变）
- `page_perms_4k@.dom() = {q_addr}`
- `container_map_4k = {c → ∅}`

**Impl E (hypothetical)** — 在 Impl A 基础上**额外**偷走 q：
- 跟 Impl A 一样处理 target_ptr
- 额外：`set_state(idx(q), Unavailable4k)` 把 q 改成 Unavailable4k
- 额外（proof 块）：把 q 从 `free_pages_4k` 列表移除（`free_pages_4k.seq@` 设为 `[]`）
- 额外（proof 块）：`tracked_remove(q_addr)` from `page_perms_4k` 并 drop 掉
- final `page_array[2]`: `{ state: Unavailable4k, is_io_page: false, ref_count: 0, owning_container: None, mappings: ∅, io_mappings: ∅, ... }`
- final `mapped_pages_4k@ = ∅`; `free_pages_4k@ = []`
- final `page_perms_4k@.dom() = ∅`
- final `container_map_4k = {c → ∅}`

### 两个 impl 都满足 ensures + wf

| ensures 项 | Impl A | Impl E |
|---|---|---|
| `self.wf()` | ✓ | ✓ 见下方分项 |
| `allocated_pages_4k/2m/1g() =~= old` | ✓ ∅=∅ | ✓ ∅=∅（q 没变 allocated） |
| `forall p mapped ∧ p≠target_ptr: page_mappings/io_mappings 不变` | ✓ vacuous | ✓ q 在 new 里 `page_is_mapped(q)==false`，蕴含前件假，vacuous |
| `page_mappings(target_ptr) =~= old` (=∅) | ✓ | ✓ |
| `page_io_mappings(target_ptr) =~= old.remove((I,V))` (=∅) | ✓ | ✓ |
| `container_map_4k =~= old.insert(c, old[c].remove(target_ptr))` | ✓ {c→∅} | ✓ {c→∅}（q 不在任何 container） |
| `container_map_2m/1g =~= old` | ✓ | ✓ |

**wf 验证**（关键子条款，重点看 Impl E 对 q 的处理）：

| 子 wf | Impl E 验证 |
|---|---|
| `page_array_wf` | `q.addr == page_index2page_ptr(idx(q))` 未改 ✓ |
| `free_pages_4k_wf` 正向（`state==Free4k ⇒ ∈ free_pages_4k.to_set`） | q.state 现在 Unavailable4k，前件假 ✓；其他页同 Impl A ✓ |
| `free_pages_4k_wf` 反向（`∈ free_pages_4k.to_set ⇒ state==Free4k ∧ rev_pointer==... ∧ is_io_page==false`） | q 已从 list 移除（new.list=[]），反向 forall 空集合下 vacuous ✓ |
| `mapped_pages_4k_wf` 双向 | q.state ≠ Mapped4k；mapped set = ∅ ✓ |
| `allocated_pages_4k_wf` 双向 | q.state ≠ Allocated4k；allocated 不变 ✓ |
| `perm_wf`（`dom = mapped + free.to_set`） | new.dom = ∅，new.mapped + new.free.to_set = ∅ + ∅ ✓ |
| `container_wf` | q.owning_container = None，q.state ∉ Mapped3 ✓ |
| `mapped_pages_have_reference_counter` | q.ref_count = 0, mappings + io_mappings = 0+0 = 0, q.state ∉ Mapped3 ✓ |
| `hugepages_wf` | 只约束 state ∈ {Mapped2m, Free2m, Allocated2m, Unavailable2m} 的 2m-aligned 页；q.state=Unavailable4k 不触发 ✓ |
| `merged_pages_wf` | 只约束 state==Merged2m/1g；q 不是 Merged ✓ |

→ Impl E 完整通过 ensures + 所有 wf。

### 可观察差异

| 量 | Impl A | Impl E |
|---|---|---|
| `page_array.seq@[2].state` | `Free4k` | `Unavailable4k` |
| `free_pages_4k@` (Seq view) | `[q_addr]` | `[]` |
| `free_pages_4k().to_set()` | `{q_addr}` | `∅` |
| `page_perms_4k@.dom()` | `{q_addr}` | `∅` |

→ det check SAT。**任意数量的无关 Free4k 页都可以被同样地"偷走"**——还可以反过来"凭空"把 Unavailable4k 页加进 free 池（state→Free4k、list→push、构造 perm）；spec-level ghost view 不强制 linearity，所以 perm 的添加在 spec 层也合法。

### 这是真的能在 Verus 代码层实现的攻击吗

是。所有需要的原语都已存在：
- `set_state(idx, Unavailable4k)` —— 已有 setter（line 707）
- `tracked_remove(q_addr)` from `page_perms_4k` —— current impl 处理 target_ptr 时已经这么用（line 606）
- `free_pages_4k` 字段是 `pub`，其 `seq@` 是 `Ghost`，proof block 可任意改

唯一可能 trip up 的是从 `StaticLinkedList` 删一个非头节点需要 exec API；如果 list 没暴露这种 op，real Rust 代码写不出来。但 **spec-level det check 不看 exec 可达性**——它只问"是否存在 σ 满足 ensures + wf"。即便 real impl 永远不会这么干，spec 仍然 SAT。

### 对比：add_io_mapping_4k vs helper1 的本质区别

| 函数 | `free_pages_4k()` 在 ensures 中 | `mapped_pages_4k()` 在 ensures 中 | Free pool 是否锚定 |
|---|---|---|---|
| `add_io_mapping_4k` | `=~= old` 直接钉死 | `=~= old` 直接钉死 | ✅ 两个 anchor 都有 |
| `remove_io_mapping_4k_helper1` | ❌ 缺 | 经 `container_map_4k` 间接钉死 | ❌ Free 无 anchor |

`add_io_mapping_4k` 的 incompleteness 只是 Seq vs Set（B-Seq passive，setter→public 用了弱 `=~=`）。  
`helper1` 的 incompleteness 是 **Set 本身就没钉死**（A0 真缺约束）——严重程度高一档。

### 分类与修法

| 自由度 | 类别 | 修法 |
|---|---|---|
| 任意 old.Free4k 页 `q` (≠target_ptr) 可被改成 Unavailable4k 并从 free pool 删除 | **A0**：Free pool 无 anchor | ensures 加 `self.free_pages_4k() =~= old(self).free_pages_4k()`（4k 的 free pool 不变） |
| 任意 old.Unavailable4k 页可被改成 Free4k 并加入 free pool | 同上（A0） | 同上 |
| `target_ptr.state` 选 `Unavailable4k` 还是别的非 Mapped 非 Allocated state | A0 衍生 | ensures 加 `self.page_array@[page_ptr2page_index(target_ptr) as int].state == PageState::Unavailable4k` |
| 2m/1g free pool 同样无 anchor | A0 衍生 | ensures 加 `self.free_pages_2m() =~= old(self).free_pages_2m()` 和 `_1g()` |
| target_ptr 的 perm 是否真的从 page_perms_4k 移除 | A0 衍生 | ensures 加 `self.page_perms_4k@ =~= old(self).page_perms_4k@.remove(target_ptr)` 和 `_2m/_1g@ =~= old` |
| Free pool Set 钉死后剩的 Seq 排列 | B-Seq passive | 同 `add_io_mapping_4k`，setter→public 用 `==` 而非 `=~=`（或上层加 `det_equal` Seq↔Set 扩展） |

注意：`mapped_pages_4k()`、`allocated_pages_*()` 不需要再加，因为已分别由 `container_map_4k` 和 `allocated_pages_*()` ensures 间接锁死。

### 实际 impl 的 deterministic 假象

Real impl 只走 setter library。setter 限制：
- `set_state` ensures 钉死 `is_io_page, rev_pointer, addr, ref_count, owning_container, mappings, io_mappings` 全部 `=~= old`，所以"翻转任意页 state 但不动其他字段"在 real Rust 代码里需要 exec 入口
- StaticLinkedList 删非头节点需要专门 exec API
- 没有 `set_is_io_page`、`set_rev_pointer` setter

所以 Impl E 在 real Rust 写不出来——这是为什么真实 Atmosphere 跑起来 deterministic。但 **spec-level det check 必须依据 spec 自身的可推性**：所有字段 `pub`、`page_array.seq` 是 `pub Ghost`、`StaticLinkedList` 内部字段也 `pub`，proof block 绕过 setter 在 spec 层完全合法。

这跟 `add_io_mapping_4k` 是**同一类问题的强化版**：那里 setter 强 / public ensures 弱（Seq vs Set），这里 setter 限制行为 / public ensures **整个 Free pool 不提**。**修法同源**：把 setter library 已经隐含保证的事情显式写入 public ensures。

**Confirmed verdict**: ✅ **A0 + B-Seq passive**。A0 是真 spec bug（Free pool 全无 anchor，2m/1g free pool 同样未钉死，target_ptr 的 state、page_perms_4k 都未约束）；B-Seq passive 部分跟 add_io_mapping_4k 同源。建议作为 P0 spec bug 报告给开发者。


---

## `remove_mapping_4k_helper1`  — Pattern **B**  (1 entry)  ← **Sibling of `remove_io_mapping_4k_helper1`**

**Confirmed verdict**: ✅ **A0 + B-Seq passive**（与 `remove_io_mapping_4k_helper1` 完全同构，同根因，Impl E witness 直接套用）。

Files:
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper1.rs`

```rust
    fn remove_mapping_4k_helper1(&mut self, target_ptr: PagePtr, pcid: Pcid, va: VAddr)
        requires
            old(self).wf(),
            old(self).mapped_pages_4k().contains(target_ptr),
            old(self).page_mappings(target_ptr).contains((pcid, va)),
            old(self).page_array@[page_ptr2page_index(target_ptr) as int].is_io_page == true,
            old(self).page_array@[page_ptr2page_index(target_ptr) as int].ref_count == 1,
        ensures
            self.wf(),
            self.allocated_pages_4k/2m/1g() =~= old(self).allocated_pages_4k/2m/1g(),
            forall|p: PagePtr| self.page_is_mapped(p) && p != target_ptr ==>
                self.page_mappings(p) =~= old.page_mappings(p) &&
                self.page_io_mappings(p) =~= old.page_io_mappings(p),
            self.page_mappings(target_ptr) =~= old.page_mappings(target_ptr).remove((pcid, va)),
            self.page_io_mappings(target_ptr) =~= old.page_io_mappings(target_ptr),
            self.container_map_2m/1g@ =~= old.container_map_2m/1g@,
            self.container_map_4k@ =~= old.container_map_4k@.insert(c, old[c].remove(target_ptr)),
    {
        // impl: set_ref_count(0) → set_mapping(∅) → set_state(Unavailable4k) →
        //       set_owning_container(None) → tracked_remove(target_ptr)
        // 与 remove_io_mapping_4k_helper1 同样的 Unavailable4k 回收路径
    }
```

### 与 `remove_io_mapping_4k_helper1` 的对照

| 维度 | `remove_io_mapping_4k_helper1` | `remove_mapping_4k_helper1` |
|---|---|---|
| 删除的条目 | `(ioid, va) ∈ page_io_mappings` | `(pcid, va) ∈ page_mappings` |
| ensures 改 | `page_io_mappings(tp) =~= old.remove((I,V))` | `page_mappings(tp) =~= old.remove((P,V))` |
| ensures 不变 | `page_mappings(tp) =~= old` | `page_io_mappings(tp) =~= old` |
| 共同 ensures | `wf()`, `allocated_* =~= old`, `forall p mapped∧p≠tp 不变`, `container_map_4k =~= old.insert(c, old[c].remove(tp))`, `container_map_2m/1g =~= old` | 同 |
| requires | 含 `is_io_page == true` | 同（即 `is_io_page == true`） |
| 当前 impl | `set_ref_count` → `set_io_mapping(∅)` → `set_state(Unavailable4k)` → `set_owning_container(None)` → `tracked_remove` | `set_ref_count` → `set_mapping(∅)` → `set_state(Unavailable4k)` → `set_owning_container(None)` → `tracked_remove` |

由 `ref_count = mappings.len + io_mappings.len` 与 `ref_count==1 ∧ mappings∋(P,V)` 可推 `old.io_mappings(tp)=∅`，所以 ensures 中 "io_mappings 不变" 实际等价于 "io_mappings=∅"。与 io 版的"mappings=∅"对称。

### Anchor 结构同构 → 同一 Impl E witness

Free pool 无 anchor（4k 和 2m/1g 都缺）→ 任意 old.Free4k 页 q (≠target_ptr) 可被"私自"从 free pool 删除（state→Unavailable4k、从 list 移除、tracked_remove(q)），逐项 ensures + wf 检查与 io 版的 Impl E 验证表**逐行一致**（只把"page_io_mappings 不变"换成"page_mappings 不变"，跟 q 都无关）。

### 待问开发者的小疑点

requires 里 `is_io_page == true` 看上去奇怪——这是删**普通**映射的 helper，理论上应是 `false` 或不要这条。**但其实不矛盾**：`is_io_page` 是"该 page 在物理上属于某个 IO 设备"的 sticky 标志，跟当前是否有 io_mappings 是独立的；这个 helper 处理的是"既是 io page、又恰好被分配作普通映射"的边界情形。post-call `is_io_page` 字段不在 ensures 也不在 Unavailable4k state 的 wf 约束中——同样的 C-Field 自由度（real impl 因为没有 `set_is_io_page` setter 而保留 old 值；spec 层自由）。建议在汇报时一并问开发者澄清意图。

### 修法

跟 io 版完全相同：
```rust
self.page_array@[page_ptr2page_index(target_ptr) as int].state == PageState::Unavailable4k,
self.free_pages_4k() =~= old(self).free_pages_4k(),
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
self.page_perms_4k@ =~= old(self).page_perms_4k@.remove(target_ptr),
self.page_perms_2m@ =~= old(self).page_perms_2m@,
self.page_perms_1g@ =~= old(self).page_perms_1g@,
```

`mapped_pages_4k()` 已由 `container_map_4k` 间接锁死，`allocated_pages_*()` 已显式钉死，无需重复添加。


---

## `remove_mapping_4k_helper2`  — Pattern **B**  (1 entry)

**Confirmed verdict**: ✅ **A0(强化) + B-Seq passive**。除了和 helper1 同源的"Free pool 无 anchor"问题，此函数还有一个**特殊维度**：ensures 与 helper1 完全相同，但 real impl 走截然不同的回收路径（Free4k push 入池 vs helper1 的 Unavailable4k drop perm），spec 不强制选哪条。

Files (verusage per-file extraction):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper2.rs`

```rust
    fn remove_mapping_4k_helper2(&mut self, target_ptr: PagePtr, pcid: Pcid, va: VAddr)
        requires
            old(self).wf(),
            old(self).mapped_pages_4k().contains(target_ptr),
            old(self).page_mappings(target_ptr).contains((pcid, va)),
            old(self).page_array@[page_ptr2page_index(target_ptr) as int].is_io_page == false,
            old(self).page_array@[page_ptr2page_index(target_ptr) as int].ref_count == 1,
        ensures
            self.wf(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            forall|p: PagePtr|
                self.page_is_mapped(p) && p != target_ptr ==> self.page_mappings(p) =~= old(
                    self,
                ).page_mappings(p) && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            self.page_mappings(target_ptr) =~= old(self).page_mappings(target_ptr).remove(
                (pcid, va),
            ),
            self.page_io_mappings(target_ptr) =~= old(self).page_io_mappings(target_ptr),
            // self.container_map_4k@ =~= old(self).container_map_4k@,
            self.container_map_2m@ =~= old(self).container_map_2m@,
            self.container_map_1g@ =~= old(self).container_map_1g@,
            self.container_map_4k@ =~= old(self).container_map_4k@.insert(
                old(self).page_array@[page_ptr2page_index(
                    target_ptr,
                ) as int].owning_container.unwrap(),
                old(self).container_map_4k@[old(self).page_array@[page_ptr2page_index(
                    target_ptr,
                ) as int].owning_container.unwrap()].remove(target_ptr),
            ),
    {
```

**Audit notes**:

### `is_io_page` 是什么字段

`Page` 结构有个独立的 `is_io_page: bool` 字段（跟 `state` 正交）：
- `is_io_page == true` ⇔ 物理页属于某 IO 设备地址空间（MMIO 区、DMA buffer 等）
- `is_io_page == false` ⇔ 普通 RAM

这是个**粘性**字段——一旦标了就不变（setter library 里没有 `set_is_io_page`，只有 `set_state` ensures 中 `is_io_page == old.is_io_page`）。它与 `state` 正交：一个 io page 可以处于 `Mapped4k`、`Io`、`Unavailable4k` 等任意 state。

### 一个 page 怎么会"既是 io page 又有普通 mapping"

1. 初始化阶段某些物理范围（如 MMIO）就被标 `is_io_page=true`
2. `alloc_and_map_io_4k` 把 io page 拉成 `Mapped4k` 状态，加 `(ioid, va)` 到 `page_io_mappings`
3. **关键**：`add_mapping_4k` requires 仅 `mapped_pages_4k().contains(target_ptr)`，所以**一个 io page 可以再被附加普通 (pcid, va) mapping**——典型场景：用户态进程 mmap MMIO 区域，让进程的 va 也能访问

所以 `is_io_page=true ∧ state=Mapped4k ∧ mappings 非空 ∧ io_mappings 非空` 是合法且常见的中间状态。

### helper1 vs helper2 的设计语义

两个 helper 都在 `remove_mapping_4k` 删除最后一条 `(pcid, va)` 时触发（`ref_count==1`），但 page "归宿" 不同：

| 维度 | `remove_mapping_4k_helper1` (`is_io_page=true`) | `remove_mapping_4k_helper2` (`is_io_page=false`) |
|---|---|---|
| 触发场景 | io page 上最后一条普通 mapping 被撤销（io 那边的 `(ioid,va)` 已先撤销，因 `ref_count==1 ∧ mappings∋(P,V) ⇒ io_mappings=∅`） | 普通 RAM 页上最后一条 mapping 被撤销 |
| 物理含义 | **交还** IO 子系统（hand-off） | **回收**到 free 池（recycle） |
| 目的 state | `Unavailable4k`（allocator 视角"消失"） | `Free4k`（allocator 视角"可分配"） |
| `free_pages_4k` | 不入 | `push(target_ptr)` |
| `page_perms_4k` | `tracked_remove(target_ptr)` 释放 | 保留（等下次 alloc 转交） |
| `rev_pointer` | 无关（Unavailable 不用） | `set_rev_pointer(idx, list.get_node_ref)` |
| 下一步 | 等 io subsystem 再次调 `alloc_and_map_io_4k` | 等 page allocator 再次调 `alloc_page_4k` |
| **为什么不能 push 入 free 池** | 因为该页**物理上仍属于 IO 设备**，如果普通 RAM 分配器拿到这地址会写到 MMIO 寄存器触发硬件动作 | N/A（这就是要走的路径） |
| **为什么不能 drop perm** | N/A（这就是要走的路径） | 因为该页要被 page allocator 复用，perm 必须留在 `page_perms_4k` 里供下次 alloc 转交 |

### Real impl 路径（line 643-648）

```rust
let rev_index = self.free_pages_4k.push(&target_ptr);
self.set_rev_pointer(page_ptr2page_index(target_ptr), rev_index);
self.set_ref_count(page_ptr2page_index(target_ptr), 0);
self.set_mapping(page_ptr2page_index(target_ptr), Ghost(Set::empty()));
self.set_state(page_ptr2page_index(target_ptr), PageState::Free4k);
self.set_owning_container(page_ptr2page_index(target_ptr), None);
```

与 helper1 的 `set_state(Unavailable4k) → tracked_remove` 路径**完全相反**。

### Incompleteness 分析

helper2 的 ensures 与 helper1 (mapping 版) **逐字相同**（只 requires 里 `is_io_page` 翻 true→false）。但两个 helper 的语义意图不同，**spec 完全没把这层差异写出来**。后果：

**Impl A' (real, Free4k path)**：state=Free4k、push 到 free pool、保留 perm
**Impl B' (alt, helper1-style Unavailable4k path)**：state=Unavailable4k、不入 free pool、drop perm

两者都过 ensures + wf 检查：

| 子 wf | Impl A' | Impl B' |
|---|---|---|
| `free_pages_4k_wf` 双向 | tp∈list ⇒ state=Free4k ∧ rev_pointer=list.ref ∧ is_io_page=false ✓ | tp∉list ∧ state≠Free4k ✓ |
| `mapped_pages_4k_wf` 双向 | tp.state≠Mapped4k ∧ mapped_pages_4k@=∅ ✓ | 同 |
| `container_wf` (owning_container ⇔ Mapped3) | None 配 Free4k ✓ | None 配 Unavailable4k ✓ |
| `perm_wf` (dom = mapped + free.to_set) | dom = ∅ + {tp} = {tp} ✓ | dom = ∅ + ∅ = ∅ ✓ |
| `mapped_pages_have_reference_counter` | ref_count=0 ∧ state∉Mapped3 ∧ ref_count=∅.len+∅.len ✓ | 同 |

→ Impl B' 完整合法。这意味着 **spec 不强制 helper2 走"回收"路径**，允许它走 helper1 的"移交"路径（错误地把普通 RAM 当 io page 丢弃）。

**外加** Impl E（额外偷无关 Free 页改 Unavailable4k）也合法，与 helper1 同源。

### 与 helper1 (mapping 版) 的 verdict 对照

| 自由度 | helper1 (mapping) | helper2 |
|---|---|---|
| target_ptr 回收目的 state | 自由（Free4k vs Unavailable4k 都合法） | **同样自由**，但 real impl 选 Free4k，与 helper1 真实路径形成对照——spec 真的把语义意图丢了 |
| Free pool 增删无关页 (Impl E) | 自由（A0） | 同 |
| Seq 排列 | 自由（B-Seq passive） | 同 |
| `is_io_page` 字段 post-call | 自由（C-Field） | 同（real impl 不动） |

### 为什么这是 P0 spec bug

两个 helper 的 ensures 一模一样，但**语义意图根本不同**：

- helper1 ensures 没写"不入 free 池、drop perm" → 改 impl 错误地 push 到 free 池也通过 spec → **可能让普通 RAM 分配器拿到 MMIO 地址 → IO 安全问题**
- helper2 ensures 没写"入 free 池、保留 perm" → 改 impl 错误地丢弃 perm 不入 free 池也通过 spec → **可能导致普通 RAM 内存泄漏**

这两种 impl 错误都会**逃过 Verus 验证**，因为 ensures 双向都允许。det check 把这个发现暴露出来是真正抓到了 spec bug——不是过宽容一点而是缺关键安全约束。

### 修法

跟 helper1 镜像，但 target_ptr 目的 state 改 Free4k，且强制 perm 保留：

```rust
self.page_array@[page_ptr2page_index(target_ptr) as int].state == PageState::Free4k,
self.free_pages_4k() =~= old(self).free_pages_4k().insert(target_ptr),  // ← 关键差异：加入 free pool
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
self.page_perms_4k@.dom() =~= old(self).page_perms_4k@.dom(),  // perm 保留（关键差异）
self.page_perms_2m@ =~= old(self).page_perms_2m@,
self.page_perms_1g@ =~= old(self).page_perms_1g@,
```

helper1 写 `.remove(target_ptr)` 把 perm 丢掉，helper2 写保留 dom 不变——**这一条清晰地暴露出两个 helper 的真正语义差异**，但当前 spec 完全看不出来。

**Confirmed verdict**: ✅ **A0(强化) + B-Seq passive**。根因同 helper1（Free pool 无 anchor），但多了一层 spec/impl 意图分歧：spec 把 helper1 和 helper2 写成了一模一样的 ensures，real impl 却走截然不同的回收路径。**强烈建议**作为 P0 报告给开发者——典型的 spec 复制粘贴时丢了关键差异化信息的 bug。

Files (verusage per-file extraction; ensures are identical across files):
- `verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper3.rs`

```rust
    fn remove_mapping_4k_helper3(&mut self, target_ptr: PagePtr, pcid: Pcid, va: VAddr)
        requires
            old(self).wf(),
            old(self).mapped_pages_4k().contains(target_ptr),
            old(self).page_mappings(target_ptr).contains((pcid, va)),
            old(self).page_array@[page_ptr2page_index(target_ptr) as int].ref_count != 1,
        ensures
            self.wf(),
            self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
            self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
            self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
            forall|p: PagePtr|
                self.page_is_mapped(p) && p != target_ptr ==> self.page_mappings(p) =~= old(
                    self,
                ).page_mappings(p) && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
            self.page_mappings(target_ptr) =~= old(self).page_mappings(target_ptr).remove(
                (pcid, va),
            ),
            self.page_io_mappings(target_ptr) =~= old(self).page_io_mappings(target_ptr),
            self.container_map_4k@ =~= old(self).container_map_4k@,
            self.container_map_2m@ =~= old(self).container_map_2m@,
            self.container_map_1g@ =~= old(self).container_map_1g@,
    {
```

**Audit notes**:

### 函数语义（real impl）

helper3 是 `remove_mapping_4k` 的**最简单分支**：当被删的 `(pcid, va)` 不是 target_ptr 上最后一条 mapping（`ref_count >= 2`），page 仍被其他 mapping 引用着，不能回收，只需 ref_count 减 1 并从 mappings 移除该条目。target_ptr 保持 Mapped4k 状态，留在原 container，free pool / perm 完全不动。

real impl 只两步（line 605-606）：
```rust
self.set_ref_count(page_ptr2page_index(target_ptr), old_ref_count - 1);
self.set_mapping(page_ptr2page_index(target_ptr), Ghost(old_mappings@.remove((pcid, va))));
```

### 与 helper1/2 的关键差异：`container_map_4k =~= old` 未注释

| ensures | helper1 / helper2 | helper3 |
|---|---|---|
| `container_map_4k` | `=~= old.insert(c, old[c].remove(target_ptr))` — target 从容器移走 | **`=~= old`** — 所有容器内容完全不变 |

这条强 ensures 通过 `container_wf` 双向锁死：
- `container_map_4k =~= old` ⇒ target_ptr 仍 ∈ `old.container_map_4k[c]`
- `container_wf` 双向（line 466-470 + 487-495）⇒ `target_ptr.state == Mapped4k`（不变）
- 所有非-target 的 Mapped4k 状态也都被锁住

加上 `allocated_pages_*() =~= old` 锁住 Allocated 状态，helper3 **唯一剩下的自由度是 Free pool**。

### ensures 直接锁死或间接锁死的字段

- `target_ptr.state == Mapped4k` ✓（via `container_map_4k =~= old` + `container_wf`）
- `target_ptr.mappings == old.mappings.remove((pcid, va))` ✓（显式）
- `target_ptr.io_mappings == old.io_mappings` ✓（显式）
- `target_ptr.ref_count == old.ref_count - 1` ✓（via `mapped_pages_have_reference_counter`：`ref_count = mappings.len + io_mappings.len`）
- `target_ptr.owning_container == Some(c)` ✓（via `container_wf`：state=Mapped4k ⇔ owning_container.is_Some()，加 container_map_4k 不变）
- 所有其他 Mapped4k 页保持原状 ✓
- 所有 Allocated* 页保持原状 ✓

### ensures 没钉死的（incompleteness 维度）

1. **Free pool 仍无 anchor** —— 同 helper1/2 的 A0 cross-page 攻击仍然适用
2. `target_ptr.is_io_page`、`rev_pointer`（C-Field；real impl 因没 setter 不动）
3. 非 Mapped、非 Allocated 的 4k 页（Free4k/Unavailable4k/Pagetable/Io）之间互相翻转
4. `free_pages_4k/2m/1g` Seq 排列（B-Seq passive）

注意：helper3 **没有"target_ptr 目的 state 二义性"** —— target stay Mapped4k 是被 spec 强制的，因为 `container_map_4k =~= old` 直接锁住。所以 helper3 比 helper1/2 **少一个 A0 维度**，只剩跨页 A0 + B-Seq + C-Field。

### Impl E 仍然适用

**Impl A (real)**：只走 line 605-606 两步
**Impl E (alt)**：在 Impl A 基础上额外偷一个无关的 `q ∈ old.free_pages_4k.to_set()`：
- `set_state(idx(q), Unavailable4k)`
- proof: 从 `free_pages_4k` 列表移除 q
- proof: `tracked_remove(q)` from `page_perms_4k`

逐项 ensures 验证：

| ensures 项 | Impl E 验证 |
|---|---|
| `self.wf()` | 见下方分项 ✓ |
| `allocated_pages_4k/2m/1g() =~= old` | q 没动 allocated ✓ |
| `forall p mapped ∧ p≠target_ptr: 不变` | q 在 new 里 `page_is_mapped(q)==false`，蕴含前件假，vacuous ✓ |
| `page_mappings(target_ptr) =~= old.remove((P,V))` | 跟 q 无关 ✓ |
| `page_io_mappings(target_ptr) =~= old` | 跟 q 无关 ✓ |
| `container_map_4k =~= old` | q ∉ 任何 container ✓ |
| `container_map_2m/1g =~= old` | ✓ |

wf 子条款验证与 helper1 的 Impl E 验证表逐行一致：
- `free_pages_4k_wf` 双向：q.state=Unavailable4k 时前件假；q 已从 list 移除时反向 forall 空集合下 vacuous ✓
- `mapped_pages_4k_wf` 双向：q.state≠Mapped4k ✓
- `allocated_pages_4k_wf` 双向：q.state≠Allocated4k ✓
- `perm_wf`（dom = mapped + free.to_set）：new.dom 减少 {q}，new.free.to_set 也减少 {q} ✓
- `container_wf`：q.owning_container=None ∧ q.state ∉ Mapped3 ✓
- `mapped_pages_have_reference_counter`：q.ref_count=0 ∧ q.state ∉ Mapped3 ∧ ref_count=0+0 ✓
- `hugepages_wf`、`merged_pages_wf`：q.state=Unavailable4k 不触发任一前件 ✓

→ Impl E 合法，det check SAT。

### 可观察差异

| 量 | Impl A | Impl E |
|---|---|---|
| `page_array.seq@[idx(q)].state` | `Free4k` | `Unavailable4k` |
| `free_pages_4k@` (Seq view) | `[..., q_addr, ...]` | `[..., ...]`（移除 q） |
| `free_pages_4k().to_set()` | 含 q | 不含 q |
| `page_perms_4k@.dom()` | 含 q | 不含 q |
| `page_array.seq@[idx(target_ptr)].ref_count` | `old.ref_count - 1` | 同 |
| `page_array.seq@[idx(target_ptr)].mappings` | `old.remove((P,V))` | 同 |

### Verdict 对照（4 个 remove helper 全家福）

| Helper | A0 维度数 | 说明 |
|---|---|---|
| `remove_io_mapping_4k_helper1` | **2** | Free pool 跨页攻击 + target_ptr 目的 state 自由 |
| `remove_mapping_4k_helper1` | **2** | 同（与 io 版同构） |
| `remove_mapping_4k_helper2` | **2 (强化)** | Free pool 跨页攻击 + target_ptr 目的 state 自由（real impl 走 Free4k 路径，与 helper1 的 Unavailable4k 路径正相反，spec 不区分） |
| `remove_mapping_4k_helper3` | **1** | 仅 Free pool 跨页攻击（target stay Mapped4k 由 `container_map_4k =~= old` 强制） |

helper3 是这一族里**最干净**的 case：只剩 "Free pool 无 anchor" 这一个 A0 缺陷，其他都被 ensures + wf 锁住了。**最适合作为示范 case** 向开发者解释 Free pool 无 anchor 这个跨函数系统性问题——spec 看起来"该锁的都锁了"（target/container/allocated/mapped 全锁住），唯独漏了 Free pool。

### 修法

```rust
self.free_pages_4k() =~= old(self).free_pages_4k(),
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
self.page_perms_4k@ =~= old(self).page_perms_4k@,
self.page_perms_2m@ =~= old(self).page_perms_2m@,
self.page_perms_1g@ =~= old(self).page_perms_1g@,
```

target_ptr.state、container、ref_count、mappings 等都不用加（已由 `container_map_4k =~= old` + wf 间接锁死）。

**Confirmed verdict**: ✅ **A0 + B-Seq passive + C-Field**——最少的 A0 维度（只跨页 Free pool 攻击），不像 helper1/2 还有 target_ptr 自身的目的 state 自由。仍是真正的 spec bug，且**作为 demo 最直观**：直接对开发者展示"看，spec 把所有跟 target 直接相关的事情都钉死了，但 Free pool 仍然能被悄悄改动"。