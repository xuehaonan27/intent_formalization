# Incompleteness Summary (post-audit)

> **Status (2026-05-26)** — consolidated view of every spec-incompleteness case found in the verusage corpus rerun11 pipeline, after manual audit of all 45 entries the classifier flagged as `incomplete`. Underlying data sources: `corpus_rerun11_results.md`, `atmosphere_incomplete_audit.md`, `ironkv-spec-incompleteness-cases-2026-05-20.en.md`, and today's three follow-up audits (`erase`, `host_model_next_delegate`, `process_received_packet_next_impl`).

---

## 1. Per-repo statistics

`classify_ok` buckets from the rerun11 baseline+LLM pipeline (counts are det-check entries, not fn templates):

| project          | total | complete | +LLM | incomplete | inconclusive | crash | verus_err |
|------------------|------:|---------:|-----:|-----------:|-------------:|------:|----------:|
| ironkv           |   214 |      157 |    2 |         16 |           39 |     0 |         0 |
| atmosphere       |  1361 |     1082 |   23 |         29 |          162 |    65 |         0 |
| memory-allocator |    16 |       15 |    0 |          0 |            1 |     0 |         0 |
| nrkernel         |     8 |        7 |    0 |          0 |            1 |     0 |         0 |
| anvil-library    |     1 |        0 |    0 |          0 |            1 |     0 |         0 |
| storage          |    43 |       21 |    0 |          4 |           11 |     0 |         7 |
| vest             |     2 |        2 |    0 |          0 |            0 |     0 |         0 |
| **TOTAL**        | **1645** | **1284** | **25** |  **49** | **215** |  **65** |    **7** |

> **2026-05-26 update (atmosphere)** — atmosphere baseline `verus_err` cleared from 49 → 0 by three fixes
> committed today (extractor: preserve `&mut` on `Tracked(p): Tracked<&mut T>` destructures
> + skip fns inside `/* ... */` block comments; gen_det: auto-`&`-prefix method-call args
> for renamed `&mut`-param idents). 47 of the 49 previously-failing entries now compile cleanly
> (23 promoted to `complete`, 24 to `inconclusive`); 2 are dropped from the total
> (they were extracted from block-commented source). See
> `corpus_rerun11_results.md §"Update 2026-05-26"` for the full bucket-by-bucket breakdown.
>
> **2026-05-26 update (storage)** — storage baseline `verus_err` cleared from 43 → 7 by four
> pipeline patches in working tree (single_file: `_find_verus_block_close` brace-aware
> injection + `_rewrite_deps_hack` shim + multi-line View-header cleanup; gen_det:
> `sig_for_prune` extended with ensures/requires; classify: blanket-impl `closed spec fn`
> reveal-target suppression). 36 newly-compiling cases break down as 21 `complete` /
> 4 `incomplete` permitted / 11 `inconclusive`. The 7 residual `verus_err` are inherent
> source / vstd-version incompatibilities (4× `Box<S>: SpecEq<S>`, 3× `iter.end` on
> `VerusForLoopWrapper`). See `corpus_rerun11_results.md §"Update 2026-05-26 — storage"`.
>
> **2026-05-26 update (nrkernel)** — nrkernel baseline `verus_err` cleared from 2 → 0 by
> a one-line crate-level allow: `#![allow(repr_transparent_non_zst_fields)]` is auto-inserted
> when the source contains `#[repr(transparent)]`. Newer rustc hard-errors on
> `repr(transparent)` structs containing Verus's `Ghost<T>` (ZST field of an external type
> with private fields); both nrkernel cases hit this on `pub struct PDE { entry: usize,
> layer: Ghost<nat> }`. The allow silences the lint without altering layout. Both cases
> now compile + verify (1 promoted to `complete`, 1 to `inconclusive`).

