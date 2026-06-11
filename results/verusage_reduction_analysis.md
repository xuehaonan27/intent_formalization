# VeruSAGE exec-fn reduction analysis

This note records how the source-level exec-fn count relates to the public-fn determinism checking result.

## Count funnel

| Stage | Count | Meaning |
|---|---:|---|
| Source scan, dedup by `(project, fn)` | 861 | Comments/strings skipped; `spec fn` and `proof fn` excluded; only exec fns with `ensures`; deduped by project/function name over selected source-repo paths. |
| Source scan, dedup by `(project, type_base, fn)` | 1027 | Same source scan, but using the later pipeline key. This is finer because methods with the same name on different receiver types split. |
| `pub_fn_eval_per_case_2026-06-05.json` raw unique entries | 370 | Pipeline-level entries from VeruSAGE standalone tasks, deduped by `(project, function_name, type_base)`. |
| Private entries excluded | 41 | Raw eval rows with `pub=priv`; excluded from public-API determinism. |
| Public eval entries | 329 | Raw eval rows with `pub=pub`, documented as the 2026-06-05 public-fn evaluation set. |
| Weekly 2026-06-02/06-09 status total | 346 | Progress-table status aggregate for the public-fn determinism line; not the exact same raw file/version as the 329-row 2026-06-05 eval. |

## Source-level reduction reasons

`results/verusage_fn_reduction_by_name.csv` has one row per `(project, fn)` from the 861-style source scan.

| Reduction status | Count | Meaning |
|---|---:|---|
| `included_in_pub_eval_raw` | 307 | Matched a raw public-fn evaluation row. |
| `not_in_pub_fn_eval_raw; not selected/extracted as determinism target from VeruSAGE standalone tasks` | 461 | Exists in the source repo scan, but did not become a public-fn determinism target in the raw eval. |
| `project_not_in_public_determinism_run` | 61 | Project/scope was not included in that public-fn determinism run. |
| `raw_eval_private_not_public_api` | 31 | Found by raw eval, but classified as private, so excluded from public API determinism. |
| `type_context_mismatch_or_duplicate_name; raw has same project/function but different type_base` | 2 | Same project/function name appeared, but the receiver/type context did not match the raw eval key. |

## Per-project coverage table

Saved as:

- `results/verusage_exec_fn_coverage_summary.csv`

`checked_in_verified_reported_total` is the 346-row determinism status table from the 2026-06-02/06-09 progress notes. `matched_to_pub_eval_raw` is the subset that can be matched back to the local source scan through the 2026-06-05 raw public-fn eval file; it is useful for explaining the source-scan partition but is not the same versioned aggregate as the 346-row progress table.

| Project | Exec fn with postcondition | Checked in verified (reported) | Matched to raw eval | Found in `unverified/` | Mentioned only in `unverified/` | Verified-only unmeasured | Not matched | Incomplete |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ironkv | 112 | 80 | 58 | 34 | 1 | 0 | 19 | 9 |
| atmosphere | 297 | 222 | 218 | 12 | 4 | 0 | 63 | 16 |
| memory-allocator | 178 | 15 | 15 | 0 | 1 | 0 | 162 | 1 |
| nrkernel | 70 | 8 | 2 | 45 | 1 | 0 | 22 | 1 |
| anvil-library | 19 | 1 | 0 | 3 | 2 | 3 | 11 | 1 |
| anvil-controller | 28 |  | 0 | 13 | 3 | 0 | 12 |  |
| node-replication | 33 |  | 0 | 0 | 2 | 0 | 31 |  |
| storage | 93 | 18 | 12 | 31 | 1 | 0 | 49 | 9 |
| vest | 32 | 2 | 2 | 1 | 2 | 1 | 26 | 0 |
| **SUMMARY** | **862** | **346** | **307** | **139** | **17** | **4** | **395** | **37** |

## Are `not selected/extracted` functions from `source-projects/*/unverified`?

Mostly no. The `unverified/` directories in VeruSAGE are benchmark input files: they are the same extracted tasks as `verified/`, but with the target body removed. They are not the same thing as "unverified original source code." The source scan started from the original source repositories, so many functions it found never appear as VeruSAGE tasks at all.

Content-based cross-check of `not_in_pub_fn_eval_raw` functions against `verusage/source-projects/<project>/{unverified,verified}` is saved in:

- `results/verusage_not_selected_unverified_check.csv`

