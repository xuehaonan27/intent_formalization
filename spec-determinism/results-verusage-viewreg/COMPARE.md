# Corpus rerun comparison

| | commit |
|---|---|
| baseline  | `a343a56` |
| candidate | `4cd29b4` |

Definitions:
- **ok_with_witness** — Verus accepted the equal-fn but z3 emitted
  a counterexample (`status=="ok" AND assumes!=[]`). The A-2
  false-positive metric.
- **fixed** — was ok_with_witness in baseline, now plain ok in
  candidate. **Wins go here.**
- **witness → verus_error** — was ok_with_witness, now Verus
  rejects the equal-fn. View compiled but blocked verification;
  not a clean win.
- **regressed** — was clean ok (no witness) in baseline, now
  verus_error in candidate. **This number must be ~0**
  to consider the change safe to land.

## Per-project totals

| project | n | ok | verus_err | ok_with_witness (base → cand) | Δ witness |
|---|---:|---:|---:|---|---:|
| anvil-controller | 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 |
| anvil-library | 1 | 0 → 0 | 1 → 1 | 0 → 0 | 0 |
| atmosphere | 1363 | 1262 → 1242 | 100 → 119 | 289 → 258 | **-31** |
| ironkv | 214 | 170 → 171 | 44 → 43 | 76 → 76 | 0 |
| memory-allocator | 16 | 15 → 15 | 1 → 1 | 9 → 1 | **-8** |
| node-replication | 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 |
| nrkernel | 8 | 6 → 6 | 2 → 2 | 1 → 0 | **-1** |
| storage | 43 | 0 → 0 | 43 → 43 | 0 → 0 | 0 |
| vest | 2 | 2 → 2 | 0 → 0 | 1 → 1 | 0 |
| **TOTAL** | **1647** | **1455 → 1436** | **191 → 209** | **376 → 336** | **-40** |

## Per-project A-2 transitions


### atmosphere

**fixed** (11 targets — witness → ok):
- `atmosphere__verified__pagetable__pagetable__pagemap__impl0__set__set`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__block_running_thread__thread_set_blocking_endpoint_endpoint_ref_scheduler_ref_state_and_ipc_payload`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__block_running_thread_and_change_queue_state__thread_set_blocking_endpoint_endpoint_ref_scheduler_ref_state_and_ipc_payload`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__block_running_thread_and_change_queue_state_and_set_trap_frame__thread_set_blocking_endpoint_endpoint_ref_scheduler_ref_state_and_ipc_payload`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__block_running_thread_and_change_queue_state_and_set_trap_frame__thread_set_trap_frame_fast`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__block_running_thread_and_set_trap_frame__thread_set_blocking_endpoint_endpoint_ref_scheduler_ref_state_and_ipc_payload`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__block_running_thread_and_set_trap_frame__thread_set_trap_frame_fast`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__pass_endpoint__endpoint_add_ref`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__schedule_blocked_thread__thread_set_blocking_endpoint_endpoint_ref_scheduler_ref_state_and_ipc_payload`
- `atmosphere__verified__process_manager__process_manager__impl_drop_enpoints__impl0__drop_endpoint__endpoint_remove_ref`
- `atmosphere__verified__process_manager__process_manager__impl_new_container__impl0__new_container_with_endpoint__endpoint_add_ref`

**witness → verus_error** (19 targets — view compiled but blocked verification):
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__new_endpoint__container_push_endpoint`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__new_endpoint__container_set_quota_mem_4k`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__schedule_blocked_thread__scheduler_push_thread`
- `atmosphere__verified__process_manager__process_manager__impl_base__impl0__set_container_mem_quota_mem_4k__container_set_quota_mem_4k`
- `atmosphere__verified__process_manager__process_manager__impl_drop_enpoints__impl0__drop_endpoint__container_pop_endpoint`
- `atmosphere__verified__process_manager__process_manager__impl_kill_container__impl0__transfer_idle_cpu__container_insert_cpu`
- `atmosphere__verified__process_manager__process_manager__impl_kill_container__impl0__transfer_idle_cpu__container_remove_cpu`
- `atmosphere__verified__process_manager__process_manager__impl_kill_proc__impl0__kill_process_none_root__container_remove_proc`
- `atmosphere__verified__process_manager__process_manager__impl_kill_thread__impl0__kill_running_thread__container_set_owned_threads`
- `atmosphere__verified__process_manager__process_manager__impl_kill_thread__impl0__kill_scheduled_thread__container_set_owned_threads`
- `atmosphere__verified__process_manager__process_manager__impl_kill_thread__impl0__kill_scheduled_thread__scheduler_remove_thread`
- `atmosphere__verified__process_manager__process_manager__impl_new_container__impl0__new_container_with_endpoint__container_push_child`
- `atmosphere__verified__process_manager__process_manager__impl_new_container__impl0__new_container_with_endpoint__container_push_proc`
- `atmosphere__verified__process_manager__process_manager__impl_new_container__impl0__new_container_with_endpoint__container_set_owned_threads`
- `atmosphere__verified__process_manager__process_manager__impl_new_container__impl0__new_container_with_endpoint__container_set_quota`
- `atmosphere__verified__process_manager__process_manager__impl_new_container__impl0__new_container_with_endpoint__scheduler_push_thread`
- `atmosphere__verified__process_manager__process_manager__impl_new_thread__impl0__new_thread__container_set_owned_threads`
- `atmosphere__verified__process_manager__process_manager__impl_new_thread__impl0__new_thread__container_set_quota_mem_4k`
- `atmosphere__verified__process_manager__process_manager__impl_new_thread__impl0__new_thread__scheduler_push_thread`

### ironkv

**fixed** (1 targets — witness → ok):
- `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__parse_command_line_configuration`

### memory-allocator

**fixed** (8 targets — witness → ok):
- `memory-allocator__verified__commit_mask__commit_mask__impl__clear__clear`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create__create`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create__create_full`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create_empty__create_empty`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create_full__create_full`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create_intersect__create_intersect`
- `memory-allocator__verified__commit_mask__commit_mask__impl__empty__empty`
- `memory-allocator__verified__commit_mask__commit_mask__impl__set__set`

### nrkernel

**fixed** (1 targets — witness → ok):
- `nrkernel__verified__spec_t_mmu__defs__spec_t__mmu__defs__x86_arch_exec__x86_arch_exec`
