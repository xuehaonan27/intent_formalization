# Real incompleteness findings (witness-bearing)

Triage of 367 witnesses produced by the spec-determinism
verusage batch (commit eed6038, post-soundness-fix). Classified as
**real** when the postcondition shows the return value or post-state
is genuinely underdetermined (∃-quantifier, set/multiset membership
on the result, disjunction over distinct outcomes, or `choose|...|`).

- **real**: 29
- suspect (functional-shape ensures, witness likely a tooling artifact): 338
- unclear (no ensures captured): 0

## Real, by project

### atmosphere (28 occurrence(s))

#### `alloc_and_map_4k`  (2×)

- **file**: `atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_4k.rs`
- **artifact_key**: `atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__alloc_and_map_4k__alloc_and_map_4k`
- **rounds**: 2
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              // self.free_pages_4k() =~= old(self).free_pages_4k(),
              self.free_pages_2m() =~= old(self).free_pages_2m(),
              self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret),
              self.free_pages_1g() =~= old(self).free_pages_1g(),
              self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
              self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
              self.allocated_pages_1g() =~= old(self...
  ```
- **witness (assumes)**:
  ```
  !det_alloc_and_map_4k_equal(r1, r2, post1_self_, post2_self_)
  ```
- additional artifacts (1 more):
  - `atmosphere__verified__kernel__kernel__create_and_map_pages__impl0__alloc_and_map__alloc_and_map_4k`

#### `alloc_and_map_io_4k`  (2×)

- **file**: `atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_io_4k.rs`
- **artifact_key**: `atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__alloc_and_map_io_4k__alloc_and_map_io_4k`
- **rounds**: 2
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              // self.free_pages_4k() =~= old(self).free_pages_4k(),
              self.free_pages_2m() =~= old(self).free_pages_2m(),
              self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret),
              self.free_pages_1g() =~= old(self).free_pages_1g(),
              self.allocated_pages_4k() =~= old(self).allocated_pages_4k(),
              self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
              self.allocated_pages_1g() =~= old(self...
  ```
- **witness (assumes)**:
  ```
  !det_alloc_and_map_io_4k_equal(r1, r2, post1_self_, post2_self_)
  ```
- additional artifacts (1 more):
  - `atmosphere__verified__kernel__kernel__create_and_map_pages__impl0__alloc_and_map_io__alloc_and_map_io_4k`

#### `alloc_page_4k`  (8×)

- **file**: `atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_4k.rs`
- **artifact_key**: `atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__alloc_page_4k__alloc_page_4k`
- **rounds**: 2
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              // self.free_pages_4k() =~= old(self).free_pages_4k(),
              self.free_pages_2m() =~= old(self).free_pages_2m(),
              self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret.0),
              self.free_pages_1g() =~= old(self).free_pages_1g(),
              self.allocated_pages_4k() =~= old(self).allocated_pages_4k().insert(ret.0),
              self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
              self.allocated_pages_1...
  ```
- **witness (assumes)**:
  ```
  !det_alloc_page_4k_equal(r1, r2, post1_self_, post2_self_)
  ```
- additional artifacts (7 more):
  - `atmosphere__verified__kernel__kernel__mem_util__impl0__create_entry__alloc_page_4k`
  - `atmosphere__verified__kernel__kernel__mem_util__impl0__create_iommu_table_entry__alloc_page_4k`
  - `atmosphere__verified__kernel__kernel__syscall_new_container__impl0__syscall_new_container_with_endpoint__alloc_page_4k`
  - `atmosphere__verified__kernel__kernel__syscall_new_proc__impl0__syscall_new_proc_with_endpoint__alloc_page_4k`
  - `atmosphere__verified__kernel__kernel__syscall_new_proc_with_iommu__impl0__syscall_new_proc_with_endpoint_iommu__alloc_page_4k`
  - `atmosphere__verified__kernel__kernel__syscall_new_thread__impl0__syscall_new_thread__alloc_page_4k`
  - `atmosphere__verified__kernel__kernel__syscall_new_thread_with_endpoint__impl0__syscall_new_thread_with_endpoint__alloc_page_4k`

#### `alloc_page_4k_for_new_container`  (2×)

- **file**: `atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_page_4k_for_new_container.rs`
- **artifact_key**: `atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__alloc_page_4k_for_new_container__alloc_page_4k_for_new_container`
- **rounds**: 2
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              // self.free_pages_4k() =~= old(self).free_pages_4k(),
              self.free_pages_2m() =~= old(self).free_pages_2m(),
              self.free_pages_4k() =~= old(self).free_pages_4k().remove(ret.0),
              self.free_pages_1g() =~= old(self).free_pages_1g(),
              self.allocated_pages_4k() =~= old(self).allocated_pages_4k().insert(ret.0),
              self.allocated_pages_2m() =~= old(self).allocated_pages_2m(),
              self.allocated_pages_1...
  ```
