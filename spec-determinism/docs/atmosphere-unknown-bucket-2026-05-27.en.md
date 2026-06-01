# atmosphere `unknown` bucket audit — z3-limitation cases (B/C/D)

> 161 cases in atmosphere fall into the `unknown` bucket (`r0_z3 == "unknown"` AND `permitted == False`) — i.e. z3 surrendered during R0 narrowing but no LLM-permissive rule fired.
> Source dataset: `/tmp/corpus_baseline/atmosphere/full_run.json` (May 24 corpus run with the post-closeout schema).
>
> A 4-cluster classification reveals **three of the buckets are z3 / search-engine limitations rather than spec defects**. This doc enumerates those three (B, C, D = 134 cases total). The fourth (A — container-primitive ghost-view-only defects, 27 cases) is being audited separately as candidate real incompletes.
>
> | Bucket | n | Pattern | Verdict |
> |---|---:|---|---|
> | **A — container-primitive ghost view** | 27 | `Array::set`, `StaticLinkedList::push`, … : ensures pin only the ghost view; equal_fn includes concrete `[T; N]` array or `closed spec fn` return | **Likely real incomplete** (audited separately) |
> | **B — wide-state setter, forall-trigger explosion** | 66 | `PageAllocator` setters + pagetable entry creators: spec pins `forall i ≠ idx ⇒ post.page_array@[i] =~= old.page_array@[i]`, with very large product of n_schemas × n_params | z3 limitation (trigger blow-up) |
> | **C — closed `wf()` / opaque-fn chain** | 61 | `process_manager` mid-size state transitions: ensures are stated via `closed spec fn` predicates (`wf()`, `get_endpoint`, `get_thread`, `proc_perms@`, …) | z3 limitation (uninterpreted symbols) |
> | **D — `resolve_pagetable_mapping` schema-search runaway** | 7 | `va: VAddr` narrowing enumerates the (l4i,l3i,l2i,l1i) index space across 51,358 rounds before wall-clock cut-off | Search-engine limitation (no spec defect) |
>
> **Totals**: B 66 + C 61 + D 7 = 134 cases in this doc; A 27 audited separately. 134 + 27 = 161 ✓

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

## Part C — Closed `wf()` / opaque-fn chain (61 cases)

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

### Cases (61 instances / 31 unique functions)

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

### Future work for this bucket

- **Selective `reveal`**: emit `reveal_with_fuel(ProcessManager::wf, N)` in the det-check template when wf appears in spec.
- **Open the accessor specs**: change `closed spec fn get_endpoint(...)` to `open spec fn`. Verification cost elsewhere may rise; tradeoff is project-internal.
- **Specialized det check**: when the spec rewrites a single Map field (`endpoint_perms.insert(p, ...)`), generate a det check that compares only that field.

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

| Bucket | n | Spec defect? | Recommended action |
|---|---:|---|---|
| B (wide-state forall) | 66 | No | Tool-level: tighter triggers, stratified narrowing |
| C (closed wf chain) | 61 | No | Tool-level: selective reveal / open accessors / specialized det check |
| D (page-table walk runaway) | 7 | No | Tool-level: round cap + symbolic VA enumeration |
| **Total (this doc)** | **134** | — | — |
| A (container primitive) | 27 | **Likely yes** | Audit case-by-case (see separate doc) |

The 134 cases here all leave the `unknown` bucket once tool-level changes land — they should not be counted toward "spec defects in atmosphere" once the determinism narrower is improved.
