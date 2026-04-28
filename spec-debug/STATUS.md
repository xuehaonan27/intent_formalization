# Spec-Debug — Status Snapshot (2026-04-28)

This is a working summary of where the project stands: what's built, what's
designed, what's been validated by hand, and what we still don't know how
to do well. It is meant to be read alongside `HANDOFF.md` (project layout
and v0 history), `REPAIR-CRITERIA.md` (the prior MDL-based criteria draft),
`METRICS.md` (the current metrics framework), and `EXPERIMENTS.md` (15-patch
audit data).

---

## 1. What's built (pipeline)

End-to-end v0.1 pipeline, working on nanvix:

```
spec-determinism-run <fn>
        │  (witness: assumes + det_check_template + equal_fn)
        ▼
spec_debug.classify_assumes
        │  (driving / collateral split via policy lens)
        ▼
spec_debug.prompt.build_prompt
        │  (witness + classified assumes + spec snippets)
        ▼
LLM (Copilot CLI)
        │  (response.md → patch.spec.rs)
        ▼
apply_patch (whole-file replacement of <crate>.spec.rs)
        │
        ▼
spec-determinism-regen <fn>     ← refresh det_check_template (CRITICAL)
spec-determinism-run <fn>       ← rerun
        │
        ▼
report.json + report.md (before/after assumes, closed/added)
        │
        ▼
revert (cp backup), regen baseline
```

- CLI driver: `spec_debug/cli.py:cmd_run` (~lines 32–85).
- Prompt template: `spec_debug/prompt.py` (v0.1 with "Layering rules" still
  in place — pending the simplification discussed in this round).
- Default config: `~/intent_formalization/spec-determinism/configs/nanvix.toml`
  pointing at `~/nanvix`.
- Three v0 demo cases under `observations/v0/`: `bitmap::new`,
  `slab::from_raw_parts`, `kernel::from_raw_parts`. Reports include
  baseline witness, prompt, response, applied patch, rerun delta.

The pipeline is sound but coarse: whole-file `.spec.rs` replacement, no
proof-annotation edits to `.rs`, no iterative refinement.

---

## 2. What's designed (criteria)

The repair quality criteria are defined in `REPAIR-CRITERIA.md` (five
criteria, four hard gates + one soft ranker) and revised by `METRICS.md`
(this round's discussion).

### 2.1 Source-of-truth criteria — REPAIR-CRITERIA.md

| # | Criterion | Type | Status in this round |
|---|---|---|---|
| 1 | **Soundness** — original impl still verifies against repaired spec | Hard gate | Kept, but **relaxed** to "workspace `cargo verus build` passes" so the LLM may add proof annotations in `.rs`. (See METRICS Axis E.) |
| 2 | **Determinism resolved** — rerun spec-determinism, witness eliminated | Hard gate | Kept; refined to `driving_closed` rather than raw `closed_count`. EXPERIMENTS confirms the refinement matters (bitmap-B1, kheap-K2 close many collateral assumes while driving stays at 0/2). |
| 3 | **No witness constants** — repair AST has no literals from the witness that aren't already in the original spec | Hard gate | Kept in spirit; **demoted to observation flag** in METRICS (Axis D) under the strict/free principle. Worth revisiting. |
| 4 | **Vocabulary subset** — repair uses only symbols already in spec vocab + vstd | Hard gate | Kept in spirit; **demoted to observation flag** in METRICS (Axis B). Same caveat as #3 — should re-examine empirically before committing to demotion. |
| 5 | **Minimality (MDL)** — token-tier cost + structural cost over AST | Soft ranker | **Kept, not yet implemented.** Listed in §6 next steps. |

### 2.2 Revisions and additions made this round (METRICS.md)

- **Organising principle**: spec-determinism is strict / rule-based,
  spec-debug is free / LLM-driven. The relaxations of #3, #4, #1 above
  follow from this — judge the repair by outcome (does it close the gap,
  does the impl verify), not by surface form.

- **New A.1 — policy verdict (gap validity precedes gap closure)**.
  Before scoring `driving_closed`, run a counterfactual by toggling
  spec-determinism's policy knobs (`errs_equivalent`, `opaque_ok`,
  …). If the witness disappears under a relaxed policy, label it
  `policy_spurious` and feed back upstream rather than patching the
  spec. This is the canonical resolution for bitmap::new's OOM-driven
  `(Ok, Err)` (EXPERIMENTS §1).

- **New gate — no impl-side admissions**. Because criterion 1 was
  relaxed to "workspace verifies" (allowing `.rs` edits), there's a new
  cheat path: add `assume(false)` / `admit()` in the impl. The gate
  `no_new_admissions_in_impl` (git-diff check) blocks it.

- **New flag — stability**. Re-running the LLM on the same witness
  should yield close candidates; large variance is a prompt-drift
  signal. (Observation only.)

