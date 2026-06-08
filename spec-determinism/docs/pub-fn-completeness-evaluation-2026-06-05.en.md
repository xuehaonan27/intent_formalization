# Concrete + abstract completeness — full pub-fn evaluation results (2026-06-05)

> Records the per-case `concrete` and `abstract` completeness outcomes for **every** `pub fn` in the corpus that was put through the determinism pipeline as of 2026-06-05.
>
> Persistent raw data: `files/pub_fn_eval_per_case_2026-06-05.json` in the session workspace (370 rows including private fns; 329 pub fn rows used here).

## 1. Methodology

- **Pipeline scope**: 7 projects — atmosphere, ironkv, memory-allocator, nrkernel, anvil-library, storage, vest.
- **Dedup key**: `(project, function_name, type_base)` — `type_base` strips generics; free functions get the empty key. After dedup: **370 unique entries**, of which **329 are `pub fn`** (41 are private and are not part of the public-API determinism question).
- **Concrete completeness** is the per-function result recorded in each project's `spec-determinism/results-verusage-viewreg/<proj>/full_run.json`. Three buckets:
  - `verified` — `status == 'ok'` *and* `assumes == []` (truly concretely deterministic on the supplied spec).
  - `verified (assume-rescued)` — `status == 'ok'` but only with one or more `assume` hypotheses (axioms added during search). Not counted as concretely complete on the original spec; **not forwarded to abstract sweep**.
  - `failed` — `status` is `verus_error` or `runner_crash`. **Not forwarded to abstract sweep**.
- **Abstract completeness** (view-quotient Step 2) is the per-function result of the 2026-06-05 mechanical sweep ([`step2-mechanical-sweep-2026-06-05.en.md`](step2-mechanical-sweep-2026-06-05.en.md)). It runs **only** on the 109 `pub fn`s in the `verified` (clean) bucket. Outcomes:
  - `verified` — Step-2 obligation discharged from `s1@ == s2@` plus the shared per-call requires.
  - `failed (...)` — Step-2 obligation rejected. After the strict hint-only reclassification:
    - `failed (A)` — true abstract-incompleteness on the current spec; can not be rescued by body-only proof hints (see [`view-quotient-failure-summary-2026-06-05.en.md`](view-quotient-failure-summary-2026-06-05.en.md))
    - `failed (B)` — sweep false positive: spec is fine, two-line body hint suffices (SMT auto-trigger gap)
    - `failed (C)` — vacuous obligation: both `view` and the spec under test are `uninterp`, no axiom relates them
    - `failed (D)` — source is provably view-deterministic; the auto-generated `det_*_equal` oracle uses struct-eq instead of view-eq

    Types B / C / D together form the sweep's framework-side false positives — see [`step2-false-positives-2026-06-05.en.md`](step2-false-positives-2026-06-05.en.md).

## 2. Aggregate numbers

| metric | value |
|--------|------:|
| total pub fns evaluated | **329** |
| concrete: verified (clean, no assumes) | 109 |
| concrete: verified (assume-rescued) | 142 |
| concrete: failed (verus_error / crash) | 78 |
| abstract: evaluated | 109 |
| abstract: verified | **102** |
| abstract: failed — total | 7 |
| &nbsp;&nbsp;&nbsp;&nbsp;of which true abstract-incompleteness (A) | **4** |
| &nbsp;&nbsp;&nbsp;&nbsp;of which framework-side false positives (B + C + D) | 3 |

A-class abstract-incompleteness cases collapse to **2 distinct design defects** (one in `StaticLinkedList::len`, one shared across `StaticLinkedList::{get_value, get_next, get_prev}`); see [`view-quotient-failure-summary-2026-06-05.en.md`](view-quotient-failure-summary-2026-06-05.en.md).

## 3. Per-project breakdown

| project | pub fn | concrete:verified | concrete:assume-rescued | concrete:failed | abstract:verified | abstract:failed |
|---------|-------:|------------------:|------------------------:|---------------:|------------------:|----------------:|
| atmosphere       | 225 | 67 | 113 | 45 | 62 | 5 |
| ironkv           |  67 | 22 |  27 | 18 | 20 | 2 |
| memory-allocator |  15 | 13 |   1 |  1 | 13 | 0 |
| nrkernel         |   8 |  6 |   0 |  2 |  6 | 0 |
| anvil-library    |   0 |  0 |   0 |  0 |  0 | 0 |
| storage          |  12 |  0 |   0 | 12 |  0 | 0 |
| vest             |   2 |  1 |   1 |  0 |  1 | 0 |
| **total**        | **329** | **109** | **142** | **78** | **102** | **7** |

