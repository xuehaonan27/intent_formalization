# Verus-error Classification — Smoke Run 2026-05-13

Cross-project smoke after the view-registry rerun (4eb7376). Inputs:
`/tmp/{atmosphere,storage,anvil-library,nrkernel,vest}-after/full_run.json`.

| project | n | ok_without_witness | ok_with_witness (A-2) | verus_error (A-1) | crash |
|---|---:|---:|---:|---:|---:|
| atmosphere | 1363 | 984 | 257 | 120 | 2 |
| storage | 43 | 0 | 0 | 43 | 0 |
| anvil-library | 1 | 0 | 0 | 1 | 0 |
| nrkernel | 8 | 6 | 0 | 2 | 0 |
| vest | 2 | 2 | 0 | 0 | 0 |
| **total** | **1417** | **992** | **257** | **166** | **2** |

`stderr_tail` of all 166 `verus_error` records bucketed below.

## Summary table

| ID | Bucket | Count | Nature | Root cause (short) | Fix path |
|---|---|---:|---|---|---|
| **A1** | parse_err `?:` (anon param) | **42** (38+4) | witness generation bug | Param pattern `Tracked(x): Tracked<T>` rendered as `?: Tracked<T>` — ident fallback missing | Template ident fallback in spec-fn param printer |
| **A2** | parse_err missing `*` | **11** | witness generation bug | `4 * va_range.len` → `4 va_range.len` — `BinOp::Mul` printer drops operator when both sides are atoms | AST printer fix for `BinOp::Mul` |
| **A3** | type_err `&T` vs `T` | **23** | witness generation bug | Callee param is `&PageEntry`, our call-site emits `p` (owned) — `&` ref-modifier dropped | Preserve callee ref-modifier in codegen call-site |
| **A4** | trait_err: `View` not impl | **20** | witness generation bug (PR-B side effect) | PR-B emits `field@` on fields whose type has no `View` impl (`StaticLinkedList<usize,10>`, `ArraySet<32>`) | Gate `@` emission on view-registry membership of the **field** type, not just outer struct |
| **A5** | SMT rlimit exceeded | **7** | too much conditions in an assumption | Injected context too large (e.g. 325 params / 181 sub-fields) | split into multi-assmuption statements |

| **A5** | mismatched-types buried in deprecation warnings | **16** | tail truncation | Not a separate class — these are A3/A4 cases hidden by 31 lines of `is_Some` deprecation warnings filling the 4 KB tail buffer | Bump `stderr_tail` cap to 16 KB and re-bucket |

