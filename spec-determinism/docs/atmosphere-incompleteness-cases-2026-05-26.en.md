# atmosphere spec-incompleteness case set

> 10 cases / 14 unique spec functions / 29 underlying instances.
> Each witness shows two implementations whose post-states differ on the same input even though both satisfy the spec — i.e. the spec is incomplete with respect to determinism.
> Source dataset: `spec-determinism/results-verusage-viewreg/atmosphere/full_run.json`.
>
> Cases are partitioned into three groups by the nature of the freedom the spec admits.
> - **Part 1 — Spec gaps** (5 cases): the spec is missing constraints; the witness shows two implementations that compute observably different end-states. These are genuine bugs in the spec.
> - **Part 2 — `Seq` ordering free** (3 cases): the public ensures uses Set-level `=~=` on a field whose underlying view is `Seq<T>` (`StaticLinkedList`). Two impls may produce permutations of the same Set. Mechanical fix: tighten `=~=` to `==` to mirror the underlying setters (see appendix).
> - **Part 3 — Symmetric allocation choice** (5 cases): the spec correctly constrains `ret ∈ old.free_pool` but leaves the choice among ≥2 free elements unspecified; the resulting post-states differ only by which fresh element was picked.
>
> All 29 entries originally tripped a `permitted_reason=permissive_or` detector targeting the `|||` inside the closed spec fn `page_is_mapped`. That `|||` is plain boolean disjunction and is not itself a source of non-determinism — the real sources are the three patterns above.

## Overview

| # | Case | Sibling cases | Pattern | Notes |
|---|------|---------------|---------|-------|
| 1 | `alloc_and_map_2m` | — | Spec gap | No `contains(ret)` clause on `ret` |
| 2 | `merged_4k_to_2m` | — | Spec gap | ensures references neither `target_ptr` nor `target_page_idx` |
| 3 | `remove_io_mapping_4k_helper1` | `remove_mapping_4k_helper1` | Spec gap | Free pool has no anchor in ensures |
| 4 | `remove_mapping_4k_helper2` | — | Spec gap (P0) | Identical ensures to `helper1` but opposite recycle path |
| 5 | `remove_mapping_4k_helper3` | — | Spec gap | Free pool no anchor (cleanest single-dimension case) |
| 6 | `add_io_mapping_4k` | `add_mapping_4k` | Seq ordering free | `free_pages_*` Set-level `=~=` |
| 7 | `free_page_4k` | — | Seq ordering free | insertion position of `target_ptr` in list free |
| 8 | `alloc_page_4k` | `alloc_page_4k_for_new_container` | Symmetric choice | `ret` ∈ `old.free_pages_4k`, any choice legal |
| 9 | `alloc_page_2m` | — | Symmetric choice | `ret` constrained via `Tracked<PagePerm2m>` linearity |
| 10 | `alloc_and_map_4k` | `alloc_and_map_io_4k` | Symmetric choice | `ret` pinned by `LEN-1 + !old.page_is_mapped(ret) + !old.allocated_pages_4k().contains(ret)` |

## Witness format

Each witness is written as a list of assumed facts about the inputs and the two outputs (`r1` / `r2`, `post1_self_` / `post2_self_`). Lines containing `==` are equalities the witness commits to; the closing line starting with `!det_*_equal(...)` is the negated equivalence that fails the structural equality check. `pX` denotes a `PagePtr` value, `cX` a `ContainerPtr`, etc.

---

## Part 1 — Spec gaps

### #1 `alloc_and_map_2m` (×1 instance)

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_2m.rs:590`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_2m.rs#L590)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__alloc_and_map_2m__alloc_and_map_2m/`

#### Why this is incomplete

Unlike its 4k sibling, `alloc_and_map_2m`'s ensures never says `old(self).free_pages_2m().contains(ret)`. The only clause linking `ret` to the free pool is `self.free_pages_2m() =~= old.free_pages_2m().remove(ret)`, which is also satisfied when `ret ∉ old.free_pages_2m` (`Set::remove` is a no-op there). An implementation may return a page that is **already mapped** in `old(self)`, overwriting its mapping rather than allocating from the free pool.

#### Source function

```rust
pub fn alloc_and_map_2m(&mut self, pcid: Pcid, va: VAddr, c_ptr: ContainerPtr) -> (ret: PagePtr)
    requires
        old(self).wf(),
        old(self).free_pages_2m.len() > 0,
        old(self).container_map_2m@.dom().contains(c_ptr),
    ensures
        self.wf(),
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
            self.page_is_mapped(p) && p != ret ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
        self.page_mappings(ret) =~= Set::<(Pcid, VAddr)>::empty().insert((pcid, va)),
        self.page_io_mappings(ret) =~= Set::<(IOid, VAddr)>::empty(),
{ /* … */ }
```

#### Generated equal_fn

```rust
spec fn det_alloc_and_map_2m_equal(r1: PagePtr, r2: PagePtr,
    post1_self_: PageAllocator, post2_self_: PageAllocator) -> bool {
    (r1 == r2)
    && post1_self_.page_array == post2_self_.page_array
    && post1_self_.free_pages_4k == post2_self_.free_pages_4k
    && post1_self_.free_pages_2m == post2_self_.free_pages_2m
    && /* … all 16 fields of PageAllocator … */
}
```

#### Witness

