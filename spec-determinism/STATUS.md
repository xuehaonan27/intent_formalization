# spec-determinism — STATUS

_Last updated: 2026-05-11_

## What this project does

Given a corpus of Verus exec functions with `ensures` clauses, decide whether
each function is **deterministic with respect to its specification** — i.e.
two executions that agree on the visible inputs cannot produce specifications
that disagree on what the ensures requires.

The pipeline synthesises a per-function `equal_<fn>` and asks Verus to prove
that any pair of pre-states satisfying the ensures must in fact have equal
post-states. When Verus accepts the proof, the function is deterministic.
When Verus produces a counterexample, we record the witness as evidence of
non-determinism.

## Where we are

### Verusage corpus baseline (commit `42c1248`, snapshot 2026-04-29)

| project          |     n |    ok | verus_err | **ok\_with\_witness** |
|------------------|------:|------:|----------:|----------------------:|
| atmosphere       |  1363 |  1262 |       100 |               **289** |
| ironkv           |   214 |   170 |        44 |                **76** |
| memory-allocator |    16 |    15 |         1 |                 **9** |
| nrkernel         |     8 |     6 |         2 |                 **1** |
| vest             |     2 |     2 |         0 |                 **1** |
| storage          |    43 |     0 |        43 |                     0 |
| anvil-library    |     1 |     0 |         1 |                     0 |
| **TOTAL**        |  1647 |  1455 |       191 |               **376** |

`ok_with_witness` = Verus accepted the equal-fn but z3 generated a
counterexample — the **A-2 false-positive metric**. Every one of these 376
is a function we should be proving deterministic but aren't, because our
equal-fn uses structural `==` where the spec only inspects the view.

### Today (2026-05-11)

Closed out Phase 2 (A-2 view-aware equal-fn) end-to-end:

| commit    | scope | |
|-----------|---|---|
| `5ea750b` | PR-A: `view/impl_scanner` — find existing `impl View for X` blocks | L3 |
| `b65d37f` | PR-B: `view/registry` — L1 prelude + L2 alias + L3 impl scanner, no LLM | resolver |
| `5a67804` | PR-C: thread `ViewRegistry` into `gen_det` / `single_file` / `verusage_run` | integration |
| `f094843` | PR-D1: `view/llm` — Copilot-CLI L4 synthesiser + on-disk cache + CLI | L4 |
| `1f7a245` | PR-D2: L4 wired into `ViewRegistry`; `gen_det` injects `impl View` prelude before the equal-fn | wiring |
| `226d93f` | refactor: `spec_determinism/` → 5 functional subpackages (extract / codegen / verus / corpus / view) | hygiene |
| `ab5f5d6` | refactor: shared `spec_determinism.llm.copilot.CopilotCLI` (was duplicated in view + codegen) | hygiene |
| `f47125f` | **codex-backed critic pass** on every LLM-generated view; reject → `_rejected.jsonl`, revise → cached with issues recorded | quality gate |
| `aaa4059` | `scripts/prefill_all.sh` — sequential driver for all 7 verusage projects | infra |
| `aa0744e` | `view/llm`: fine-grained `status_out` (cache_hit / ok / llm_fail / parse_fail / validate_fail / critic_reject) + `scripts/rerun_corpus.sh` + `scripts/compare_runs.py` | infra |
| `7531eeb` | `scripts/auto_chain.sh` — wait-for-prefill → rerun → compare automation | infra |
| `1751dc1` | fix: 4 cross-subpackage relative imports silently broken by the layout refactor (caught by manual smoketest) | bug |
| `a343a56` | docs: COMPARE.md template + tricky-shape audit + ISSUES.md (4 + 1 entries, including the newly-found `arbitrary()` over-collapse) | docs |
| `ad691cd` | **lint: `view body must reference self`** static check + critic prompt rule #8 + `docs/critic-criteria.md` | quality gate |
| _next_   | compare_runs.py header rows + true-regression bucket + e2e retry-path selftest | infra |

