# atmosphere `unknown` bucket audit — z3-limitation cases (B/C/D)

> The May 24 corpus run produced **161 raw `unknown` artifacts** in atmosphere (`r0_z3 == "unknown"` AND `permitted == False`). After the 2026-05-28 → 2026-06-01 audit chain, the bucket has been re-partitioned:
>
> | Class | Raw artifacts | Unique source specs | Status | Doc |
> |---|---:|---:|---|---|
> | Codegen-defect false positives (top-level-self view-registry gap) | **20** | **4** | **Reclassified to `complete`** (no spec change needed; codegen fix pending) | [`atmosphere-unknown-A-view-gap-2026-05-28.en.md`](./atmosphere-unknown-A-view-gap-2026-05-28.en.md) |
> | Real spec incompletes | 5 | 2 | Spec defect (`permitted` candidates) | [`atmosphere-incompleteness-cases-2026-05-26.en.md`](./atmosphere-incompleteness-cases-2026-05-26.en.md) #11 + #12 |
> | z3 tool limitation — B (forall trigger explosion) | 66 | 26 | Unproven (tool gap) | this doc, Part B |
> | z3 tool limitation — C (multi-instance forall coordination) | 63 | 33 | Unproven (tool gap) | this doc, Part C |
> | z3 tool limitation — D (page-table walk runaway) | 7 | 2 | Unproven (tool gap) | this doc, Part D |
> | **Residual `unknown` bucket (after audit)** | **141** | **62** | — | — |
>
> **This doc covers the bottom three rows: 136 raw / ~60 unique specs of z3 tool limitations** — neither spec defects nor codegen bugs, just queries z3 doesn't conclude in the time budget. They should be tracked separately from spec-incompleteness counts.
>
> Source dataset: `/tmp/corpus_baseline/atmosphere/full_run.json` (May 24 corpus run with the post-closeout schema).
>
> **Note on counts (corpus inflation)**: the corpus uses *single-file packaging*, so every caller file inlines the source of every callee primitive it touches. As a result, the same source-level spec function appears multiple times in the corpus — once at its canonical `__<fn>.rs` source file, plus once per caller file that inlines it. The headline raw counts are corpus-artifact counts; the "Unique source specs" columns are deduplicated to the source level. Some severely-inlined primitives like `Array::set` (15 raw artifacts) collapse to a single source-level spec; the worst single-source-spec-to-artifact ratio in atmosphere is `set` (1:15).
>
> The four mechanical classifier buckets (A/B/C/D) were assigned by `(n_schemas, n_rounds)` thresholds; see the methodology section below. After the 2026-05-28 reclassifications moved `PageMap::init` and `VaRange4K::new` from A to C, and the 2026-06-01 codegen-defect reclassification moved 20 raw / 4 unique specs out of `unknown` into `complete`, the table above reflects the final partition.
>
> | Bucket | Raw artifacts | Unique specs | Pattern | Verdict |
> |---|---:|---:|---|---|
> | **A — container-primitive ghost view** | 5 (residual) | 2 (residual) | `Array::new`, `StaticLinkedList::push`: ensures don't pin ret / new ghost slots → real incompleteness | **Real spec defects** — see incompleteness doc #11 + #12. The other 20 raw / 4 unique A-bucket entries were codegen false positives and have been moved to `complete`. |
> | **B — wide-state setter, forall-trigger explosion** | 66 | 26 | `PageAllocator` setters + pagetable entry creators: spec pins `forall i ≠ idx ⇒ post.page_array@[i] =~= old.page_array@[i]`, with very large product of n_schemas × n_params | z3 limitation (trigger blow-up) |
> | **C — closed `wf()` / opaque-fn chain** | 63 | 33 | `process_manager` mid-size state transitions: ensures are stated via `closed spec fn` predicates (`wf()`, `get_endpoint`, `get_thread`, `proc_perms@`, …) | z3 limitation (multi-instance quantifier coordination) |
> | **D — `resolve_pagetable_mapping` schema-search runaway** | 7 | 2 | `va: VAddr` narrowing enumerates the (l4i,l3i,l2i,l1i) index space across 51,358 rounds before wall-clock cut-off | Search-engine limitation (no spec defect) |
>
> **Residual unknown totals (this doc + #11+#12 incomplete)**: 5 A + 66 B + 63 C + 7 D = 141 raw / ~62 unique specs. The 20 raw / 4 unique codegen false positives are no longer counted here.

## Classification methodology

```python
# classify each unknown by (n_schemas, n_rounds)
if r['n_rounds'] > 1000:
    bucket = 'D_runaway'
elif r['n_schemas'] <= 3:
    bucket = 'A_container_primitive'
elif r['n_schemas'] <= 100:
    bucket = 'C_closed_wf_chain'
else:
    bucket = 'B_forall_explosion'
```

`n_schemas` proxies for "size of the post-state being witnessed", `n_rounds` for "how long narrowing kept iterating before z3 gave up". The buckets fall cleanly along these two axes, with each bucket also lining up with a single function family (Array primitives / page allocator setters / process_manager state machines / page table walk).

---

## Part B — Wide-state setter, `forall` trigger explosion (66 cases)

### Pattern

`PageAllocator` carries a 14-field state including `page_array: Array<Page, NUM_PAGES>` where `Page` is itself a 6-field struct. Per-page setters (`set_state`, `set_ref_count`, `set_mapping`, `set_owning_container`, `set_io_mapping`, `set_rev_pointer`, `page_perm_to_page_map`) all share the same spec shape:

```rust
pub fn set_io_mapping(&mut self, index: usize, io_mapping: Ghost<Set<(IOid, VAddr)>>)
    requires old(self).page_array.wf(), 0 <= index < NUM_PAGES,
    ensures
        self.page_array.wf(),
        forall|i: int|
            #![trigger self.page_array@[i]]
            #![trigger old(self).page_array@[i]]
            0 <= i < NUM_PAGES && i != index ==> self.page_array@[i] =~= old(self).page_array@[i],
        // ~5–10 per-field pins on `self.page_array@[index]`:
        self.page_array@[index as int].addr =~= old(self).page_array@[index as int].addr,
        self.page_array@[index as int].state =~= old(self).page_array@[index as int].state,
        // …
```

The pagetable variants (`create_entry_l[234]`, `map_4k_page`, `map_2m_page`, `remove_l[23]_entry`) follow the same template but on `PageTable.entries` (~880 schemas, ~45 MB SMT2).

### Why z3 surrenders

The R0 narrowing engine generates ~180–960 schemas per function (each schema is a possible field combination that could differ). For each schema, z3 must reason about:
1. The `forall|i: int|` quantifier on `page_array@[i]` instantiates against any term shaped `_array@[?i]` in the goal — combined with multiple `=~=` extensional rewrites this fans out.
2. `Array::view()` is `#[verifier(inline)]`, so the `@` unfolds to a `Seq` and z3 needs `Seq::index` axioms to make the trigger fire.
3. The `Ghost<Set<...>>` `io_mapping` parameter is opaque on update; z3 has to model `post.page_array@[index].io_mapping == io_mapping@` and propagate through the trigger pattern.

Net: ~3.7 MB–53 MB SMT2 per case, 18–399 narrowing rounds, 2.3–18 s wall — z3 returns `unknown` rather than `unsat` or `sat`. Not a witness that two impls differ; just a search that does not terminate within the budget.

### Cases (66 instances / 26 unique functions)

| n | Function | n_schemas | n_rounds | smt2_max | wall_max |
|--:|----------|----------:|---------:|---------:|---------:|
| 10 | `set_state` | 199 | 45 | 4.6 MB | 2.6 s |
| 9 | `set_ref_count` | 185 | 50 | 4.3 MB | 2.6 s |
| 7 | `set_mapping` | 188 | 45 | 4.3 MB | 2.5 s |
| 6 | `set_owning_container` | 185 | 45 | 4.3 MB | 2.6 s |
| 5 | `set_io_mapping` | 188 | 45 | 4.3 MB | 2.5 s |
| 3 | `block_running_thread_and_set_trap_frame` | 117 | 150 | 4.6 MB | 8.3 s |
| 3 | `block_running_thread_and_change_queue_state_and_set_trap_frame` | 119 | 151 | 4.5 MB | 8.3 s |
| 2 | `set_rev_pointer` | 183 | 44 | 4.2 MB | 2.4 s |
| 2 | `page_perm_to_page_map` | 173 | 18 | 4.6 MB | 3.5 s |
| 2 | `new_container_with_endpoint` | 113 | 181 | 10.9 MB | 19.2 s |
| 2 | `new_thread` | 103 | 147 | 3.0 MB | 7.7 s |
| 1 | `pop_scheduler_for_idle_cpu` | 187 | 395 | 5.8 MB | 16.2 s |
| 1 | `new_proc_with_endpoint` | 103 | 147 | 6.1 MB | 11.2 s |
| 1 | `new_proc_with_endpoint_iommu` | 103 | 147 | 6.6 MB | 10.9 s |
| 1 | `new_thread_with_endpoint` | 103 | 144 | 5.3 MB | 10.1 s |
| 1 | `schedule_running_thread` | 103 | 140 | 8.2 MB | 9.1 s |
| 1 | `run_blocked_thread` | 213 | 399 | 7.7 MB | 16.3 s |
| 1 | `create_entry_l2` | 879 | 78 | 45.0 MB | 11.2 s |
| 1 | `create_entry_l3` | 879 | 78 | 45.1 MB | 11.4 s |
| 1 | `create_entry_l4` | 879 | 78 | 44.7 MB | 10.8 s |
| 1 | `map_2m_page` | 797 | 74 | 36.2 MB | 10.2 s |
| 1 | `map_4k_page` | 797 | 74 | 36.1 MB | 10.4 s |
| 1 | `remove_l2_entry` | 965 | 84 | 52.9 MB | 12.1 s |
| 1 | `remove_l3_entry` | 965 | 84 | 53.0 MB | 11.9 s |
| 1 | `page_to_thread_with_endpoint` | 219 | 144 | 7.1 MB | 5.7 s |
| 1 | `page_to_thread` | 219 | 144 | 5.7 MB | 4.6 s |

### Future work for this bucket

- **Tighter trigger annotations**: replace `#![trigger self.page_array@[i]]` with quantifier-instantiation patterns that fire on specific field accesses rather than the whole `@`.
- **Stratified narrowing**: detect "this is a per-index setter" and pre-split into per-field schemas instead of full Cartesian product.
- **Custom equal-fn**: for `PageAllocator`, generate a custom det check that uses the same `forall i ≠ idx` shape rather than full structural `==` on `Array<Page, NUM_PAGES>`.

These are all out-of-scope for the spec-level audit (spec is well-formed; tool surrenders).

---

## Part C — Closed `wf()` / opaque-fn chain (63 cases)

### Pattern

`ProcessManager` has 10+ `Map` / `Set` fields (`proc_dom`, `thread_perms`, `container_perms`, `endpoint_perms`, …) plus a long chain of closed spec accessors (`get_proc`, `get_thread`, `get_container`, `get_endpoint`). Mid-size state transitions like `schedule_blocked_thread` use these in both `requires` and `ensures`:

```rust
pub fn schedule_blocked_thread(&mut self, endpoint_ptr: EndpointPtr)
    requires
        old(self).wf(),
        old(self).endpoint_dom().contains(endpoint_ptr),
        old(self).get_endpoint(endpoint_ptr).queue.len() > 0,
        old(self).get_container(
            old(self).get_thread(
                old(self).get_endpoint(endpoint_ptr).queue@[0],
            ).owning_container,
        ).cpu == old(self).get_thread(...).owning_cpu,
        // …
    ensures
        // similar closed-fn chain rewriting endpoint_perms / thread_perms / proc_perms
```

`wf()`, `get_endpoint`, `get_thread`, `get_container` are all `closed spec fn` — z3 treats them as uninterpreted symbols.

### Why z3 surrenders

For determinism narrowing, z3 needs to derive equalities like `post1.get_endpoint(p) == post2.get_endpoint(p)` from facts of the form `post1.endpoint_perms@.insert(...) == ...` and `post2.endpoint_perms@.insert(...) == ...`. Without bodies for `get_endpoint`, the link from the raw field to the accessor is invisible. n_schemas stays in the 40–90 range (modest by B's standard) but z3 still surrenders because none of the equalities composes.

This bucket is *closer* to a real spec issue than B — if the project opened `wf()` and the accessors, z3 might prove unsat. But that is a project-level engineering decision (opening `wf()` would explode verification time elsewhere), not a determinism-spec defect: two impls satisfying the ensures *do* have to produce the same observable state via the closed accessors.

> **⚠️ Diagnosis correction (2026-05-29 rerun verification)**. The "closed `wf()` / opaque-fn chain" framing above is **only partially accurate**, and for most C-bucket cases it is the **wrong** root cause. See [Rerun verification](#rerun-verification-2026-05-29) below.

### Cases (63 instances / 33 unique functions)

| n | Function | n_schemas | n_rounds | smt2_max | wall_max |
|--:|----------|----------:|---------:|---------:|---------:|
| 9 | `schedule_blocked_thread` | 61 | 17 | 4.3 MB | 5.9 s |
| 5 | `set_container_mem_quota_mem_4k` | 63 | 23 | 3.1 MB | 5.4 s |
| 5 | `block_running_thread` | 75 | 24 | 3.9 MB | 5.8 s |
| 5 | `block_running_thread_and_change_queue_state` | 77 | 25 | 3.9 MB | 5.8 s |
| 3 | `pass_endpoint` | 61 | 17 | 3.8 MB | 5.5 s |
| 2 | `drop_endpoint` | 65 | 21 | 2.6 MB | 5.7 s |
| 2 | `kill_process_none_root` | 61 | 17 | 3.0 MB | 6.5 s |
| 2 | `kill_scheduled_thread` | 61 | 17 | 2.7 MB | 6.2 s |
| 2 | `kill_running_thread` | 61 | 17 | 2.7 MB | 6.3 s |
| 2 | `page_entry2usize` | 15 | 20 | 0.2 MB | 1.5 s |
| 2 | `endpoint_push` | 40 | 26 | 2.0 MB | 2.0 s |
| 2 | `endpoint_push_and_set_state` | 42 | 27 | 2.2 MB | 2.0 s |
| 2 | `thread_to_page` | 89 | 10 | 2.4 MB | 2.3 s |
| 1 | `merge_4k_pages_to_2m_page` | 8 | 9 | 0.8 MB | 1.4 s |
| 1 | `kill_process_root` | 61 | 17 | 2.6 MB | 6.5 s |
| 1 | `kill_blocked_thread` | 65 | 19 | 3.0 MB | 7.3 s |
| 1 | `iommu_table_array_create_iommu_table_l2_entry_t` | 87 | 10 | 2.8 MB | 2.5 s |
| 1 | `iommu_table_array_create_iommu_table_l3_entry_t` | 87 | 10 | 2.7 MB | 2.3 s |
| 1 | `iommu_table_array_create_iommu_table_l4_entry_t` | 87 | 10 | 2.5 MB | 2.0 s |
| 1 | `pagetable_array_create_pagetable_l2_entry_t` | 87 | 10 | 2.8 MB | 2.5 s |
| 1 | `pagetable_array_create_pagetable_l3_entry_t` | 87 | 10 | 2.6 MB | 2.2 s |
| 1 | `pagetable_array_create_pagetable_l4_entry_t` | 87 | 10 | 2.4 MB | 2.0 s |
| 1 | `new_endpoint` | 61 | 21 | 2.8 MB | 4.0 s |
| 1 | `endpoint_pop_head` | 40 | 26 | 1.9 MB | 2.0 s |
| 1 | `endpoint_to_page` | 14 | 10 | 1.3 MB | 1.7 s |
| 1 | `proc_to_page` | 24 | 10 | 1.5 MB | 2.1 s |
| 1 | `proc_remove_child` | 70 | 26 | 2.6 MB | 2.6 s |
| 1 | `proc_perms_remove_subtree_set` | 18 | 10 | 2.0 MB | 2.5 s |
| 1 | `container_perms_update_subtree_set` | 18 | 10 | 2.7 MB | 3.3 s |
| 1 | `page_to_proc_with_first_thread` | 62 | 29 | 2.7 MB | 3.1 s |
| 1 | `proc_push_thread` | 70 | 26 | 2.4 MB | 2.4 s |
| 1 | `PageMap::init` *(moved from A-bucket; see audit note)* | 1 | 2 | 0.3 MB | 0.0 s |
| 1 | `VaRange4K::new` *(moved from A-bucket; semantically complete, see audit note)* | 3 | 8 | 0.2 MB | 0.0 s |

### Future work for this bucket

- ~~**Selective `reveal`**: emit `reveal_with_fuel(ProcessManager::wf, N)` in the det-check template when wf appears in spec.~~ Disproven by 2026-05-29 rerun — see [Rerun verification](#rerun-verification-2026-05-29) below. The existing `closed→opaque + reveal` infrastructure already runs on these targets and `reachable_spec_fns` reports no closed fns in the 4-hop ensures chain.
- ~~**Open the accessor specs**: change `closed spec fn get_endpoint(...)` to `open spec fn`.~~ Same — the accessors that matter aren't `closed` in source; they're already `open`. Re-opening doesn't apply.
- **Trigger-engineering inside the det-check template** (new — replaces the two crossed-out items): for every `forall|i| P(post@[i])` clause in ensures, emit a quantifier instantiation hint that pairs the `i` between `post1@[i]` and `post2@[i]`. Without this, z3 fires the body forall on one side only and never composes the two sides.
- **Specialized det check**: when the spec rewrites a single Map field (`endpoint_perms.insert(p, ...)`), generate a det check that compares only that field.

### Rerun verification (2026-05-29)

Five cases were re-run on HEAD (commit `659c9bdc` already wires the source-aware codegen path: `verusage_run → run_single_file → build_det_check_spec(..., source=...)`, which triggers `reachable_spec_fns` → `rewrite_closed_to_opaque` → `reveal(...)` injection).

| case | baseline `r0_z3` / n_sch / n_rd | rerun `r0_z3` / n_sch / n_rd | `opened_closed_specs` | flipped to unsat? |
|---|---|---|---|---|
| A4 PageMap::init | unknown / 1 / 2 | unknown / 1 / 2 | `[]` | ❌ no |
| A6 VaRange4K::new | unknown / 3 / 8 | unknown / 3 / 8 | `['view_match_spec']` | ❌ no |
| C-small `merge_4k_pages_to_2m_page` | unknown / 8 / 9 | unknown / 8 / 9 | `[]` | ❌ no |
| C-mid `schedule_blocked_thread` | unknown / 61 / 17 | unknown / 61 / 17 | `[]` | ❌ no |
| C-large `kill_blocked_thread` | unknown / 65 / 19 | unknown / 65 / 19 | `[]` | ❌ no |

Two distinct failure modes:

**Failure 1 — `opened_closed_specs == []` for 4 / 5 cases (A4 + 3 of the C sample)**. `reachable_spec_fns(ensures, source, max_depth=8)` returned, for A4: `['is_empty', 'wf']` — **both already `open`**, no closed fns reached at all. Manual inspection of `merge_4k_pages_to_2m_page` confirms: the closed fns in its file (`free_pages_4k`, `mapped_pages_4k`, …) are simply not in the ensures' 4-hop reach. So the "closed `wf()` chain" framing in this section's pattern description is **not the actual root cause** for these cases — there is nothing closed for the existing mechanism to open. The real bottleneck is the next failure mode.

**Failure 2 — A6: `opened_closed_specs == ['view_match_spec']`, reveal emitted, R0 still unknown**. The injected template has `reveal(VaRange4K::view_match_spec);` before `{ASSUMES}`, so the body is fully visible during the det check. Logically:

```text
r1.view_match_spec() ≡ forall|i: usize| #![trigger spec_va_add_range(r1.start, i)]
                          0 <= i < r1.len ==> spec_va_add_range(r1.start, i) == r1@[i as int]
// same for r2; plus r1.start == r2.start == va, r1.len == r2.len == len from ensures
```

…should give `forall i, r1@[i] == r2@[i]`, hence `r1@ == r2@` by Seq extensionality. But z3 still returns unknown. **The blocker is the trigger heuristic**: the `forall` body's trigger pattern `spec_va_add_range(self.start, i)` needs to fire on **two independent ground instances** (r1 and r2) and align the `i` between them. z3's E-matching does fire each side independently but doesn't auto-correlate the witnesses across the two `forall` instances unless an extensional Seq lemma (`Seq::ext_equal` / `=~=`) is asserted explicitly.

**Joint diagnosis**: For atmosphere's unknown bucket (this 136-case set), the dominant root cause is **not** closed-spec opacity — it is **multi-instance `forall` trigger coordination**. The existing `closed→opaque + reveal` infrastructure (commit `659c9bdc`) is *necessary* for a minority of cases (A6-like) but *not sufficient*, and *inapplicable* for the majority where the ensures' spec fns are already `open`.

**Implication for the next round of tool work**: the leverage is now on (a) emitting per-axis `Seq/Set/Map::ext_equal` lemmas as assumes in the det template, and (b) per-element trigger pairing across the `r1` / `r2` ensures, **not** on further closed→opaque expansion.

### Audit addendum — `PageMap::init` (moved from the A-bucket audit)

During the A-bucket (container-primitive) audit (2026-05-28), `PageMap::init` was initially clustered with `Array::set` and friends but turned out to belong here. The view registry **already wires `PageMap`** at the top-level self position — the generated equal-fn compares `Seq<PageEntry>` extensionally (`post1_self_: Seq<PageEntry>, post2_self_: Seq<PageEntry>; ... post1_self_ =~= post2_self_`). Under that comparator the spec is genuinely deterministic:

```rust
ensures
    self.wf(),
    forall|i: int| #![trigger self@[i].is_empty()] 0 <= i < 512 ==> self@[i].is_empty(),
```

`PageEntry::is_empty()` is an open spec fn that fully pins all 6 fields (`addr == 0`, all `perm.*` flags false), so pointwise `is_empty()` on both `post1@[i]` and `post2@[i]` forces equal PageEntries, and Seq-`=~=` lifts to extensional Seq equality. UNSAT in principle.

The actual result is `r0_z3 == unknown` with `n_schemas == 1, n_rounds == 2`, `search_ms == 37` — z3 surrenders on R0 before any narrowing. The triggers `#![trigger self@[i].is_empty()]` and `#![trigger usize2page_entry(self.ar@[i])]` (the latter from `wf()`'s closed clause) do not auto-instantiate together for both `post1` and `post2` at the same `i`, so z3 cannot align the pointwise `is_empty()` facts.

This is the same shape as the rest of the C bucket — closed/forall-trigger composition that z3 surrenders on — just with very small `n_schemas`. The fix is also the same: selective reveal / open of `wf()` + opening `PageEntry::is_empty()` body via `reveal_with_fuel` in the det-check template.

### Audit addendum — `VaRange4K::new` (moved from the A-bucket audit, semantically complete)

`VaRange4K::new(va, len)` is the constructor for `VaRange4K { start: VAddr, len: usize, view: Ghost<Seq<VAddr>> }`. The generated equal-fn already uses view-first comparison (`((r1)@ == (r2)@)`), and the public spec is:

```rust
pub fn new(va: VAddr, len: usize) -> (ret: Self)
    requires spec_va_4k_valid(va), va_4k_range_valid(va, len), va < usize::MAX - len * 4096,
    ensures ret.wf(), ret.start == va, ret.len == len,

// where:
pub open spec fn wf(&self) -> bool {
    ...
    &&& self@.len() == self.len
    &&& self@.no_duplicates()
    &&& forall|i: int| #![trigger self@[i]] 0 <= i < self.len ==> spec_va_4k_valid(self@[i])
    &&& self.view_match_spec()                              // ← closed!
}

pub closed spec fn view_match_spec(&self) -> bool {
    &&& forall|i: usize|
          #![trigger spec_va_add_range(self.start, i)]
          0 <= i < self.len ==> spec_va_add_range(self.start, i) == self@[i as int]
}
```

**Semantically the spec is complete**: `view_match_spec()`'s body pins each `self@[i]` to `spec_va_add_range(va, i)`, fully determining the ghost sequence. Two impls satisfying ensures must produce identical `view@`.

**Z3 returns `unknown` only because `view_match_spec` is `closed`** — its body is invisible outside the module, so z3 sees `r1.view_match_spec() == true` and `r2.view_match_spec() == true` as two uninterpreted facts that say nothing about element-wise equality. Open the body and the goal becomes UNSAT instantly.

Verdict: **complete (closure-policy hides the determinism witness)**. Not a real incomplete; not a view-policy gap. Same root cause as the rest of the C bucket — closed-spec-fn body opacity blocks z3 from composing the constraints — just at a smaller schema scale.

**Update (2026-05-29 rerun)**: empirically, opening the body via `reveal(VaRange4K::view_match_spec)` is **not by itself sufficient** for z3 to discharge this. With the commit-`659c9bdc` infrastructure already injecting `opened_closed_specs: ['view_match_spec']` + the corresponding `reveal(...)` line, R0 is still `unknown` and schema narrowing still walks through all 8 rounds without progress. The residual blocker is multi-instance `forall` trigger coordination (E-matching does not auto-pair `i` across the two `view_match_spec` body instantiations for `r1` and `r2`). So while the spec is still semantically complete, fixing it tool-side requires an additional `assert by(...) { ... };` or explicit `Seq::ext_equal` lemma — not just reveal. See the [Rerun verification](#rerun-verification-2026-05-29) section for full evidence.

---

## Part D — `resolve_pagetable_mapping` schema-search runaway (7 cases)

### Pattern

```rust
pub fn resolve_pagetable_mapping(&self, pcid: Pcid, va: VAddr) -> (ret: Option<PageEntry>)
    requires self.wf(), self.pcid_active(pcid), va_4k_valid(va),
    ensures
        self.get_pagetable_by_pcid(pcid).unwrap().mapping_4k().dom().contains(va)
            == ret.is_Some(),
        ret.is_Some() ==> self.get_pagetable_by_pcid(pcid).unwrap().mapping_4k().dom().contains(va)
            && self.get_pagetable_by_pcid(pcid).unwrap().mapping_4k()[va]
                == page_entry_to_map_entry(&ret.unwrap()),
```

Same defect family as `resolve_iommu_table_mapping`. The spec is only 3 ensures clauses, but the input `va: VAddr` is enumerated by the narrowing engine over the 4-level (l4,l3,l2,l1) index decomposition. The R0 narrower hits **51,358 rounds** of schema search before being cut off at ~150 s.

### Why z3 surrenders

This is not a spec-determinism issue at all — it is a **narrowing engine** limitation. The engine attempts to construct a model for `va` satisfying `va_4k_valid(va)` and the index decomposition, fanning out across the 2^9 × 2^9 × 2^9 × 2^9 page-table address space. There is no round cap, so it runs until wall-clock cut-off.

This is the same root cause as the `pagetable_map_4k_page` family that appears in the `runner_crash` bucket (corpus_rerun11_results.md). The only reason these 7 land in `unknown` rather than `runner_crash` is wall-clock < 300 s.

### Cases (7 instances / 2 unique functions)

| n | Function | n_schemas | n_rounds | smt2_max | wall_max |
|--:|----------|----------:|---------:|---------:|---------:|
| 5 | `resolve_pagetable_mapping` | 212 | 51,358 | 6.0 MB | 152.6 s |
| 2 | `resolve_iommu_table_mapping` | 212 | 51,358 | 5.8 MB | 151.5 s |

### Future work for this bucket

- **Round cap on narrowing**: cap `n_rounds` at e.g. 5,000 and emit a structured `narrowing_capped` result instead of relying on wall-clock cut-off.
- **Symbolic VA enumeration**: detect the (l4i, l3i, l2i, l1i) factorization pattern and avoid enumerating concrete `va` values.
- **Custom det check**: for resolve-style accessors, compare only `ret` (an `Option<PageEntry>`) rather than the whole `self`.

---

## Summary

| Bucket | Raw artifacts | Unique specs | Spec defect? | Recommended action |
|---|---:|---:|---|---|
| B (wide-state forall) | 66 | 26 | No | Tool-level: tighter triggers, stratified narrowing |
| C (multi-instance forall coordination; **not** closed-fn opacity, see 2026-05-29 rerun) | 63 | 33 | No | Tool-level: per-axis `Seq/Set/Map::ext_equal` lemmas + r1↔r2 trigger pairing |
| D (page-table walk runaway) | 7 | 2 | No | Tool-level: round cap + symbolic VA enumeration |
| **Total (this doc — z3 tool limitations)** | **136** | **~60** | No | — |
| A residual (real incompletes, see incompleteness doc #11 + #12) | 5 | 2 | **Yes** | Spec change: tighten ensures on return / fresh slot |
| **Total residual atmosphere unknowns (after 2026-06-01 reclassification)** | **141** | **~62** | — | — |

**Reclassified out of `unknown` on 2026-06-01**: 20 raw / 4 unique codegen-defect false positives (A bucket, view-registry top-level-self gap; see [`atmosphere-unknown-A-view-gap-2026-05-28.en.md`](./atmosphere-unknown-A-view-gap-2026-05-28.en.md)). These were never spec defects — the source-level specs are complete under the project's view-first equality policy; only a codegen fix (≈10 lines in `gen_det.py`'s `build_det_check_spec`) is needed to flip them from `unknown` → `unsat` in the next corpus rerun.

The 136 cases here all leave the `unknown` bucket once tool-level changes land — they should not be counted toward "spec defects in atmosphere" once the determinism narrower is improved. Note that the 2026-05-29 rerun confirmed the existing closed→opaque + reveal infrastructure (commit `659c9bdc`) is **not** the right lever for the C bucket (`reachable_spec_fns` returns empty for most of these); the actual gap is in multi-instance quantifier coordination, see [Rerun verification](#rerun-verification-2026-05-29).