- **Composite score (current)** — hard gates first
  (`policy_verdict.kind == "valid"`, `impl_still_verifies`,
  `no_new_admissions_in_impl`, `symbol_table_stable`,
  `equal_fn_def_stable`), then lexicographic
  `(driving_closed_ratio, ¬new_witness_driving)`. **MDL ranking goes
  here once implemented** (currently missing — see §6).

### 2.3 Prompt strategy

- Expose goals to the LLM: `driving_closed`, `impl_verifies`,
  `new_witness_driving`.
- Hide police: bypass detection, structural shape rules, literal-bleed
  heuristics stay client-side as gates, not prompt content.
- Pending: drop the "Layering rules" section in `prompt.py`.

---

## 3. What's been validated by hand

`EXPERIMENTS.md` records 15 manually-applied patches: 5 per incompleteness
case, full regen→det→verus cycles, metric scores per patch.

Headline takeaways verified empirically:
- Raw `closed_count` is misleading where driving is preserved (bitmap-B1
  closes 1 collateral, driving 0/2; kheap-K2 closes ~hundreds, driving
  0/2).
- **Only one patch in 15 closed driving** (bitmap-B4: spec-determinism
  declares the function deterministic). It promptly fails Axis E because
  of `RawArray::new`'s `external_body` OOM clause — exactly the
  `policy_verdict` case Axis A.1 was designed to flag.
- New driving witnesses recur with the same shape (slab S1/S2/S5),
  validating `new_witness_driving` as a useful signal.
- Patches generated by manual reasoning hit the same trap as expected of
  LLM patches: wrong axis (kheap K1-K5 all targeted Err.reason while
  current driving is Ok-vs-Ok), wrong layout assumption (slab S3),
  contradicting impl (slab S5), syntax/type errors (slab S4, kheap K4).

---

## 4. Problems encountered

### 4.1 Stale `det_check_template` after spec edits

`spec-determinism-run` caches the function's ensures into `det_spec.json`.
Editing `lib.rs`'s inline `verus_spec(...)` does *not* update the cache —
you must run `spec-determinism-regen` between every patch. Cost the
session a few hours of confusion before being identified. Worth a note
upstream.

### 4.2 `verus build` flags vary by crate

bitmap/slab use `--features std`; kernel needs
`--features microvm --features error -Z build-std=...
--target x86-kernel.json`. The harness `run_one.sh` had to be specialised
to `run_kheap.sh`. Pipeline integration must read `nanvix.toml`'s
per-crate `extra_args`/`features`.

### 4.3 Verification-vs-build status disambiguation

`cargo verus build` prints both Verus `verification results:: N verified,
M errors` AND a Rust compile pass. The kernel binary fails Rust compile
on a pre-existing `stmt_expr_attributes` issue, so exit code is non-zero
even when verification succeeded. Detection logic must parse Verus output
specifically, not rely on exit code.

### 4.4 Patch syntax errors at the source-replace level

Two of fifteen patches (slab S4 type-mismatch, kheap K4 brace mismatch)
failed before reaching either Verus reasoning or det-search. The harness
treated these as `verus_status = fail`, but they're a separate failure
class: "patch is not a valid Rust/Verus AST". Need a parse-only pre-check.

### 4.5 Kheap's baseline drifted from v0

`observations/v0/kernel__from_raw_parts/report.json` shows `(Err, Err)`
with different reason strings; current baseline is `(Ok, Ok)` with
per-slab field divergence. Likely caused by the uncommitted nanvix edits
in `kheap.proof.rs`/`Cargo.toml`/`build/verus-version`. Implication: v0
case data ages out as the repo evolves; we need a frozen snapshot for
empirical study (Section 5.3).

---

## 5. User-flagged limitations (need attention)

### 5.1 Repairs are similar even when sampling many

Even with multiple Copilot rolls per witness, candidates cluster around
the same shape (most often "constrain `Err.code`"). EXPERIMENTS.md echoes
this: B1, B2, B3, B5 all attack the Err side; B4 was the only structural
departure, and that came from manual reasoning.

Likely causes:
1. The witness lists collateral assumes prominently (`Err.code is
   OperationNotPermitted`, `Err.reason == ""`), drawing attention
   to those fields.
2. The prompt doesn't surface the equal_fn's structure, so the model
   can't see *which* assumes are driving vs. collateral.
3. Temperature / sampling settings on Copilot CLI may be too low for
   genuine diversity.

Possible mitigations to test:
- Render `det_*_equal` directly in the prompt and label each assume
  as driving / collateral upfront (we have this data from
  `classify_assumes`).
- Add a "diversity directive" prompt segment: "Do not repeat any
  approach used in <previous responses>". Requires plumbing previous
  candidates back in.