- **witness (assumes)**:
  ```
  !det_alloc_page_4k_for_new_container_equal(r1, r2, post1_self_, post2_self_)
  ```
- additional artifacts (1 more):
  - `atmosphere__verified__kernel__kernel__syscall_new_container__impl0__syscall_new_container_with_endpoint__alloc_page_4k_for_new_container`

#### `drop_endpoint`  (2×)

- **file**: `atmosphere/verified/kernel/kernel__kernel_drop_endpoint__impl0__kernel_drop_endpoint.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__kernel_drop_endpoint__impl0__kernel_drop_endpoint__drop_endpoint`
- **rounds**: 4
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              ret.is_Some() ==> self.page_closure() =~= old(self).page_closure().remove(ret.unwrap().0),
              ret.is_Some() ==> old(self).page_closure().contains(ret.unwrap().0),
              ret.is_Some() ==> ret.unwrap().0 == ret.unwrap().1@.addr(),
              ret.is_Some() ==> ret.unwrap().1@.is_init(),
              ret.is_Some() ==> old(self).container_dom().contains(ret.unwrap().0) == false,
              ret.is_None() ==> self.page_closure() =~= old(self).p...
  ```
- **witness (assumes)**:
  ```
  r1 is Some
  r2 is Some
  !det_drop_endpoint_equal(r1, r2, post1_self_, post2_self_)
  ```
- additional artifacts (1 more):
  - `atmosphere__verified__process_manager__process_manager__impl_drop_enpoints__impl0__drop_endpoint__drop_endpoint`

#### `kill_blocked_thread`  (1×)

- **file**: `atmosphere/verified/kernel/kernel__kernel_kill_thread__impl0__kernel_kill_thread.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__kernel_kill_thread__impl0__kernel_kill_thread__kill_blocked_thread`
- **rounds**: 2
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              self.thread_dom() == old(self).thread_dom().remove(thread_ptr),
              threads_unchanged_except(*old(self), *self, set![]),
              self.proc_dom() == old(self).proc_dom(),
              process_tree_unchanged(*old(self), *self),
              self.container_dom() == old(self).container_dom(),
              containers_tree_unchanged(*old(self), *self),
              self.get_proc(old(self).get_thread(thread_ptr).owning_proc).owned_threads@ == 
          ...
  ```
- **witness (assumes)**:
  ```
  !det_kill_blocked_thread_equal(r1, r2, post1_self_, post2_self_)
  ```

#### `kill_process_none_root`  (2×)