Legend:
- `complete` / `+LLM` — baseline z3 (resp. LLM-authored proof) proved R0=unsat
- `incomplete` — `permitted=True` and `r0_z3 ∈ {sat, unknown}`: classifier promoted via `permissive_or` / `spec_underconstrained_manual` detectors
- `inconclusive` — `r0_z3=unknown` without `permitted` flag (z3 surrendered, no detector pardon)
- `crash` — 300 s subprocess wall (atmosphere only — schema-search runaway)
- `verus_err` — baseline Verus compile failure (infra, not determinism); see corpus_rerun11 §"verus_error"

### Post-audit refinement of the `incomplete` column

Manual triage classifies each of the 45 incompletes as either Real (genuine spec admits multiple post-states) or FP (structural false positive of the detector — spec is actually deterministic). Only ironkv and atmosphere have any incompletes; the other 5 repos contribute 0.

| project    | incomplete entries | Real | FP | Real fn templates | FP fn templates |
|------------|-------------------:|-----:|---:|-------------------:|----------------:|
| atmosphere |                 29 |   29 |  0 |                 14 |               0 |
| ironkv     |                 16 |   15 |  1 |                  8 |               1 |
| **TOTAL**  |              **45** | **44** | **1** |          **22** |           **1** |

→ Detector precision on rerun11 (Real / (Real+FP)): **44 / 45 = 97.8 %** by entry; **22 / 23 = 95.7 %** by fn template.

### Atmosphere — detector vs. semantic reason

All 29 atmosphere entries carry `permitted_reason=permissive_or`, structurally traced to the `|||` inside `page_is_mapped`'s body. That `|||` is a bool-returning disjunction, **not** a top-level post-state choice — so the *detector reason* is a FP. Manual audit nevertheless confirms all 29 entries are **semantically real** incompletes, with the genuine non-determinism coming from two unrelated sources:

| sub-pattern | description | entries | fn templates |
|-------------|-------------|--------:|-------------:|
| Pattern A (alloc choice) | ret pointer constrained only to `free_pages_*().contains(ret)` — multiple legal choices when free set has >1 elem | 16 | 6 |
| Pattern B (Seq ordering) | `=~=` Set-level ensures, but underlying field is `Vec`/`Seq` whose Seq view is unconstrained (insertion position, permutations) | 13 | 8 |

The "right answer for the wrong reason" problem is a paper-claim hygiene issue, not a correctness one. Suggested taxonomy refinement: replace the single `permissive_or` reason with three more precise reasons (`permissive_or_top_level`, `alloc_choice_underconstrained`, `seq_ordering_underconstrained`) — full discussion in `corpus_rerun11_results.md`.

### ironkv — top-level `|||` and manual REAL_SAT allowlist

| permitted_reason | entries | fn templates | sub-meaning |
|------------------|--------:|-------------:|-------------|
| `spec_underconstrained_manual` (REAL_SAT allowlist) | 9 | 5 | curated cases where ensures genuinely leaves part of post-state free (e.g. `ret.1` when `!ret.0`, `InvalidMessage` branch, Seq vs Set image) |
| `permissive_or` — real top-level `\|\|\|` | 6 | 3 | `||| normal_path ||| ignore_unparseable` shape in host-step ensures; no guard distinguishing the branches |
| `permissive_or` — structural FP | 1 | 1 | `<==>` RHS internal `|||` in `erase`'s `gap` predicate — spec actually deterministic on `m@` |

The 1 FP (`erase`) is the only "detector wrong" case in the entire corpus rerun.

---

## 2. Consolidated case table

One row per fn template (23 rows total). Entry counts agree with §1 totals (29 + 16 = 45).

