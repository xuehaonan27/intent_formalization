# atmosphere — codegen-defect false-positive unknowns (reclassified to **complete**)

> **Verdict (2026-06-01)**: the 20 raw corpus artifacts / 4 unique source-level spec functions catalogued in this doc are **source-level complete**. They show up as `r0_z3 == unknown` in the May 24 baseline only because of a codegen defect (top-level-self view-registry gap, see below). They are therefore **reclassified as `complete`** in the atmosphere status ledger; only a codegen fix is required to flip them from `unknown` → `unsat` in the next corpus rerun. No spec change is needed.
>
> | | Raw artifacts | Unique source specs |
> |---|---:|---:|
> | Reclassified to complete (this doc) | **20** | **4** |
> | Remaining in `unknown` bucket | 141 | 62 |
> | Original `unknown` bucket size | 161 | 66 |
>
> Sub-audit of the "container-primitive" bucket (A) inside the original 161 atmosphere unknowns (`r0_z3 == "unknown"` AND `permitted == False`). Sibling doc covering the **real** spec incompletes in the same A bucket (still classified as defects): [`atmosphere-incompleteness-cases-2026-05-26.en.md`](./atmosphere-incompleteness-cases-2026-05-26.en.md) #11 (`Array::new`) and #12 (`StaticLinkedList::push`), totaling 5 raw / 2 unique.
>
> **Why the artifact count > unique-spec count**: each verified function ships in a self-contained `.rs` file that inlines all callees. Primitives like `Array::set` are inlined into every caller file that touches `Array` — 15 caller files, hence 15 corpus artifacts pointing back to the same single canonical source-level `Array::set` spec definition. Headline counts in this doc are deduplicated to the source level; per-case sections give both numbers.
>
> These cases are **NOT** spec defects under the project's view-first equality policy. Each case has a struct with a `view()` method, and ensures pin the post-state up to view equality, but the generated `det_*_equal` does **full structural `==`** on the top-level `self` instead of `self@ == self@`. This is the same pattern as documented in [`fp-nested-view-uninterpretation.md`](./fp-nested-view-uninterpretation.md), only at the **top-level self position** rather than at an inner Vec / Option-of-Vec position.
>
> **Policy** (project-wide rule the user reaffirmed in this audit, 2026-05-28):
>
> > If the self type has a `View` impl, the det check should compare `post1@ == post2@` (with `=~=` or via `view()` accessor), **not** the underlying struct's field-wise structural equality.
>
> When this policy is honoured, the cases in this doc all become trivially UNSAT (the ensures pin `post@` to the same expression of `old@` on both sides).
>
> **Evidence the gap is at the codegen layer, not in the spec**: the very same `Array<A, N>` type is compared via `(post1.page_array)@ == (post2.page_array)@` when it appears as a **field** of `PageAllocator`, but via full structural `==` when it is the **top-level self** of `Array::set`. So the view_registry already knows about `Array`'s view — the top-level codegen path just doesn't consult it.
>
> Audit source dataset: `/tmp/corpus_baseline/atmosphere/full_run.json`.
> Sibling doc covering tool-limitation buckets B/C/D: [`atmosphere-unknown-bucket-2026-05-27.en.md`](./atmosphere-unknown-bucket-2026-05-27.en.md).

## Overview

| # | Family | Unique specs | Raw artifacts | Verdict | Notes |
|---|--------|-------------:|--------------:|---------|-------|
| A1 | `Array::set` | 1 | 15 | View-policy gap (top-level self) | One canonical `Array::set` spec, inlined into 15 caller files. Generated `det_set_equal` uses `post1_self_ == post2_self_` on `Array<A, N>`; ensures pin `seq@`; view-first comparison would prove unsat. |
| A2 + A3 | `Array::init2zero` / `Array::init2none` | 2 | 3 | View-policy gap (top-level self) | Two distinct source-level specs (`init2zero` in `impl2` and `impl3`, `init2none` in `impl4`), 1 raw artifact each except `init2zero` has 2 (impl2 + impl3 = 2 raw). Same defect family as A1. |
| A7 | `ArrayVec::pop_unique` | 1 | 2 | View-policy gap (top-level self) | One canonical `pop_unique` spec, inlined into 2 `alloc_iommu_table.rs` / `alloc_page_table.rs` caller files. Same defect family as A1. |
| **Total** | | **4** | **20** | | |

---

## A1 — `Array::set` (1 unique source-level spec → 15 corpus artifacts via per-caller inlining)

