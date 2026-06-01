# atmosphere page-allocator spec — incompleteness audit (PR-ready summary)

> **7 actionable spec defects** in `verified/allocator/` (+ 2 entries filed for discussion).
> Audit derived from a determinism analysis of the VeruSAGE-Bench atmosphere corpus.
> Long-form rationale, full witnesses, and per-case source / equal-fn listings are in [`atmosphere-incompleteness-cases-2026-05-26.en.md`](./atmosphere-incompleteness-cases-2026-05-26.en.md); this file is the compressed PR companion.

## TL;DR

For each function below, the public `ensures` admits two implementations whose post-states differ observably on the same input — i.e. the spec is incomplete with respect to determinism.

| Group | Cases | Nature | Suggested action |
|---|---|---|---|
| **Part 1 — Spec gaps**          | 5 | Missing constraints; spec under-promises | Per-case ensures additions (each is 1–6 lines) |
| **Part 2 — Set vs Seq anchor**  | 2 | Public `=~=` (Set) hides the underlying `StaticLinkedList` `Seq` order | Bulk fix in **Appendix A**: tighten `=~=` → `==` on `free_pages_*` in the affected public APIs |
| **Discussion only** (#8, #9)    | 2 | Knowingly accepted in the project (Array fresh-alloc, slinkedlist::push slot choice) | Discussion required with spec authors before acting (latent intent / API shape decisions) |

The 5 Part-1 cases are independent and each can be merged in isolation.
The 2 Part-2 cases collapse into the single setter-mirror change described in Appendix A.

## Overview

| # | Case | Sibling | Group | One-line summary |
|---|------|---------|-------|------------------|
| 1 | `alloc_and_map_2m`              | —                              | Spec gap         | No `contains(ret)` clause; impl may overwrite a *mapped* page |
| 2 | `merged_4k_to_2m`               | —                              | Spec gap         | ensures references neither `target_ptr` nor `target_page_idx` |
| 3 | `remove_io_mapping_4k_helper1`  | `remove_mapping_4k_helper1`    | Spec gap         | `Free*` pools have no anchor; impl may steal an unrelated free page |
| 4 | `remove_mapping_4k_helper2`     | —                              | Spec gap (**P0**) | ensures byte-identical to `helper1` despite opposite recycle path |
| 5 | `remove_mapping_4k_helper3`     | —                              | Spec gap         | Cleanest "Free pool no anchor" instance |
| 6 | `add_io_mapping_4k`             | `add_mapping_4k`               | Set vs Seq       | `free_pages_*` permutation legal under `=~=` |
| 7 | `free_page_4k`                  | —                              | Set vs Seq       | Insertion position of `target_ptr` in the free list unspecified |
| 8 | `Array::new`                    | —                              | Discussion       | `ensures ret.wf()` (= `len==N`) only; sole caller overwrites |
| 9 | `StaticLinkedList::push`        | —                              | Discussion       | Returned `SLLIndex` reveals which free slot was popped; all callers `permitted=True` |

---

## Part 1 — Spec gaps (5 cases, actionable)

### #1 `alloc_and_map_2m`

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_2m.rs:590`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_2m.rs#L590)

**Problem.** Unlike its 4k sibling, the ensures never says `old(self).free_pages_2m().contains(ret)`. The only clause linking `ret` to the free pool is `self.free_pages_2m() =~= old.free_pages_2m().remove(ret)`, which is also satisfied when `ret ∉ old.free_pages_2m` (`Set::remove` is a no-op there). An implementation may return a page that is **already mapped** in `old(self)`, overwriting its existing mapping rather than allocating from the free pool.

**Suggested fix.** Add the missing anchor, mirroring `alloc_page_4k` line 627:

```rust
ensures
    old(self).free_pages_2m().contains(ret),
```

---

### #2 `merged_4k_to_2m`

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__merged_4k_to_2m.rs:610`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__merged_4k_to_2m.rs#L610)

**Problem.** The ensures references **neither** `target_ptr` **nor** `target_page_idx`. The only constraint on the free pools is the *count delta* (4k: −512, 2m: +1). An implementation may ignore the caller's input and merge any other 2m-aligned block of 512 consecutive `Free4k` pages.

**Suggested fix.** Bind the input to the post-state:

```rust
ensures
    self.free_pages_2m() =~= old(self).free_pages_2m().insert(target_ptr),
    self.free_pages_4k() =~= old(self).free_pages_4k().difference(
        Set::new(|p: PagePtr| exists|i: int|
            target_page_idx <= i < target_page_idx + 512
                && p == page_index2page_ptr(i as usize))
    ),
    self.page_array@[target_page_idx as int].state == PageState::Free2m,
    forall|i: int| target_page_idx < i < target_page_idx + 512
        ==> self.page_array@[i].state == PageState::Merged2m,
```

---

### #3 `remove_io_mapping_4k_helper1` (and sibling `remove_mapping_4k_helper1`)

- **Source (io)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_io_mapping_4k_helper1.rs:552`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_io_mapping_4k_helper1.rs#L552)
- **Source (sibling)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper1.rs:551`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper1.rs#L551)

**Problem.** The ensures anchors `Mapped*`, `Allocated*`, and `container_map_*`, but provides **no anchor for the `Free*` pools or `page_perms_*`**. Page-array entries in state `Free4k` / `Unavailable4k` / `Pagetable` / `Io` are unconstrained. An implementation may, in addition to recycling `target_ptr`, secretly remove an unrelated `Free4k` page `q` from `free_pages_4k`, flip its state to `Unavailable4k`, and `tracked_remove` its perm. The dual `free_pages_4k_wf` invariant becomes vacuous because both directions are degenerate (state was flipped and the seq is empty).

**Suggested fix.**

```rust
ensures
    self.free_pages_4k() =~= old(self).free_pages_4k(),
    self.free_pages_2m() =~= old(self).free_pages_2m(),
    self.free_pages_1g() =~= old(self).free_pages_1g(),
    self.page_perms_4k@ =~= old(self).page_perms_4k@.remove(target_ptr),
    self.page_perms_2m@ =~= old(self).page_perms_2m@,
    self.page_perms_1g@ =~= old(self).page_perms_1g@,
    self.page_array@[page_ptr2page_index(target_ptr) as int].state == PageState::Unavailable4k,
```

The mapping sibling has identical ensures and takes the same fix.

---

### #4 `remove_mapping_4k_helper2` — **P0**

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper2.rs:598`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper2.rs#L598)

**Problem (most serious of the set).** `helper2`'s ensures is **byte-for-byte identical** to `helper1`'s; only the `requires` flips `is_io_page == true → false`. But the two helpers have opposite *recycle paths*:

- `helper1` (IO page, hand-off): target's `state → Unavailable4k`, perm dropped, **not** in free pool.
- `helper2` (RAM page, recycle): target's `state → Free4k`, perm kept, **pushed into** `free_pages_4k`.

Because the spec doesn't distinguish them, an implementation of `helper2` may walk the `helper1` path (treat the RAM page as MMIO and silently drop it = **memory leak**), or vice versa (hand a MMIO address back to the general allocator = **IO safety bug**). Both wrong impls pass Verus.

**Suggested fix.** Mirror `helper1`'s shape but flip the recycle target (the two clauses marked below are precisely what makes the two helpers semantically different):

```rust
ensures
    self.page_array@[page_ptr2page_index(target_ptr) as int].state == PageState::Free4k,
    self.free_pages_4k() =~= old(self).free_pages_4k().insert(target_ptr),  // ← KEY diff vs helper1
    self.free_pages_2m() =~= old(self).free_pages_2m(),
    self.free_pages_1g() =~= old(self).free_pages_1g(),
    self.page_perms_4k@.dom() =~= old(self).page_perms_4k@.dom(),           // ← KEY diff vs helper1
    self.page_perms_2m@ =~= old(self).page_perms_2m@,
    self.page_perms_1g@ =~= old(self).page_perms_1g@,
```

---

### #5 `remove_mapping_4k_helper3`

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper3.rs:570`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper3.rs#L570)

**Problem.** The cleanest demonstration of the "Free pool no anchor" pattern: `helper3` is the `ref_count != 1` branch (target stays `Mapped4k`, only a single `(pcid, va)` entry is removed). Target is fully anchored via `container_map_4k =~= old`; the only freedom left is the same cross-page free-pool attack as #3. Target's `state` / `ref_count` / `owning_container` are already locked by `container_map_4k =~= old` + `*_wf`.

**Suggested fix.**

```rust
ensures
    self.free_pages_4k() =~= old(self).free_pages_4k(),
    self.free_pages_2m() =~= old(self).free_pages_2m(),
    self.free_pages_1g() =~= old(self).free_pages_1g(),
    self.page_perms_4k@ =~= old(self).page_perms_4k@,
    self.page_perms_2m@ =~= old(self).page_perms_2m@,
    self.page_perms_1g@ =~= old(self).page_perms_1g@,
```

---

## Part 2 — Set vs Seq anchor (2 cases, one bulk fix)

Both cases use Set-level `=~=` on `free_pages_*` whose underlying field is a `StaticLinkedList<PagePtr, _>` (`View = Seq<PagePtr>`). Two implementations may compute the same `to_set()` image with different `Seq` orderings and structurally distinct post-states. The same bulk fix described in **Appendix A** closes both.

### #6 `add_io_mapping_4k` (and sibling `add_mapping_4k`)

- **Source (io)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k.rs:566`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k.rs#L566)
- **Source (sibling)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__add_mapping_4k.rs:570`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__add_mapping_4k.rs#L570)

**Problem.** The function only writes to `target_ptr`'s `io_mappings` (resp. `mappings`). `free_pages_*` should be untouched — and the underlying setters (`set_io_mapping`, `set_ref_count`) **do** promise field-level `==` (see Appendix A). The public ensures, however, only writes Set-level `=~=`, so an impl may re-shuffle the `StaticLinkedList` (updating each Free page's `rev_pointer` to keep `free_pages_4k_wf`) and pass verification.