```
  pre_self_.wf()
  pre_self_.free_pages_2m.len() > 0
  pre_self_.container_map_2m@.dom().contains(c0)
  // Two distinct PagePtrs: p0 currently Free2m, p1 currently Mapped2m to (pcid_x, va_x).
  pre_self_.page_array@[0].state == PageState::Free2m
  pre_self_.page_array@[1].state == PageState::Mapped2m
  pre_self_.page_array@[1].mappings@ == set![(pcid_x, va_x)]
  pre_self_.page_array@[1].owning_container == Some(c0)
  pre_self_.free_pages_2m@ == seq![p0]
  pre_self_.mapped_pages_2m@ == set![p1]
  pre_self_.allocated_pages_2m@ == set![]
  pre_self_.page_perms_2m@.dom() == set![p0, p1]
  pre_self_.container_map_2m@[c0] == set![p1]
  // Inputs.
  (pcid, va) != (pcid_x, va_x)
  // Run 1 — Impl A: allocate p0 from the free pool.
  r1 == p0
  post1_self_.page_array@[0].state == PageState::Mapped2m
  post1_self_.page_array@[0].mappings@ == set![(pcid, va)]
  post1_self_.page_array@[1] == pre_self_.page_array@[1]
  post1_self_.free_pages_2m@ == seq![]
  post1_self_.mapped_pages_2m@ == set![p0, p1]
  // Run 2 — Impl B: overwrite the already-mapped p1.
  r2 == p1
  post2_self_.page_array@[1].mappings@ == set![(pcid, va)]
  post2_self_.page_array@[1].io_mappings@ == set![]
  post2_self_.page_array@[1].state == PageState::Mapped2m
  post2_self_.page_array@[0] == pre_self_.page_array@[0]
  post2_self_.free_pages_2m@ == seq![p0]
  post2_self_.mapped_pages_2m@ == set![p1]
  !det_alloc_and_map_2m_equal(r1, r2, post1_self_, post2_self_)
```

Both runs satisfy every ensures clause and `wf()`. They differ on `r`, `free_pages_2m`, `mapped_pages_2m`, and two entries of `page_array`.

#### Suggested fix

Add `old(self).free_pages_2m().contains(ret)`, mirroring `alloc_page_4k`'s line 627.

---

### #2 `merged_4k_to_2m` (×1 instance)

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__merged_4k_to_2m.rs:610`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__merged_4k_to_2m.rs#L610)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__merged_4k_to_2m__merged_4k_to_2m/`

#### Why this is incomplete

The ensures references **neither** `target_ptr` **nor** `target_page_idx`. The only constraint on the free pools is *counts*: 4k decreases by 512, 2m increases by 1. An implementation may ignore the caller's input and merge any 2m-aligned block of 512 consecutive `Free4k` pages.

#### Source function

```rust
pub fn merged_4k_to_2m(&mut self, target_ptr: PagePtr, target_page_idx: usize)
    requires
        old(self).wf(),
        target_page_idx + 512 <= NUM_PAGES,
        forall|i: int| target_page_idx <= i < target_page_idx + 512
            ==> old(self).page_array[i].state == PageState::Free4k
                && old(self).page_array[i].is_io_page == false,
        old(self).free_pages_2m().len() < NUM_PAGES,
        page_ptr_2m_valid(page_index2page_ptr(target_page_idx)),
        old(self).free_pages_4k().len() >= 512,
    ensures
        self.wf(),
        forall|p: PagePtr|
            self.page_is_mapped(p) ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
        self.container_map_4k@ =~= old(self).container_map_4k@,
        self.container_map_2m@ =~= old(self).container_map_2m@,
        self.container_map_1g@ =~= old(self).container_map_1g@,
        self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
        self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
        self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
        self.free_pages_4k().len() == old(self).free_pages_4k().len() - 512,
        self.free_pages_2m().len() == old(self).free_pages_2m().len() + 1,
        self.free_pages_1g().len() == old(self).free_pages_1g().len(),
{ /* … */ }
```

#### Generated equal_fn

```rust
spec fn det_merged_4k_to_2m_equal(r1: (), r2: (),
    post1_self_: PageAllocator, post2_self_: PageAllocator) -> bool {
    (r1 == r2)
    && post1_self_.page_array == post2_self_.page_array
    && /* … all 16 fields of PageAllocator … */
}
```

#### Witness

```
  pre_self_.wf()
  // Setup: NUM_PAGES = 1024, two 2m-aligned all-Free4k blocks at idx 0 and idx 512.
  forall i in 0..512:    pre_self_.page_array@[i].state == PageState::Free4k
  forall i in 512..1024: pre_self_.page_array@[i].state == PageState::Free4k
  forall i in 0..1024:   pre_self_.page_array@[i].is_io_page == false
  pre_self_.free_pages_4k@.to_set() == set![addr_0, addr_1, .., addr_1023]
  pre_self_.free_pages_4k.len() == 1024
  pre_self_.free_pages_2m@ == seq![]
  pre_self_.allocated_pages_4k@ == set![]
  pre_self_.allocated_pages_2m@ == set![]
  pre_self_.page_perms_4k@.dom() == set![addr_0, .., addr_1023]
  pre_self_.page_perms_2m@.dom() == set![]
  // Inputs: caller asks for the block starting at idx 0.
  target_page_idx == 0
  target_ptr == page_index2page_ptr(0)
  // Run 1 — Impl A: honour the input.
  r1 == ()
  post1_self_.page_array@[0].state == PageState::Free2m
  forall i in 1..512:    post1_self_.page_array@[i].state == PageState::Merged2m
  forall i in 512..1024: post1_self_.page_array@[i].state == PageState::Free4k
  post1_self_.free_pages_4k@.to_set() == set![addr_512, .., addr_1023]
  post1_self_.free_pages_2m@.to_set() == set![addr_0]
  post1_self_.page_perms_4k@.dom() == set![addr_512, .., addr_1023]
  post1_self_.page_perms_2m@.dom() == set![addr_0]
  // Run 2 — Impl B: ignore the input, merge the OTHER 2m block.
  r2 == ()
  forall i in 0..512:    post2_self_.page_array@[i].state == PageState::Free4k
  post2_self_.page_array@[512].state == PageState::Free2m
  forall i in 513..1024: post2_self_.page_array@[i].state == PageState::Merged2m
  post2_self_.free_pages_4k@.to_set() == set![addr_0, .., addr_511]
  post2_self_.free_pages_2m@.to_set() == set![addr_512]
  post2_self_.page_perms_4k@.dom() == set![addr_0, .., addr_511]
  post2_self_.page_perms_2m@.dom() == set![addr_512]
  !det_merged_4k_to_2m_equal(r1, r2, post1_self_, post2_self_)
```