- Try several distinct prompt templates (axis-by-axis: one for "pin
  Ok-side fields", one for "constrain inputs", one for "treat policy
  upstream"). Cheaper than asking for diversity from one template.

### 5.2 Hard to efficiently sample multiple patches

Each candidate currently costs a full regen + det + verus cycle (~30 s
to ~10 min depending on crate, with Kheap dominating). Per-patch
iteration is the bottleneck preventing wide search.

Possible mitigations to test:
- **Parallelise** by patch: each candidate edits a *separate* worktree
  (`git worktree add`) so regen+det+verus can run concurrently.
- **Cheap pre-filter**: rustc parse check + `cargo check` (no Verus)
  before the expensive verus run. Catches S4 / K4-class failures
  immediately.
- **Cache regen** when only one function changed in a multi-function
  crate; the regen already takes ~10 s but adds up.
- Skip Verus when det shows the patch *trivially fails* (e.g. driving
  ratio still 0 and witness shape unchanged) — though this changes
  semantics: a patch that doesn't help det but breaks impl is still a
  failure, just one you might not want to score.
- Long-run: a Verus-incremental cache so that re-verifying a function
  whose dependencies are unchanged is cheap.

### 5.3 Metrics are intuitive — empirical study needed

The metrics in METRICS.md were designed inductively from three v0 cases
plus this round's hand-tuning. The 15-patch audit confirmed they behave
as intended on the cases I examined, but that's all the same three
witnesses. Open questions only an empirical study can answer:

- Do the gates (Axes A.1, C, E) ever falsely reject good repairs in the
  wild? We have one near-positive example (bitmap-B4 closes driving;
  Axis E rejects; the *intended* verdict is "redirect upstream", not
  "this patch is bad" — which the framework supports via A.1, but
  arguably mis-labels in summary form).
- Does `driving_closed_ratio` correlate with what humans call "real
  progress" across many cases? On the 15 we have, yes; on a richer
  population we don't know.
- How does it score on cases where the right fix is *structural* (e.g.
  pin Ok-side fields via a layout helper) and the LLM produces dozens
  of candidates that are all structurally similar but arithmetically
  varied? My intuition is the metrics will still discriminate, but I
  can't prove it.

The blocker is corpus: nanvix gives us 3 cases, of which one's baseline
already drifted. We need ~20+ to do statistics.

Candidate corpus paths:
- Sweep all `[crates.*]` in `nanvix.toml` (there are more than 3) and
  let spec-determinism scan every function for nondeterminism.
- Add `verusage` workspaces or other Verus-using projects to the
  config.
- Synthesise toy cases from a controlled spec template (parametrised
  underspec patterns: missing `Err==>cond`, missing field-pin,
  reason-string-driven, etc.) — useful for unit-style validation but
  not real-world generalisation.

---

## 6. Suggested next steps (in priority order)

1. **Apply the prompt-strategy decisions to `prompt.py`**: drop "Layering
   rules"; label assumes as driving/collateral; expose the equal_fn.
2. **Implement MDL soft ranker** (REPAIR-CRITERIA C5) — token-tier cost
   (T1 spec-local 1.0 / T2 module 2.0 / T3 vstd 3.0 / T4 novel 10.0)
   plus structural cost (∀/∃ +3.0, let +2.0, match/if +2.0, fn-call
   +1.0, binop +0.5) over the repair AST. Currently absent from the
   pipeline; without it the tier-2 lexicographic ordering has nothing
   to break ties on.
3. **Patch parse-pre-check**: a `cargo check -p <crate>` pass before
   any det/verus work. Cheap, eliminates S4/K4-class failures.
4. **Worktree-per-candidate**: enables parallel sampling. Probably the
   single highest-leverage performance change.
5. **Implement Axis A.1 in code**: counterfactual policy run, write
   `policy_verdict` into `report.json`. This converts bitmap-B4
   from "Reject" to "Redirect upstream" automatically.
6. **Build a real corpus** for empirical study: enumerate all
   nondeterministic functions in nanvix (and additional projects),
   freeze a snapshot, score each. Goal: 20+ witnesses.
7. **Diversity in sampling**: try the multi-template approach before
   investing in fancier diversity techniques.
8. **Workspace patch scope**: drop whole-file `.spec.rs` replacement;
   let Copilot edit anywhere in the cargo workspace; reverts via
   `git stash` / `git reset`.
9. **Re-examine the demotion of REPAIR-CRITERIA C3 / C4** (no witness
   constants / vocabulary subset) once the corpus exists. The
   strict/free principle argues for demotion; we don't have evidence
   either way yet.

Items 1–5 are pipeline; 6 is the empirical lift; 7–9 fold back into
pipeline once the corpus exists.

---

## 7. Where things live

- `spec-debug/HANDOFF.md` — project state, v0 history.
- `spec-debug/REPAIR-CRITERIA.md` — earlier MDL-based draft (predates
  this round; some content superseded by METRICS.md).
- `spec-debug/METRICS.md` — current metrics framework.
- `spec-debug/EXPERIMENTS.md` — 15-patch manual audit (this round's
  empirical artifact).
- `spec-debug/observations/v0/*` — three v0 cases with reports.
- `spec-debug/spec_debug/{cli.py,prompt.py,...}` — pipeline code.
- `spec-determinism/configs/nanvix.toml` — per-crate config (verus
  flags, features, modules).