> The 78 `concrete: failed` and 142 `concrete: assume-rescued` are not forwarded to the abstract sweep on purpose: the abstract obligation is well-defined only if the function is concretely deterministic on its *original* spec.

## 4. Per-case results (all 329)

Sections below partition the 329 pub fns by outcome. Within each section rows are sorted by `(project, type_base, fn)`.

## 4.1 Abstract step-2 FAILED (7)

| proj | type | fn | concrete | abstract |
|------|------|----|----------|----------|
| atmosphere | `ArrayVec` | `len` | verified | failed (B) |
| atmosphere | `StaticLinkedList` | `get_next` | verified | failed (A) |
| atmosphere | `StaticLinkedList` | `get_prev` | verified | failed (A) |
| atmosphere | `StaticLinkedList` | `get_value` | verified | failed (A) |
| atmosphere | `StaticLinkedList` | `len` | verified | failed (A) |
| ironkv | `CKeyHashMap` | `to_vec` | verified | failed (C) |
| ironkv | `CSendState` | `get` | verified | failed (D) |

## 4.2 Abstract step-2 VERIFIED (102)

| proj | type | fn | concrete | abstract |
|------|------|----|----------|----------|
| atmosphere | `(free)` | `container_tree_check_is_ancestor` | verified | verified |
| atmosphere | `(free)` | `endpoint_add_ref` | verified | verified |
| atmosphere | `(free)` | `endpoint_remove_ref` | verified | verified |
| atmosphere | `(free)` | `page_index2page_ptr` | verified | verified |
| atmosphere | `(free)` | `page_ptr2page_index` | verified | verified |
| atmosphere | `(free)` | `proc_tree_check_is_ancestor` | verified | verified |
| atmosphere | `(free)` | `thread_set_blocking_endpoint_endpoint_ref_scheduler_ref_state_and_ipc_payload` | verified | verified |
| atmosphere | `(free)` | `thread_set_trap_frame_fast` | verified | verified |
| atmosphere | `(free)` | `usize2pa` | verified | verified |
| atmosphere | `(free)` | `usize2page_entry` | verified | verified |
| atmosphere | `(free)` | `usize2page_entry_perm` | verified | verified |
| atmosphere | `(free)` | `v2l1index` | verified | verified |
| atmosphere | `(free)` | `v2l2index` | verified | verified |
| atmosphere | `(free)` | `v2l3index` | verified | verified |
| atmosphere | `(free)` | `v2l4index` | verified | verified |
| atmosphere | `(free)` | `va2index` | verified | verified |
| atmosphere | `(free)` | `va_1g_valid` | verified | verified |
| atmosphere | `(free)` | `va_2m_valid` | verified | verified |
| atmosphere | `(free)` | `va_4k_range_valid` | verified | verified |
| atmosphere | `(free)` | `va_4k_valid` | verified | verified |
| atmosphere | `(free)` | `va_add_range` | verified | verified |
| atmosphere | `Array` | `get` | verified | verified |
| atmosphere | `EndpointState` | `is_receive` | verified | verified |
| atmosphere | `EndpointState` | `is_send` | verified | verified |
| atmosphere | `IPCPayLoad` | `get_payload_as_endpoint` | verified | verified |
| atmosphere | `IPCPayLoad` | `get_payload_as_va_range` | verified | verified |
| atmosphere | `Kernel` | `get_address_space_va_range_none` | verified | verified |
| atmosphere | `MemoryManager` | `get_iommu_table_l1_entry` | verified | verified |
| atmosphere | `MemoryManager` | `get_iommu_table_l2_entry` | verified | verified |
| atmosphere | `MemoryManager` | `get_iommu_table_l3_entry` | verified | verified |
| atmosphere | `MemoryManager` | `get_iommu_table_l4_entry` | verified | verified |
| atmosphere | `MemoryManager` | `get_pagetable_l1_entry` | verified | verified |
| atmosphere | `MemoryManager` | `get_pagetable_l2_entry` | verified | verified |
| atmosphere | `MemoryManager` | `get_pagetable_l3_entry` | verified | verified |
| atmosphere | `MemoryManager` | `get_pagetable_l4_entry` | verified | verified |
| atmosphere | `PageAllocator` | `get_page_reference_counter` | verified | verified |
| atmosphere | `PageMap` | `get` | verified | verified |
| atmosphere | `PageMap` | `set` | verified | verified |
| atmosphere | `PageTable` | `get_entry_1g_l3` | verified | verified |
| atmosphere | `PageTable` | `get_entry_2m_l2` | verified | verified |
| atmosphere | `PageTable` | `get_entry_l1` | verified | verified |
| atmosphere | `PageTable` | `get_entry_l2` | verified | verified |
| atmosphere | `PageTable` | `get_entry_l3` | verified | verified |
| atmosphere | `PageTable` | `get_entry_l4` | verified | verified |
| atmosphere | `ProcessManager` | `container_check_is_ancestor` | verified | verified |
| atmosphere | `ProcessManager` | `get_container` | verified | verified |
| atmosphere | `ProcessManager` | `get_container_by_proc_ptr` | verified | verified |
| atmosphere | `ProcessManager` | `get_cpu` | verified | verified |
| atmosphere | `ProcessManager` | `get_endpoint` | verified | verified |
| atmosphere | `ProcessManager` | `get_endpoint_by_endpoint_idx` | verified | verified |
| atmosphere | `ProcessManager` | `get_endpoint_ptr_by_endpoint_idx` | verified | verified |
| atmosphere | `ProcessManager` | `get_owning_proc_by_thread_ptr` | verified | verified |
| atmosphere | `ProcessManager` | `get_proc` | verified | verified |
| atmosphere | `ProcessManager` | `get_thread` | verified | verified |
| atmosphere | `Quota` | `subtract_mem_4k` | verified | verified |
| atmosphere | `StaticLinkedList` | `get_head` | verified | verified |
| atmosphere | `SyscallReturnStruct` | `NoNextThreadNew` | verified | verified |
| atmosphere | `SyscallReturnStruct` | `NoSwitchNew` | verified | verified |
| atmosphere | `SyscallReturnStruct` | `SwitchNew` | verified | verified |
| atmosphere | `SyscallReturnStruct` | `is_error` | verified | verified |
| atmosphere | `TrapFrameOption` | `unwrap` | verified | verified |
| atmosphere | `VaRange4K` | `index` | verified | verified |
| ironkv | `(free)` | `ckeyhashmap_max_serialized_size_exec` | verified | verified |
| ironkv | `(free)` | `do_end_points_match` | verified | verified |
| ironkv | `(free)` | `do_vec_u8s_match` | verified | verified |
| ironkv | `(free)` | `endpoints_contain` | verified | verified |
| ironkv | `(free)` | `make_empty_event_results` | verified | verified |
| ironkv | `(free)` | `make_send_only_event_results` | verified | verified |
| ironkv | `(free)` | `test_unique` | verified | verified |
| ironkv | `CKeyHashMap` | `from_vec` | verified | verified |
| ironkv | `CKeyHashMap` | `len` | verified | verified |
| ironkv | `CMessage` | `is_message_marshallable` | verified | verified |
| ironkv | `CTombstoneTable` | `lookup` | verified | verified |
| ironkv | `DelegationMap` | `delegate_for_key_range_is_host_impl` | verified | verified |
| ironkv | `EndPoint` | `valid_physical_address` | verified | verified |
| ironkv | `KeyIterator` | `end` | verified | verified |
| ironkv | `KeyIterator` | `get` | verified | verified |
| ironkv | `KeyIterator` | `is_end` | verified | verified |
| ironkv | `KeyIterator` | `new` | verified | verified |
| ironkv | `Ordering` | `is_eq` | verified | verified |
| ironkv | `Parameters` | `static_params` | verified | verified |
| ironkv | `SHTKey` | `clone` | verified | verified |
| memory-allocator | `(free)` | `align_down` | verified | verified |
| memory-allocator | `(free)` | `align_up` | verified | verified |
| memory-allocator | `CommitMask` | `all_set` | verified | verified |
| memory-allocator | `CommitMask` | `any_set` | verified | verified |
| memory-allocator | `CommitMask` | `clear` | verified | verified |
| memory-allocator | `CommitMask` | `create` | verified | verified |
| memory-allocator | `CommitMask` | `create_empty` | verified | verified |
| memory-allocator | `CommitMask` | `create_full` | verified | verified |
| memory-allocator | `CommitMask` | `create_intersect` | verified | verified |
| memory-allocator | `CommitMask` | `empty` | verified | verified |
| memory-allocator | `CommitMask` | `is_empty` | verified | verified |
| memory-allocator | `CommitMask` | `is_full` | verified | verified |
| memory-allocator | `CommitMask` | `set` | verified | verified |
| nrkernel | `(free)` | `MASK_ADDR` | verified | verified |
| nrkernel | `(free)` | `MASK_L1_PG_ADDR` | verified | verified |
| nrkernel | `(free)` | `MASK_L2_PG_ADDR` | verified | verified |
| nrkernel | `(free)` | `MASK_L3_PG_ADDR` | verified | verified |
| nrkernel | `(free)` | `MAX_PHYADDR` | verified | verified |
| nrkernel | `(free)` | `x86_arch_exec` | verified | verified |
| vest | `(free)` | `compare_slice` | verified | verified |