- **file**: `atmosphere/verified/kernel/kernel__kernel_kill_proc__impl0__helper_kernel_kill_proc_non_root.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__kernel_kill_proc__impl0__helper_kernel_kill_proc_non_root__kill_process_none_root`
- **rounds**: 2
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              self.container_dom() == old(self).container_dom(),
              containers_tree_unchanged(*old(self), *self),
              self.proc_dom() == old(self).proc_dom().remove(proc_ptr),
              processes_fields_unchanged(*old(self), *self),
              self.thread_dom() == old(self).thread_dom(),
              threads_unchanged(*old(self), *self),
              self.page_closure() =~= old(self).page_closure().remove(ret.0),
              old(self).page_closure()...
  ```
- **witness (assumes)**:
  ```
  !det_kill_process_none_root_equal(r1, r2, post1_self_, post2_self_)
  ```
- additional artifacts (1 more):
  - `atmosphere__verified__process_manager__process_manager__impl_kill_proc__impl0__kill_process_none_root__kill_process_none_root`

#### `kill_process_root`  (1×)

- **file**: `atmosphere/verified/kernel/kernel__kernel_kill_proc__impl0__helper_kernel_kill_proc_root.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__kernel_kill_proc__impl0__helper_kernel_kill_proc_root__kill_process_root`
- **rounds**: 2
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              self.container_dom() == old(self).container_dom(),
              containers_tree_unchanged(*old(self), *self),
              self.proc_dom() == old(self).proc_dom().remove(proc_ptr),
              processes_fields_unchanged(*old(self), *self),
              self.thread_dom() == old(self).thread_dom(),
              threads_unchanged(*old(self), *self),
              self.page_closure() =~= old(self).page_closure().remove(ret.0),
              old(self).page_closure()...
  ```
- **witness (assumes)**:
  ```
  !det_kill_process_root_equal(r1, r2, post1_self_, post2_self_)
  ```

#### `kill_running_thread`  (2×)

- **file**: `atmosphere/verified/kernel/kernel__kernel_kill_thread__impl0__kernel_kill_thread.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__kernel_kill_thread__impl0__kernel_kill_thread__kill_running_thread`
- **rounds**: 2
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              self.thread_dom() == old(self).thread_dom().remove(thread_ptr),
              threads_unchanged_except(*old(self), *self, set![]),
              self.proc_dom() == old(self).proc_dom(),
              process_tree_unchanged(*old(self), *self),
              self.container_dom() == old(self).container_dom(),
              containers_tree_unchanged(*old(self), *self),
              self.get_proc(old(self).get_thread(thread_ptr).owning_proc).owned_threads@ == 
          ...
  ```
- **witness (assumes)**:
  ```
  !det_kill_running_thread_equal(r1, r2, post1_self_, post2_self_)
  ```
- additional artifacts (1 more):
  - `atmosphere__verified__process_manager__process_manager__impl_kill_thread__impl0__kill_running_thread__kill_running_thread`

#### `kill_scheduled_thread`  (2×)

- **file**: `atmosphere/verified/kernel/kernel__kernel_kill_thread__impl0__kernel_kill_thread.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__kernel_kill_thread__impl0__kernel_kill_thread__kill_scheduled_thread`
- **rounds**: 2
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              self.thread_dom() == old(self).thread_dom().remove(thread_ptr),
              threads_unchanged_except(*old(self), *self, set![]),
              self.proc_dom() == old(self).proc_dom(),
              process_tree_unchanged(*old(self), *self),
              self.container_dom() == old(self).container_dom(),
              containers_tree_unchanged(*old(self), *self),
              self.get_proc(old(self).get_thread(thread_ptr).owning_proc).owned_threads@ == 
          ...
  ```
- **witness (assumes)**:
  ```
  !det_kill_scheduled_thread_equal(r1, r2, post1_self_, post2_self_)
  ```
- additional artifacts (1 more):
  - `atmosphere__verified__process_manager__process_manager__impl_kill_thread__impl0__kill_scheduled_thread__kill_scheduled_thread`

#### `new_proc_with_endpoint`  (1×)