The check no longer uses task filenames. It scans file contents and classifies each function name by whether it appears as a `fn <name>` definition/signature in `unverified/`, appears only as a textual mention in `unverified/`, appears only in `verified/`, or has no benchmark-task content match.

Summary:

| Project | Not selected | Defined in `unverified/` | Mentioned only in `unverified/` | Mentioned/defined only in `verified/` | Not matched |
|---|---:|---:|---:|---:|---:|
| anvil-library | 18 | 2 | 2 | 3 | 11 |
| ironkv | 32 | 12 | 1 | 0 | 19 |
| memory-allocator | 163 | 0 | 1 | 0 | 162 |
| nrkernel | 68 | 45 | 1 | 0 | 22 |
| atmosphere | 75 | 8 | 4 | 0 | 63 |
| storage | 75 | 25 | 1 | 0 | 49 |
| vest | 30 | 1 | 2 | 1 | 26 |

Overall, out of 461 `not selected/extracted` functions, 93 are defined in `unverified/` task files, 12 are only textually mentioned in `unverified/`, 4 are only mentioned/defined in `verified/`, and 352 have no task-content match.

For Memory Allocator specifically, none of the 163 `not selected/extracted` source functions are defined in `verusage/source-projects/memory-allocator/unverified/`. One name (`new`) is textually mentioned in unverified task files; the other 162 have no task-content match. Examples include allocator/runtime helpers from `verus-mimalloc/types.rs`, `linked_list.rs`, `arena.rs`, `page.rs`, `free.rs`, and `flags.rs`.

So the answer for the Memory Allocator example is: these excluded functions are not the target functions under `source-projects/memory-allocator/unverified/`; they are mostly original source-repo functions that VeruSAGE did not extract into the benchmark/public determinism target set.

Per-project examples:

| Project | Defined in `unverified/` examples | Mentioned only in `unverified/` examples | Source-repo-only examples |
|---|---|---|---|
| anvil-library | `new`, `verus_clone` | `insert`, `len` | `bool_to_string`, `clone`, `dash_free_exec`, `extend`, `get`, `get_uncloned`, `i32_to_string`, `keys` |
| ironkv | `_is_marshalable`, `cmp`, `deserialize`, `is_lt`, `lemma_from_vec`, `lemma_to_vec`, `lemma_to_vec_view`, `lt` | `filter` | `clone_arg`, `clone_option_end_point`, `clone_value`, `contains_exec`, `get_time`, `greatest_lower_bound`, `init_impl`, `is_ge` |
| memory-allocator | — | `new` | `add_offset`, `add_offset_and_check`, `append`, `arena_alloc_aligned`, `bin`, `block_write_ptr`, `bound_on_1_lists`, `bound_on_2_lists` |
| nrkernel | `ack_shootdown`, `acquire_lock`, `allocate`, `axiom_max_phyaddr_width_facts`, `barrier`, `deallocate`, `do_concurrent_trs`, `entry_base` | `is_page` | `aligned_exec`, `change_page_permissions`, `entry_at`, `entry_at_protect`, `entry_at_unmap`, `finish_protect_and_release_lock`, `handle_shootdown_ipi`, `insert_empty_directory` |
| atmosphere | `capacity`, `get_cr3_by_pcid`, `remove_l4_entry`, `resolve`, `syscall_new_proc_with_endpoint_iommu`, `syscall_receive_empty_block`, `syscall_receive_empty_no_block`, `transfer_idle_cpu` | `empty`, `insert`, `is_none`, `is_some` | `adopt_dom0`, `container_perms_subset_remove`, `container_remove_child`, `container_set_root_proc`, `container_to_page`, `endpoint_remove_thread`, `endpoint_set_owning_container`, `flush_tlb_4kentry` |
| storage | `advance_head`, `as_slice`, `commit`, `compare_crcs`, `flush`, `get_pm_region_ref`, `new_with_condition`, `padding_needed` | `append` | `alloc_list_node_and_append`, `alloc_list_node_update_item_and_append`, `append_to_list`, `append_to_list_and_update_item`, `bytes_crc`, `check_for_required_space`, `compute_log_capacities`, `copy_from_slice` |
| vest | `init_vec_u8` | `len`, `new` | `and_then`, `apply`, `as_byte_slice`, `as_u32`, `as_usize`, `btc_varint_inner`, `clone`, `compare` |
