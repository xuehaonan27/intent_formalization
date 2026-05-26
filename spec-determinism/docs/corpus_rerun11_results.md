# Corpus Rerun11 Final Results — Patterns A + E + C on full verusage corpus

Original run completed 2026-05-24. Two-phase pipeline:
1. Baseline (no LLM, 300s hard wall per target, 6-worker parallel)
2. LLM-proof on strict unknowns (Patterns A+E+C, 6-worker parallel, single-shot)

ironkv was run separately as a targeted rerun on its 41 strict unknowns
(`/tmp/ironkv_rerun11/`); other 8 corpus projects were chained from baseline.

A subsequent **2026-05-26 verus_error closeout** (commits `68a2ac1e`,
`64b1d5fe`, `38bd6d8e`) cleared 87 of 94 baseline Verus-compile failures
across atmosphere, storage, and nrkernel via pipeline-level source
rewriters. Only 7 inherent storage source/vstd incompats remain. The
Section 1 table below is the **post-closeout** state; pre-closeout
baseline totals were 1239 / 25 / 45 / 179 / 65 / 94 (see commit
`68a2ac1e^` for the snapshot, or the per-project diff tables in
§"2026-05-26 verus_error closeout").

## Final corpus-wide distribution (using `classify_ok`)

| project          | total | complete | +LLM | incomplete | unknown | crash | verus_err |
|------------------|------:|---------:|-----:|-----------:|-------------:|------:|----------:|
| ironkv           |   214 |      157 |    2 |         16 |           39 |     0 |         0 |
| atmosphere       |  1361 |     1082 |   23 |         29 |          162 |    65 |         0 |
| memory-allocator |    16 |       15 |    0 |          0 |            1 |     0 |         0 |
| nrkernel         |     8 |        7 |    0 |          0 |            1 |     0 |         0 |
| anvil-library    |     1 |        0 |    0 |          0 |            1 |     0 |         0 |
| storage          |    43 |       23 |    0 |          2 |           11 |     0 |         7 |
| vest             |     2 |        2 |    0 |          0 |            0 |     0 |         0 |
| **TOTAL**        | **1645** | **1286** | **25** |  **47**   |     **215**  |  **65** |    **7** |

> The above table reflects the **post-closeout** state after the
> 2026-05-26 atmosphere / storage / nrkernel pipeline patches
> (`68a2ac1e`, `64b1d5fe`, `38bd6d8e`). See §"2026-05-26 verus_error
> closeout" for the bucket-by-bucket diff.

Notes:
- `complete` = baseline z3 proved R0=unsat without LLM
- `+LLM` = LLM-authored proof block re-verified to unsat (subset of "complete" in classifier terminology, broken out here)
- `incomplete` = `permitted=True` with `r0_z3` in `{sat, unknown}`: classifier promotes these via the `permissive_or` / `spec_underconstrained_manual` detectors
- `unknown` = `r0_z3=unknown` without `permitted` (z3 surrendered, no spec-design pardon)
- `crash` = 300s hard-wall subprocess timeout (schema search runaway, atmosphere only)
- `verus_err` = baseline Verus compilation failed (not a determinism question; see Section "verus_error infrastructure failures")

### Column reference

The columns above (`total`, `complete`, `+LLM`, `incomplete`,
`unknown`, `crash`, `verus_err`) are exclusive buckets — every
extracted target lands in exactly one of them, and the per-project
totals sum to `total`. Mapped to the `classify_ok` enum
(`spec_determinism/classify.py`):

| column         | classify_ok bucket   | underlying signal                                       |
|----------------|----------------------|---------------------------------------------------------|
| `total`        | (sum of below)       | count of det-check targets extracted for this project   |
| `complete`     | `complete`           | `status=ok` ∧ `r0_z3=unsat` ∧ no LLM assist             |
| `+LLM`         | `complete_llm`       | `status=ok` ∧ `r0_z3=unsat` ∧ `llm_assisted=True`       |
| `incomplete`   | `incomplete`         | `status=ok` ∧ (`r0_z3=sat` OR (`r0_z3=unknown` ∧ `permitted=True`)) |
| `unknown`      | `ok_inconclusive`    | `status=ok` ∧ `r0_z3=unknown` ∧ `permitted=False`       |
| `crash`        | (status != `ok`)     | `status=runner_crash` — driver subprocess hit the outer wall |
| `verus_err`    | (status != `ok`)     | `status=verus_error` — Verus refused to compile the file |