**Suggested fix.** Replace the three Set-level lines:

```rust
self.free_pages_4k() =~= old(self).free_pages_4k(),
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
```

with the Seq-level lines the underlying setters already promise:

```rust
self.free_pages_4k == old(self).free_pages_4k,
self.free_pages_2m == old(self).free_pages_2m,
self.free_pages_1g == old(self).free_pages_1g,
```

See Appendix A for the rationale and a list of the other functions in this file family that should receive the same treatment.

*Note:* `add_io_mapping_4k.rs` line 582 and `add_mapping_4k.rs` line 582 contain a duplicate `free_pages_4k() =~= old(self).free_pages_4k()` line that appears to be a copy-paste of the line above; almost certainly intended to be `free_pages_2m`.

---

### #7 `free_page_4k`

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__free_page_4k.rs:613`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__free_page_4k.rs#L613)

**Problem.** Same shape as #6, but for the *insertion* direction: ensures says `self.free_pages_4k() =~= old.free_pages_4k().insert(target_ptr)` (Set-level), so the freedom is *where* `target_ptr` lands in the underlying `Seq` (head / tail / any middle slot) and how the other entries' `rev_pointer`s rotate.

**Suggested fix.** Match the real impl's `push` semantics at the Seq level:

```rust
self.free_pages_4k@ == old(self).free_pages_4k@.push(target_ptr),
self.free_pages_2m == old(self).free_pages_2m,
self.free_pages_1g == old(self).free_pages_1g,
```

---

## Appendix A — Setter vs public-API ensures inconsistency

> **Applies to:** primarily **#6** and **#7** (Part 2 — Set vs Seq anchor) — tightening the public ensures as described below closes both wholesale. The same pattern also strengthens the free-pool / perm-map anchors in **#3** and **#5** (Part 1) and matches what the per-case fix snippets for those entries already propose.

Every `impl2__*.rs` file in `verified/allocator/` contains two layers:

1. **Low-level setters** (marked `#[verifier(external_body)]`, e.g. `set_state`, `set_io_mapping`, `set_mapping`, `set_ref_count`, `set_owning_container`, `set_rev_pointer`): ensures use **field-level `==`** on every untouched field — including `self.free_pages_4k == old(self).free_pages_4k` (Seq-level), plus all 12+ ghost / tracked maps.