- **Spec source**: [`verified/array/array__impl4__init2none.rs:30`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/array/array__impl4__init2none.rs#L30) (and 14 sibling files; all identical).
- **Artifact (representative)**: `/tmp/corpus_baseline/atmosphere/artifacts/atmosphere__verified__array__array__impl4__init2none__set/`

### (1) What the function is

`Array::set` is a length-N array container's element-write primitive (`#[verifier(external_body)]`, body `unimplemented!()`). The host struct:

```rust
pub struct Array<A, const N: usize> {
    pub seq: Ghost<Seq<A>>,
    pub ar: [A; N],
}

impl<A, const N: usize> Array<A, N> {
    #[verifier(inline)]
    pub open spec fn view(&self) -> Seq<A> { self.seq@ }

    pub open spec fn wf(&self) -> bool { self.seq@.len() == N }
}
```

`Array<A, N>` is used as the underlying storage inside `ArraySet`, `ArrayVec`, `PageMap`, `MemoryManager`, the per-page state of `PageAllocator`, etc.

### (2) What it is meant to do

Conceptually: write `out` into slot `i` of both the abstract view `seq@` and the concrete `ar` field. The spec only writes the ghost view side.

### (3) Where it would be incomplete under the **default** (structural) equal-fn policy

```rust
pub fn set(&mut self, i: usize, out: A)
    requires 0 <= i < N, old(self).wf(),
    ensures
        self.seq@ =~= old(self).seq@.update(i as int, out),
        self.wf(),
```

Ensures only pin `self.seq@` and `self.wf()` (= `self.seq@.len() == N`). The concrete field `ar: [A; N]` is not constrained. The currently generated equal-fn is structural:

```rust
// generated equal_fn for Array::set (verbatim from det_spec.json)
spec fn det_set_equal<A, const N: usize>(
    r1: (), r2: (),
    post1_self_: Array<A, N>, post2_self_: Array<A, N>,
) -> bool {
    (r1 == r2) && (post1_self_ == post2_self_)
}
```

Under this comparator, two impls — one that writes `out` into `ar[i]`, one that leaves `ar` untouched — both satisfy ensures (`seq@` ends up the same) yet have unequal `ar`, so they fail the structural eq. z3 returns `unknown` after narrowing because no witness on `seq@` exists but the `ar` slack keeps the goal satisfiable in the model space.

### (4) Why it is **not** a spec defect under the view-first policy

The correct comparator under the view-first policy is:

```rust
spec fn det_set_equal<A, const N: usize>(
    r1: (), r2: (),
    post1_self_: Array<A, N>, post2_self_: Array<A, N>,
) -> bool {
    (r1 == r2) && (post1_self_@ == post2_self_@)   // ← seq@ == seq@
}
```

Under this comparator the goal is trivial:

```
post1_self_.seq@ == old.seq@.update(i, out)         // from ensures on post1
post2_self_.seq@ == old.seq@.update(i, out)         // from ensures on post2
⇒ post1_self_@ == post2_self_@                       // transitivity
```

UNSAT. No witness exists for the negated equal-fn.

The 15 unknown-bucket cases would all flip to `complete` if the top-level codegen consulted `view_registry` the way the field-position codegen already does.

### Confirming the gap is at codegen, not at the spec

The same `Array<A, N>` type appears as a **field** of `PageAllocator` (in `set_io_mapping` and the other B-bucket setters). There the generated equal-fn uses `@`:

```rust
// generated equal_fn for PageAllocator::set_io_mapping (verbatim)
spec fn det_set_io_mapping_equal(
    r1: (), r2: (),
    post1_self_: PageAllocator, post2_self_: PageAllocator,
) -> bool {
    (r1 == r2)
    && (((post1_self_.page_array)@ == (post2_self_.page_array)@) && ... )
    //   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    //   view-first comparison on the page_array: Array<Page, NUM_PAGES> field
}
```

So `view_registry` already has the entry for `Array<_, _>`; the bug is the top-level codegen path skipping registry consultation when `self` itself has a `View` impl.

### Instances (15 cases — all same spec; one row per call site)

| Module / file | Artifact key suffix |
|---|---|
| `array/array__impl2__init2zero.rs` | `…__array__impl2__init2zero__set` |
| `array/array__impl3__init2zero.rs` | `…__array__impl3__init2zero__set` |
| `array/array__impl4__init2none.rs` | `…__array__impl4__init2none__set` |
| `array/array_set__impl0__init.rs` | `…__array_set__impl0__init__set` |
| `array/array_set__impl0__new.rs` | `…__array_set__impl0__new__set` |
| `pagetable/pagetable__pagemap__impl0__init.rs` | `…__pagetable__pagemap__impl0__init__set` |
| `memory_manager/memory_manager__spec_impl__impl0__alloc_iommu_table.rs` | `…__alloc_iommu_table__set` |
| `memory_manager/memory_manager__spec_impl__impl0__alloc_page_table.rs` | `…__alloc_page_table__set` |
| `allocator/allocator__page_allocator_spec_impl__impl2__merged_4k_to_2m.rs` | `…__merged_4k_to_2m__set` |
| `process_manager/…__block_running_thread.rs` | `…__block_running_thread__set` |
| `process_manager/…__block_running_thread_and_change_queue_state.rs` | `…__block_running_thread_and_change_queue_state__set` |
| `process_manager/…__block_running_thread_and_change_queue_state_and_set_trap_frame.rs` | (same suffix) |
| `process_manager/…__block_running_thread_and_set_trap_frame.rs` | (same suffix) |
| `process_manager/…__transfer_idle_cpu.rs` | `…__transfer_idle_cpu__set` |
| `process_manager/…__kill_running_thread.rs` | `…__kill_running_thread__set` |

### Suggested codegen fix

In the equal-fn builder (`gen_det.build_equal_expr`), when generating the body for the top-level `post1_self_` vs `post2_self_` comparison, consult the same `view_registry` lookup currently used at field positions. If the `self_type` has a registered View, emit `(post1_self_)@ =~= (post2_self_)@` (or `@ == @`) instead of structural `==`. The current "L4-llm view declarations (generated, see view_registry cache)" preamble already shows the registry is loaded — the fix is just to thread the same lookup through the top-level branch.

---

## A2 + A3 — `Array::init2zero` (2 specs → 2 corpus artifacts) / `Array::init2none` (1 spec → 1 corpus artifact)

- **Spec source (init2zero)**: `verified/array/array__impl2__init2zero.rs:46`, `verified/array/array__impl3__init2zero.rs:46` (identical).
- **Spec source (init2none)**: `verified/array/array__impl4__init2none.rs:46`.
- **Artifacts**: `…__array__impl{2,3}__init2zero__init2zero`, `…__array__impl4__init2none__init2none`.

### (1) What the functions are

Two `Array<A, N>` bulk-initializer primitives (host struct identical to A1: `seq: Ghost<Seq<A>>` + `ar: [A; N]`). `init2zero` is defined on `Array<usize, N>` (`impl2` / `impl3` share the spec verbatim); `init2none` is defined on `Array<Option<T>, N>` (`impl4`).

### (2) What they are meant to do

`init2zero` zeros every slot; `init2none` writes `None` into every slot. Physically: clobber the whole `ar` field. Specwise: force `seq@[i] == 0` (resp. `.is_None()`) for all `i < N`.

### (3) Where they would be incomplete under the default (structural) equal-fn policy

```rust
// init2zero
pub fn init2zero(&mut self)
    requires old(self).wf(), N <= usize::MAX,
    ensures
        forall|index:int| 0 <= index < N ==> #[trigger] self@[index] == 0,
        self.wf(),

// init2none — same shape, different per-element predicate
pub fn init2none(&mut self)
    requires old(self).wf(), N <= usize::MAX,
    ensures
        forall|index:int| 0 <= index < N ==> #[trigger] self@[index].is_None(),
        self.wf(),
```

Both pin only `self@[index]` (= `self.seq@[index]`) on every index plus `self.wf()` (`seq@.len() == N`). The concrete `ar: [A; N]` field is unconstrained. The generated equal-fn is structural (`post1_self_ == post2_self_`), so two impls with the same `seq@` but different `ar` are judged unequal.

### (4) Why they are **not** spec defects under the view-first policy

View is `self.seq@`. Under view-first equality the goal becomes `post1_self_@ =~= post2_self_@`, and both sides' forall-ensures pin `_@[i]` pointwise across `0..N`, giving extensional Seq equality by `=~=`. UNSAT.

Same root cause as A1; same one-line codegen fix (consult view_registry at the top-level self position) clears all 3 cases.

### Instances (3 cases)

| # | Function | File | Notes |
|--:|----------|------|-------|
| 1 | `init2zero` | `array/array__impl2__init2zero.rs` | `Array<usize, N>`, impl2 |
| 2 | `init2zero` | `array/array__impl3__init2zero.rs` | `Array<usize, N>`, impl3 — identical spec to impl2, different instantiation site |
| 3 | `init2none` | `array/array__impl4__init2none.rs` | `Array<Option<T>, N>` |

---

- Apply the same view-first repair to the rest of the A-class entries below as they are audited.
- A regression test should pin: for every type `T` that appears as `self` of a public function AND has an `impl View for T`, the generated `det_*_equal` must use `@` rather than structural `==` on `T`.

---

## A7 — `ArrayVec::pop_unique` (1 unique source-level spec → 2 corpus artifacts via per-caller inlining)

- **Spec source** (file local copies, identical bodies): `verified/memory_manager/memory_manager__spec_impl__impl0__alloc_iommu_table.rs:717-787` and `verified/memory_manager/memory_manager__spec_impl__impl0__alloc_page_table.rs` (same `ArrayVec` impl shared via copy-paste).
- **Artifact (representative)**: `/tmp/corpus_baseline/atmosphere/artifacts/atmosphere__verified__memory_manager__memory_manager__spec_impl__impl0__alloc_iommu_table__pop_unique/`

### (1) What the function is

`ArrayVec<T, N>` is a `#[verifier::external_body]` length-`N` vector backed by an inner `Array<T, N>` plus a `len: usize` cursor:

```rust
pub struct ArrayVec<T, const N: usize> {
    pub data: Array<T, N>,
    pub len: usize,
}

impl<T: Copy, const N: usize> ArrayVec<T, N> {
    pub open spec fn view(&self) -> Seq<T>
        recommends self.wf(),
    { self.view_until(self.len() as nat) }

    pub open spec fn view_until(&self, len: nat) -> Seq<T> {
        self.data@.subrange(0, len as int)
    }

    pub open spec fn wf(&self) -> bool {
        0 <= N <= usize::MAX
            && self.len() <= self.capacity()
            && self.data.wf()
    }

    pub fn pop_unique(&mut self) -> (ret: &T)
        requires
            old(self).wf(),
            old(self)@.len() > 0,
            old(self)@.no_duplicates(),
        ensures
            self.wf(),
            self@.len() == old(self)@.len() - 1,
            ret == old(self)@[old(self).len() - 1],
            self@ =~= old(self)@.drop_last(),
            self@.no_duplicates(),
    { unimplemented!() }
}
```

### (2) Generated equal-fn

```rust
spec fn det_pop_unique_equal<T: Copy, const N: usize>(
    r1: &T, r2: &T,
    post1_self_: ArrayVec<T, N>, post2_self_: ArrayVec<T, N>,
) -> bool {
    (r1 == r2) && (post1_self_ == post2_self_)
}
```

Top-level self position is compared via **structural** `==` on `ArrayVec<T,N>`, not via the view (`self.data@.subrange(0, self.len() as int)`).

### (3) Why it shows up as `unknown` (artifact-level)

The ensures pin the post-state only up to view: `self@ =~= old(self)@.drop_last()` and `self@.len() == old(self)@.len() - 1`. They say nothing about `self.data@` beyond the `0..self.len` prefix. Under structural `ArrayVec<T,N>` equality, the tail of `data` (indices `self.len..N`) is free, and the unused inner `Array`'s `seq: Ghost<Seq<T>>` may carry any historical content. Two impls trivially differ on those slots while both satisfying the spec, so the SAT round of R0 finds a non-equal-tail witness — except n_schemas/n_rounds = 1/2 means z3 returns unknown before even narrowing.

### (4) Why it is **not** a spec defect under the view-first policy

`ArrayVec` has an `open spec fn view(&self) -> Seq<T>`. Under view-first equality the comparator becomes `post1_self_@ =~= post2_self_@`, and both sides' ensures pin `post@ =~= pre@.drop_last()` to the same RHS. UNSAT immediately.

Same root cause and same one-line codegen fix as A1: consult the view registry at the top-level self position.

### (5) Return value `ret: &T`

`ret == old(self)@[old(self).len() - 1]` pins the return value to a fully-determined Seq element of the pre-view. `r1 == r2` is trivially established once pre-view is the shared `old(self)`.

### Instances (2 cases)

| # | Artifact | Caller context |
|--:|----------|----------------|
| 1 | `memory_manager__spec_impl_impl0__alloc_iommu_table__pop_unique` | Used by `MemoryManager::alloc_iommu_table` (extracts the next free IOid). |
| 2 | `memory_manager__spec_impl_impl0__alloc_page_table__pop_unique` | Used by `MemoryManager::alloc_page_table` (extracts the next free Pcid). |

Both inherit the *same* `ArrayVec` impl by source-file copy, hence two artifact entries with identical defect mechanics.