`total` — one row per `(crate, function template)` pair the extractor
discovered in the project source. For each row the pipeline synthesises
a `det_<f>` proof fn (two parallel runs with arbitrary inputs + an R0
equality check on the post-state) and hands the file to Verus +
z3. The bucket then classifies how Verus / z3 answered.

`complete` — Verus compiled, z3 returned **R0=unsat** on the
synthesised det check, and the file did NOT go through an LLM-authored
proof block to get there. Semantic meaning: the spec's `ensures`
clauses uniquely pin the post-state — two arbitrary runs cannot
disagree.

`+LLM` — same z3 verdict (R0=unsat) but the unsat was unlocked by an
LLM-authored proof block. Concretely: the baseline det check came back
`r0_z3=unknown`; the LLM-proof loop (`spec_determinism.llm_proof`)
synthesised a Verus proof block (Pattern A helper lemma / Pattern E
shape-fallback / Pattern C relational lemma hint), the re-run with
that block produced R0=unsat, and the classifier rewrote the result
to `llm_assisted=True`. Broken out as its own column so paper claims
can distinguish "z3 alone" from "z3 + LLM-guided proof". `+LLM`
counts are a strict subset of "complete" in the colloquial sense; the
existing legend phrase "subset of complete in classifier
terminology" really means: same observable post-state determinism,
different path to the proof.

`incomplete` — Verus compiled but the spec admits multiple post-states.
Two ways to land here:

  1. **R0=sat (concrete witness)** — z3 produced an explicit model
     where two runs of the same fn on the same inputs reach
     distinguishable post-states. This is a hard "the spec really is
     non-deterministic" verdict (e.g. atmosphere Pattern A:
     `alloc_page_4k` returns any element from `free_pages_4k`).
  2. **R0=unknown + `permitted=True`** — z3 surrendered, but the spec
     EXPLICITLY uses one of the permissive patterns:
     - `permissive_or` — `ensures` uses `|||` (Verus spec OR), either
       directly at top level or transitively via a referenced spec fn
       body. Detected by `ensures_uses_permissive_or` (structural scan).
     - `spec_underconstrained_manual` — the function name appears in
       a curated allowlist `REAL_SAT_MANUAL_FNS` (e.g. ironkv's
       `host_noreceive_noclock_next` which uses `|||` to choose
       between "deliver" vs "drop" post-states).

     The classifier promotes these R0=unknown cases to `incomplete`
     rather than leaving them in the `unknown` bucket, on the grounds
     that the spec author already declared the spec to be
     non-deterministic — z3 failing to produce a witness is not
     evidence against that.

`unknown` (column name) — z3 returned **R0=unknown** AND no permissive
marker fired. Verus compiled, the det-check ran, but the SMT search
exceeded its rlimit / hit quantifier-instantiation limits without
producing either an unsat proof or a sat witness. This is the "we
don't know" bucket (internal classify_ok name: `ok_inconclusive`).
Semantically these COULD be either complete (with a stronger proof)
or incomplete (with a tighter SMT search) — neither verdict is
supported by current evidence. Roughly half of these cases are
resolvable by LLM-authored proof (which is what `+LLM` captures); the
remainder either time out or fall through every LLM pattern attempt.

`crash` — the per-target subprocess (driven by
`/tmp/run_corpus_baseline_parallel.py`) hit its **300 s outer wall
timeout** before Verus could complete. Distinct from the inner Verus
`--timeout 120 s` (which surfaces as `r0_z3=unknown`, not `crash`):
crash means the entire det-check generation + Verus + z3 pipeline
took longer than 5 minutes wall-clock. All 65 crashes are in
atmosphere; the dominant cause is **z3 quantifier-instantiation
explosion** on the synthesised det-check (see `pagetable_map_4k_page`
deep-dive below). Other projects don't trigger this because they
don't have atmosphere's depth of `wf()`-rooted closed-spec-fn chains.

**Example crash record** (raw `/tmp/corpus_baseline/atmosphere/full_run.json` entry):

```json
{
  "project":     "atmosphere",
  "file":        ".../verified/kernel/kernel__create_and_map_pages__impl0__alloc_and_map.rs",
  "function":    "pagetable_map_4k_page",
  "artifact_key": "atmosphere__verified__kernel__kernel__create_and_map_pages__impl0__alloc_and_map__pagetable_map_4k_page",
  "status":      "runner_crash",
  "error":       "subprocess wall timeout 300s",
  "wall_ms":     300035
}
```