2. **Public APIs that compose these setters** (the Part 2 functions above): ensures use **closed-spec-fn `=~=`** comparison, e.g. `self.free_pages_4k() =~= old(self).free_pages_4k()` (Set-level, via `closed spec fn free_pages_4k() = self.free_pages_4k@.to_set()`).

Example — `add_io_mapping_4k.rs` lines 580–583 (public API) vs lines 801–815 (`set_io_mapping` setter):

```rust
// Public API add_io_mapping_4k.ensures:
self.free_pages_4k.len() == old(self).free_pages_4k.len(),   // Seq.len()
self.free_pages_4k() =~= old(self).free_pages_4k(),          // Set =~=
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),

// Underlying setter set_io_mapping.ensures:
self.free_pages_4k == old(self).free_pages_4k,               // Seq == (STRONGER)
self.free_pages_2m == old(self).free_pages_2m,
self.free_pages_1g == old(self).free_pages_1g,
self.allocated_pages_4k == old(self).allocated_pages_4k,     // Ghost<Set> ==
self.mapped_pages_4k    == old(self).mapped_pages_4k,
self.page_perms_4k      == old(self).page_perms_4k,          // Tracked<Map> ==
/* ... 12+ ghost/tracked fields with == ... */
```

The setter library is the only way an implementation can mutate state. So every public API in this family is *actually* constrained at the Seq / ghost-identity level — but only writes the weaker Set-level statement to its callers and to the verifier.

