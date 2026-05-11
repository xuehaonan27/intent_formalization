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

Background batch driver (`scripts/prefill_all.sh`) is rolling through all 7
projects, then `scripts/auto_chain.sh` will auto-fire the corpus rerun with
`--use-view-registry` and produce `results-verusage-viewreg/COMPARE.md`
against the baseline above.

Done so far in the prefill batch:

| project          | uncovered | ok | critic-reject | critic-error |
|------------------|----------:|---:|--------------:|-------------:|
| anvil-library    |         2 |  2 |             0 |            0 |
| memory-allocator |         6 |  6 |             0 |            1 |
| vest             |         0 |  0 |             0 |            0 |
| storage          |        20 | 19 |             1 |            0 |
| nrkernel         |  in flight | … |               |              |
| ironkv           |   pending |    |               |              |
| atmosphere       |   pending |    |               |              |

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

1. **Wait for the in-flight rerun to finish + COMPARE.md** — the
   auto-chain (`scripts/auto_chain.sh`) is already running
   `scripts/rerun_corpus.sh` (the `results-verusage-viewreg/` tree is
   being populated). Once it completes, the same chain will fire
   `scripts/compare_runs.py` and produce the headline A-2-drop
   numbers against the `42c1248` baseline.
2. **Retry the four `_rejected.jsonl` types** once the rerun is
   done — `storage/CrcDigest`, `nrkernel/PTDir`,
   `nrkernel/LoadResult`, plus the freshly-quarantined
   `storage/MaybeCorruptedBytes` (the `arbitrary()` case). Run with
   `--force --project <p>` so each type re-prompts the LLM; the new
   lint + critic rule #8 will gate the second attempt automatically.
3. **Commit `results-verusage/view_registry/`** (currently
   untracked; 130 valid cached entries + per-project audit and
   resolver-audit JSONs + `_rejected.jsonl` durability files).
4. **PR-E**: SCC whole-component prompt for the
   `{Directory, NodeEntry, PTDir}` cycle in nrkernel. Without it,
   the single-type retry on `PTDir` will keep failing for the same
   inner-map-lift reason — the dep's view isn't visible in the
   single-type prompt context.
5. **Integration smoketest for `--use-view-registry`** (ISSUES.md
   #5) — a single-target end-to-end run wired into `make check` or
   equivalent. Would have caught the four broken relative imports
   in `1751dc1` immediately rather than after a manual rerun.
6. **Tracked / Ghost-aware narrows (A-1)** and **nested-Err policy
   (A-3)** are next in line once A-2 lands.

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
