# Corpus Rerun11 Final Results — Patterns A + E + C on full verusage corpus

Run completed 2026-05-24. Two-phase pipeline:
1. Baseline (no LLM, 300s hard wall per target, 6-worker parallel)
2. LLM-proof on strict unknowns (Patterns A+E+C, 6-worker parallel, single-shot)

ironkv was run separately as a targeted rerun on its 41 strict unknowns
(`/tmp/ironkv_rerun11/`); other 8 corpus projects were chained from baseline.

## Final corpus-wide distribution (using `classify_ok`)

| project          | total | complete | +LLM | incomplete | inconclusive | crash | verus_err |
|------------------|------:|---------:|-----:|-----------:|-------------:|------:|----------:|
| ironkv           |   214 |      157 |    2 |         16 |           39 |     0 |         0 |
| atmosphere       | 1363  |     1059 |   23 |         29 |          138 |    65 |        49 |
| memory-allocator |    16 |       15 |    0 |          0 |            1 |     0 |         0 |
| nrkernel         |     8 |        6 |    0 |          0 |            0 |     0 |         2 |
| anvil-library    |     1 |        0 |    0 |          0 |            1 |     0 |         0 |
| storage          |    43 |       21 |    0 |          4 |           11 |     0 |         7 |
| vest             |     2 |        2 |    0 |          0 |            0 |     0 |         0 |
| **TOTAL**        | **1647** | **1260** | **25** |  **49**   |     **190**  |  **65** |    **58** |

Notes:
- `complete` = baseline z3 proved R0=unsat without LLM
- `+LLM` = LLM-authored proof block re-verified to unsat (subset of "complete" in classifier terminology, broken out here)
- `incomplete` = `permitted=True` with `r0_z3` in `{sat, unknown}`: classifier promotes these via the `permissive_or` / `spec_underconstrained_manual` detectors
- `inconclusive` = `r0_z3=unknown` without `permitted` (z3 surrendered, no spec-design pardon)
- `crash` = 300s hard-wall subprocess timeout (schema search runaway, atmosphere only)
- `verus_err` = baseline Verus compilation failed (not a determinism question; see Section "verus_error infrastructure failures")

## Pattern E (shape-fallback cache) impact

23 atmosphere LLM-PASSes break down as:

| function template          | LLM raw write | shape_fallback replay | rows |
|----------------------------|--------------:|----------------------:|-----:|
| `set_state`                |             1 |                     6 |    7 |
| `set_mapping`              |             1 |                     5 |    6 |
| `set_owning_container`     |             1 |                     3 |    4 |
| `set_io_mapping`           |             2 |                     1 |    3 |
| `set_ref_count`            |             1 |                     0 |    1 |
| `init`                     |             1 |                     0 |    1 |
| `new`                      |             1 |                     0 |    1 |
| **TOTAL**                  |         **8** |                **15** | **23** |

8 LLM-authored proofs unlocked 15 same-shape replays via the Pattern E cache.
Saved ≈ 2–3 wall hours of LLM time.

ironkv's 2 LLM-PASSes (`greatest_lower_bound_index`, `delegation_map_v::impl1::insert`)
were both raw LLM writes with no fallback replays.

## atmosphere incomplete breakdown (29 entries)

All 29 entries carry `permitted_reason=permissive_or` — i.e. the structural
detector found `|||` somewhere in the ensures (directly or via a transitively
referenced closed spec fn). The `|||` was always traced back to the same
closed spec fn `page_is_mapped`:

```rust
pub open spec fn page_is_mapped(&self, p: PagePtr) -> bool {
    ||| self.mapped_pages_4k().contains(p)
    ||| self.mapped_pages_2m().contains(p)
    ||| self.mapped_pages_1g().contains(p)
}
```

This particular `|||` is **pure boolean disjunction returning a `bool`** —
deterministic on its own. Reaching `permissive_or` through it is, on its
face, a structural false positive of the detector.

**However, manual triage of each function shows that all 29 entries ARE
genuinely incomplete — just for reasons unrelated to `page_is_mapped`.**
The detector hit the right answer for the wrong reason.

### Real source of non-determinism in atmosphere allocator

#### Pattern A — Underconstrained allocation pointer

Six function templates return a ptr whose value is *not* pinned uniquely
by the ensures, only constrained to be drawn from a non-empty input set:

| function                          | constraint on returned ptr `ret`            |
|-----------------------------------|---------------------------------------------|
| `alloc_page_4k`                   | `old(self).free_pages_4k().contains(ret.0)` |
| `alloc_page_2m`                   | `old(self).free_pages_2m().contains(ret.0)` |
| `alloc_page_4k_for_new_container` | `old(self).free_pages_4k().contains(ret.0)` |
| `alloc_and_map_4k`                | `old(self).free_pages_4k().contains(ret)`   |
| `alloc_and_map_io_4k`             | `old(self).free_pages_4k().contains(ret)`   |
| `alloc_and_map_2m`                | `old(self).free_pages_2m().contains(ret)`   |

When `|free_pages_4k| > 1`, `ret.0` can legally take any element of the
free set. Each choice fully determines the post-state (set views are pinned
relative to `ret.0`), but the choice itself is free. Two runs of the same
function on the same input may pick different free pages → distinct
observable post-states → **genuine non-determinism**.

#### Pattern B — Underconstrained internal `Seq`/`Vec` ordering

Eight function templates take a specific `target_ptr` (or `(pcid, va)`,
`(ioid, va)`) and update internal lists. The ensures pin the `Set` view
(`.free_pages_4k()` returns `Set<PagePtr>`), but the underlying field
`self.free_pages_4k` is `Vec<PagePtr>` with `View = Seq<PagePtr>` (ordered).

E.g. `free_page_4k`:
```rust
self.free_pages_4k() =~= old(self).free_pages_4k().insert(target_ptr),
```
constrains the set view but leaves the insertion position (head / tail /
sorted) free. Different impls (or even non-deterministic Verus `Vec::push`
intrinsics) produce different `Seq<PagePtr>` orderings → `det_seq_equal`
on the underlying field is sat → **genuine non-determinism**.

Templates in this bucket: `free_page_4k`, `add_mapping_4k`,
`add_io_mapping_4k`, `remove_mapping_4k_helper1/2/3`,
`remove_io_mapping_4k_helper1`, `merged_4k_to_2m`.

### Compare with real ironkv permissive_or

ironkv's `host_noreceive_noclock_next` uses `|||` in a relational-step
pattern that **does** describe a top-level state choice:
```rust
||| {
    &&& pre.received_packet is None
    &&& SingleDelivery::receive(pre.sd, post.sd, pkt, ack, out)
    ...
}
||| {
    // drop the packet, stay
    &&& post == pre
    &&& out == Set::<Packet>::empty()
}
```
This is **structurally** an explicit choice of post-state, the canonical
form of "the spec admits multiple posts".

### Atmosphere incomplete listing

**Layer 1 — `page_allocator_spec_impl::impl2` primary methods (14):**

| function                       | non-det source        |
|--------------------------------|------------------------|
| `alloc_page_4k`                | A: alloc choice       |
| `alloc_page_2m`                | A: alloc choice       |
| `alloc_page_4k_for_new_container` | A: alloc choice    |
| `alloc_and_map_4k`             | A: alloc choice       |
| `alloc_and_map_io_4k`          | A: alloc choice       |
| `alloc_and_map_2m`             | A: alloc choice       |
| `free_page_4k`                 | B: Seq ordering       |
| `add_mapping_4k`               | B: Seq ordering       |
| `add_io_mapping_4k`            | B: Seq ordering       |
| `remove_mapping_4k_helper1`    | B: Seq ordering       |
| `remove_mapping_4k_helper2`    | B: Seq ordering       |
| `remove_mapping_4k_helper3`    | B: Seq ordering       |
| `remove_io_mapping_4k_helper1` | B: Seq ordering       |
| `merged_4k_to_2m`              | B: Seq ordering       |

**Layer 2 — kernel callers transitively inheriting Layer 1 non-determinism (15):**

| caller                                                       | inherited from |
|--------------------------------------------------------------|----------------|
| `kernel::create_and_map_pages::alloc_and_map_4k`             | Pattern A      |
| `kernel::create_and_map_pages::alloc_and_map_io_4k`          | Pattern A      |
| `kernel::create_and_share_pages::add_mapping_4k`             | Pattern B      |
| `kernel::kernel_drop_endpoint::free_page_4k`                 | Pattern B      |
| `kernel::kernel_kill_proc::helper_kernel_kill_proc_non_root` | Pattern B      |
| `kernel::kernel_kill_proc::helper_kernel_kill_proc_root`     | Pattern B      |
| `kernel::kernel_kill_thread`                                 | Pattern B      |
| `kernel::mem_util::create_entry`                             | Pattern A      |
| `kernel::mem_util::create_iommu_table_entry`                 | Pattern A      |
| `kernel::syscall_new_container::syscall_new_container_with_endpoint` (× 2: alloc_page_4k + alloc_page_4k_for_new_container) | Pattern A |
| `kernel::syscall_new_proc::syscall_new_proc_with_endpoint`   | Pattern A      |
| `kernel::syscall_new_proc_with_iommu::syscall_new_proc_with_endpoint_iommu` | Pattern A |
| `kernel::syscall_new_thread::syscall_new_thread`             | Pattern A      |
| `kernel::syscall_new_thread_with_endpoint`                   | Pattern A      |