**Question for the spec author.**

1. Is the weak public ensures intentional (e.g. to allow future impls that bypass these setters, or to keep proof obligations lighter)?
2. Or is it accidental — should the public API ensures simply mirror the setters?

If accidental: tightening `=~=` to `==` on `free_pages_*` (and adding the missing `page_perms_*` / `allocated_pages_*` / `mapped_pages_*` lines) closes Part 2 in one pass and eliminates the entire Set-vs-Seq class. The affected public APIs in this family are at least:

- `add_io_mapping_4k`, `add_mapping_4k`               (#6 + sibling)
- `free_page_4k`                                       (#7)
- `remove_*_helper*` family                            (also covers #3, #5)
- the alloc-and-map functions

Tightening `=~=` → `==` would not, however, close Part 1 (#1, #2, #4) — those have genuinely missing constraints that need new ensures lines.

---

## Discussion only

These two entries are technically incomplete with respect to determinism but are **not** filed as PR-actionable bugs in this audit — either the project explicitly marks the callers `permitted=True`, or the under-specification is provably unobservable in this codebase. They are included so spec authors can see the full audit result.

### #8 `Array::new` — sole caller already overwrites

- **Source**: [`verified/array/array_set__impl0__new.rs:17`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/array/array_set__impl0__new.rs#L17)

`Array::new()` is an `#[verifier(external_body)]` constructor whose ensures only pins `ret.wf()` (= `ret.seq@.len() == N`); element values are free. Two impls returning, e.g., `seq![false]` and `seq![true]` (for `A=bool, N=1`) both satisfy ensures but produce different views.

**Why not filed for action.** The only call site in the corpus is `ArraySet::new`, which runs `for i in 0..N { ret.data.set(i, false); }` immediately after `Array::new()`, with a loop invariant `forall|j: int| 0 <= j < i ==> ret.data@[j] == false`. The under-specified initial `seq@` is overwritten before any client can observe it.

**Note on unstated intent.** That the sole caller bothers to run a full coverage loop is itself evidence of a *latent* design intent — the freshly constructed array is supposed to be predictable / safe to read — but this intent is currently enforced ad-hoc at the call site, not expressed anywhere in the spec. If a future caller forgets the overwrite loop, Verus will silently accept reads of undefined ghost contents. Worth a discussion with the spec authors on whether to surface this intent in the API (e.g. via stronger ensures, a different constructor name, or both).

### #9 `StaticLinkedList::push` — slot choice exposed but project-tolerated

- **Source**: [`verified/slinkedlist/slinkedlist__spec_impl_u__impl2__push.rs:232`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__push.rs#L232)

`push` returns `ret: SLLIndex` = the free-list slot it popped to host the new element. The return is pinned only via `post.get_node_ref(*new_value) == ret`, which by the closed body of `get_node_ref` resolves to `post.value_list@[…]` — the **internal** allocation slot. When `pre.free_list@.len() ≥ 2`, two impls may pop different free-list elements; both pass ensures (`post@ = pre@.push(*new_value)`, existing slot indices preserved, `post.wf()`), but return different `SLLIndex` values.

**Recommended spec tightening (low cost).** Every real implementation already maintains `free_list_head` as part of `wf()` and pops it as the natural / canonical choice (popping any other slot would require either a linear scan or extra bookkeeping). So pinning `ret` to `free_list_head` is strictly stronger than the current spec without forcing any impl change:

```rust
ensures
    ret == pre.free_list_head,
    post.value_list@ == pre.value_list@.push(pre.free_list_head),
```

Adopting this would let all four caller sites drop their `permitted=True` annotation, and would surface any future regression that secretly randomises the slot choice. The alternative — exposing a `spec fn next_free_slot() -> SLLIndex` accessor and requiring `ret == old(self).next_free_slot()` — gives the same guarantee with one extra layer of indirection.