- **file**: `atmosphere/verified/kernel/kernel__syscall_new_proc__impl0__syscall_new_proc_with_endpoint.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__syscall_new_proc__impl0__syscall_new_proc_with_endpoint__new_proc_with_endpoint`
- **rounds**: 128
- **why real**: disjunction
- **ensures**:
  ```
  ensures
              self.wf(),
              self.page_closure() =~= old(self).page_closure().insert(page_ptr_1).insert(page_ptr_2),
              self.proc_dom() =~= old(self).proc_dom().insert(page_ptr_1),
              self.endpoint_dom() == old(self).endpoint_dom(),
              self.container_dom() == old(self).container_dom(),
              self.thread_dom() == old(self).thread_dom().insert(page_ptr_2),
              old(self).get_container(
                  old(self).get_thread(thread_ptr).owning_con...
  ```
- **witness (assumes)**:
  ```
  pt_regs.r15 == 0
  pt_regs.r14 == 0
  pt_regs.r13 == 0
  pt_regs.r12 == 0
  pt_regs.rbp == 0
  pt_regs.rbx == 0
  pt_regs.r11 == 0
  pt_regs.r10 == 0
  pt_regs.r9 == 0
  pt_regs.r8 == 0
  pt_regs.rcx == 0
  pt_regs.rdx == 0
  pt_regs.rsi == 0
  pt_regs.rdi == 0
  pt_regs.rax == 0
  pt_regs.error_code == 0
  pt_regs.rip == 0
  pt_regs.cs == 0
  pt_regs.flags == 0
  pt_regs.rsp == 0
  pt_regs.ss == 0
  !det_new_proc_with_endpoint_equal(r1, r2, post1_self_, post2_self_)
  ```

#### `new_proc_with_endpoint_iommu`  (1×)

- **file**: `atmosphere/verified/kernel/kernel__syscall_new_proc_with_iommu__impl0__syscall_new_proc_with_endpoint_iommu.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__syscall_new_proc_with_iommu__impl0__syscall_new_proc_with_endpoint_iommu__new_proc_with_endpoint_iommu`
- **rounds**: 128
- **why real**: disjunction
- **ensures**:
  ```
  ensures
              self.wf(),
              self.page_closure() =~= old(self).page_closure().insert(page_ptr_1).insert(page_ptr_2),
              self.proc_dom() =~= old(self).proc_dom().insert(page_ptr_1),
              self.endpoint_dom() == old(self).endpoint_dom(),
              self.container_dom() == old(self).container_dom(),
              self.thread_dom() == old(self).thread_dom().insert(page_ptr_2),
              old(self).get_container(
                  old(self).get_thread(thread_ptr).owning_con...
  ```
- **witness (assumes)**:
  ```
  pt_regs.r15 == 0
  pt_regs.r14 == 0
  pt_regs.r13 == 0
  pt_regs.r12 == 0
  pt_regs.rbp == 0
  pt_regs.rbx == 0
  pt_regs.r11 == 0
  pt_regs.r10 == 0
  pt_regs.r9 == 0
  pt_regs.r8 == 0
  pt_regs.rcx == 0
  pt_regs.rdx == 0
  pt_regs.rsi == 0
  pt_regs.rdi == 0
  pt_regs.rax == 0
  pt_regs.error_code == 0
  pt_regs.rip == 0
  pt_regs.cs == 0
  pt_regs.flags == 0
  pt_regs.rsp == 0
  pt_regs.ss == 0
  !det_new_proc_with_endpoint_iommu_equal(r1, r2, post1_self_, post2_self_)
  ```

#### `new_thread_with_endpoint`  (1×)