### Implication

The classifier verdict (`incomplete`) is **semantically correct** for all
29 entries — they really do admit multiple legal post-states. But the
*reason field* recorded (`permissive_or` traced to `page_is_mapped`) is
misleading; the actual non-determinism comes from Patterns A and B above.

For paper/claim purposes:
1. Keep `incomplete = 29` (correct count).
2. Add a more accurate `permitted_reason` taxonomy:
   - `permissive_or_top_level` — `|||` choosing between post-state branches
     (ironkv style)
   - `alloc_choice_underconstrained` — ret value drawn from a set without
     further constraint (atmosphere Pattern A)
   - `seq_ordering_underconstrained` — set-view pinned but underlying
     `Vec`/`Seq` ordering free (atmosphere Pattern B)
3. Optionally tighten `ensures_uses_permissive_or` to only fire when `|||`
   appears in a clause that references a post-state symbol (vs. inside a
   `spec fn ...(...) -> bool` body), and add the two new detectors above
   so that all 29 atmosphere cases land in their semantic-true bucket.

The current pipeline gets the right answer for the wrong reason; sharpening
the rationale is mostly a paper-claim hygiene issue, not a correctness one.

## verus_error infrastructure failures (94 total)

These are baseline Verus compile failures, not determinism semantics:

| project    | count | dominant cause |
|------------|------:|----------------|
| storage    |    43 | `use deps_hack::...` — cross-crate import, killed by single-file inject |
| atmosphere |    49 | `String::View` trait impl scattered across crate; generic `A` not inferrable in `old::<A>(...)` without workspace context |
| nrkernel   |     2 | `#[repr(transparent)]` over `Ghost<nat>` blocked by new rustc deny lint `repr_transparent_non_zst_fields` |

Suggested action: report these in a separate `infra_failure` bucket so they
don't pollute the determinism numerator/denominator.

### Update 2026-05-26 — atmosphere verus_error cleared

After the source-rewriter overhaul (`7ec0f2d7`) and two follow-up patches
landed today, **all 49 atmosphere verus_error cases now compile cleanly**:

| pre-fix bucket | count | post-fix outcome |
|----------------|------:|------------------|
| `View` trait impl missing (`String::View` etc.) | 20 | 20 `ok` (View trait synth from inherent `spec fn view`) |
| `Dereference this mutable reference` (postcondition) | 16 | 16 `ok` (source-level `final(p)` / `*final(p)` rewrite) |
| E0308 `Tracked(p): Tracked<&mut T>` destructure loses `&mut` | 11 | 11 `ok` (extractor preserves inner `&mut`; gen_det auto-`&`-prefixes method-call args) |
| E0425 `spec_va_2m_valid` / `spec_va_1g_valid` not in scope | 2 | 2 `extract_error` (extractor now skips block-commented fns) |
| **TOTAL** | **49** | **47 ok + 2 extract_error / 0 verus_error** |

Net effect on `incompleteness_summary` Section 1 stats:

| project    | total | complete | +LLM | incomplete | inconclusive | crash | verus_err |
|------------|------:|---------:|-----:|-----------:|-------------:|------:|----------:|
| atmosphere (pre-fix)  | 1363 |     1059 |   23 |         29 |          138 |    65 |        49 |
| atmosphere (post-fix) | 1361 |     1082 |   23 |         29 |          162 |    65 |          0 |

The 47 newly-clean atmosphere cases break down to **23 `r0_z3=unsat`**
(promoted to `complete`) + **24 `r0_z3=unknown`** (promoted to
`inconclusive`). The 2 `extract_error` cases drop from the total
(block-commented `va_{2m,1g}_valid` are no longer scraped as targets).

Full rerun of the 49 baseline-failing entries: `/tmp/atmosphere_rerun_2026-05-26.json`. Methodology: same baseline driver, `--timeout 180s`.

### Update 2026-05-26 — storage verus_error 43 → 7

After four pipeline patches landed (this session), **storage drops from
43 baseline `verus_error` to 7** (36 newly compile-and-classify
cleanly). All four patches are in working tree; details in commit
message.