Same input, same `(target_ptr, target_page_idx)`, two completely different post-states — both satisfy ensures + `wf()`.

#### Suggested fix

Bind the input to the post-state:

```rust
self.free_pages_2m() =~= old(self).free_pages_2m().insert(target_ptr),
self.free_pages_4k() =~= old(self).free_pages_4k().difference(
    Set::new(|p: PagePtr| exists|i:int|
        target_page_idx <= i < target_page_idx + 512 && p == page_index2page_ptr(i as usize))
),
self.page_array@[target_page_idx as int].state == PageState::Free2m,
forall|i:int| target_page_idx < i < target_page_idx + 512
    ==> self.page_array@[i].state == PageState::Merged2m,
```

---

### #3 `remove_io_mapping_4k_helper1` (×1 instance; also `remove_mapping_4k_helper1`, ×1 instance)

- **Source (io)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_io_mapping_4k_helper1.rs:552`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_io_mapping_4k_helper1.rs#L552)
- **Source (sibling)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper1.rs:551`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper1.rs#L551)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__remove_io_mapping_4k_helper1__remove_io_mapping_4k_helper1/`

#### Why this is incomplete

The ensures anchors `Mapped*`, `Allocated*`, and `container_map_*` (each Mapped state is dually pinned by `*_wf`), but provides **no anchor for the `Free*` pools**. Page-array entries whose state is `Free4k` / `Unavailable4k` / `Pagetable` / `Io` are not constrained. An implementation may, in addition to recycling `target_ptr`, secretly remove an unrelated `Free4k` page `q` from `free_pages_4k`, flip its state to `Unavailable4k`, and `tracked_remove` its perm.

#### Source function (io variant; mapping sibling is identical modulo `is_io_page` / `pcid`-vs-`ioid`)

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
            self.page_is_mapped(p) && p != target_ptr ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
        self.page_mappings(target_ptr) =~= old(self).page_mappings(target_ptr),
        self.page_io_mappings(target_ptr) =~= old(self).page_io_mappings(target_ptr).remove((ioid, va)),
        self.container_map_2m@ =~= old(self).container_map_2m@,
        self.container_map_1g@ =~= old(self).container_map_1g@,
        self.container_map_4k@ =~= old(self).container_map_4k@.insert(
            old(self).page_array@[page_ptr2page_index(target_ptr) as int].owning_container.unwrap(),
            old(self).container_map_4k@[old(self).page_array@[page_ptr2page_index(target_ptr) as int]
                .owning_container.unwrap()].remove(target_ptr),
        ),
{ /* … */ }
```

#### Generated equal_fn

```rust
spec fn det_remove_io_mapping_4k_helper1_equal(r1: (), r2: (),
    post1_self_: PageAllocator, post2_self_: PageAllocator) -> bool {
    (r1 == r2)
    && post1_self_.page_array == post2_self_.page_array
    && /* … all 16 fields of PageAllocator … */
}
```

#### Witness

```
  pre_self_.wf()
  // target_ptr (= tp) is the io page being released.
  pre_self_.page_array@[0].state == PageState::Mapped4k
  pre_self_.page_array@[0].is_io_page == true
  pre_self_.page_array@[0].ref_count == 1
  pre_self_.page_array@[0].mappings@ == set![]
  pre_self_.page_array@[0].io_mappings@ == set![(I, V)]
  pre_self_.page_array@[0].owning_container == Some(c)
  pre_self_.mapped_pages_4k@ == set![tp]
  pre_self_.container_map_4k@[c] == set![tp]
  // q is an UNRELATED Free4k page. Impl E will steal it.
  pre_self_.page_array@[2].state == PageState::Free4k
  pre_self_.page_array@[2].owning_container == None
  pre_self_.free_pages_4k@ == seq![q_addr]
  pre_self_.page_perms_4k@.dom() == set![tp, q_addr]
  // Inputs.
  target_ptr == tp
  ioid == I
  va == V
  // Run 1 — Impl A: only touch target.
  r1 == ()
  post1_self_.page_array@[0].state == PageState::Unavailable4k
  post1_self_.page_array@[0].ref_count == 0
  post1_self_.page_array@[0].io_mappings@ == set![]
  post1_self_.page_array@[0].owning_container == None
  post1_self_.page_array@[2] == pre_self_.page_array@[2]
  post1_self_.free_pages_4k@ == seq![q_addr]
  post1_self_.page_perms_4k@.dom() == set![q_addr]
  post1_self_.mapped_pages_4k@ == set![]
  post1_self_.container_map_4k@ == map![c => set![]]
  // Run 2 — Impl E: also steal q.
  r2 == ()
  post2_self_.page_array@[0] == post1_self_.page_array@[0]
  post2_self_.page_array@[2].state == PageState::Unavailable4k
  post2_self_.free_pages_4k@ == seq![]
  post2_self_.page_perms_4k@.dom() == set![]
  post2_self_.mapped_pages_4k@ == set![]
  post2_self_.container_map_4k@ == map![c => set![]]
  !det_remove_io_mapping_4k_helper1_equal(r1, r2, post1_self_, post2_self_)
```

Both runs satisfy ensures + `wf()`. The Free pool's domain check is dual: `free_pages_4k_wf` requires `state==Free4k ⇒ ptr ∈ free_pages_4k@` (vacuous for Impl E because `q.state` was flipped) and `ptr ∈ free_pages_4k@ ⇒ state==Free4k` (vacuous because `free_pages_4k@ == []`). `perm_wf`'s `dom = mapped + free` is preserved on both sides.

The mapping-version sibling `remove_mapping_4k_helper1` (same file family, `is_io_page == false` flipped to `true` in requires) has identical ensures and admits the same witness.

#### Suggested fix

```rust
self.free_pages_4k() =~= old(self).free_pages_4k(),
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
self.page_perms_4k@ =~= old(self).page_perms_4k@.remove(target_ptr),
self.page_perms_2m@ =~= old(self).page_perms_2m@,
self.page_perms_1g@ =~= old(self).page_perms_1g@,
self.page_array@[page_ptr2page_index(target_ptr) as int].state == PageState::Unavailable4k,
```

---

### #4 `remove_mapping_4k_helper2` (×1 instance) — **P0**

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper2.rs:598`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper2.rs#L598)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper2__remove_mapping_4k_helper2/`