- **file**: `atmosphere/verified/kernel/kernel__syscall_new_thread_with_endpoint__impl0__syscall_new_thread_with_endpoint.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__syscall_new_thread_with_endpoint__impl0__syscall_new_thread_with_endpoint__new_thread_with_endpoint`
- **rounds**: 128
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              self.page_closure() =~= old(self).page_closure().insert(page_ptr),
              self.proc_dom() =~= old(self).proc_dom(),
              self.endpoint_dom() == old(self).endpoint_dom(),
              self.container_dom() == old(self).container_dom(),
              self.thread_dom() == old(self).thread_dom().insert(ret),
              old(self).get_container(old(self).get_thread(thread_ptr).owning_container).quota.spec_subtract_mem_4k(self.get_container(self.get_t...
  ```
- **witness (assumes)**:
  ```
  pt_regs.r15 == 0
  pt_regs.r14 == 0
  pt_regs.r13 == 0
  pt_regs.r12 == 0
  pt_regs.rbp == 0
  pt_regs.rbx == 0
  pt_regs.r11 == 0
  pt_regs.r10 == 0
  pt_regs.r9 == 0
  pt_regs.r8 == 0
  pt_regs.rcx == 0
  pt_regs.rdx == 0
  pt_regs.rsi == 0
  pt_regs.rdi == 0
  pt_regs.rax == 0
  pt_regs.error_code == 0
  pt_regs.rip == 0
  pt_regs.cs == 0
  pt_regs.flags == 0
  pt_regs.rsp == 0
  pt_regs.ss == 0
  !det_new_thread_with_endpoint_equal(r1, r2, post1_self_, post2_self_)
  ```

#### `pop_scheduler_for_idle_cpu`  (1×)

- **file**: `atmosphere/verified/kernel/kernel__schedule_idle_cpu__impl0__schedule_idle_cpu.rs`
- **artifact_key**: `atmosphere__verified__kernel__kernel__schedule_idle_cpu__impl0__schedule_idle_cpu__pop_scheduler_for_idle_cpu`
- **rounds**: 380
- **why real**: r ∈ container
- **ensures**:
  ```
  ensures
              self.wf(),
              self.page_closure() =~= old(self).page_closure(),
              self.proc_dom() =~= old(self).proc_dom(),
              self.endpoint_dom() == old(self).endpoint_dom(),
              self.container_dom() == old(self).container_dom(),
              self.thread_dom() == old(self).thread_dom(),
              self.thread_dom().contains(ret),
              forall|p_ptr: ProcPtr|
                  #![trigger self.get_proc(p_ptr)]
                  self.proc_dom().contains(p_...
  ```
- **witness (assumes)**:
  ```
  pre_pt_regs.r15 == 0
  pre_pt_regs.r14 == 0
  pre_pt_regs.r13 == 0
  pre_pt_regs.r12 == 0
  pre_pt_regs.rbp == 0
  pre_pt_regs.rbx == 0
  pre_pt_regs.r11 == 0
  pre_pt_regs.r10 == 0
  pre_pt_regs.r9 == 0
  pre_pt_regs.r8 == 0
  pre_pt_regs.rcx == 0
  pre_pt_regs.rdx == 0
  pre_pt_regs.rsi == 0
  pre_pt_regs.rdi == 0
  pre_pt_regs.rax == 0
  pre_pt_regs.error_code == 0
  pre_pt_regs.rip == 0
  pre_pt_regs.cs == 0
  pre_pt_regs.flags == 0
  pre_pt_regs.rsp == 0
  pre_pt_regs.ss == 0
  post1_pt_regs.r15 == 0
  post1_pt_regs.r14 == 0
  post1_pt_regs.r13 == 0
  post1_pt_regs.r12 == 0
  post1_pt_regs.rbp == 0
  post1_pt_regs.rbx == 0
  post1_pt_regs.r11 == 0
  post1_pt_regs.r10 == 0
  post1_pt_regs.r9 == 0
  post1_pt_regs.r8 == 0
  post1_pt_regs.rcx == 0
  post1_pt_regs.rdx == 0
  post1_pt_regs.rsi == 0
  post1_pt_regs.rdi == 0
  post1_pt_regs.rax == 0
  post1_pt_regs.error_code == 0
  post1_pt_regs.rip == 0
  post1_pt_regs.cs == 0
  post1_pt_regs.flags == 0
  post1_pt_regs.rsp == 0
  post1_pt_regs.ss == 0
  post2_pt_regs.r15 == 0
  post2_pt_regs.r14 == 0
  post2_pt_regs.r13 == 0
  post2_pt_regs.r12 == 0
  post2_pt_regs.rbp == 0
  post2_pt_regs.rbx == 0
  post2_pt_regs.r11 == 0
  post2_pt_regs.r10 == 0
  post2_pt_regs.r9 == 0
  post2_pt_regs.r8 == 0
  post2_pt_regs.rcx == 0
  post2_pt_regs.rdx == 0
  post2_pt_regs.rsi == 0
  post2_pt_regs.rdi == 0
  post2_pt_regs.rax == 0
  post2_pt_regs.error_code == 0
  post2_pt_regs.rip == 0
  post2_pt_regs.cs == 0
  post2_pt_regs.flags == 0
  post2_pt_regs.rsp == 0
  post2_pt_regs.ss == 0
  !det_pop_scheduler_for_idle_cpu_equal(r1, r2, post1_self_, post2_self_, post1_pt_regs, post2_pt_regs)
  ```

### ironkv (1 occurrence(s))

#### `parse_command_line_configuration`  (1×)

- **file**: `ironkv/verified/host_impl_v/host_impl_v__impl2__real_init_impl.rs`
- **artifact_key**: `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__parse_command_line_configuration`
- **rounds**: 272
- **why real**: disjunction
- **ensures**:
  ```
  ensures ({
          let abstract_end_points = parse_args(abstractify_args(*args));
          match rc {
              None => {
                  ||| abstract_end_points.is_None()
                  ||| abstract_end_points.unwrap().len()==0
                  ||| !seq_is_unique(abstract_end_points.unwrap())
              },
              Some(c) => {
                  &&& abstract_end_points.is_some()
                  &&& abstract_end_points.unwrap().len() > 0
                  &&& seq_is_unique(abstract_end_points.u...
  ```
- **witness (assumes)**:
  ```
  r1 is Some
  r1->Some_0.params.max_seqno == 18446744073709551615
  r1->Some_0.params.max_delegations == 9223372036854775807
  r2 is Some
  r2->Some_0.params.max_seqno == 18446744073709551615
  r2->Some_0.params.max_delegations == 9223372036854775807
  !det_parse_command_line_configuration_equal(r1, r2)
  ```

## Suspect (likely false positives or tooling artifacts)

These are witnesses where the captured ensures clauses pin the return /
post-state functionally (no exists, no membership-on-result, no disjunctions),
yet the schema solver still produced a separating witness. Common causes:

- equal-fn over-compares fields the spec leaves implicit ("rest unchanged"
  is not in the ensures, so the equal-fn includes them and finds a difference);
- opaque datatypes whose internal fields are accessed via `.@` views that
  the synthesized equal-fn cannot fully constrain;
- truncated ensures (the function body has more spec elsewhere — e.g. lemmas).

Total: 338 witnesses across 152 unique fns.

| project | fn | occurrences |
|---|---|---:|
| atmosphere | `set` | 16 |
| atmosphere | `set_next` | 10 |
| atmosphere | `set_prev` | 10 |
| atmosphere | `set_state` | 10 |
| atmosphere | `schedule_blocked_thread` | 9 |
| atmosphere | `set_ref_count` | 9 |
| ironkv | `clone_up_to_view` | 8 |
| atmosphere | `pop` | 7 |
| atmosphere | `set_mapping` | 7 |
| ironkv | `new` | 7 |
| atmosphere | `set_owning_container` | 6 |
| ironkv | `insert` | 6 |
| ironkv | `set` | 6 |
| atmosphere | `block_running_thread` | 5 |
| atmosphere | `block_running_thread_and_change_queue_state` | 5 |
| atmosphere | `resolve_pagetable_mapping` | 5 |
| atmosphere | `set_container_mem_quota_mem_4k` | 5 |
| atmosphere | `set_io_mapping` | 5 |
| atmosphere | `thread_set_blocking_endpoint_endpoint_ref_scheduler_ref_state_and_ipc_payload` | 5 |
| atmosphere | `alloc_page_table` | 4 |
| atmosphere | `container_set_owned_threads` | 4 |
| atmosphere | `push` | 4 |
| ironkv | `clone_end_point` | 4 |
| ironkv | `send_single_cmessage` | 4 |
| atmosphere | `block_running_thread_and_change_queue_state_and_set_trap_frame` | 3 |
| atmosphere | `block_running_thread_and_set_trap_frame` | 3 |
| atmosphere | `container_set_quota_mem_4k` | 3 |
| atmosphere | `init` | 3 |
| atmosphere | `new` | 3 |
| atmosphere | `pass_endpoint` | 3 |
| atmosphere | `scheduler_push_thread` | 3 |
| atmosphere | `thread_set_endpoint_descriptor` | 3 |
| atmosphere | `add_mapping_4k` | 2 |
| atmosphere | `alloc_iommu_table` | 2 |
| atmosphere | `create_entry` | 2 |
| atmosphere | `create_entry_and_share` | 2 |
| atmosphere | `endpoint_add_ref` | 2 |
| atmosphere | `endpoint_push` | 2 |
| atmosphere | `endpoint_push_and_set_state` | 2 |
| atmosphere | `free_page_table` | 2 |
| atmosphere | `init2zero` | 2 |
| atmosphere | `kernel_drop_endpoint` | 2 |
| atmosphere | `kernel_kill_thread` | 2 |
| atmosphere | `new_thread` | 2 |
| atmosphere | `page_entry2usize` | 2 |
| atmosphere | `pagetable_map_4k_page` | 2 |
| atmosphere | `pop_unique` | 2 |
| atmosphere | `proc_remove_thread` | 2 |
| atmosphere | `resolve_iommu_table_mapping` | 2 |
| atmosphere | `set_rev_pointer` | 2 |
| atmosphere | `set_value` | 2 |
| atmosphere | `share_mapping` | 2 |
| atmosphere | `thread_set_trap_frame_fast` | 2 |
| atmosphere | `thread_to_page` | 2 |
| ironkv | `cack_state_swap` | 2 |
| ironkv | `erase` | 2 |
| ironkv | `maybe_ack_packet_impl` | 2 |
| ironkv | `put` | 2 |
| ironkv | `receive_ack_impl` | 2 |
| ironkv | `receive_impl` | 2 |
| ironkv | `remove` | 2 |
| ironkv | `retransmit_un_acked_packets` | 2 |
| ironkv | `retransmit_un_acked_packets_for_dst` | 2 |
| ironkv | `vec_erase` | 2 |
| memory-allocator | `create_full` | 2 |
| atmosphere | `add_io_mapping_4k` | 1 |
| atmosphere | `alloc_and_map` | 1 |
| atmosphere | `alloc_and_map_2m` | 1 |
| atmosphere | `alloc_and_map_io` | 1 |
| atmosphere | `alloc_page_2m` | 1 |
| atmosphere | `container_insert_cpu` | 1 |
| atmosphere | `container_perms_update_subtree_set` | 1 |
| atmosphere | `container_pop_endpoint` | 1 |
| atmosphere | `container_push_child` | 1 |
| atmosphere | `container_push_endpoint` | 1 |
| atmosphere | `container_push_proc` | 1 |
| atmosphere | `container_remove_cpu` | 1 |
| atmosphere | `container_remove_proc` | 1 |
| atmosphere | `container_set_quota` | 1 |
| atmosphere | `create_entry_and_alloc_and_map` | 1 |
| atmosphere | `create_entry_and_alloc_and_map_io` | 1 |
| atmosphere | `create_iommu_table_entry` | 1 |
| atmosphere | `endpoint_pop_head` | 1 |
| atmosphere | `endpoint_remove_ref` | 1 |
| atmosphere | `endpoint_to_page` | 1 |
| atmosphere | `helper_kernel_kill_proc_non_root` | 1 |
| atmosphere | `helper_kernel_kill_proc_root` | 1 |
| atmosphere | `init2none` | 1 |
| atmosphere | `iommu_table_map_4k_page` | 1 |
| atmosphere | `kernel_proc_kill_all_threads` | 1 |
| atmosphere | `map_2m_page` | 1 |
| atmosphere | `map_4k_page` | 1 |
| atmosphere | `merge_4k_pages_to_2m_page` | 1 |
| atmosphere | `merged_4k_to_2m` | 1 |
| atmosphere | `new_endpoint` | 1 |
| atmosphere | `page_to_container_tree_version_1` | 1 |
| atmosphere | `page_to_endpoint_with_thread_and_container` | 1 |
| atmosphere | `page_to_proc_with_first_thread` | 1 |
| atmosphere | `proc_perms_remove_subtree_set` | 1 |
| atmosphere | `proc_push_thread` | 1 |
| atmosphere | `proc_remove_child` | 1 |
| atmosphere | `proc_to_page` | 1 |
| atmosphere | `remove` | 1 |
| atmosphere | `remove_helper1` | 1 |
| atmosphere | `remove_helper2` | 1 |
| atmosphere | `remove_helper3` | 1 |
| atmosphere | `remove_helper4` | 1 |
| atmosphere | `remove_helper5` | 1 |
| atmosphere | `remove_helper6` | 1 |
| atmosphere | `remove_helper7` | 1 |
| atmosphere | `remove_io_mapping_4k_helper1` | 1 |
| atmosphere | `remove_l2_entry` | 1 |
| atmosphere | `remove_l3_entry` | 1 |
| atmosphere | `remove_mapping_4k_helper1` | 1 |
| atmosphere | `remove_mapping_4k_helper2` | 1 |
| atmosphere | `remove_mapping_4k_helper3` | 1 |
| atmosphere | `run_blocked_thread` | 1 |
| atmosphere | `schedule_idle_cpu` | 1 |
| atmosphere | `schedule_running_thread` | 1 |
| atmosphere | `scheduler_remove_thread` | 1 |
| atmosphere | `syscall_mmap` | 1 |
| atmosphere | `syscall_new_container_with_endpoint` | 1 |
| atmosphere | `syscall_new_proc_with_endpoint` | 1 |
| atmosphere | `syscall_new_thread` | 1 |
| atmosphere | `syscall_new_thread_with_endpoint` | 1 |
| atmosphere | `syscall_receive_endpoint` | 1 |
| atmosphere | `syscall_receive_pages` | 1 |
| atmosphere | `syscall_send_empty_block` | 1 |
| atmosphere | `syscall_send_empty_no_block` | 1 |
| atmosphere | `syscall_send_empty_try_schedule` | 1 |
| atmosphere | `syscall_send_endpoint` | 1 |
| atmosphere | `syscall_send_pages` | 1 |
| ironkv | `clone_option_vec_u8` | 1 |
| ironkv | `clone_optional_value` | 1 |
| ironkv | `clone_vec_u8` | 1 |
| ironkv | `empty` | 1 |
| ironkv | `extract_range_impl` | 1 |
| ironkv | `get_internal` | 1 |
| ironkv | `get_my_end_point` | 1 |
| ironkv | `parse_end_point` | 1 |
| ironkv | `parse_end_points` | 1 |
| ironkv | `receive_real_packet_impl` | 1 |
| ironkv | `sht_demarshall_data_method` | 1 |
| memory-allocator | `clear` | 1 |
| memory-allocator | `create` | 1 |
| memory-allocator | `create_empty` | 1 |
| memory-allocator | `create_intersect` | 1 |
| memory-allocator | `empty` | 1 |
| memory-allocator | `next_run` | 1 |
| memory-allocator | `set` | 1 |
| nrkernel | `x86_arch_exec` | 1 |
| vest | `set_range` | 1 |