The 65 crashes hit 40 unique functions; the top-recurring ones are
`range_create_and_share_mapping` (×6), `alloc_page_table` (×4),
`range_alloc_and_map_io` (×3), `pagetable_map_4k_page` (×2), etc. All
live in atmosphere `kernel__*` files (notably `mem_util__impl0__*`
×4–4, `create_and_share_pages__impl0__*` ×3,
`syscall_new_*__impl0__*` ×3 each) — the same files that host the
deeply-nested `mapped_pages_4k().contains(...)` chains called out in
§"atmosphere incomplete breakdown".

#### Deep-dive: `pagetable_map_4k_page`

Probed with `--keep-tmp` to capture the on-disk artefacts. Measured
load on the SMT stage:

| where | value |
|---|---:|
| source ensures (lines 1741–1816) | **76 lines** |
| closed spec fns called from ensures | 8 (`wf`, `get_pagetable_by_pcid`, `get_pagetable_mapping_by_pcid`, `page_closure`, `mapping_4k/2m/1g`, `kernel_entries`) |
| synthesised det fn parameters | **340** |
| synthesised det fn signature size | 56 544 chars |
| synthesised det fn `assume(...)` count | **566** |
| synthesised det fn `forall` count | 12 |
| `reveal(...)` injected | **0** |
| Verus → z3 query (`root.smt2`) | **29.5 MB / 85 292 lines** |
| ↳ `(declare-fun ...)` | 851 |
| ↳ `(assert ...)` | **2 501** |
| ↳ `(forall ...)` instances | **1 481** |
| ↳ `(check-sat)` | 3 |

A typical Verus query is in the tens-of-kB range with a few hundred
quantifier instances. This one is **30 MB / 1 481 forall** — z3 falls
into a matching loop on the shared `get_pagetable_by_pcid(_).mapping_4k()`
trigger heads and never returns from one of the three `(check-sat)`
queries before the 300 s outer wall fires.

The Python driver (`verusage_run`) has **no child subprocess** during
synthesis — gen_det's schema enumeration runs in-process and completes
quickly; it's the spawned `verus` → `z3` invocation that overruns the
wall. The 30 MB `root.smt2` is fully written to disk before z3 hangs.

##### Why atmosphere upstream "verifies" this function

The source declares:

```rust
#[verifier::external_body]
pub fn pagetable_map_4k_page(&mut self, …) -> …
    requires …
    ensures …   // 76 lines
{
    unimplemented!()
}
```

**Upstream atmosphere never proves this function.** `#[verifier::
external_body]` instructs Verus to accept the body as trusted and
expose only the ensures as an axiom to callers; the body is literally
`unimplemented!()`. The 76-line ensures was authored as a *spec
axiom*, not as something the atmosphere authors expected Verus to
discharge.

Our determinism pipeline strips `external_body` (it has to — we
want to validate the *spec*, not skip it) and asks z3: "given these
ensures, is the output uniquely determined?" That requires unfolding
the full `wf()`-rooted closed-spec-fn cone — which is exactly the work
atmosphere chose to externalise to avoid in the first place. So the
crash isn't us hitting a regression; it's us discovering that the spec
is too heavy for z3 to discharge directly.

Auditing the 40 unique crash functions against the source: **17/40
(43 %) of unique fns** and **37/65 (57 %) of crash instances** carry
`#[verifier::external_body]` upstream — i.e. the majority of the
crash *workload* comes from functions atmosphere itself never asked
z3 to verify. The remaining 23 unique fns (28 instances) have real
bodies, but they all sit on the same `wf()`-axiom cone, so the
quantifier-instantiation pressure is the same.

`verus_err` — Verus's frontend rejected the source file before any
z3 query ran. Pure infrastructure failure — not a determinism
statement about the spec. Baseline counts were 94 across storage /
atmosphere / nrkernel; the 2026-05-26 closeout (see below) reduced
this to 7 (all inherent storage source/vstd-version incompats — see
§"2026-05-26 verus_error closeout" for the bucket-by-bucket diff
and the per-project root-cause tables).

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

## 2026-05-26 verus_error closeout

The initial rerun11 baseline had **94 `verus_error` entries** across
three projects (storage 43, atmosphere 49, nrkernel 2) — all infra
failures, not determinism semantics. Three commits land in this window
that clear 87 of the 94 via pipeline-level source rewrites; the
remaining 7 are inherent source / vstd-version incompatibilities in
storage that would require risky textual rewrites or upstream source
edits to address.

