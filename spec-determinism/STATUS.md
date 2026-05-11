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

### Today (2026-05-11, evening update — PR-D4 closed)

| commit    | scope | |
|-----------|---|---|
| `943f59c` | PR-D4 rerun + aggregator fix + ISSUES.md #6 + COMPARE.md case studies | results |
| `a71ff15` | Quarantine 14 broken L4 views (ISSUES.md #7) + lint rule drafts (M1/M2/M3) | quality gate |
| `33bd09a` | `--include-quarantined` skip mechanism + M1/M2/M3 detector sketches (tree-sitter / AST level) | infra + docs |
| `<this>`  | Final PR-D4 numbers + STATUS update | docs |

**Headline numbers (vs `42c1248` baseline):**

| metric | baseline | PR-D4 candidate | Δ |
|---|---:|---:|---:|
| **ok_with_witness (A-2 false positives)** | **376** | **366** | **−10** |
| verus_error | 191 | 190 | −1 |
| ok (clean) | 1455 | 1456 | +1 |
| runner_crash | 1 | 1 | 0 |

**Transition matrix.** 11 clean fixes (`ok_w → ok`), 0 clean
regressions (`ok → verus_error`), 1 soft improvement
(`verus_error → ok_w` on `ironkv/host_model_receive_packet`).
The net witness count `−10` differs from the 11-win prediction
solely because the soft-improvement target adds +1 to witnesses
(was a verus_error in baseline; now compiles with a still-emitting
witness — strictly better than a parse failure). Full per-target
analysis in `results-verusage-viewreg/COMPARE.md`.

**The 11 fixes:** 8 from `memory-allocator/CommitMask` (`Vec<u64>` →
`Seq<u64>` view, fixes 88.9 % of the project's A-2 witnesses), plus
`atmosphere/PageMap`, `ironkv/Constants`, and `nrkernel/ArchExec`.
All follow the same algebraic recipe: parent has `Vec<T>` field(s),
view lifts to `Seq<T>`, z3 closes via the seq-equal axiom.

**The 14 quarantines (PR-D4 ISSUES.md #7):**

| failure mode | count | example |
|---|---:|---|
| **M1** `<X as View>::V` / `self.f@` on a head with no View | 5 | atmosphere/Kernel |
| **M2** `self.f@@` past Ghost into Set/Map | 1 | atmosphere/Endpoint |
| **M3** parent type is `external_body` / `repr(C)` opaque | 2 | ironkv/CKeyHashMap, atmosphere/Registers |
| **M4** semantic V-type mismatch (wrong namespace) | 1 | ironkv/EndPoint |
| cascade (deps on a quarantined root) | 5 | 5 ironkv types transitively view EndPoint |

`docs/critic-criteria.md` carries copy-paste-grade tree-sitter / AST
detector sketches for M1/M2/M3 (PR-D5 candidate work to
implement them; the sticky `.json.quarantine` marker in `33bd09a`
already prevents re-synthesis of any of the 14 broken types).

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

PR-D4 closed cleanly; the A-2 view-aware equal-fn pipeline is now
proven safe at the corpus level (11 wins, 0 regressions). Next:

1. **PR-D5 — implement the M1/M2/M3 lint rules** sketched in
   `docs/critic-criteria.md`. The post-quarantine spike showed
   that 14 broken views slipped past the critic; lint coverage
   would have caught all 14 mechanically. Detectors are
   already specified at tree-sitter / AST traversal level
   (commit `33bd09a`).
2. **PR-E — SCC whole-component prompt** for the
   `{Directory, NodeEntry, PTDir}` cycle in `nrkernel`. Without
   it, the single-type retry on `PTDir` keeps failing for the
   inner-map-lift reason; the dep's view isn't visible in the
   single-type prompt context. Also covers the 5 cascade-quarantined
   ironkv types (`CSingleDelivery`, `CSingleMessage`, etc.) once
   their roots have a correct view.
3. **PR-F — A-1 (Tracked/Ghost-aware narrows)** and
   **PR-G — A-3 (nested-Err policy)** are the remaining axis-1
   improvements once A-2 is fully landed.
4. **Retry the four `_rejected.jsonl` types** —
   `storage/CrcDigest`, `nrkernel/PTDir`, `nrkernel/LoadResult`,
   `storage/MaybeCorruptedBytes`. The new lint + critic rule #8 +
   `--include-quarantined` opt-in mean these can now be safely
   retried without poisoning the cache.
5. **Integration smoketest for `--use-view-registry`** (ISSUES.md
   #5) — single-target end-to-end run wired into `make check` or
   equivalent. Would have caught the four broken relative imports
   in `1751dc1` immediately rather than after a manual rerun.
6. **Commit `results-verusage/view_registry/`** — currently
   untracked; 130 valid cached entries + 14 `.json.quarantine`
   markers + per-project audit JSONs + `_rejected.jsonl`
   durability files. Decision pending on whether to keep them in
   git or under DVC.

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