### Currently running

_(none — PR-D4 landed cleanly; corpus rerun + COMPARE.md are committed)_

### Today (2026-05-11, evening update — PR-D5 closed)

| commit    | scope | |
|-----------|---|---|
| `943f59c` | PR-D4 rerun + aggregator fix + ISSUES.md #6 + COMPARE.md case studies | results |
| `a71ff15` | Quarantine 14 broken L4 views (ISSUES.md #7) + lint rule drafts (M1/M2/M3) | quality gate |
| `33bd09a` | `--include-quarantined` skip mechanism + M1/M2/M3 detector sketches (tree-sitter / AST level) | infra + docs |
| `4cd29b4` | PR-D4 final numbers + STATUS update | docs |
| `e61a504` | **PR-D5: M1/M2/M3 lint impl + retroactive scan + 4 new quarantines** | quality gate |

### Today (2026-05-12 — PR-F + PR-G closed)

| commit    | scope | |
|-----------|---|---|
| `<this>`  | **PR-F: A-1 Tracked/Ghost/PointsTo TypeKinds + narrow strategies + schema enumeration** | axis-1 |
| `<this>`  | **PR-G: A-3 nested-Err policy for `Seq<Result<…>>` / `Map<_, Result<…>>`** | axis-1 |

**PR-G — nested-Err policy lift.** The bug: `build_equal_expr` had
`TypeKind.SEQ` in the primitive-`==` list, so `Seq<Result<U, Err>> ==
Seq<Result<U, Err>>` compared `Err` payloads structurally even with
`errs_equivalent=True`. Same root for `Map<K, V>` (fell through the
UNKNOWN `==` branch). Fix: new `_contains_result(ty)` /
`_container_needs_elementwise(ty, policy)` helpers; explicit SEQ
branch emits `len ==` + `forall|i: int| 0 <= i < len ==> elem_eq`
when the element contains Result and the policy collapses Err.
Explicit MAP branch emits `dom ==` + `forall|k: K| dom.contains(k)
==> val_eq` when value contains Result. Top-level Result and
Result-in-Result already worked via existing recursion.
`TypeKind.SET` is left at raw `==` (no positional indexing; lifting
errs-equivalence element-wise would require a custom set-equivalence
relation — recorded as a known limitation in the branch comment).

**PR-F — Tracked/Ghost/PointsTo narrows + equality.** Three new
`TypeKind` variants (`TRACKED`, `GHOST`, `POINTS_TO`). Extractor
`_KNOWN_GENERICS` table extended; `_parse_type_node`'s `generic_type`
branch now (a) accepts `scoped_type_identifier` as a name node and
(b) strips module-path scope + `<…>` suffix before lookup, so
`vstd::pcell::Tracked<T>` is recognised. Two new narrow strategies:
`narrow_tracked_or_ghost` projects via `(var)@` and recurses on the
inner type; `narrow_points_to` probes `(var).is_init()` (bool),
`(var).value()` (V, only meaningful when `is_init()`), `(var).addr()`
(usize). `build_equal_expr` gained TRACKED/GHOST and POINTS_TO
branches with corresponding equality structure (recurses on inner so
PR-G policy rules apply through wrappers — e.g. `Ghost<Seq<Result<…>>>`
now lifts errs-equivalence correctly). Schema enumeration in
`schema_search/schemas.py` extended for the same three kinds so
narrow assumes have a schema to hit — without this, narrows would
emit `pass_untranslatable` and witnesses would stay partial.

**Self-test infrastructure.** `narrow.py` and `gen_det.py` each
gained `_run_self_tests` + `if __name__ == "__main__"` entry points
(invoke with `python -m spec_determinism.{extract.narrow,
codegen.gen_det} test`). gen_det's suite covers PR-G (Result,
Seq<Result>, Map<_, Result>, Seq<u32>, Map<int, u32>,
Result<Seq<Result>>, Struct with Result field, self-ref no-loop) and
PR-F (Tracked<u32>, Ghost<Seq<u32>>, PointsTo<u32>) plus interaction
fixtures (`Ghost<Result<…>>`, `Tracked<Seq<Result<…>>>`).
narrow.py's suite uses a stub SearchContext that records assumes
without invoking Z3.