| # | Repo | Function | Entries | Verdict | Detector reason | Real source / FP cause |
|---|------|----------|--------:|---------|-----------------|------------------------|
| 1 | atmosphere | `alloc_page_4k` | 8 | Real | `permissive_or` (FP via `page_is_mapped`) | **A**: `ret.0 ∈ free_pages_4k`, multiple choices |
| 2 | atmosphere | `alloc_page_4k_for_new_container` | 2 | Real | `permissive_or` (FP via `page_is_mapped`) | **A**: same |
| 3 | atmosphere | `alloc_page_2m` | 1 | Real | `permissive_or` (FP via `page_is_mapped`) | **A**: `Tracked<PagePerm2m>` linearity ⇒ ret ∈ free_perm pool, multiple choices |
| 4 | atmosphere | `alloc_and_map_4k` | 2 | Real | `permissive_or` (FP via `page_is_mapped`) | **A**: ret ∈ old.free_pages_4k by len-1 + `!page_is_mapped(ret)` + `!allocated(ret)` |
| 5 | atmosphere | `alloc_and_map_io_4k` | 2 | Real | `permissive_or` (FP via `page_is_mapped`) | **A**: same |
| 6 | atmosphere | `alloc_and_map_2m` | 1 | Real (**A0 spec bug**) | `permissive_or` (FP via `page_is_mapped`) | **A**: no `contains(ret)`, no `len()-1`, no `Tracked<PagePerm2m>` — admits "overwrite already-Mapped2m page" |
| 7 | atmosphere | `free_page_4k` | 5 | Real | `permissive_or` (FP via `page_is_mapped`) | **B**: `free_pages_4k() =~= old.insert(target)` pins Set view; underlying `StaticLinkedList<PagePtr>` Seq order free |
| 8 | atmosphere | `add_mapping_4k` | 2 | Real | `permissive_or` (FP via `page_is_mapped`) | **B**: `page_mappings(target_ptr).insert((pcid,va))` pins Set, free pool Seq passive-free |
| 9 | atmosphere | `add_io_mapping_4k` | 1 | Real | `permissive_or` (FP via `page_is_mapped`) | **B**: same shape, `page_io_mappings(target_ptr).insert((ioid,va))` |
| 10 | atmosphere | `merged_4k_to_2m` | 1 | Real (**A0 spec bug**) | `permissive_or` (FP via `page_is_mapped`) | **B**: ensures references **neither** `target_ptr` nor `target_page_idx`, only `len()==` counts — impl can merge any 2m-aligned all-Free4k block |
| 11 | atmosphere | `remove_io_mapping_4k_helper1` | 1 | Real (**A0 spec bug**) | `permissive_or` (FP via `page_is_mapped`) | **B+A0**: omits target_ptr's state assignment + free pool no-anchor — impl can recycle target into Free4k vs Unavailable4k |
| 12 | atmosphere | `remove_mapping_4k_helper1` | 1 | Real (**A0 spec bug**) | `permissive_or` (FP via `page_is_mapped`) | **B+A0**: same as #11 (sibling) |
| 13 | atmosphere | `remove_mapping_4k_helper2` | 1 | Real (**A0 spec bug**) | `permissive_or` (FP via `page_is_mapped`) | **B+A0**: real impl walks Free4k path while spec also admits Unavailable4k (no `is_io_page` field constraint) + free pool no-anchor |
| 14 | atmosphere | `remove_mapping_4k_helper3` | 1 | Real (**A0 spec bug**) | `permissive_or` (FP via `page_is_mapped`) | **B+A0**: target stays Mapped4k (forced by `container_map_4k =~= old`), only free-pool no-anchor A0 dim remains — *cleanest* witness of "Free pool needs an anchor" |
| 15 | ironkv | `retransmit_un_acked_packets` | 2 | Real | `spec_underconstrained_manual` | equal_fn-too-strict candidate: spec pins `.to_set()` image of `Vec<CPacket>`; equal_fn falls back to structural `Vec==` and rejects permutations |
| 16 | ironkv | `retransmit_un_acked_packets_for_dst` | 2 | Real | `spec_underconstrained_manual` | same shape as #15 (sibling) |
| 17 | ironkv | `values_agree` | 2 | Real | `spec_underconstrained_manual` | when `ret.0 == true`, spec leaves `ret.1` entirely unconstrained |
| 18 | ironkv | `keys_in_index_range_agree` | 2 | Real | `spec_underconstrained_manual` | same shape as #17 (sibling) |
| 19 | ironkv | `sht_demarshall_data_method` | 1 | Real | `spec_underconstrained_manual` | spec's `InvalidMessage` branch leaves all return fields unconstrained |
| 20 | ironkv | `host_model_next_receive_message` | 2 | Real | `permissive_or` (top-level) | A-class top-level `\|\|\|`: `\|\|\| normal_receive \|\|\| host_ignoring_unparseable`, no guard distinguishing branches |
| 21 | ironkv | `host_model_next_delegate` | 2 | Real | `permissive_or` (top-level) | A-class same shape as #20: `\|\|\| next_delegate \|\|\| host_ignoring_unparseable` |
| 22 | ironkv | `process_received_packet_next_impl` | 2 | Real | `permissive_or` (top-level) | A-class same shape as #20: `\|\|\| process_received_packet_next \|\|\| ignore_nonsensical_delegation_packet` |
| 23 | ironkv | `erase` (`impl4__set`, `StrictlyOrderedMap`) | 1 | **FP** | `permissive_or` (structural) | The `\|\|\|` lives on the RHS of `<==>` inside the `gap` predicate definition (boolean disjunction defining `gap`, not a post-state choice). Spec uniquely determines `m@` via the per-key ITE ensures clause; equal_fn compares only `view() == m@`. z3 returns unknown because of forall + ITE + `<==>` quantifier wall + closed-spec opacity on `valid()`/`map_valid()`, not because spec admits multiple posts. |