| **S1** | storage `deps_hack` chain | **36** (18 E0432 + 10 parse + 8 E0433) | environment | smoke runner Cargo workspace has no `deps_hack` proc-macro crate; downstream macros (`pmsized_primitive!`) fail to expand | Add `deps_hack = { path = ".../storage/deps_hack" }` to runner workspace |
| **S2** | storage misc (`Self` etc.) | **7** | environment / corpus | Tail of the `deps_hack` chain (`E0411 cannot find Self`, etc.) | Same fix as S1 will likely clear most |
| **N1** | `repr(transparent)` + `Ghost<nat>` | **2** | toolchain drift | nightly rustc promoted [rust#78586](https://github.com/rust-lang/rust/issues/78586) from warning → error; `Ghost<nat>` has private fields | Pin nightly to a pre-promotion date or drop `repr(transparent)` from affected structs |
| **V1** | vstd lemma rename | **1** | corpus drift | `lemma_seq_properties` → `group_seq_properties` (broadcast group convention) | One-line `s/lemma_/group_/` in corpus prefill |

## Rolled up by responsibility

| Owner | Buckets | Cases | Share |
|---|---|---:|---:|
| **spec-determinism codegen** | A1 + A2 + A3 + A4 + A5 | **112** | **67 %** |
| **smoke runner env** | S1 + S2 | **43** | **26 %** |
| **real SMT failure** | A6 | **7** | **4 %** |
| **Rust / vstd drift** | N1 + V1 | **3** | **2 %** |

## Highest-ROI fixes (single PR each)

| Rank | Fix | Wins | Net atmosphere A-1 after |
|---:|---|---:|---:|
| 1 | A1 param-pattern fallback | 42 | 120 → 78 |
| 2 | A4 PR-B gating on field-type view membership | 28 (20 + ≈8 from A5 reshuffle) | 78 → 50 |
| 3 | A3 callee `&` ref-modifier | 31 (23 + ≈8 from A5 reshuffle) | 50 → 19 |
| 4 | A2 `BinOp::Mul` printer | 11 | 19 → 8 |
| 5 | S1 link `deps_hack` in runner | 36 (storage) | storage 43 → 4 |
| 6 | A6 schema pruning | 7 | residual |

Three codegen PRs (A1 + A3 + A4) clear **~100 atmosphere verus_errors** — slide-13 baseline of 100 A-1 becomes ~20.

## Per-bucket exemplar

### A1 — anon param `?:`
- Artifact: `atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__free_page_4k__free_page_4k`
- Spec source:
  ```rust
  pub fn free_page_4k(&mut self, target_ptr: PagePtr,
                      Tracked(target_perm): Tracked<PagePerm4k>)
  ```
- Injected:
  ```rust
  proof fn det_free_page_4k(g_neq_tuple: bool, pre_self_: PageAllocator,
      target_ptr: PagePtr, ?: Tracked<PagePerm4k>, post1_self_: PageAllocator, ...)
                          ^^
  ```

### A2 — missing `*`
- Artifact: `atmosphere__verified__kernel__kernel__create_and_map_pages__impl0__range_alloc_and_map__range_alloc_and_map`
- Spec source (line 2234): `).mem_4k >= 4 * va_range.len,`
- Injected (line 2832): `).mem_4k >= 4 va_range.len),`

### A3 — `&T` vs `T`
- Artifact: `atmosphere__verified__kernel__kernel__create_and_map_pages__impl0__check_address_space_va_range_free__page_entry_to_map_entry`
- Spec source: `pub open spec fn spec_page_entry_to_map_entry(p: &PageEntry) -> MapEntry`
- Injected: `(r2 =~= spec_page_entry_to_map_entry(p))` → expected `&PageEntry`, found `PageEntry`

### A4 — overreaching `@`
- Artifact: `atmosphere__verified__process_manager__process_manager__impl_base__impl0__new_endpoint__container_push_endpoint`
- Injected: `scheduler: self.scheduler@,` where `scheduler: StaticLinkedList<usize, 10>` has no `View` impl

### A5 — truncated tail
- Artifact: `atmosphere__verified__kernel__kernel__syscall_new_container__impl0__syscall_new_container_with_endpoint__new_container_with_endpoint`
- Tail shows 31 `is_Some` deprecation warnings + `aborting due to 1 previous error` — the real error is truncated

### A6 — rlimit
- Artifact: `atmosphere__verified__pagetable__pagetable__pagetable_impl_base__impl0__create_entry_l4__usize2page_entry_perm`
- `n_params=325, n_schemas=181` — SMT context too large for default rlimit

### S1 — `deps_hack`
- Artifact: `storage__verified__log_inv__inv_L_active_metadata_set_after_crash__size_of`
- `use deps_hack::{PmSized, pmsized_primitive};` → `E0432: unresolved import deps_hack`

### N1 — `repr(transparent)` × `Ghost<nat>`
- Artifact: `nrkernel__verified__impl_u__l2_impl__impl_u__l2_impl__impl0__address__address`
- `#[repr(transparent)] pub layer: Ghost<nat>` rejected post-rust#78586 promotion

### V1 — vstd lemma rename
- Artifact: `anvil-library__verified__vstd_exd__vec_lib__vec_lib__vec_filter`
- `lemma_seq_properties::<V>()` → vstd renamed to `group_seq_properties`
