# spec-debug — Handoff Document

Purpose: this file is the entry point for a fresh session to pick up
`spec-debug` development. It summarises what exists, where the wires
run, what has been observed, and what is explicitly open. For richer
narrative, see `README.md` (intent + v0 scope) and
`observations/README.md` (v0 data + analysis).

---

## 1. What is spec-debug

Sibling project to `spec-determinism/`. Takes a **nondeterminism
witness** produced by `spec-determinism` (a committed list of `assume(...)`
statements + the generated `equal_fn`) and drives an LLM to **patch the
Verus spec file** so the gap closes. Explicitly observation-first: v0
was built to *watch* what LLM-generated spec fixes look like and then
design metrics/strategy from data, not theory.

Pipeline:

```
witness (spec-determinism result)   → gap.classify_assumes
  → prompt.build_prompt             → LLM (manual paste / copilot CLI)
  → patch.apply_patch (whole-file)  → verify (= spec-determinism rerun)
  → report.write_report             → runs/<ts>/<crate>__<fn>/report.{json,md}
```

No optimisation loop, no scorer, no automated candidate selection.
Every run is a single prompt, single LLM reply, single patch attempt,
single rerun.

---

## 2. Current state (version map)

| Version | Commit  | What changed                                                              |
|---------|---------|---------------------------------------------------------------------------|
| v0      | `c5fd0f0` | Pipeline scaffolded end-to-end. Generic prompt, no policy awareness.      |
| v0 docs | `eb929b7` | `observations/README.md` published with analysis of 3 nanvix bugs.        |
| v0.1    | `bfc1797` | Policy-aware prompt: surface `equal_fn_def`, split driving/collateral assumes, add layer directive. |

All three commits are on `origin/main`. Nothing else has been pushed to
spec-debug since v0.1.

Install (from repo root):

```sh
cd spec-debug && pip install -e .
# depends on spec-determinism being pip-installed in the same env
```

Run:

```sh
spec-debug run bitmap::new                 # manual-paste LLM (default)
spec-debug run bitmap::new --llm copilot   # copilot CLI backend
spec-debug run bitmap::new --llm copilot --model <x> --effort <x>
spec-debug run bitmap::new --skip-initial-rerun
```

Config: `configs/nanvix.toml` points at the concrete nanvix tree and
reuses `spec-determinism`'s `CorpusConfig` loader (so `crate → src/spec
path` resolution is shared). The abstract nanvix tree is **not** wired
into spec-debug yet — see §5.3.

---

## 3. Code layout

```
spec_debug/
  __init__.py
  cli.py        # argparse entry: `spec-debug run <crate::fn>`
  config.py     # DebugConfig (corpus path + runs_dir), reuses spec-determinism config
  gap.py        # Witness loader + classify_assumes (driving/input/collateral)
  prompt.py     # PROMPT_TEMPLATE + build_prompt(witness) (v0.1 policy-aware)
  patch.py      # apply_patch: write response.md → overwrite .spec.rs whole-file
  verify.py     # rerun: invoke spec-determinism-run; diff before/after assumes
  report.py     # dump report.json + render report.md
  llm/
    base.py     # LLMClient protocol
    manual.py   # prompts user to drop response.md into run_dir
    copilot.py  # CopilotLLMClient: `copilot -p <meta> --allow-all-tools`
observations/
  README.md     # v0 analysis of 3 nanvix cases (read this first)
  v0/           # frozen artifacts: prompt.md / response.md / patch.spec.rs / report.*
configs/
  nanvix.toml   # points at concrete nanvix tree