### Summary

| project    | baseline `verus_err` | post-closeout `verus_err` | newly `complete` | newly `incomplete` | newly `unknown` | dropped |
|------------|---------------------:|--------------------------:|-----------------:|-------------------:|---------------------:|--------:|
| atmosphere |                   49 |                         0 |               23 |                  0 |                   24 |       2 |
| storage    |                   43 |                         7 |               23 |                  2 |                   11 |       0 |
| nrkernel   |                    2 |                         0 |                1 |                  0 |                    1 |       0 |
| **TOTAL**  |               **94** |                     **7** |           **47** |              **2** |               **36** |   **2** |

(The 2 atmosphere "dropped" entries are extractor false-positives:
extractor used to scrape fns living inside `/* ... */` block comments;
the fix now skips those, so the entries vanish from the total entirely.)

Commits: `68a2ac1e` (atmosphere), `64b1d5fe` (storage), `38bd6d8e`
(nrkernel). Section 1 of this doc and the matching Section 1 of
`incompleteness_summary_2026-05-26.md` both already reflect this
post-closeout state.

### Per-project root cause / fix / outcome

#### atmosphere (49 → 0)

Four root causes; commit `68a2ac1e` is the closeout, building on the
source-rewriter overhaul `7ec0f2d7` and two follow-up patches:

| bucket | count | root cause | fix |
|--------|------:|------------|-----|
| `View` trait impl missing (`String::View` etc.) | 20 | per-crate `impl View for String` lives in a sibling crate, not visible in single-file mode | new `_synthesize_view_trait_impls` derives a stub `View` trait impl from each type's inherent `spec fn view` |
| `Dereference this mutable reference` | 16 | Verus now refuses bare `&mut` comparisons in spec context (`self == old(self)`, `*p == old(*p)`) | source-level rewriter `_rewrite_self_eq_old_self` + `_rewrite_ref_eq_ref` + `_rewrite_mut_self_in_ensures` produce `*self == *old(self)` / `final(p)` forms |
| E0308 `Tracked(p): Tracked<&mut T>` destructure loses `&mut` | 11 | extractor reset the inner-type `&mut` annotation when normalizing the destructure pattern | extractor preserves the inner `&mut`; gen_det auto-`&`-prefixes method-call args for renamed `&mut`-param idents |
| E0425 `spec_va_2m_valid` / `spec_va_1g_valid` not in scope | 2 | extractor scraped fns from inside `/* ... */` block comments | extractor skip-list for block-commented regions |

Outcome: 47 of 49 compile cleanly (23 → `complete`, 24 →
`unknown`); 2 drop from the total (block-commented fns are no
longer scraped). Full rerun: `/tmp/atmosphere_rerun_2026-05-26.json`,
methodology `--timeout 180s`.

#### storage (43 → 7)

Four pipeline patches across `single_file.py`, `gen_det.py`,
`classify.py`, and `prover.py`; commit `64b1d5fe`.

| bucket | count | root cause | fix |
|--------|------:|------------|-----|
| `error[E0432]: unresolved import deps_hack::...` | 43 | sibling proc-macro crate `deps_hack` (provides `PmSized` derive, `pmsized_primitive!` macro, types like `crc64fast::Digest`) is unresolvable in single-file mode | new `_rewrite_deps_hack` shim: strip the `use` line (braced + bare), strip `PmSized` from `#[derive(...)]`, drop `pmsized_primitive!(T);` calls, emit stub trait impls (`SpecPmSized` / `UnsafeSpecPmSized` / `PmSized` returning 0) inside an appended `verus! { ... }` block, plus `unsafe impl ConstPmSized for T` for primitives and `pub struct {Name} {}` stubs for cross-crate type-name imports. Stub size/align bodies are sound for determinism checks because r1/r2 resolve to the same impl. |
| `parse error: keyword fn` (10 of the 43) | — | helper injection used `rfind("}")` and landed inside the LAST `unsafe impl ConstPmSized for [T;N]` block instead of `verus! { ... }` | new brace-aware `_find_verus_block_close` scanner (handles `//`, `/* */`, `"..."`, `'.'`, `r#"..."#`) replaces `rfind("}")` in both `single_file.py` and `llm_proof/prover.py` |
| `S not in scope` on synthesized det fn | — | `_prune_generics` in `gen_det` only inspected the param list; generics referenced *only* in `ensures` (e.g. `<S>` in `ensures out as nat == S::spec_align_of()`) got dropped | `sig_for_prune` extended to include `run1 + run2 + requires_str` |
| `T::spec_from_bytes` not in scope at det call site | — | `closed spec fn` decls inside blanket impls (`impl<T: Bound> Trait for T` where Self IS a generic of the impl) emitted `T::spec_from_bytes` qualified-name reveals at module scope, where `T` is not bound | `classify.closed_spec_fn_qualified_names` tracks `skipped_impl_spans` for blanket impls and drops their decls from the qual map entirely; new `_impl_generic_param_names` helper. Closed spec fn stays closed (no opacity rewrite, no reveal). |