## 4.3 Concrete verified — rescued by `assumes` axioms (142, abstract not evaluated)

| proj | type | fn | concrete | abstract |
|------|------|----|----------|----------|
| atmosphere | `(free)` | `container_perms_update_subtree_set` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `endpoint_pop_head` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `endpoint_push` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `endpoint_push_and_set_state` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `endpoint_to_page` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `merge_4k_pages_to_2m_page` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `page_entry2usize` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `page_to_container_tree_version_1` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `page_to_endpoint_with_thread_and_container` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `page_to_proc_with_first_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `proc_perms_remove_subtree_set` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `proc_push_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `proc_remove_child` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `proc_remove_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `proc_to_page` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `thread_set_endpoint_descriptor` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `(free)` | `thread_to_page` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Array` | `init2none` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Array` | `init2zero` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Array` | `new` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Array` | `set` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ArraySet` | `init` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ArraySet` | `new` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ArrayVec` | `pop_unique` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `alloc_and_map` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `alloc_and_map_io` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `create_entry` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `create_entry_and_alloc_and_map` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `create_entry_and_alloc_and_map_io` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `create_entry_and_share` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `create_iommu_table_entry` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `helper_kernel_kill_proc_non_root` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `helper_kernel_kill_proc_root` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `kernel_drop_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `kernel_kill_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `kernel_proc_kill_all_threads` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `schedule_idle_cpu` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `share_mapping` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_mmap` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_new_container_with_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_new_proc_with_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_new_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_new_thread_with_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_receive_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_receive_pages` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_send_empty_block` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_send_empty_no_block` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_send_empty_try_schedule` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_send_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `Kernel` | `syscall_send_pages` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `MemoryManager` | `alloc_iommu_table` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `MemoryManager` | `alloc_page_table` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `MemoryManager` | `free_page_table` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `MemoryManager` | `iommu_table_map_4k_page` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `MemoryManager` | `pagetable_map_4k_page` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `MemoryManager` | `resolve_iommu_table_mapping` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `MemoryManager` | `resolve_pagetable_mapping` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `add_io_mapping_4k` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `add_mapping_4k` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `alloc_and_map_2m` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `alloc_and_map_4k` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `alloc_and_map_io_4k` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `alloc_page_2m` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `alloc_page_4k` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `alloc_page_4k_for_new_container` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `merged_4k_to_2m` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `set_io_mapping` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `set_mapping` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `set_owning_container` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `set_ref_count` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `set_rev_pointer` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageAllocator` | `set_state` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageMap` | `init` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageTable` | `map_2m_page` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageTable` | `map_4k_page` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageTable` | `remove_l2_entry` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `PageTable` | `remove_l3_entry` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `block_running_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `block_running_thread_and_change_queue_state` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `block_running_thread_and_change_queue_state_and_set_trap_frame` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `block_running_thread_and_set_trap_frame` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `drop_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `kill_blocked_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `kill_process_none_root` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `kill_process_root` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `kill_running_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `kill_scheduled_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `new_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `new_proc_with_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `new_proc_with_endpoint_iommu` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `new_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `new_thread_with_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `pass_endpoint` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `pop_scheduler_for_idle_cpu` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `run_blocked_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `schedule_blocked_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `schedule_running_thread` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `ProcessManager` | `set_container_mem_quota_mem_4k` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `init` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `pop` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `push` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `remove` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `remove_helper1` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `remove_helper2` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `remove_helper3` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `remove_helper4` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `remove_helper5` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `remove_helper6` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `remove_helper7` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `set_next` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `set_prev` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `StaticLinkedList` | `set_value` | verified (assume-rescued) | N/A — concrete used assumes |
| atmosphere | `VaRange4K` | `new` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `(free)` | `clone_end_point` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `(free)` | `clone_option_vec_u8` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `(free)` | `clone_optional_value` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `(free)` | `clone_vec_u8` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `(free)` | `sht_demarshall_data_method` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `(free)` | `vec_erase` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CAckState` | `new` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CMessage` | `clone_up_to_view` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSendState` | `cack_state_swap` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSendState` | `put` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSingleDelivery` | `empty` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSingleDelivery` | `maybe_ack_packet_impl` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSingleDelivery` | `receive_ack_impl` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSingleDelivery` | `receive_impl` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSingleDelivery` | `receive_real_packet_impl` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSingleDelivery` | `retransmit_un_acked_packets` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSingleDelivery` | `retransmit_un_acked_packets_for_dst` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSingleDelivery` | `send_single_cmessage` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `CSingleMessage` | `clone_up_to_view` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `DelegationMap` | `get` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `DelegationMap` | `new` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `DelegationMap` | `set` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `EndPoint` | `clone_up_to_view` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `HashMap` | `insert` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `HashMap` | `keys` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `HashMap` | `new` | verified (assume-rescued) | N/A — concrete used assumes |
| ironkv | `NetClient` | `get_my_end_point` | verified (assume-rescued) | N/A — concrete used assumes |
| memory-allocator | `CommitMask` | `next_run` | verified (assume-rescued) | N/A — concrete used assumes |
| vest | `(free)` | `set_range` | verified (assume-rescued) | N/A — concrete used assumes |

## 4.4 Concrete FAILED — verus_error / runner_crash (78, abstract not evaluated)

| proj | type | fn | concrete | abstract |
|------|------|----|----------|----------|
| atmosphere | `(free)` | `container_insert_cpu` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `container_pop_endpoint` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `container_push_child` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `container_push_endpoint` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `container_push_proc` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `container_remove_cpu` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `container_remove_proc` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `container_set_owned_threads` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `container_set_quota` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `container_set_quota_mem_4k` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `page_entry_to_map_entry` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `page_map_set` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `page_map_set_kernel_entry_range` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `page_map_set_no_requires` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `page_perm_to_page_map` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `page_to_thread` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `page_to_thread_with_endpoint` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `scheduler_push_thread` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `scheduler_remove_thread` | failed | N/A — concrete failed |
| atmosphere | `(free)` | `thread_set_current_cpu` | failed | N/A — concrete failed |
| atmosphere | `Array` | `iommu_table_array_create_iommu_table_l2_entry_t` | failed | N/A — concrete failed |
| atmosphere | `Array` | `iommu_table_array_create_iommu_table_l3_entry_t` | failed | N/A — concrete failed |
| atmosphere | `Array` | `iommu_table_array_create_iommu_table_l4_entry_t` | failed | N/A — concrete failed |
| atmosphere | `Array` | `pagetable_array_create_pagetable_l2_entry_t` | failed | N/A — concrete failed |
| atmosphere | `Array` | `pagetable_array_create_pagetable_l3_entry_t` | failed | N/A — concrete failed |
| atmosphere | `Array` | `pagetable_array_create_pagetable_l4_entry_t` | failed | N/A — concrete failed |
| atmosphere | `Kernel` | `check_address_space_va_range_free` | failed | N/A — concrete failed |
| atmosphere | `Kernel` | `check_address_space_va_range_shareable` | failed | N/A — concrete failed |
| atmosphere | `Kernel` | `check_io_space_va_range_free` | failed | N/A — concrete failed |
| atmosphere | `Kernel` | `range_alloc_and_map` | failed | N/A — concrete failed |
| atmosphere | `Kernel` | `range_alloc_and_map_io` | failed | N/A — concrete failed |
| atmosphere | `Kernel` | `range_create_and_share_mapping` | failed | N/A — concrete failed |
| atmosphere | `MemoryManager` | `create_iommu_table_l2_entry` | failed | N/A — concrete failed |
| atmosphere | `MemoryManager` | `create_iommu_table_l3_entry` | failed | N/A — concrete failed |
| atmosphere | `MemoryManager` | `create_iommu_table_l4_entry` | failed | N/A — concrete failed |
| atmosphere | `MemoryManager` | `create_pagetable_l2_entry` | failed | N/A — concrete failed |
| atmosphere | `MemoryManager` | `create_pagetable_l3_entry` | failed | N/A — concrete failed |
| atmosphere | `MemoryManager` | `create_pagetable_l4_entry` | failed | N/A — concrete failed |
| atmosphere | `PageAllocator` | `free_page_4k` | failed | N/A — concrete failed |
| atmosphere | `PageTable` | `create_entry_l2` | failed | N/A — concrete failed |
| atmosphere | `PageTable` | `create_entry_l3` | failed | N/A — concrete failed |
| atmosphere | `PageTable` | `create_entry_l4` | failed | N/A — concrete failed |
| atmosphere | `ProcessManager` | `new_container_with_endpoint` | failed | N/A — concrete failed |
| atmosphere | `Quota` | `subtract_new_quota` | failed | N/A — concrete failed |
| atmosphere | `Registers` | `set_self_fast` | failed | N/A — concrete failed |
| ironkv | `(free)` | `receive_with_demarshal` | failed | N/A — concrete failed |
| ironkv | `(free)` | `send_packet` | failed | N/A — concrete failed |
| ironkv | `(free)` | `send_packet_seq` | failed | N/A — concrete failed |
| ironkv | `CAckState` | `truncate` | failed | N/A — concrete failed |
| ironkv | `CKeyHashMap` | `bulk_remove` | failed | N/A — concrete failed |
| ironkv | `CKeyHashMap` | `bulk_update` | failed | N/A — concrete failed |
| ironkv | `CKeyHashMap` | `insert` | failed | N/A — concrete failed |
| ironkv | `CKeyHashMap` | `remove` | failed | N/A — concrete failed |
| ironkv | `DelegationMap` | `range_consistent_impl` | failed | N/A — concrete failed |
| ironkv | `HashMap` | `get` | failed | N/A — concrete failed |
| ironkv | `HostState` | `deliver_outbound_packets` | failed | N/A — concrete failed |
| ironkv | `HostState` | `deliver_packet_seq` | failed | N/A — concrete failed |
| ironkv | `HostState` | `host_noreceive_noclock_next` | failed | N/A — concrete failed |
| ironkv | `HostState` | `real_init_impl` | failed | N/A — concrete failed |
| ironkv | `HostState` | `real_next_impl` | failed | N/A — concrete failed |
| ironkv | `HostState` | `receive_packet_next` | failed | N/A — concrete failed |
| ironkv | `NetClient` | `receive` | failed | N/A — concrete failed |
| ironkv | `NetClient` | `send` | failed | N/A — concrete failed |
| memory-allocator | `(free)` | `calculate_page_block_at` | failed | N/A — concrete failed |
| nrkernel | `PDE` | `address` | failed | N/A — concrete failed |
| nrkernel | `PDE` | `new_entry` | failed | N/A — concrete failed |
| storage | `(free)` | `calculate_crc` | failed | N/A — concrete failed |
| storage | `(free)` | `calculate_crc_bytes` | failed | N/A — concrete failed |
| storage | `(free)` | `check_cdb` | failed | N/A — concrete failed |
| storage | `(free)` | `check_crc` | failed | N/A — concrete failed |
| storage | `(free)` | `get_region_sizes` | failed | N/A — concrete failed |
| storage | `(free)` | `read_cdb` | failed | N/A — concrete failed |
| storage | `(free)` | `read_log_variables` | failed | N/A — concrete failed |
| storage | `(free)` | `write_setup_metadata` | failed | N/A — concrete failed |
| storage | `CrcDigest` | `new` | failed | N/A — concrete failed |
| storage | `CrcDigest` | `sum64` | failed | N/A — concrete failed |
| storage | `CrcDigest` | `write` | failed | N/A — concrete failed |
| storage | `CrcDigest` | `write_bytes` | failed | N/A — concrete failed |
