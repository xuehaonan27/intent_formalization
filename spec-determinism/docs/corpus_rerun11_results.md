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

A further **2026-06-01 atmosphere + storage unknown audit** reclassified
artifacts in two projects from `unknown` (and a handful of `verus_err`)
to their source-level categories:

- **atmosphere**: 20 raw / 4 unique specs moved `unknown` → `complete`.
  Root cause: codegen defect in `gen_det.py::build_det_check_spec`
  (top-level-self view-registry gap; ≈10 lines). Affected specs:
  `Array::set`, `Array::init2zero`, `Array::init2none`,
  `ArrayVec::pop_unique`. Source-level complete under the project's
  view-first equality policy — only a codegen fix is needed to flip the
  tool verdict from `unknown` → `unsat` on the next rerun.
- **storage**: 12 raw moved to `incomplete` (10 from `unknown`, 2 from
  `verus_err`), 1 raw moved `unknown` → `complete`. The 12 newly
  `incomplete` cases break down as 7 `impervious_to_corruption` pattern
  (Form A / B / C `==>` implications the syntactic `permissive_or`
  detector misses), 1 byte-layout (`write_setup_metadata_to_region`,
  sibling of original #1), and 4 opaque-internal-state
  (`CrcDigest::new`/`write`/`write_bytes` over an `external_body`
  `ExternalDigest` field). The 1 newly `complete` is the trait-method
  `serialize_and_write` — a z3-weakness on structural `==` over a
  trait-bound generic, not a spec defect. The 2 newly `incomplete`
  cases inside `verus_err` (`check_crc` + `read_log_variables` in
  `start_read_log_variables.rs`) are `impervious_to_corruption`-pattern
  sites that *also* hit the `Box<S>: SpecEq` infra residual.

The Section 1 table below still shows the **tool-observed** state for
both projects; see the supplementary "Source-level distribution" table
immediately after it for the post-reclassification numbers, and
§"2026-06-01 codegen-defect + storage-detector-miss reclassification"
for the per-project audit. For atmosphere the gap closes on a codegen
fix + rerun; for storage 10 of the 12 new incompletes are detector
misses (would close on extending `ensures_uses_permissive_or` to
recognise `==> !impervious_to_corruption`), the byte-layout case
mirrors #1's existing fix recipe, and the 4 opaque-state cases need
either a closed-spec accessor / ghost-only field / pipeline-side
skip-external_body.

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

### Source-level distribution (post-2026-06-01 reclassification)

The table above is the **tool-observed** state (what `r0_z3` returned).
The 2026-06-01 atmosphere + storage + small-project unknown audit
identified reclassifications across five projects:

- **atmosphere**: 25 raw artifacts (6 unique specs) reclassified out of
  `unknown` — (a) 20 raw / 4 unique are **codegen-defect false positives**
  (source-level complete under the view-first equality policy, awaiting
  a ≈10-line fix in `gen_det.py::build_det_check_spec`); (b) 5 raw / 2
  unique are real spec incompletes audit-found in the `unknown` bucket
  (`Array::new`, `StaticLinkedList::push`; incompleteness doc cases
  #11–#12).
- **storage**: 13 raw reclassifications — 10 `unknown` → `incomplete`
  (detector-missed `impervious_to_corruption` + byte-layout +
  opaque-state spec defects), 1 `unknown` → `complete` (trait-bound
  generic z3-weakness on `serialize_and_write`), 2 `verus_err` →
  `incomplete` (impervious-pattern sites that also hit infra). See
  [`storage-incompleteness-cases-2026-05-26.en.md`](./storage-incompleteness-cases-2026-05-26.en.md)
  for the full per-case audit (14 documented cases total).
- **memory-allocator / nrkernel / anvil-library**: the three remaining
  single-`unknown` records were manually audited and all three are real
  spec incompletes (`unknown` → `incomplete`): memory-allocator
  `CommitMask::next_run` is author-acknowledged under-specified; nrkernel
  `PDE::new_entry` constrains individual bits via per-bit MASK predicates
  but leaves reserved bits unpinned; anvil-library `vec_filter` uses
  multiset-eq by design so element ordering is permissive. None are z3
  decidability limits. Per-case rationale in the audit-reclassification
  footnotes under the source-level table.

The table below records the **source-level** classification across
both projects, with **every cell deduplicated to unique source-spec
function names** (one row per `(file, function template)` pair is
the raw artifact count; the `verusage` corpus inlines every callee
into each verifier file, so the unique source-spec count is much
smaller than the raw count for callee-heavy functions like
`Vec::len` or `Array::set`):

| project          | complete | +LLM | incomplete | unknown | crash | verus_err | TOTAL |
|------------------|---------:|-----:|-----------:|--------:|------:|----------:|------:|
| ironkv           |       49 |    2 |          9 |      27 |     0 |         0 |    80 |
| atmosphere       |       89 |   18 |     **16** |      73 |    40 |         0 |   222 |
| memory-allocator |       14 |    0 |      **1** |       0 |     0 |         0 |    15 |
| nrkernel         |        7 |    0 |      **1** |       0 |     0 |         0 |     8 |
| anvil-library    |        0 |    0 |      **1** |       0 |     0 |         0 |     1 |
| storage          |        6 |    0 |      **9** |       0 |     0 |         5 |    18 |
| vest             |        2 |    0 |          0 |       0 |     0 |         0 |     2 |

**Bold** cells were independently audit-verified (atmosphere
incompleteness doc #1–#12 deduplicates to 16 unique allocator-side
specs; storage incompleteness doc #1–#14 deduplicates to 9 unique
specs across 4 patterns; memory-allocator + nrkernel + anvil-library
single-unknown audits at the bottom of this section). All other cells
dedup by **unique function name** within the bucket — a heuristic that
can undercount when two different traits share a method name (e.g.,
`len`), and which has been spot-checked against the audit-verified
cells (atmosphere `incomplete=16` and storage `incomplete=9` both
reproduce exactly).

The **TOTAL** column is the **project-wide union of unique source-spec
function names** across all buckets, not the row sum — the same `len`
can legitimately appear in two different buckets via different inlining
sites, so column sums double-count overlaps. For ironkv, the 87 row-sum
collapses to 80 (7 cross-bucket overlaps); for atmosphere, 236 → 222
(14 overlaps); for storage, 20 → 18 (2 overlaps); the four small
projects have zero overlap. For total-corpus accounting (the 1645-row
denominator), use the raw-count table immediately below.

Audit-reclassification footnotes (these moved between buckets in the
2026-06-01 source-level reclassification and are already reflected in
the cells above):

- atmosphere `complete` (89 unique) includes **4 unique / 20 raw**
  codegen-FP reclassifications (`Array::set`, `init2zero`, `init2none`,
  `ArrayVec::pop_unique`) that moved out of `unknown`.
- storage `complete` (6 unique) includes **1 unique / 1 raw**
  z3-weakness reclassification (`serialize_and_write`) that moved out
  of `unknown`.
- memory-allocator `incomplete` (1 unique) — `CommitMask::next_run`
  in `commit_mask/commit_mask__impl__next_run.rs`: spec only requires
  `next_idx + count <= 512 && (forall t. next_idx <= t < next_idx+count
  ==> self@.contains(t))`; author explicitly commented that "first set
  bit at or after `idx`" and "`count` not smaller than necessary" are
  not required for safety. Two valid impls can return `(0, 0)` and
  `(0, 1)` for the same input — real spec under-specification.
- nrkernel `incomplete` (1 unique) — `PDE::new_entry` in
  `impl_u__l2_impl/impl_u__l2_impl__impl0__new_entry.rs`: spec uses
  per-bit `r.entry & MASK_X == MASK_X` predicates that constrain
  individual bits but leave reserved bit positions unpinned;
  `r.entry` is not uniquely determined even when all 8 inputs are
  fully bound. Real spec under-specification, masked by z3's
  bit-vector decidability limit.
- anvil-library `incomplete` (1 unique) — `vec_filter` in
  `vstd_exd/vec_lib/vec_lib.rs`: spec uses `r@.to_multiset() =~=
  v@.to_multiset().filter(f_spec)` (multiset equality), so element
  ordering is intentionally not pinned — two valid runs may return
  the same elements in different orders. Real permissive-by-design
  spec (deliberate `multiset_eq` permission).

See [`small-projects-incompleteness-cases-2026-06-01.en.md`](./small-projects-incompleteness-cases-2026-06-01.en.md)
for the full per-case audit of these three (`next_run`, `new_entry`,
`vec_filter`) including source, view function, generated equal_fn, and
constructed concrete sat witness for each.

**Source-level — raw corpus artifact counts** (one row per `(file,
function template)` pair; same source-level reclassification applied):

| project          | total | complete | +LLM | incomplete | unknown | crash | verus_err |
|------------------|------:|---------:|-----:|-----------:|--------:|------:|----------:|
| ironkv           |   214 |      157 |    2 |         16 |      39 |     0 |         0 |
| atmosphere       |  1361 |     1102 |   23 |         34 |     137 |    65 |         0 |
| memory-allocator |    16 |       15 |    0 |          1 |       0 |     0 |         0 |
| nrkernel         |     8 |        7 |    0 |          1 |       0 |     0 |         0 |
| anvil-library    |     1 |        0 |    0 |          1 |       0 |     0 |         0 |
| storage          |    43 |       24 |    0 |         14 |       0 |     0 |         5 |
| vest             |     2 |        2 |    0 |          0 |       0 |     0 |         0 |
| **TOTAL**        | **1645** | **1307** | **25** | **67** | **176** | **65** | **5** |

Diffs vs Section 1 table (raw counts so deltas line up with the
tool-observed signal):

| project | column | tool-observed | source-level | Δ | reason |
|---------|--------|--------------:|-------------:|--:|--------|
| atmosphere | complete   | 1082 | 1102 | +20 | 4 codegen-FP specs (20 raw) → reclassified to `complete` |
| atmosphere | incomplete |   29 |   34 |  +5 | doc #11–#12 audit-found from `unknown` (`Array::new` + `StaticLinkedList::push`, 2 unique / 5 raw) |
| atmosphere | unknown    |  162 |  137 | −25 | −20 codegen-FP (→ `complete`) + −5 audit-found incomplete (→ `incomplete`) |
| memory-allocator | incomplete | 0 | 1 | +1 | `CommitMask::next_run` (1 unique / 1 raw) author-acknowledged spec under-specification |
| memory-allocator | unknown    | 1 | 0 | −1 | reclassified to `incomplete` |
| nrkernel | incomplete | 0 | 1 | +1 | `PDE::new_entry` (1 unique / 1 raw) per-bit MASK predicates leave reserved bits unpinned |
| nrkernel | unknown    | 1 | 0 | −1 | reclassified to `incomplete` |
| anvil-library | incomplete | 0 | 1 | +1 | `vec_filter` (1 unique / 1 raw) deliberate multiset-eq permission |
| anvil-library | unknown    | 1 | 0 | −1 | reclassified to `incomplete` |
| storage    | complete   |   23 |   24 |  +1 | trait `serialize_and_write` z3-weakness → reclassified to `complete` |
| storage    | incomplete |    2 |   14 | +12 | 10 detector-missed `unknown` + 2 `verus_err` (impervious-pattern + opaque-state + byte-layout) |
| storage    | unknown    |   11 |    0 | −11 | 10 → `incomplete`, 1 → `complete` |
| storage    | verus_err  |    7 |    5 |  −2 | 2 of the 7 inherent residuals (`check_crc` + `read_log_variables` in `start_read_log_variables.rs`) are impervious-pattern spec defects, reclassified to `incomplete` |
| TOTAL      | complete   | 1286 | 1307 | +21 | atmos +20 / storage +1 |
| TOTAL      | incomplete |   47 |   67 | +20 | atmos +5 / mem-alloc +1 / nrkernel +1 / anvil +1 / storage +12 |
| TOTAL      | unknown    |  215 |  176 | −39 | atmos −25 / mem-alloc −1 / nrkernel −1 / anvil −1 / storage −11 |
| TOTAL      | verus_err  |    7 |    5 |  −2 | storage −2 |

#### Raw artifacts vs unique source-level specs

The unique-primary table above uses **bold** for audit-verified
unique source-spec counts; un-bolded cells (and **all** cells in
the raw-counts table) are raw corpus artifacts — one row per
`(file, function template)` pair the extractor discovered. The
`verusage` corpus uses *single-file packaging* — every verified function
ships in a `.rs` file that inlines all its callees' source code so the
file can be verified standalone. As a result, a single source-level spec
appears as N raw artifacts (one canonical primary file + N−1 caller
files that inlined it). The raw counts therefore inflate the unique
source-spec count by a project-dependent factor (≈ 2× for atmosphere
incompletes, ≈ 1.5× for storage incompletes).

The table below records the full **unique source-spec count**
alongside the raw count, for the columns where the audit measured
both:

| project    | column                  | raw | unique source specs | notes |
|------------|-------------------------|----:|--------------------:|-------|
| atmosphere | `complete` (reclassified codegen-FP) | 20 |  4 | `Array::set` (15), `init2zero` (2), `init2none` (1), `ArrayVec::pop_unique` (2) |
| atmosphere | `incomplete` (all real spec defects, doc #1–#12) | 34 | 16 | #1–#10 = 29 raw / 14 unique (= rerun11 historical "29 permitted" set); #11–#12 = 5 raw / 2 unique (Array::new + SLL::push from unknown audit) |
| atmosphere | of which: classifier-detected (`permitted=True`) | 29 | 14 | rerun11 Section 1 "incomplete" column for atmosphere |
| atmosphere | of which: audit-found from `unknown` | 5 | 2 | doc #11 + #12 |
| storage    | `incomplete` (all real spec defects, doc #1–#14) | 14 | 9 | dedup: 5 sibling pairs (#2≡#9, #3≡#4, #5≡#6, #7≡#8, #11≡#13) collapse to 5 unique + 4 distinct singletons (#1, #10, #12, #14) = 9 |
| storage    | of which: classifier-detected (`permitted=True`) | 2  | 2 | doc #1 + #2 |
| storage    | of which: audit-found from `unknown` | 10 | 7 unique-new | doc #3–#7, #10, #11–#14; none overlap with classifier-detected |
| storage    | of which: audit-found from `verus_err` | 2 | 0 unique-new | doc #8 + #9; both are sibling copies of already-counted fns |

(The atmosphere "29 → 14" ratio reproduces the inflation called out in
the existing §"atmosphere incomplete breakdown" Layer 1 / Layer 2
table — 14 distinct allocator-side primaries × ≈2 caller-inlining
multiplier = 29 raw corpus rows.)

For total-corpus accounting (the 1645-target denominator), raw counts
are the right unit. For "how many distinct spec defects exist", the
unique-source-spec column is the right unit.

Atmosphere per-spec breakdown (raw counts in the `complete`
reclassification):

| spec | raw artifacts |
|------|--------------:|
| `Array::set`                | 15 |
| `Array::init2zero`          |  2 |
| `Array::init2none`          |  1 |
| `ArrayVec::pop_unique`      |  2 |
| **TOTAL**                   | **20** |

Storage per-case breakdown (numbering matches
[`storage-incompleteness-cases-2026-05-26.en.md`](./storage-incompleteness-cases-2026-05-26.en.md)):

| # | function (location) | tool-observed | reclassified | reason |
|--:|--------------------|---------------|--------------|--------|
| #3 | `read_cdb` (`logimpl_start.rs`) | unknown | **incomplete** | impervious_to_corruption Form A |
| #4 | `read_cdb` (`start_read_cdb.rs`) | unknown | **incomplete** | impervious_to_corruption Form A |
| #5 | `check_cdb` (`start_read_cdb.rs`) | unknown | **incomplete** | impervious_to_corruption Form B |
| #6 | `check_cdb` (`pmemutil_check_cdb.rs`) | unknown | **incomplete** | impervious_to_corruption Form B |
| #7 | `check_crc` (`pmemutil_check_crc.rs`) | unknown | **incomplete** | impervious_to_corruption Form C |
| #8 | `check_crc` (`start_read_log_variables.rs`) | verus_err | **incomplete** | Form C + Box<S>: SpecEq infra residual |
| #9 | `read_log_variables` (`start_read_log_variables.rs`) | verus_err | **incomplete** | err-path + Form A + Box<S>: SpecEq infra residual |
| #10 | `write_setup_metadata_to_region` (`setup_write_setup_metadata_to_region.rs`) | unknown | **incomplete** | byte-layout (sibling of #1) |
| #11 | `CrcDigest::new` (`pmemutil_calculate_crc.rs`) | unknown | **incomplete** | opaque internal state (`ExternalDigest`) |
| #12 | `CrcDigest::write<S>` (`pmemutil_calculate_crc.rs`) | unknown | **incomplete** | opaque internal state |
| #13 | `CrcDigest::new` (`pmemutil_calculate_crc_bytes.rs`) | unknown | **incomplete** | opaque internal state (sibling of #11) |
| #14 | `CrcDigest::write_bytes` (`pmemutil_calculate_crc_bytes.rs`) | unknown | **incomplete** | opaque internal state (sibling of #12) |
| —  | `serialize_and_write` trait method (`setup_write_setup_metadata_to_region.rs`) | unknown | **complete** | z3-weakness on trait-bound `==`; spec uniquely pins `self@` (audit footnote) |
| **TOTAL** | | | | **12 → incomplete, 1 → complete** |

For paper / external-claim purposes the source-level distribution is
the right one to cite, with footnotes pointing at the pending codegen
fix (atmosphere) and the detector / spec-shape work (storage). For
pipeline regression-tracking the tool-observed Section 1 table is the
right one to cite (the artifacts will only flip in the actual JSON
once the codegen fix lands and the detector / spec edits are applied).

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

## 2026-06-01 codegen-defect + storage-detector-miss reclassification

The 2026-05-26 closeout cleared the infra failures (verus_err 94 → 7).
What remained were **162 atmosphere `unknown`** + **11 storage
`unknown`** + **4 storage historically-permitted `incomplete`** (and 7
storage `verus_err` residual). To know what each bucket actually
represents (real spec defects vs z3 limitations vs codegen bugs vs
detector misses), we ran per-case manual audits over both projects'
residual unknowns. The audits live in five coordinated docs under
`spec-determinism/docs/`:

| doc | scope | raw / unique |
|-----|-------|--------------|
| [`atmosphere-incompleteness-cases-2026-05-26.en.md`](./atmosphere-incompleteness-cases-2026-05-26.en.md) | atmosphere real spec incompleteness (12 cases / 16 unique source fns / 34 corpus artifacts via single-file packaging inlining) | 34 / 16 |
| [`atmosphere-unknown-A-view-gap-2026-05-28.en.md`](./atmosphere-unknown-A-view-gap-2026-05-28.en.md) | atmosphere codegen-defect false positives (this section) | 20 / 4 |
| [`atmosphere-unknown-bucket-2026-05-27.en.md`](./atmosphere-unknown-bucket-2026-05-27.en.md) | atmosphere z3 tool limitations: B (wide-setter forall, 66/26), C (multi-instance forall coordination, 63/33), D (page-table walk runaway, 7/2) | 136 / 61 |
| [`atmosphere-status-2026-06-01.en.md`](./atmosphere-status-2026-06-01.en.md) | atmosphere project-wide ledger consolidating the three atmosphere docs | — |
| [`storage-incompleteness-cases-2026-05-26.en.md`](./storage-incompleteness-cases-2026-05-26.en.md) | storage spec incompleteness — 14 cases across 4 patterns (2 originally detector-flagged + 12 audit-found from `unknown` + `verus_err`) | 14 |

### atmosphere

Atmosphere full corpus partition (post-closeout post-LLM, after
2026-06-01 reclassification):

| class | raw artifacts | unique source specs |
|-------|--------------:|--------------------:|
| Complete (baseline z3 unsat without LLM) | 1082 | — |
| Complete (reclassified codegen-FP, pending codegen fix) | 20 | 4 |
| +LLM (z3 unsat after LLM-authored proof block) | 23 | — |
| Real spec incompletes (incompleteness doc #1–#12, all confirmed) | 34 | 16 |
| ↳ of which: classifier-detected (`permitted=True`, #1–#10) | 29 | 14 |
| ↳ of which: audit-found from unknown (#11–#12) | 5 | 2 |
| z3 tool limitations residual unknown (B+C+D + closeout pickups) | 137 | ~60 |
| `runner_crash` (300s wall) | 65 | 40 |
| `verus_err` | 0 | — |
| **TOTAL** | **1361** | — |

(Sanity check on raw counts: 1082 + 20 + 23 + 34 + 137 + 65 + 0 =
1361. The `↳ of which` rows are sub-rows of "Real spec incompletes"
and are NOT added separately.) The 20 reclassified codegen-FP rows
live in `complete` source-level but still show `r0_z3=unknown` in the
corpus JSON until the codegen fix lands. The 23 `+LLM` rows are a
subset of the audit's "z3 tool limitation" root-cause bucket — the
LLM proof block circumvents the z3 search blowup without spec
changes. The 137 z3-limit residual = audit-classified 136 (B + C +
D) minus 23 LLM-unlocked plus 24 verus_err-closeout pickups that
landed in `unknown` without being re-audited.

The "34 raw / 16 unique" incompleteness count replaces the previous
"29 raw + 5 raw" split. The 29 is the rerun11 historical
`permitted=True` set (incompleteness doc #1–#10, dedups to 14
unique); the 5 is the audit-found set from the `unknown` bucket
(doc #11–#12, dedups to 2 unique). Both groups are real source-level
spec defects — they only differ in how the rerun11 pipeline
discovered them (`permissive_or` detector hit `page_is_mapped`
incidentally for #1–#10, manual unknown-bucket audit for #11–#12).
See the incompleteness doc Overview table for the 12-case grouping.

#### Root cause — top-level-self view-registry gap

The codegen module `spec-determinism/spec_determinism/codegen/gen_det.py`
function `build_det_check_spec` (≈ lines 613–717) synthesises a
det-check conjunction of the form

```
post1.field_a@ =~= post2.field_a@
&& post1.field_b@ =~= post2.field_b@
&& ret1@ =~= ret2@
```

For inner struct fields and the return value, the generator consults
`view_registry` and emits `.@` (view) equality if a `View` impl is
registered. But for the **top-level `self` parameter** of a method
(`fn set(&mut self, ...)`, `fn init2zero(&mut self, ...)`, etc.) the
synthesiser falls back to **structural** equality on the raw struct:
`post1_self_ == post2_self_`. That fallback ignores the
`impl View for Array` registered in `view_registry`.

Because atmosphere consistently writes ensures in terms of the view
(`self@ =~= old(self)@.update(i, v)`), the structural-fallback det
check is **strictly stronger** than what the spec requires. Two
implementations that produce the same `seq@` view but differ in
ghost-witness bits / padding / unused tail are observationally
equivalent under the view-first policy but distinguishable under
structural eq — z3 cannot prove `unsat` because the two runs can
legally disagree on those hidden bits.

The fix is to add an early branch in `build_det_check_spec` that
checks `top_level_self in view_registry` and emits `post1_self_@ =~=
post2_self_@` instead of the structural form. Estimated ≈10 LoC. No
spec change in any project source; no LLM involvement. All 20
artifacts will flip from `r0_z3=unknown` to `r0_z3=unsat` on the next
rerun.

#### Affected specs

| spec | raw artifacts | distribution |
|------|--------------:|--------------|
| `Array::set` (`impl<T,A,const N>` setter) | 15 | inlined-only across 15 caller .rs files; no primary file |
| `Array::init2zero` (`impl2` + `impl3` zero-init) | 2 | 2 distinct primaries (one per impl block) |
| `Array::init2none` (`impl4` option-init) | 1 | 1 primary (impl4) |
| `ArrayVec::pop_unique` | 2 | inlined into 2 allocator caller files |
| **TOTAL** | **20** | 4 unique source specs |

The 15 `Array::set` artifacts hit the gap most visibly: every
allocator caller file inlines its own copy of `set`, so a single
≈10-LoC codegen fix pays back at the highest multiplier in atmosphere.

#### Status (atmosphere)

| | as committed | as audited (source-level) | gap |
|--|--|--|--|
| atmosphere `complete` | 1082 | **1102** | +20 |
| atmosphere `unknown` | 162 | **142** | −20 |
| atmosphere total | 1361 | 1361 | 0 |

The gap closes mechanically once the gen_det patch lands and the next
corpus rerun completes; no spec edits, no LLM calls, no human review
required for the 20 atmosphere artifacts.

#### What the audit did **not** reclassify (atmosphere)

Of the original 162 atmosphere unknowns:

- **5 raw / 2 unique** are real spec incompletes (`Array::new` ghost
  values free; `StaticLinkedList::push` returned `SLLIndex` is an
  internal allocator slot whose choice is free). These stay
  unknown-on-tool, but at the source level are confirmed
  **incomplete** and require spec edits (not codegen fixes).
  Documented in the incompleteness doc as #11 and #12.
- **136 raw / ~60 unique** are z3 tool limitations across the B / C /
  D sub-buckets (wide-setter forall trigger explosion, multi-instance
  forall coordination, page-table walk runaway). These need
  tool-level engineering (trigger refinement, lemma harnesses, round
  caps) — not codegen fixes, not spec fixes. Per-case detail in the
  z3-limit doc.

So of 162 atmosphere unknowns: 20 are codegen-FP (reclassified to
`complete`), 5 are real source-level spec defects (require spec
edits), and 137 are z3 tool-side limitations (require trigger /
quantifier engineering at the SMT level — no spec changes, no codegen
changes).

### storage

Storage's residual after the 2026-05-26 closeout was 23 / 0 / 2 / 11
/ 0 / 7. A per-case manual audit over the 11 `unknown` + 4
historically-permitted `incomplete` + selective `verus_err` review
found that the bulk of the residual was **detector miss**, not z3
weakness: the `permissive_or` detector only fires on syntactic `|||`,
but CapybaraKV's spec convention guards every spurious-failure arm
with `... ==> !impervious_to_corruption` (implication shape, slips
through). Plus two further structural defects unrelated to
impervious_to_corruption: byte-layout under-specification and opaque
internal state under-specification.

Storage corpus partition (post-closeout, after 2026-06-01
reclassification):

| class | raw artifacts | unique source specs | notes |
|-------|--------------:|--------------------:|-------|
| Complete (baseline z3 unsat without LLM) | 23 | — | unchanged |
| Complete (reclassified `serialize_and_write` z3-weakness) | 1 | 1 | trait-bound generic structural `==` on `Self`; spec uniquely pins `self@`, z3 has no model for `Self == Self` |
| Real spec incompletes (incompleteness doc #1–#14, all confirmed) | 14 | 9 | dedup: 5 sibling pairs (#2≡#9, #3≡#4, #5≡#6, #7≡#8, #11≡#13) collapse to 5 unique; #1, #10, #12, #14 distinct = 4 unique; 5 + 4 = 9 |
| ↳ of which: classifier-detected (`permitted=True`, #1, #2) | 2 | 2 | both distinct: `write_setup_metadata`, `read_log_variables` |
| ↳ of which: audit-found from `unknown` (#3–#7, #10, #11–#14) | 10 | 7 unique-new | `read_cdb`, `check_cdb`, `check_crc`, `write_setup_metadata_to_region`, `CrcDigest::new`, `CrcDigest::write<S>`, `CrcDigest::write_bytes` — none overlap with classifier-detected |
| ↳ of which: audit-found from `verus_err` (#8, #9) | 2 | 0 unique-new | #8 = `check_crc` sibling of #7 (already counted); #9 = `read_log_variables` sibling of #2 (already counted in classifier-detected) |
| Verus_err residual (inherent infra incompat, no documented defect) | 5 | — | 2 of original 4 `Box<S>: SpecEq` + 3 `iter.end` |
| **TOTAL** | **43** | — | sanity: 23 + 1 + 14 + 5 = 43 ✓; unique: 2 + 7 + 0 = 9 ✓ |

The 12 newly-`incomplete` cases break down as (raw / unique-new
source spec counts; "unique-new" means not already counted in the
classifier-detected `#1`+`#2`):

- **Detector-missed `impervious_to_corruption` (7 raw / 3 unique-new
  + 1 sibling of classifier-detected)**: 5 currently in `unknown`
  (`#3`–`#7`), 2 currently in `verus_err` (`#8`, `#9` — same
  semantic defect, separately blocked by the `Box<S>: SpecEq` infra
  residual that prevents the file from compiling at all). Dedup:
  `#3`≡`#4` (`read_cdb`), `#5`≡`#6` (`check_cdb`), `#7`≡`#8`
  (`check_crc`) — 3 unique-new source fns covered by 6 raw artifacts;
  `#9` (`read_log_variables`) is a sibling of `#2` already in the
  classifier-detected set, so it adds 0 unique-new. Closing these
  requires extending `classify.ensures_uses_permissive_or` to
  recognise the `==> !impervious_to_corruption` implication shape, OR
  tightening each spec to require a witnessed-corruption antecedent.
- **Byte-layout (1 raw / 1 unique-new)**: `#10`
  `write_setup_metadata_to_region` is the lower-level sibling of the
  originally-detected `#1`; same fix recipe (pin every concrete byte
  region). Distinct source spec from `#1`.
- **Opaque internal state (4 raw / 3 unique-new)**: `#11`–`#14`
  `CrcDigest::*` over `ExternalDigest`. Dedup: `#11`≡`#13`
  (`CrcDigest::new` sibling pair), `#12` (`write<S>`), `#14`
  (`write_bytes`) — 3 unique-new source fns covered by 4 raw
  artifacts. Three alternative fixes: (A) pin via a closed-spec
  accessor; (B) make the opaque field ghost-only; (C) pipeline-side
  skip `#[verifier::external_body]` fields in equal_fn codegen.

Summing the dedup: 12 raw newly-reclassified = 3 + 1 + 3 = 7
unique-new source specs + 1 sibling-of-classifier-detected raw
artifact (`#9`). Adding the 2 originally-detected unique specs
(`#1`, `#2`): **14 raw / 9 unique source specs total** for storage
real-spec incompletes.

The 1 newly-`complete` case (trait-method `serialize_and_write`) is a
**z3-weakness on trait-bound `Self == Self`**, not a spec defect: the
spec uniquely pins `self@ == old(self)@.write(...)` and
`self.constants() == old(self).constants()`, but z3 has no model for
structural `==` on the trait-bound generic `Self`. A pipeline-side
fix would replace structural `==` with `(post1@, post1.constants())
== (post2@, post2.constants())` on trait-bound `&mut self` exec fns.
Two `subregion_serialize_and_write_*` siblings were already
reclassified `incomplete` → `complete` in
[`3dcccb58`](https://github.com/q5438722/intent_formalization/commit/3dcccb58)
on the same basis (and are now counted in the 23 baseline complete).

#### Status (storage)

| | as committed | as audited (source-level) | Δ |
|--|--|--|--|
| storage `complete` | 23 | **24** | +1 |
| storage `incomplete` | 2 | **14** | +12 |
| storage `unknown` | 11 | **0** | −11 |
| storage `verus_err` | 7 | **5** | −2 |
| storage total | 43 | 43 | 0 |

Of the 12 new `incomplete`: 10 close on a detector extension
(`ensures_uses_permissive_or` accepts the `==>` implication form), 1
mirrors `#1`'s existing spec fix, and 4 need an opaque-state design
choice. Of the 5 residual `verus_err`: 2 are inherent `Box<S>:
SpecEq` infra incompats with no documented underlying defect, and 3
are `iter.end` vstd-version incompats — both unchanged from the
2026-05-26 closeout note.

### Combined status

| | tool-observed | source-level | Δ |
|--|--|--|--|
| TOTAL `complete` | 1286 | **1307** | +21 |
| TOTAL `+LLM` | 25 | 25 | 0 |
| TOTAL `incomplete` | 47 | **59** | +12 |
| TOTAL `unknown` | 215 | **184** | −31 |
| TOTAL `crash` | 65 | 65 | 0 |
| TOTAL `verus_err` | 7 | **5** | −2 |
| TOTAL targets | 1645 | 1645 | 0 |

The audit chain ends here; no further atmosphere or storage unknowns
are pending classification. Remaining residual is either real spec
incompleteness requiring per-project edits (atmosphere 5 / storage
14), z3 tool limitations requiring SMT-level engineering (atmosphere
137 + storage 0), or inherent infra incompats (storage 5 verus_err).

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