**Regression check.** Nanvix smoke (`bitmap::number_of_bits`) still
`ok`. Existing serialised `det_spec.json` artifacts unaffected (old
`Tracked<…>` was previously stored as `TypeKind.UNKNOWN` with
`name="Tracked<…>"`, so JSON round-trip still deserialises
cleanly; new kinds only appear in freshly extracted specs).

**Deferred (A-1 follow-up).** Newtype-of-`usize` unwrap (e.g.
`struct ProcPtr(usize);`) — needs cross-file type resolution; not
required for the Tracked/Ghost/PointsTo cohort.

### Today (2026-05-12 — PR-E closed)

| commit    | scope | |
|-----------|---|---|
| `<this>`  | **PR-E: M4 self-recursive view lint + Option C/B/A prompt guidance** | quality gate |

**Pre-PR-E reality check** (`/tmp/discover_sccs.py` across all 9
verusage projects): only **one** non-trivial multi-type SCC in the
whole corpus — `{Directory, NodeEntry}` in nrkernel, both **already
covered** via L4 cache. The original PR-E scope ("SCC whole-component
prompt") had no real target. The remaining problem is `T` referencing
`T` (self-recursion via container generics), which is what PR-E
v2 addresses.

Nanvix regression sweep before PR-E: **15/15 ok, 0 regressions** — the
post-PR-D5 subpackage layout has no fallout on the kernel corpus.

**PR-E outcome — M4 detector + recursive-view prompt guidance:**

* New static lint `check_m4_self_recursion_bare_at` in `view/llm.py`.
  Catches the PTDir bug class: type declares V with `T@`-lifted inner
  (e.g. `Seq<Option<TView>>`) while the body writes bare `self.f@` —
  but `<Seq<Option<T>> as View>::V = Seq<Option<T>>` (identity), so the
  inner View is never applied and the equal-fn collapses.
* `lint_view_decl` priority is now **M3 > M2 > M4 > M1**. M4 is more
  specific than M1 and emits a more useful suggestion.
* New status code `lint_m4_reject` wired through `synthesize_view`
  status_out and `prefill_project`'s status-mapping tuple.
* Prompt header (`_VIEW_SCHEMA_DOC`) gained a ~80-line
  "Self-recursive types" section documenting Option A (recursive lift,
  expensive), Option B (V mirrors concrete inner), Option C
  (`type V = Self`, cheapest). Cost-and-when-to-use guidance encoded.
* `build_view_prompt` injects a self-recursion alert block immediately
  before the schema doc whenever `_is_self_recursive(td)` is True, so
  the LLM sees a concrete callout (with offending field names) rather
  than only the generic schema text.
* `_FEW_SHOT` extended with a Tree (Option C) example.
* New critic rule #9 in `view/critic.py` as semantic backstop.
* ~150 lines of M4 self-tests (PTDir Option A buggy → reject;
  Options A-correct / B / C → accept; non-recursive → skip;
  priority M3>M4 and M4>M1).

**Retroactive scan on PR-D5 cache (7 projects, 112 active views,
19 quarantined):**

* **0 active-cache rejections.** M4 has no FP across the corpus.
* PTDir (the bug class M4 was designed for) lives in
  `nrkernel/_rejected.jsonl`, not active cache, so this is expected.
* `--include-quarantined` scan retrips the existing M1/M3 quarantines
  exactly as before; M4 does not fire on any quarantine (the 19
  quarantines are M1/M2/M3/M4-semantic/cascade, none are
  self-recursive bare-@ bugs).

**Headline corpus numbers — unchanged.** PR-E is preventive: it
hardens the synthesis pipeline against a bug class that already
manifested on PTDir (caught by critic, lives in `_rejected.jsonl`).
The 376→366 (−10 witnesses, 0 regressions) PR-D4/D5 numbers hold.

PTDir LLM retry with the new prompt is left as a follow-up.

**PR-D5 outcome — M1/M2/M3 lints implemented & wired:**

* All three detectors live in `view/llm.py` (`check_m1_view_targets_have_view`,
  `check_m2_no_double_at_past_ghost`, `check_m3_parent_not_opaque`),
  plus the priority aggregator `lint_view_decl` (M3 > M2 > M1).
* Wired into `synthesize_view` between the existing
  `check_view_body_uses_self` lint and the codex critic, with new
  `lint_m{1,2,3}_reject` status codes plumbed through the prefill
  summary's coarse action labels.
* `lint-scan` CLI sub-command performs retroactive lint on every
  cached view in a project, writes a JSON report, exits 1 on
  rejection (for CI wiring).
* 30+ self-tests in `_run_self_tests` covering each detector,
  priority order, and the FP-regression pins (Container, KeyIterator,
  IronfleetIOError, WritablePersistentMemorySubregion, unit-V collapse).

**Retroactive scan on PR-D4 cache (7 projects, 112 active views, 18
quarantined):**

| project | active | active reject | quarantined | reject (incl.) |
|---|---:|---:|---:|---:|
| anvil-library | 2 | 0 | 0 | 0 |
| atmosphere | 23 | 0 | 5 | 1 (M1) |
| ironkv | 28 | 0 | 12 | 11 (M1=9, M3=2) |
| memory-allocator | 6 | 0 | 0 | 0 |
| nrkernel | 36 | 0 | 0 | 0 |
| storage | 17 | 0 | 2 | 2 (M3=2) |
| vest | 0 | 0 | 0 | 0 |

**Active-cache lint emits 0 rejections** after FP iteration. The 4 new
quarantines from the retroactive scan were silent hidden bugs (cached
views that PR-D4 left alone but that wouldn't survive any new target
that referenced them):

| project | type | rule | reason |
|---|---|---|---|
| ironkv | HashMap | M3 | external_body + non-trivial body; inherent `uninterp spec fn view` already exists in source |
| ironkv | ReceiveResult | M1 | cascade through quarantined CPacket |
| ironkv | CTombstoneTable | M1 | cascade through newly-quarantined HashMap |
| storage | ExternalDigest | M3 | external_body + body projects `<Digest as View>::V` |

**Total quarantine count: 14 + 4 = 18.** PR-D4 numbers
(376 → 366 witnesses, 0 clean regressions) unchanged — these 4 views
were never causing PR-D4 regressions (per-target verus_error deltas
confirm), so quarantining them is preventive cleanup.

Three intentional deviations from the original PR-D5 sketch are
documented in `docs/critic-criteria.md` ("PR-D5 — M1/M2/M3 lint
impl" section): M2's `NON_VIEWABLE_INNER_HEADS` is narrowed to
`{FnSpec}` because Set/Seq/Map have identity Views; M3 honours a
unit-V exemption for the documented "legitimate unit collapse"
pattern; M1 honours impl-generic params (`impl<K: View>`) and uses
`ViewRegistry.resolve` rather than a flat name union to build
`known_view_heads`.

### Headline corpus numbers (still vs `42c1248` baseline)

| metric | baseline | PR-D5 candidate | Δ |
|---|---:|---:|---:|
| **ok_with_witness (A-2 false positives)** | **376** | **366** | **−10** |
| verus_error | 191 | 190 | −1 |
| ok (clean) | 1455 | 1456 | +1 |
| runner_crash | 1 | 1 | 0 |
| L4 cached views (active) | 130 | 112 | −18 (quarantined) |

PR-D5 does not change the corpus numbers (PR-D4 closed those). It
hardens the synthesis pipeline so the next prefill batch cannot
silently re-introduce the same broken shapes.

### The 11 fixes (carried forward from PR-D4)

8 from `memory-allocator/CommitMask` (`Vec<u64>` →
`Seq<u64>` view, fixes 88.9 % of the project's A-2 witnesses), plus
`atmosphere/PageMap`, `ironkv/Constants`, and `nrkernel/ArchExec`.
All follow the same algebraic recipe: parent has `Vec<T>` field(s),
view lifts to `Seq<T>`, z3 closes via the seq-equal axiom.

### The 18 quarantines (taxonomy)

| failure mode | count | example |
|---|---:|---|
| **M1** `<X as View>::V` / `self.f@` on a head with no View | 5 | atmosphere/Kernel |
| **M2** `self.f@@` past Ghost into Set/Map | 1 | (legacy; M2 acceptance fixture is now `Ghost<FnSpec>`) |
| **M3** parent type is `external_body` opaque | **4** (+2 new) | ironkv/CKeyHashMap, storage/MaybeCorruptedBytes, ironkv/HashMap, storage/ExternalDigest |
| **M4** semantic V-type mismatch (wrong namespace) | 1 | ironkv/EndPoint |
| cascade (deps on a quarantined root) | **7** (+2 new) | 5 ironkv types transitively view EndPoint; +ReceiveResult, CTombstoneTable |

## Critic step (`view/critic.py`)

After Copilot generates a candidate `impl View` and it passes tree-sitter
parse validation, we run a second model (`codex exec`) for a *semantic*
audit. Verdicts: `accept` / `revise` / `reject` / `error`.

`reject` is durable: the candidate is **not** cached, but the type +
issues are appended to `<cache_root>/_rejected.jsonl` so the rejection
event survives across runs. The next prefill retries the type.

**Real bugs the critic has caught so far (would have shipped without it):**

- `storage/CrcDigest`: used `self.bytes_in_digest@@` — the double-`@`
  over-projects the inner `u8` primitives after Ghost unwrap.
- `nrkernel/PTDir`: `entries: Seq<Option<PTDir>>` viewed as
  `Seq<Option<PTDirView>>` but the body `self.entries@` doesn't actually
  map inner `PTDir` → `PTDirView`.
- `nrkernel/LoadResult`: rejected (specifics in
  `results-verusage/view_registry/nrkernel/_rejected.jsonl`).

**Soft warnings (`accept` with issues) — recurring theme:**

The single most common `revise` / `accept-with-issues` message is

> "Assumes \<DepType\> has a Verus View impl; dependency context marks
> it as uncovered, so this cannot be confirmed here."

i.e. the generator wrote a view that references `<DepType as View>::V`
(or otherwise calls `dep@`) even though the dep's view wasn't supplied
in the prompt. That's an artefact of how `_dep_views_for` builds the
prompt — it only forwards already-resolved deps. The critic correctly
flags the assumption; in practice the dep is later cached and a second
codegen-time lookup resolves it.

## Spot-audit of 6 cached views (samples across kinds)

| project / type | kind | generated view | notes |
|---|---|---|---|
| anvil-library/`TempPred` | generic newtype `TempPred<T>` over `spec_fn` | `type V = spec_fn(Execution<T>) -> bool; view = self.pred` | correctly leaves `T` & `Execution<T>` at identity (no View bound) |
| memory-allocator/`CommitMask` | `[usize; 8]` bitmask | `type V = Seq<usize>; view = self.mask@` | array's built-in view + correct "usize is primitive, no extra @" rationale |
| ironkv/`CMessage` | 6-variant enum with `Option<Vec<u8>>` payloads | parallel `CMessageView` enum; unwraps `Option` manually because `View for Option<T>` is identity in vstd | sophisticated awareness of vstd semantics |
| ironkv/`EndPoint` | `Vec<u8>` wrapper | `type V = Seq<u8>; view = self.id@` | trivial, correct |
| ironkv/`CKeyHashMap` | `HashMap<CKey, Vec<u8>>` wrapper | `Map<CKey, Seq<u8>>` via `self.m@.map_values(|v| v@)` | uses HashMap's view + map_values lift; critic flagged "HashMap view assumed" |
| nrkernel/`Directory` | recursive page-table node | `DirectoryView { entries: Seq<<NodeEntry as View>::V>, … }` via `self.entries.map_values(|e| e@)` | uses associated-type projection for forward-declared dep views |

## Next milestones

PR-D5 hardened the synthesis pipeline (M1/M2/M3). PR-E added M4 +
recursive-view prompt guidance. PR-F + PR-G shipped the two
axis-1 cohorts (Tracked/Ghost/PointsTo + nested-Err policy).
Next:

1. **Full corpus rerun with `--use-view-registry`** to measure
   PR-F + PR-G impact against baseline (376 witness / 191
   verus_error). Expected: A-1 (~29) + A-3 (~30) verus_error drop
   into ok / ok_w. Run via `scripts/auto_chain.sh`; final
   numbers go into `results-verusage-viewreg/COMPARE.md`.
2. **Retry the four `_rejected.jsonl` types** —
   `storage/CrcDigest`, `nrkernel/PTDir`, `nrkernel/LoadResult`,
   `storage/MaybeCorruptedBytes`. The combined M1/M2/M3/M4 lints +
   critic rules #8/#9 + `--include-quarantined` opt-in mean these
   can now be safely retried (PR-E's M4 specifically pre-empts the
   PTDir bug class). Whether the LLM follows the new prompt guidance
   is the open question; a fallback auto-emit Option C path is
   recorded as a contingency.
3. **Integration smoketest for `--use-view-registry`** (ISSUES.md
   #5) — single-target end-to-end run wired into `make check` or
   equivalent. Would have caught the four broken relative imports
   in `1751dc1` immediately rather than after a manual rerun.
4. **Commit `results-verusage/view_registry/`** — currently
   untracked; 112 active L4 entries + 19 `.json.quarantine`
   markers + per-project `_lint_scan.json` + per-project audit
   JSONs + `_rejected.jsonl` durability files. Decision pending on
   whether to keep them in git or under DVC.
5. **Newtype-of-`usize` unwrap (A-1 follow-up)** — `struct
   ProcPtr(usize);` and similar. Needs cross-file type resolution
   so the extractor knows `ProcPtr → usize`. Defer until the rerun
   shows what fraction of remaining A-1 errors are newtype-shaped.

## Layout

```
spec_determinism/
  extract/        # type extraction, narrows, predicates, type registry
  codegen/        # equal-fn generation + equal_policy + policy_llm
  verus/          # single-file invoke wrapper + verify
  corpus/         # batch runners (verusage_run, verusage_summary, run_all, regen_artifacts)
  view/           # Phase 2 view resolver
    prelude.py    # L1
    registry.py   # 4-layer entry point (L1+L2+L3+L4 cache)
    impl_scanner.py  # L3
    llm.py        # L4 synthesiser + prefill CLI
    critic.py     # codex-backed semantic critic pass
  llm/
    copilot.py    # shared CopilotCLI used by view/llm + codegen/policy_llm
  schema_search/  # narrow predicate schema enumeration
scripts/
  prefill_all.sh      # batch L4 prefill across 7 projects
  rerun_corpus.sh     # rerun corpus with --use-view-registry → results-verusage-viewreg/
  compare_runs.py     # baseline vs candidate → A-2 transition tables
  auto_chain.sh       # wait-for-prefill → rerun → compare
results-verusage/
  view_registry/<project>/<Type>.json   # per-type L4 cache (+ critic_verdict / critic_issues)
  view_registry/<project>/_rejected.jsonl  # durable critic-reject log
  view_registry/<project>/_prefill_summary.json
```