runs/           # per-invocation timestamped workdirs (prompt + response + report)
```

Key implementation facts that are NOT obvious:

- `verify.py` does NOT invoke `cargo verus` directly; it shells out to
  `spec-determinism-run` and trusts it to run Verus internally. An
  early attempt to call `cargo verus --features ...` ourselves was
  abandoned because the command line is per-crate-arch-specific and
  duplicates logic already in `spec-determinism`.
- Patch application is **whole-file replacement**: the LLM must return
  the entire target `.spec.rs` file. Partial diffs / hunks are not
  supported. We revert to the original before every run so
  spec-determinism sees a clean tree.
- `cli.py` does an implicit `spec-determinism-run <crate::fn>` before
  loading the witness so `full_run.json` has a fresh entry for the
  target. Use `--skip-initial-rerun` to suppress it if you already ran.
- The Copilot CLI backend uses a **meta-prompt** pattern: we write the
  real prompt to `prompt.md`, then tell Copilot via `-p` to read that
  file and write the reply to `response.md`. This avoids parsing
  Copilot's stdout footer. Any model-hosted Copilot CLI with
  `--allow-all-tools --allow-all-paths` support works.

---

## 4. What v0 / v0.1 demonstrated

Three nanvix missing-ensures bugs were run through the pipeline.
Frozen artifacts live in `observations/v0/<fn>/`. Summary (full prose
in `observations/README.md`):

| # | Function                    | Witness | Patch size | Edit layer Copilot chose       | `closed / total` | Verdict         |
|---|-----------------------------|--------:|-----------:|--------------------------------|:---------------:|-----------------|
| 1 | `bitmap::new`               |       8 |      17 KB | New helper spec fn (unwired)   |      0 / 8      | **no-op**       |
| 2 | `slab::from_raw_parts`      |      17 |     3.7 KB | Struct `View::inv()` invariant |      1 / 17     | **wrong layer** |
| 3 | `kernel::from_raw_parts`    |       9 |      13 KB | New `assume_specification` block |    9 / 9      | **suspicious**  |

Three distinct failure modes surfaced:

- **Dangling helper** (#1): LLM writes new spec fns that type-check but
  are never referenced from the target function's `ensures` — semantic
  no-op that looks like a substantial fix.
- **Wrong layer** (#2): edit is in a different AST node (struct
  invariant) than where the missing content belongs (function
  `ensures`).
- **Instrumentation bypass** (#3): new `assume_specification` block may
  have changed which symbol the checker instruments; `rounds=0` on
  rerun is not distinguishable from "genuinely tight spec" without a
  structural before/after diff.

v0.1's prompt rework (policy-aware + layer directive) is the first
mitigation attempt targeting these failure modes, but **it has not
been re-benchmarked against the three cases**. A single bitmap::new
run under v0.1 (`runs/20260424T023353/bitmap__new/`) still shows 8/8
assumes surviving — but n=1, no conclusion.

### Rules out / in (from v0 data)

- ❌ `verify_pass` alone is too weak a scorer — all three patches
  compile.
- ❌ Patch size / minimality as primary signal — the smallest patch
  (slab, 3.7 KB) was the most misdirected.
- ❌ `closed` count alone — case #3 has perfect `closed=9` but the
  edit shape is dubious.
- ✅ Need a **structural check**: is the edit referenced from the
  target function's ensures?
- ✅ Need a **layer check**: which AST node type received the edit?
- ✅ Need a **symbol-stability check**: same schema count, same symbol
  table, before vs after?
- ✅ Score is (at minimum) `(closed_count, structural_flags)` — two
  axes, not one.

---

## 5. Open questions & unfinished work

### 5.1 v0.1 prompt — re-benchmark pending

The policy-aware prompt landed but has only been spot-checked on
`bitmap::new`. Next session should:

1. Re-run all 3 cases under v0.1 prompt and freeze them into
   `observations/v0.1/<fn>/` the same way v0 snapshots work.
2. Update `observations/README.md` (or add `observations/README-v0.1.md`)
   with the diff: does surfacing `equal_fn_def` + driving/collateral
   split change the edit layer Copilot picks? Does it kill the
   dangling-helper failure mode on `bitmap::new`?
3. Decide whether layer-directive language belongs in the system
   prompt or the user prompt (currently it's all in PROMPT_TEMPLATE).

### 5.2 Structural validation metrics (not implemented)

The v0 observation identified three metrics worth implementing but v0.1
**did not implement any of them**. Candidate design:

- **Referenced-from-ensures**: parse the patched `.spec.rs` with
  `tree-sitter-verus`; find all new items (spec fns, axioms, helpers)
  introduced by the patch; for each, check if it is reachable from the
  target function's `ensures` expression. A patch with unreferenced new
  items flips a `has_dangling_helpers=True` flag.
- **Edit layer**: AST-level classifier — did the patch modify
  `fn <target>`'s ensures, the struct `spec_view`, the struct
  invariant (`inv`), a free-standing `assume_specification`, or add
  new items at module scope? Emit a `layer` enum in report.json.
- **Symbol-stability diff**: after the patch, compare
  `det_spec.json.symbols` and `det_spec.json.equal_fn_def` length
  before vs after. If the symbol set shrank dramatically or the
  equal_fn rebuilt, flag `suspected_bypass=True` so case #3's
  `rounds=0` gets disambiguated.

Suggested starting point: add these as post-processing in `report.py`
using already-available `runs/<ts>/.../report.json` before/after
snapshots. Don't try to make them into a scorer yet — just surface
the flags. Ranking is a later-phase concern.

### 5.3 Abstract-tree wiring

`spec-determinism` now supports two nanvix trees (concrete + abstract)
via `configs/nanvix-abstract.toml`. spec-debug currently hard-codes the
concrete tree through its own `configs/nanvix.toml`, which uses
`CorpusConfig` from spec-determinism. Likely small change: accept a
`--config` flag that points at either spec-determinism config and
reuse `CrateConfig.spec` paths as-is. Verify by running
`spec-debug run kernel::layout_to_allocator -c ...abstract.toml`;
the witness there now includes `spec_layout_size(layout) == 0`
assumes from the LLM-discovered projections (see spec-determinism
commit `102125a`), which is a new shape the prompt hasn't been tested
against.

### 5.4 Copilot determinism & stability

Each v0 run was a single shot. For a fix-quality metric that
compares candidates, we need to know whether Copilot is stable enough
to treat "run once, keep the output" as reasonable. Suggested: add a
`--n-samples K` flag to `spec-debug run`; parallel-run the same prompt
K times, diff the responses, record "diffs_char_pct" /
"diffs_closed_count" in the report. If samples are wildly divergent
the pipeline needs to accommodate candidate comparison; if they
converge, v0.1's single-shot is fine.

### 5.5 `observations/v0` case #3 follow-up

The `kernel::from_raw_parts` case produced `rounds=0` on rerun, which
could be either (a) genuinely tight spec or (b) instrumentation
bypass. Neither has been confirmed. Quick experiment:

- Take the v0 patch from `observations/v0/kernel__from_raw_parts/patch.spec.rs`
- Also manually strip the inline `ensures` from `impl Kheap::from_raw_parts`
  in `kheap.rs` on a scratch branch
- Rerun `spec-determinism-run kernel::from_raw_parts`
- If the rerun still shows `rounds=0, closed=9`, the spec is
  genuinely tight and case #3 is a "real" fix; if rounds/schemas
  collapse or the status flips, the assume_specification block was
  shadowing the check all along.

Also worth asking the nanvix spec author whether `errs_equivalent=False`
(the policy that makes `Err.reason` strings part of the equivalence
relation) is really intended for `kernel::from_raw_parts` — realistic
callers of `Kheap::from_raw_parts` probably branch on `.code`, not on
the diagnostic string. If the policy is wrong, case #3's gap is
spurious.

### 5.6 verusage integration (not started)

Original scope in README/JOURNEY called for eventually running on
verusage corpora (Verus-verified functions at large). Zero work done
there; nanvix-only so far. Not urgent.

### 5.7 Iterative / multi-candidate search (explicitly deferred)

v0 scope boundary. Do NOT pick this up before §5.1 + §5.2 produce
concrete data. The ranking signal (`closed_count, structural_flags,
layer`) must exist before an iterative loop makes sense.

---

## 6. Where things live

| Thing                            | Path                                                          |
|----------------------------------|---------------------------------------------------------------|
| spec-debug source                | `spec-debug/spec_debug/`                                      |
| Corpus config                    | `spec-debug/configs/nanvix.toml`                              |
| Frozen v0 case artifacts         | `spec-debug/observations/v0/<fn>/`                            |
| v0 analysis write-up             | `spec-debug/observations/README.md`                           |
| Fresh run artifacts (per-invocation) | `spec-debug/runs/<timestamp>/<crate>__<fn>/`              |
| spec-determinism witness source  | `spec-determinism/results/full_run.json` + `results/artifacts/<crate>__<fn>/det_spec.json` |
| Abstract-tree witness source     | `spec-determinism/results-abstract/...` (not yet consumed)    |

---

## 7. Minimal smoke test for the next session

After cloning + `pip install -e .` in both spec-determinism and
spec-debug:

```sh
# 1) refresh spec-determinism witness (concrete tree)
cd spec-determinism && spec-determinism-run bitmap::new

# 2) run spec-debug v0.1 pipeline with Copilot
cd ../spec-debug && spec-debug run bitmap::new --llm copilot

# 3) inspect
ls runs/$(ls -t runs | head -1)/bitmap__new/
#    prompt.md  response.md  patch.spec.rs  report.json  report.md
cat runs/$(ls -t runs | head -1)/bitmap__new/report.md
```

If the report shows `after_assumes` = `before_assumes` (8 items
unchanged) you're seeing the same v0 dangling-helper failure mode and
the v0.1 prompt upgrade did not rescue this case — that's the open
starting point for §5.1.