#### Why this is incomplete

`helper2`'s ensures is **byte-for-byte identical** to `helper1`'s (only the requires flips `is_io_page == true` → `false`). But the two helpers have opposite *recycle paths*:

- `helper1` (io page, hand-off): target's `state → Unavailable4k`, perm dropped, **not** in free pool.
- `helper2` (RAM page, recycle): target's `state → Free4k`, perm kept, **pushed into** `free_pages_4k`.

Because the spec doesn't distinguish them, an implementation of `helper2` may walk the `helper1` path (treating the RAM page as if it were MMIO) and *vice versa*. A wrong choice causes either memory leakage (RAM page silently dropped) or an IO safety bug (MMIO address handed back to the general allocator). Both wrong impls pass Verus.

#### Source function

```rust
fn remove_mapping_4k_helper2(&mut self, target_ptr: PagePtr, pcid: Pcid, va: VAddr)
    requires
        old(self).wf(),
        old(self).mapped_pages_4k().contains(target_ptr),
        old(self).page_mappings(target_ptr).contains((pcid, va)),
        old(self).page_array@[page_ptr2page_index(target_ptr) as int].is_io_page == false,
        old(self).page_array@[page_ptr2page_index(target_ptr) as int].ref_count == 1,
    ensures
        // Identical to helper1 modulo (pcid, va) ↔ (ioid, va):
        self.wf(),
        self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
        /* ... allocated_pages_2m/1g, mapped-page preservation, page_mappings/page_io_mappings ... */
        self.container_map_4k@ =~= old(self).container_map_4k@.insert(
            old(self).page_array@[page_ptr2page_index(target_ptr) as int].owning_container.unwrap(),
            old(self).container_map_4k@[old(self).page_array@[page_ptr2page_index(target_ptr) as int]
                .owning_container.unwrap()].remove(target_ptr),
        ),
{
    // Real impl path (line 643-648):
    let rev_index = self.free_pages_4k.push(&target_ptr);
    self.set_rev_pointer(page_ptr2page_index(target_ptr), rev_index);
    self.set_ref_count(page_ptr2page_index(target_ptr), 0);
    self.set_mapping(page_ptr2page_index(target_ptr), Ghost(Set::empty()));
    self.set_state(page_ptr2page_index(target_ptr), PageState::Free4k);
    self.set_owning_container(page_ptr2page_index(target_ptr), None);
}
```

#### Generated equal_fn

Same shape as `helper1` — full field-by-field equality on `PageAllocator`.

#### Witness

```
  pre_self_.wf()
  // Same setup as helper1, but is_io_page == false (regular RAM).
  pre_self_.page_array@[0].state == PageState::Mapped4k
  pre_self_.page_array@[0].is_io_page == false
  pre_self_.page_array@[0].ref_count == 1
  pre_self_.page_array@[0].mappings@ == set![(P, V)]
  pre_self_.page_array@[0].io_mappings@ == set![]
  pre_self_.page_array@[0].owning_container == Some(c)
  pre_self_.mapped_pages_4k@ == set![tp]
  pre_self_.container_map_4k@[c] == set![tp]
  pre_self_.free_pages_4k@ == seq![]
  pre_self_.page_perms_4k@.dom() == set![tp]
  // Inputs.
  target_ptr == tp
  pcid == P
  va == V
  // Run 1 — Impl A' (real RAM recycle path): state→Free4k, push to free pool, keep perm.
  r1 == ()
  post1_self_.page_array@[0].state == PageState::Free4k
  post1_self_.page_array@[0].ref_count == 0
  post1_self_.page_array@[0].mappings@ == set![]
  post1_self_.page_array@[0].owning_container == None
  post1_self_.free_pages_4k@ == seq![tp]
  post1_self_.page_perms_4k@.dom() == set![tp]
  post1_self_.mapped_pages_4k@ == set![]
  post1_self_.container_map_4k@ == map![c => set![]]
  // Run 2 — Impl B' (helper1-style hand-off, WRONG for RAM): state→Unavailable4k, drop perm.
  r2 == ()
  post2_self_.page_array@[0].state == PageState::Unavailable4k
  post2_self_.page_array@[0].ref_count == 0
  post2_self_.page_array@[0].mappings@ == set![]
  post2_self_.page_array@[0].owning_container == None
  post2_self_.free_pages_4k@ == seq![]
  post2_self_.page_perms_4k@.dom() == set![]
  post2_self_.mapped_pages_4k@ == set![]
  post2_self_.container_map_4k@ == map![c => set![]]
  !det_remove_mapping_4k_helper2_equal(r1, r2, post1_self_, post2_self_)
```

Both satisfy ensures + `wf()`; the `c` container's view ends up identical; the difference is whether the RAM page got handed back to the page allocator (`A'`) or silently dropped (`B'`).

#### Suggested fix

Mirror `helper1`'s shape but flip the recycle target:

```rust
self.page_array@[page_ptr2page_index(target_ptr) as int].state == PageState::Free4k,
self.free_pages_4k() =~= old(self).free_pages_4k().insert(target_ptr),     // ← KEY diff vs helper1
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
self.page_perms_4k@.dom() =~= old(self).page_perms_4k@.dom(),               // ← KEY diff vs helper1
self.page_perms_2m@ =~= old(self).page_perms_2m@,
self.page_perms_1g@ =~= old(self).page_perms_1g@,
```

The two clauses marked `KEY diff vs helper1` are precisely what makes `helper1` and `helper2` semantically different. The current spec omits both.

---

### #5 `remove_mapping_4k_helper3` (×1 instance)

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper3.rs:570`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper3.rs#L570)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper3__remove_mapping_4k_helper3/`