Verdict legend:
- **Real** — spec genuinely admits multiple legal post-states; det-check `incomplete` verdict is semantically correct.
- **Real (A0 spec bug)** — Real, *and* the bug is a meaningful gap in ensures the developer would want to fix (vs. mere symmetric alloc choice that's `det_equal`-foldable).
- **FP** — structural false positive of the detector; spec is mathematically deterministic at the comparison level.

Pattern legend (atmosphere):
- **A** — Pattern A (alloc choice underconstrained): ret value drawn from a non-empty input set without further pinning.
- **B** — Pattern B (Seq ordering underconstrained): ensures use Set view (`=~=`) for fields that have `Vec`/`Seq` underneath.
- **A0** — atmosphere-internal axis labelling a genuine missing-ensures gap (vs. **A1**, the symmetric-choice axis foldable via `det_equal`). 6 of the 14 atmosphere fn templates carry an A0 dim and are flagged for spec patching.

---

## 3. Headline numbers

- **Corpus rerun11 incomplete count**: 45 entries / 23 fn templates / 2 repos (only atmosphere and ironkv produce any).
- **Audited verdict**: 44 Real (22 fn templates) + 1 FP (1 fn template — ironkv `erase`).
- **A0 spec-bugs flagged for fix**:
  - atmosphere: 6 fn templates (`alloc_and_map_2m`, `merged_4k_to_2m`, `remove_io_mapping_4k_helper1`, `remove_mapping_4k_helper1`, `remove_mapping_4k_helper2`, `remove_mapping_4k_helper3`)
  - ironkv: 3 top-level-`|||` A-class fn templates (`host_model_next_receive_message`, `host_model_next_delegate`, `process_received_packet_next_impl`) + 2 REAL_SAT cases with confirmed dev-side fix consensus (`values_agree` + sibling, `sht_demarshall_data_method`); remaining 2 REAL_SAT cases (`retransmit_*`) are equal_fn-too-strict candidates pending developer review.
- **Detector-precision conclusion**: the `permissive_or + spec_underconstrained_manual` detectors hit the right semantic answer on 44/45 entries; the single FP (`erase`) is fixable by tightening `ensures_uses_permissive_or` to ignore `|||` appearing on the RHS of `<==>` (or inside any boolean-returning closed spec fn body).