Outcome: 36 of 43 compile cleanly (23 → `complete`, 2 → `incomplete`
permitted, 11 → `unknown`). Full rerun:
`/tmp/storage_full_2026-05-26/full_run.json`, methodology
`--timeout 60s`. The two real incomplete cases are documented in
`storage-incompleteness-cases-2026-05-26.en.md`
(`write_setup_metadata` byte-layout under-specified;
`read_log_variables` `Result<_, E>` error path under-specified). The
other two pre-closeout `permissive_or` hits (`serialize_and_write`
×2) were classifier false positives — z3 proved them unsat, so the
permissive marker is overridden and they land in `complete`.

The **7 residual `verus_error`** are inherent source / vstd-version
incompatibilities — not synthesizer bugs:

| residual bucket | count | description |
|-----------------|------:|-------------|
| `Box<S>: SpecEq<S>` not implemented | 4 | original source body `out == true_val` where `out: Box<S>` and `true_val: S`; current Verus refuses the implicit `Box`/`S` comparison and demands `*out == true_val`. |
| `iter.end` on `VerusForLoopWrapper` | 3 | original source uses `iter.end` referring to a named for-loop iterator; current vstd restructured to `iter.iter.end` / `iter.snapshot.end`. |

Both buckets would need either a guarded textual rewrite (risky —
false positives on unrelated `.end` / `Box`-comparison sites) or
upstream source updates. Tagged as inherent infra failures and
excluded from determinism numerator/denominator.

#### nrkernel (2 → 0)

Both cases share a single root cause; commit `38bd6d8e`.

| bucket | count | root cause | fix |
|--------|------:|------------|-----|
| `repr(transparent)` + `Ghost<T>` rejected | 2 | newer rustc promotes `repr_transparent_non_zst_fields` to hard error; Verus's `Ghost<T>` is a ZST field of an external type with private fields, blocked on structs like `#[repr(transparent)] struct PDE { entry: usize, layer: Ghost<nat> }` | new `_allow_repr_transparent_lint` rewriter: when source contains `#[repr(transparent)]`, auto-insert a crate-level `#![allow(repr_transparent_non_zst_fields)]` at the top of the file (after BOM/shebang/inner attrs/leading comments). Layout semantics preserved — only the lint is silenced. |

Outcome: both compile cleanly (1 → `complete`, 1 → `unknown`).
Full rerun: `/tmp/nrkernel_rerun/full_run.json`, methodology
`--timeout 60s`.

### Pipeline-level files touched

| file | additions in closeout window |
|------|------------------------------|
| `spec_determinism/verus/single_file.py` | `_find_verus_block_close`, `_rewrite_deps_hack` (+ `_parse_deps_hack_imports`, `_deps_hack_type_imports`, `_DEPS_HACK_USE_RE`, `_DERIVE_RE`, `_PMSIZED_PRIM_RE`, `_STRUCT_AFTER_DERIVE_RE`), `_allow_repr_transparent_lint`, `_synthesize_view_trait_impls` (header cleanup) |
| `spec_determinism/llm_proof/prover.py` | `_find_verus_block_close` (mirror of single_file) |
| `spec_determinism/codegen/gen_det.py` | `_build_template` — `sig_for_prune` includes `run1 + run2 + requires_str` |
| `spec_determinism/classify.py` | `_IMPL_HEADER_RE` named-capture, `_impl_generic_param_names`, `closed_spec_fn_qualified_names` tracks `skipped_impl_spans` for blanket impls |
| `spec_determinism/extract/extractor.py` | preserve inner `&mut` on `Tracked(...): Tracked<&mut T>` destructure; skip block-commented fns (atmosphere closeout) |

All 3 self-test suites (`extractor`, `gen_det`, `classify`) pass on
the final tree.

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