#### Why this is incomplete

Cleanest demonstration of the "Free pool no anchor" pattern. `helper3` is the `ref_count != 1` branch — target stays `Mapped4k`, only a single `(pcid, va)` entry is removed. Its ensures *fully* anchors target via `container_map_4k =~= old`, and `allocated_pages_*` is anchored. **The only freedom left is the cross-page Free-pool attack** (steal an unrelated `Free4k` page).

#### Source function

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
            self.page_is_mapped(p) && p != target_ptr ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
        self.page_mappings(target_ptr) =~= old(self).page_mappings(target_ptr).remove((pcid, va)),
        self.page_io_mappings(target_ptr) =~= old(self).page_io_mappings(target_ptr),
        self.container_map_4k@ =~= old(self).container_map_4k@,
        self.container_map_2m@ =~= old(self).container_map_2m@,
        self.container_map_1g@ =~= old(self).container_map_1g@,
{ /* set_ref_count + set_mapping */ }
```

#### Witness

```
  pre_self_.wf()
  pre_self_.page_array@[0].state == PageState::Mapped4k
  pre_self_.page_array@[0].ref_count == 2
  pre_self_.page_array@[0].mappings@ == set![(P, V), (P2, V2)]
  pre_self_.page_array@[0].owning_container == Some(c)
  pre_self_.mapped_pages_4k@ == set![tp]
  pre_self_.container_map_4k@[c] == set![tp]
  // q is an unrelated Free4k page.
  pre_self_.page_array@[2].state == PageState::Free4k
  pre_self_.free_pages_4k@ == seq![q_addr]
  pre_self_.page_perms_4k@.dom() == set![tp, q_addr]
  // Inputs.
  target_ptr == tp; pcid == P; va == V
  // Run 1 — real impl: just decrement ref_count and remove (P,V) from mappings.
  r1 == ()
  post1_self_.page_array@[0].ref_count == 1
  post1_self_.page_array@[0].mappings@ == set![(P2, V2)]
  post1_self_.page_array@[2] == pre_self_.page_array@[2]
  post1_self_.free_pages_4k@ == seq![q_addr]
  post1_self_.page_perms_4k@.dom() == set![tp, q_addr]
  // Run 2 — Impl E: also steal q.
  r2 == ()
  post2_self_.page_array@[0] == post1_self_.page_array@[0]
  post2_self_.page_array@[2].state == PageState::Unavailable4k
  post2_self_.free_pages_4k@ == seq![]
  post2_self_.page_perms_4k@.dom() == set![tp]
  !det_remove_mapping_4k_helper3_equal(r1, r2, post1_self_, post2_self_)
```

#### Suggested fix

```rust
self.free_pages_4k() =~= old(self).free_pages_4k(),
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
self.page_perms_4k@ =~= old(self).page_perms_4k@,
self.page_perms_2m@ =~= old(self).page_perms_2m@,
self.page_perms_1g@ =~= old(self).page_perms_1g@,
```

Target's `state` / `ref_count` / `owning_container` are already locked by `container_map_4k =~= old` + `*_wf`.

---

## Part 2 — `Seq` ordering free

These cases have full Set-level anchors but the underlying field is `StaticLinkedList<PagePtr, _>` whose `View=Seq<PagePtr>`. Two impls may compute the same `to_set()` image but different `Seq` orderings; structural `==` rejects this. See appendix for the cross-cutting setter-vs-public-API observation.

### #6 `add_io_mapping_4k` (×1 instance; also `add_mapping_4k`, ×1 instance)

- **Source (io)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k.rs:566`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k.rs#L566)
- **Source (sibling)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__add_mapping_4k.rs:570`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__add_mapping_4k.rs#L570)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k__add_io_mapping_4k/`

#### Why this is incomplete

The function only writes to `target_ptr`'s `io_mappings`. `free_pages_*` should be completely unchanged. The ensures says so *at the Set level*:

```rust
self.free_pages_4k() =~= old(self).free_pages_4k(),    // .to_set() == .to_set()
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
```