| pre-fix bucket | count | root cause | post-fix outcome |
|----------------|------:|------------|------------------|
| `error[E0432]: unresolved import deps_hack::...` | 43 | sibling proc-macro crate (`deps_hack`) unresolvable in single-file mode | 36 `ok` via new `_rewrite_deps_hack` shim; 7 still fail on residual issues (next row) |
| `parse error: keyword fn` (10 of the 43) | — | misplaced helper injection: `rfind("}")` targeted the last `unsafe impl ConstPmSized for [T;N]` block instead of `verus! { ... }` | fixed by new brace-aware `_find_verus_block_close` scanner |
| `S not in scope` / `T::spec_from_bytes` not found | — | (a) `_prune_generics` only inspected param-list, dropped `<S>` when `S` was used only in ensures; (b) `closed spec fn` decls inside blanket impls (`impl<T: Bound> Trait for T`) emitted `T::spec_from_bytes` reveals at call sites where `T` is not in scope | (a) `sig_for_prune` extended to include `run1 + run2 + requires`; (b) `closed_spec_fn_qualified_names` tracks `skipped_impl_spans` and drops blanket-impl decls from the qual-map entirely |
| **TOTAL** | **43** | — | **36 `ok` / 7 residual `verus_error`** |

The 7 residual `verus_error` cases are inherent source / vstd-version
incompatibilities, not synthesizer bugs:
- **4× `Box<S>: SpecEq<S>` not implemented** — original source body
  `out == true_val` where `out: Box<S>` and `true_val: S`; current
  Verus refuses the implicit `Box`/`S` comparison and demands `*out
  == true_val`. Pre-dates this work.
- **3× `iter.end` on `VerusForLoopWrapper`** — original source uses
  `iter.end` referring to a named for-loop iterator; current vstd
  restructured to `iter.iter.end` / `iter.snapshot.end`.

Both buckets are source-text incompats that would need either a
guarded textual rewrite (risky — false positives on unrelated `.end` /
`Box`-comparison sites) or upstream source updates. Marked as
inherent infra failures.

Net effect on `incompleteness_summary` Section 1 stats:

| project | total | complete | +LLM | incomplete | inconclusive | crash | verus_err |
|---------|------:|---------:|-----:|-----------:|-------------:|------:|----------:|
| storage (pre-fix)  | 43 | 0 | 0 | 0 |  0 | 0 | 43 |
| storage (post-fix) | 43 | 21 | 0 | 4 | 11 | 0 |  7 |

(21 baseline `complete` / 4 `incomplete` permitted / 11 `ok_inconclusive` /
7 `verus_err` — full breakdown via the [`session-state`
checkpoints](../../.copilot/session-state/) for this session.)

Pipeline patches (working tree; about to commit):
- `verus/single_file.py` — `_find_verus_block_close` (brace-aware
  `verus! { ... }` finder, replaces `rfind("}")`), `_rewrite_deps_hack`
  (strip imports / derives / `pmsized_primitive!`, emit stub trait
  impls + stub structs), `_synthesize_view_trait_impls` header cleanup
  (drop backtick-delimited type clause that leaks past `//` on
  multi-line type clauses).
- `llm_proof/prover.py` — same `_find_verus_block_close` for the LLM
  proof inject path.
- `codegen/gen_det.py` — `sig_for_prune` includes ensures/requires.
- `classify.py` — `closed_spec_fn_qualified_names` tracks blanket-impl
  skip spans; `_impl_generic_param_names` helper.

Full rerun of the 43 baseline-failing entries: `/tmp/storage_full_2026-05-26/full_run.json`. Methodology: same baseline driver, `--timeout 60s`.

## Methodology footnotes

- Baseline driver: `/tmp/run_corpus_baseline_parallel.py` (6 ThreadPool workers
  spawning `/tmp/run_one_target.py` subprocesses with 300s wall timeout).
- LLM driver: `/tmp/run_corpus_unknowns_parallel.py` (6-worker
  ProcessPoolExecutor, fork-shared ViewRegistry per project,
  cache_mode=use, max_attempts=2, llm_timeout=600).
- ironkv driver: `/tmp/run_ironkv_unknowns_parallel.py` (same shape, ironkv-only).
- Baseline outputs: `/tmp/corpus_baseline/<project>/full_run.json`.
- LLM phase outputs: `/tmp/corpus_rerun11/full_run.json`,
  `/tmp/ironkv_rerun11/full_run.json`.
- Patterns A+E+C are committed in spec-determinism repo at `4cfce320`.