But the underlying `StaticLinkedList` is a sequence. An implementation may re-shuffle the list (updating each Free4k page's `rev_pointer` to keep `free_pages_4k_wf` happy) and still satisfy every ensures clause. The Set-level `=~=` doesn't see the permutation.

The `add_mapping_4k` sibling is structurally identical (touches `mappings` instead of `io_mappings`, same underlying setter pattern).

#### Source function

```rust
pub fn add_io_mapping_4k(&mut self, target_ptr: PagePtr, ioid: IOid, va: VAddr)
    requires
        old(self).wf(),
        old(self).mapped_pages_4k().contains(target_ptr),
        old(self).page_io_mappings(target_ptr).contains((ioid, va)) == false,
        old(self).page_mappings(target_ptr).len() + old(self).page_io_mappings(target_ptr).len() < usize::MAX,
    ensures
        self.wf(),
        self.free_pages_4k.len() == old(self).free_pages_4k.len(),
        self.free_pages_4k() =~= old(self).free_pages_4k(),
        self.free_pages_2m() =~= old(self).free_pages_2m(),
        self.free_pages_1g() =~= old(self).free_pages_1g(),
        self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
        self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
        self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
        self.mapped_pages_4k() =~= old(self).mapped_pages_4k(),
        self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
        self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
        forall|p: PagePtr|
            self.page_is_mapped(p) && p != target_ptr ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
        self.page_io_mappings(target_ptr) =~= old(self).page_io_mappings(target_ptr).insert((ioid, va)),
        self.page_io_mappings(target_ptr).len() == old(self).page_io_mappings(target_ptr).len() + 1,
        self.page_io_mappings(target_ptr).contains((ioid, va)),
        self.page_mappings(target_ptr) =~= old(self).page_mappings(target_ptr),
        self.container_map_4k@.dom() =~= old(self).container_map_4k@.dom(),
        forall|p: PagePtr| #![auto] self.page_is_mapped(p) <==> old(self).page_is_mapped(p),
        forall|c: ContainerPtr| #![auto]
            self.container_map_4k@.dom().contains(c)
                ==> self.get_container_owned_pages(c) =~= old(self).get_container_owned_pages(c),
{ /* set_ref_count + set_io_mapping */ }
```

#### Generated equal_fn

Full field equality on `PageAllocator` (including the raw `free_pages_4k` `StaticLinkedList`, comparing the underlying `Seq`).

#### Witness

```
  pre_self_.wf()
  pre_self_.mapped_pages_4k@ == set![tp]
  pre_self_.page_array@[idx(tp)].state == PageState::Mapped4k
  pre_self_.page_array@[idx(tp)].io_mappings@ == set![]
  // 4 free 4k pages, in this list order.
  pre_self_.free_pages_4k@ == seq![p1, p2, p3, p4]
  pre_self_.page_array@[idx(p1)].rev_pointer == 0
  pre_self_.page_array@[idx(p2)].rev_pointer == 1
  pre_self_.page_array@[idx(p3)].rev_pointer == 2
  pre_self_.page_array@[idx(p4)].rev_pointer == 3
  // Inputs.
  target_ptr == tp; ioid == I; va == V
  // Run 1 — Impl A: only modify tp.io_mappings.
  r1 == ()
  post1_self_.page_array@[idx(tp)].io_mappings@ == set![(I, V)]
  post1_self_.free_pages_4k@ == seq![p1, p2, p3, p4]                  // unchanged
  forall i in {p1,p2,p3,p4}: post1_self_.page_array@[idx(i)].rev_pointer == pre.…rev_pointer
  // Run 2 — Impl B: permute the free list while keeping wf.
  r2 == ()
  post2_self_.page_array@[idx(tp)].io_mappings@ == set![(I, V)]
  post2_self_.free_pages_4k@ == seq![p3, p1, p4, p2]                  // permuted
  post2_self_.page_array@[idx(p3)].rev_pointer == 0
  post2_self_.page_array@[idx(p1)].rev_pointer == 1
  post2_self_.page_array@[idx(p4)].rev_pointer == 2
  post2_self_.page_array@[idx(p2)].rev_pointer == 3
  // Both .to_set() images are {p1, p2, p3, p4}.
  !det_add_io_mapping_4k_equal((), (), post1_self_, post2_self_)
```

#### Suggested fix

The underlying setters (`set_state`, `set_io_mapping`, `set_ref_count`, …) already write `self.free_pages_4k == old(self).free_pages_4k` at the Seq level. The public ensures should mirror them — see appendix.

---

### #7 `free_page_4k` (×5 instances)

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__free_page_4k.rs:613`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__free_page_4k.rs#L613)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__free_page_4k__free_page_4k/`

#### Why this is incomplete

Same shape as `add_io_mapping_4k` but for the *insertion* direction: ensures says `self.free_pages_4k() =~= old.free_pages_4k().insert(target_ptr)` (Set-level), so the freedom is *where* `target_ptr` lands in the `Seq` — head, tail, or any middle slot — and how the other entries' `rev_pointer`s rotate to stay consistent.

#### Source function

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
        forall|c: ContainerPtr| #![auto]
            self.container_map_4k@.dom().contains(c)
                ==> self.get_container_owned_pages(c) =~= old(self).get_container_owned_pages(c),
        forall|p: PagePtr| #![auto] self.page_is_mapped(p) == old(self).page_is_mapped(p),
{ /* push + set_rev_pointer + set_state + tracked_insert */ }
```

#### Witness

```
  pre_self_.wf()
  pre_self_.page_array@[idx(tp)].state == PageState::Allocated4k
  pre_self_.allocated_pages_4k@ == set![tp]
  pre_self_.free_pages_4k@ == seq![p1, p2, p3]                       // 3 existing free pages
  pre_self_.page_array@[idx(p1)].rev_pointer == 0
  pre_self_.page_array@[idx(p2)].rev_pointer == 1
  pre_self_.page_array@[idx(p3)].rev_pointer == 2
  // Run 1 — Impl A (real, push to tail).
  r1 == ()
  post1_self_.free_pages_4k@ == seq![p1, p2, p3, tp]
  post1_self_.page_array@[idx(tp)].rev_pointer == 3
  post1_self_.page_array@[idx(p1)].rev_pointer == 0
  post1_self_.page_array@[idx(p2)].rev_pointer == 1
  post1_self_.page_array@[idx(p3)].rev_pointer == 2
  // Run 2 — Impl B (insert at head, shift others).
  r2 == ()
  post2_self_.free_pages_4k@ == seq![tp, p1, p2, p3]
  post2_self_.page_array@[idx(tp)].rev_pointer == 0
  post2_self_.page_array@[idx(p1)].rev_pointer == 1
  post2_self_.page_array@[idx(p2)].rev_pointer == 2
  post2_self_.page_array@[idx(p3)].rev_pointer == 3
  // Both .to_set() images are {p1, p2, p3, tp}.
  !det_free_page_4k_equal((), (), post1_self_, post2_self_)
```

#### Suggested fix

Public ensures should pin Seq-level structure, e.g. `self.free_pages_4k@ == old(self).free_pages_4k@.push(target_ptr)` (matching the real impl's `push` semantics). Or: leave the spec as-is and extend `det_equal` to compare `free_pages_*` via `.to_set()`.

---

## Part 3 — Symmetric allocation choice

These cases have a fully anchored `ret`, but `ret` is only constrained to lie in a multi-element `old.free_pages_*` set. Two impls may pick different elements and produce structurally distinct (but symmetric) post-states.

### #8 `alloc_page_4k` (×8 instances; also `alloc_page_4k_for_new_container`, ×2 instances)

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_4k.rs:597`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_4k.rs#L597)
- **Sibling**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_4k_for_new_container.rs:597`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_4k_for_new_container.rs#L597)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__alloc_page_4k__alloc_page_4k/`

#### Why this is incomplete

`ret` is fully pinned to be in `old.free_pages_4k()` (line 627), but the *choice* among ≥2 elements is unspecified. Both `(p1, perm_p1)` and `(p2, perm_p2)` are legal returns whenever `|old.free_pages_4k| ≥ 2`. Post-states differ on `ret.0`, `free_pages_4k`, `allocated_pages_4k`, `page_array[idx(ret)].state`, and which perm was tracked-removed.

This is not a spec defect — it is genuine non-determinism in the abstract API. A `det_equal` extension that quotients by "choice of fresh element" would fold this class away.

#### Source function

```rust
pub fn alloc_page_4k(&mut self) -> (ret: (PagePtr, Tracked<PagePerm4k>))
    requires
        old(self).wf(),
        old(self).free_pages_4k.len() > 0,
    ensures
        self.wf(),
        self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret.0),
        self.free_pages_2m() =~= old(self).free_pages_2m(),
        self.free_pages_1g() =~= old(self).free_pages_1g(),
        self.allocated_pages_4k() =~= old(self).allocated_pages_4k().insert(ret.0),
        self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
        self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
        self.mapped_pages_4k() =~= old(self).mapped_pages_4k(),
        self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
        self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
        old(self).container_map_4k@.dom() =~= self.container_map_4k@.dom(),
        forall|p: PagePtr|
            self.page_is_mapped(p) ==> self.page_mappings(p) =~= old(self).page_mappings(p)
                && self.page_io_mappings(p) =~= old(self).page_io_mappings(p),
        ret.1@.is_init(),
        ret.1@.addr() == ret.0,
        old(self).allocated_pages_4k().contains(ret.0) == false,
        page_ptr_valid(ret.0),
        old(self).free_pages_4k().contains(ret.0),
        forall|p: PagePtr| #![auto] self.page_is_mapped(p) == old(self).page_is_mapped(p),
        self.free_pages_4k.len() == old(self).free_pages_4k.len() - 1,
{ /* pop + set_state + tracked_remove */ }
```

#### Witness

```
  pre_self_.wf()
  pre_self_.free_pages_4k@.to_set() == set![p1, p2]
  pre_self_.free_pages_4k.len() == 2
  pre_self_.page_array@[idx(p1)].state == PageState::Free4k
  pre_self_.page_array@[idx(p2)].state == PageState::Free4k
  pre_self_.allocated_pages_4k@ == set![]
  pre_self_.page_perms_4k@.dom() == set![p1, p2]
  // Run 1 — Impl A: pop p1.
  r1.0 == p1
  r1.1@.addr() == p1
  post1_self_.free_pages_4k@.to_set() == set![p2]
  post1_self_.allocated_pages_4k@ == set![p1]
  post1_self_.page_array@[idx(p1)].state == PageState::Allocated4k
  post1_self_.page_array@[idx(p2)].state == PageState::Free4k
  post1_self_.page_perms_4k@.dom() == set![p2]
  // Run 2 — Impl B: pop p2.
  r2.0 == p2
  r2.1@.addr() == p2
  post2_self_.free_pages_4k@.to_set() == set![p1]
  post2_self_.allocated_pages_4k@ == set![p2]
  post2_self_.page_array@[idx(p1)].state == PageState::Free4k
  post2_self_.page_array@[idx(p2)].state == PageState::Allocated4k
  post2_self_.page_perms_4k@.dom() == set![p1]
  !det_alloc_page_4k_equal(r1, r2, post1_self_, post2_self_)
```

#### Note

`ret` is anchored via three independent mechanisms in this family — explicit `contains(ret.0)`, `len() == old - 1`, and a `Tracked<PagePerm4k>` whose linearity forces `ret.0 ∈ old.page_perms_4k@.dom() = old.mapped_4k ∪ old.free_4k`. The sibling `alloc_page_4k_for_new_container` uses the same three.

---

### #9 `alloc_page_2m` (×1 instance)

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_2m.rs:590`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_2m.rs#L590)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__alloc_page_2m__alloc_page_2m/`

#### Why this is incomplete

Same shape as `alloc_page_4k`, but the spec omits the explicit `old.free_pages_2m().contains(ret.0)` clause. `ret.0` is still pinned by the linearity of `Tracked<PagePerm2m>`: `ret.1@.addr() == ret.0` + `perm_wf`'s `page_perms_2m@.dom() = mapped_2m ∪ free_2m` + the fact that `ret.0` ends up in `allocated_pages_2m` (and is not in `old.allocated_pages_2m`). Symmetric choice remains.

#### Witness (compact)

```
  pre_self_.free_pages_2m@.to_set() == set![p1, p2]   // p1 ≠ p2, both Free2m, both in page_perms_2m@
  r1 == (p1, perm_p1)
  r2 == (p2, perm_p2)
  post1_self_.free_pages_2m@.to_set() == set![p2]
  post2_self_.free_pages_2m@.to_set() == set![p1]
  post1_self_.allocated_pages_2m@ == set![p1]
  post2_self_.allocated_pages_2m@ == set![p2]
  !det_alloc_page_2m_equal(r1, r2, post1_self_, post2_self_)
```

---

### #10 `alloc_and_map_4k` (×2 instances; also `alloc_and_map_io_4k`, ×2 instances)

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_4k.rs:597`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_4k.rs#L597)
- **Sibling**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_io_4k.rs:597`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_io_4k.rs#L597)
- **Artifact**: `spec-determinism/results-verusage-viewreg/atmosphere/artifacts/atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__alloc_and_map_4k__alloc_and_map_4k/`

#### Why this is incomplete

`ret` is pinned via three combined clauses: `self.free_pages_4k.len() == old.len() - 1`, `!old(self).page_is_mapped(ret)`, `!old.allocated_pages_4k().contains(ret)`. Combined with `wf` (`Seq=Set` cardinality and `unique()`) this proves `ret ∈ old.free_pages_4k`. Same symmetric choice as `alloc_page_4k`.

The `alloc_and_map_io_4k` sibling is identical modulo `(pcid, va) ↔ (ioid, va)`.

#### Source function

```rust
pub fn alloc_and_map_4k(&mut self, pcid: Pcid, va: VAddr, c_ptr: ContainerPtr) -> (ret: PagePtr)
    requires
        old(self).wf(),
        old(self).free_pages_4k.len() > 0,
        old(self).container_map_4k@.dom().contains(c_ptr),
    ensures
        self.wf(),
        self.free_pages_2m() =~= old(self).free_pages_2m(),
        self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret),
        self.free_pages_1g() =~= old(self).free_pages_1g(),
        self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
        self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
        self.allocated_pages_1g() =~= old(self).allocated_pages_1g(),
        self.mapped_pages_4k() =~= old(self).mapped_pages_4k().insert(ret),
        self.mapped_pages_2m() =~= old(self).mapped_pages_2m(),
        self.mapped_pages_1g() =~= old(self).mapped_pages_1g(),
        self.page_mappings(ret) =~= Set::<(Pcid, VAddr)>::empty().insert((pcid, va)),
        self.page_io_mappings(ret) =~= Set::<(IOid, VAddr)>::empty(),
        old(self).allocated_pages_4k().contains(ret) == false,
        page_ptr_valid(ret),
        !old(self).page_is_mapped(ret),
        self.page_is_mapped(ret),
        self.free_pages_4k.len() == old(self).free_pages_4k.len() - 1,
        self.get_container_owned_pages(c_ptr) =~= old(self).get_container_owned_pages(c_ptr).insert(ret),
        /* ... other Set-level invariants ... */
{ /* pop + set_state + set_mapping + container_map_4k.insert(c_ptr, …) */ }
```

#### Witness

```
  pre_self_.wf()
  pre_self_.free_pages_4k@.to_set() == set![p1, p2]
  pre_self_.mapped_pages_4k@ == set![]
  pre_self_.allocated_pages_4k@ == set![]
  pre_self_.container_map_4k@[c_ptr] == set![]
  // Inputs.
  pcid == P; va == V; c_ptr == c
  // Run 1 — Impl A: take p1.
  r1 == p1
  post1_self_.free_pages_4k@.to_set() == set![p2]
  post1_self_.mapped_pages_4k@ == set![p1]
  post1_self_.page_array@[idx(p1)].state == PageState::Mapped4k
  post1_self_.page_array@[idx(p1)].mappings@ == set![(P, V)]
  post1_self_.container_map_4k@[c] == set![p1]
  // Run 2 — Impl B: take p2.
  r2 == p2
  post2_self_.free_pages_4k@.to_set() == set![p1]
  post2_self_.mapped_pages_4k@ == set![p2]
  post2_self_.page_array@[idx(p2)].state == PageState::Mapped4k
  post2_self_.page_array@[idx(p2)].mappings@ == set![(P, V)]
  post2_self_.container_map_4k@[c] == set![p2]
  !det_alloc_and_map_4k_equal(r1, r2, post1_self_, post2_self_)
```

---

## Appendix: setter vs public-API ensures inconsistency

Every `impl2__*.rs` file in `verified/allocator/` contains:

1. **Low-level setters** (marked `#[verifier(external_body)]`, e.g. `set_state`, `set_io_mapping`, `set_mapping`, `set_ref_count`, `set_owning_container`, `set_rev_pointer`): ensures use **field-level `==`** on every untouched field — including `self.free_pages_4k == old(self).free_pages_4k` (Seq-level), plus all 12+ ghost/tracked maps.

2. **Public APIs that compose these setters** (the functions in Part 2): ensures use the **closed spec fn `=~=`** comparison, e.g. `self.free_pages_4k() =~= old(self).free_pages_4k()` (Set-level, where `free_pages_4k()` is `closed spec fn → Set<PagePtr> = self.free_pages_4k@.to_set()`).

Example — `add_io_mapping_4k.rs` lines 580–583 (public API) vs lines 801–815 (`set_io_mapping` setter):

```rust
// Public API add_io_mapping_4k.ensures:
self.free_pages_4k.len() == old(self).free_pages_4k.len(),   // Seq.len()
self.free_pages_4k() =~= old(self).free_pages_4k(),          // Set =~=
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),

// Underlying setter set_io_mapping.ensures:
self.free_pages_4k == old(self).free_pages_4k,               // Seq == (PINNED)
self.free_pages_2m == old(self).free_pages_2m,
self.free_pages_1g == old(self).free_pages_1g,
self.allocated_pages_4k == old(self).allocated_pages_4k,     // Ghost<Set> == (PINNED)
self.mapped_pages_4k    == old(self).mapped_pages_4k,
self.page_perms_4k      == old(self).page_perms_4k,          // Tracked<Map> == (PINNED)
/* ... 12+ ghost/tracked fields with == ... */
```

The setter library is the only way the implementation can mutate state. So every public API in this family is actually constrained at the Seq / ghost-identity level — but only writes the weaker Set-level statement to its callers and to the verifier.

**Question for the spec author**:

1. Is the weak public ensures intentional (e.g. to allow future impls that bypass these setters, or to keep proof obligations lighter)?
2. Or is it accidental — should the public API ensures simply mirror the setters, i.e. write `self.free_pages_4k == old(self).free_pages_4k` (Seq) instead of `self.free_pages_4k() =~= old(self).free_pages_4k()` (Set)?

If accidental: tightening the public ensures to `==` would close the entire "Seq ordering free" bucket in Part 2 without any tool-side change. The same applies to `add_mapping_4k`, the `remove_*_helper*` family, `free_page_4k`, and the alloc-and-map functions.

A small additional piece of evidence that this is a copy-paste authoring slip rather than a design choice: in both `add_io_mapping_4k.rs` (line 582) and `add_mapping_4k.rs` (line 582), the second `free_pages_4k() =~= old(self).free_pages_4k()` is a duplicate of the line above — almost certainly intended to be `free_pages_2m`.

The **Part 1** bugs are genuine spec design issues regardless of how this question is resolved — they involve missing constraints that tightening `=~=` to `==` would not fix.
