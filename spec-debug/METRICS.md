# spec-debug — Metrics Design (draft, under discussion)

Purpose: enumerate the candidate metrics for scoring an LLM-produced
spec patch, with the *reason* each is needed (grounded in a concrete
failure mode), so that `report.py` can surface the right flags and a
future iterative loop has a ranking signal.

This is design discussion, not a spec. Nothing here is implemented yet.

---

## Organising principle (revised 2026-04-27)

> **spec-determinism = strict / rule-based.** Deterministic algorithm,
> auditable.
>
> **spec-debug = free / observation-driven.** Hand the LLM the repo,
> let it read and edit; judge only by **outcome**, not by **process**.

This rules out "police the LLM via prompt rules and structural gates".
Concretely:

- **Hard gates** are outcome-only — gap validity, impl still verifies,
  no checker bypass.
- **Primary score** is outcome-only — did the driving witness close?
- **Structural / over-spec metrics are NOT gates.** They are recorded
  as observation flags in `report.json` for understanding LLM
  behaviour and post-hoc analysis, but do not restrict the prompt and
  do not enter ranking.

Lexicographic Pareto still applies, but only over outcome axes.

---

## Axis A — Gap closure (the only positive axis)

| Metric | Question | Why it exists |
|---|---|---|
| `closed_count / total` | How many witness assumes are now ruled out | Direct signal, but case #3 (kernel::from_raw_parts) proved it insufficient alone |
| **`driving_closed / driving_total`** | Of the assumes that actually flow into `equal_fn`, how many closed | Should replace the raw count as primary. bitmap::new has 8 assumes but only 2 are driving; rewarding collateral closure incentivises over-spec |
| `new_witness_driving?` | Does the rerun produce a fresh witness, and is it driving | Catches "fix the exact old witness, leave the underlying gap" patches |
| `rounds_before → rounds_after` | Search-round delta | Spike (slab 67→99) = schema blow-up; collapse to 0 alongside `schemas→0` = bypass flag (case #3) |

**Open question raised in discussion (2026-04-24): gap *validity*
precedes gap closure.** spec-determinism is deterministic; a witness it
emits is only meaningful if the `equal_fn` used to define "same output"
is itself right. If we judge the two outputs in the witness to be
semantically equivalent (the difference is in a field that shouldn't
count), the correct response is **not** to patch the spec — it is to
feed the disagreement back to spec-determinism so it can update its
equality policy / `equal_fn`. See §A.1.

### A.1 Upstream feedback path (decided 2026-04-27, revised same day)

Before measuring `driving_closed`, the witness must be classified:
- **Valid gap** — driving assumes describe a genuinely observable
  behavioural difference under the current policy. Proceed with normal
  closure metrics.
- **Policy-spurious gap** — driving assumes only distinguish fields a
  reasonable caller shouldn't branch on (diagnostic strings, opaque
  handles, etc.). Do **not** attempt to patch the spec; the gap is a
  policy issue.
- **Loose-by-design** — function is intentionally underdetermined
  (allocator-style). No fix expected.

**Where this logic lives**: in `spec-debug`, not in `spec-determinism`.
spec-determinism is presumed correct when it commits a `det-equal` /
policy — by construction it treats its policy as axiomatic and cannot
self-diagnose policy bugs. Judging "is this policy actually right for
this caller-facing API?" is a meta-judgment that belongs to the
debugger (spec-debug), alongside the other "is this gap worth fixing?"
decisions in Axes B/D.

Consequence: **spec-determinism's output stays untouched**. No new
field in the witness, no breaking change. spec-debug owns the
verdict end-to-end.

**Counterfactual mechanics** (spec-debug-driven):
1. Load `det_spec.json` for target.
2. Save original policy. For each policy knob (`errs_equivalent`,
   `opaque_ok`), write the toggled value, re-invoke
   `spec-determinism-run`, observe whether the witness disappears
   or its driving set shrinks.
3. Restore original `det_spec.json`.
4. Aggregate the counterfactual matrix into a `policy_verdict`.

This reuses the same patch-then-revert dance `verify.py` already does
for `.spec.rs` — no new spec-determinism API needed.

**Output shape**: in `spec-debug/runs/<ts>/<crate>__<fn>/report.json`:

```json
"policy_verdict": {
    "kind": "valid" | "policy_spurious" | "loose_by_design",
    "counterfactual": {
        "errs_equivalent_true":  "witness_disappears" | "driving_shrinks" | "no_change",
        "opaque_ok_true":        "..."
    },
    "suggestion": { "errs_equivalent": true }   // only when policy_spurious
}
```

Audit chain: witness → spec-debug verdict → suggestion → human
reviews → policy edited in `det_spec.json` → re-run spec-determinism.

**Pipeline placement — short-circuit before LLM**: the verdict runs
*before* prompt construction. `policy_spurious` and `loose_by_design`
skip the LLM entirely, save cost, and prevent encoding a policy bug
into the spec.

**Known limit**: counterfactual against the existing two booleans
only catches "Err-internal" and "Ok-opaque" spuriousness. Cases where
driving lives in the Ok/Err *discriminant* itself (bitmap::new) remain
valid gaps under any boolean policy. Finer-grained per-field
equivalence masks would extend the reach but are a larger change to
spec-determinism that we are not coupling to.

Concrete first target: `kernel::from_raw_parts` with
`errs_equivalent=False` forcing `Err.reason` strings to agree. The
counterfactual should flag this as `policy_spurious` and recover
case #3 as not-a-spec-bug.

---

## Axis B — Structural fit (DEMOTED to observation flags, 2026-04-27)

Per the revised principle, these no longer gate or rank patches and
no longer drive prompt restrictions. They are recorded in
`report.json` for post-hoc analysis only — useful for spotting
recurring failure shapes, writing future observations docs, and
debugging surprising results, but **not** for telling the LLM what
not to do.

| Metric | Question | Why we still record it |
|---|---|---|
| `edit_layer_counts` (set/dict) | Which AST node types were modified | Lets us track whether LLM behaviour shifts over time / across prompts |
| `dangling_new_items` | Which newly-added spec items aren't reachable from target's `ensures` | Surfaces the "dangling helper" failure shape after the fact |
| `target_ensures_modified` (bool) | Did patch touch target fn's ensures | Quick signal in report; not a gate |
| `signature_changed` (bool) | Did fn signature change | Almost certainly bad if True; surfaced for human review, not auto-rejected |
| `ensures_surface_delta` | Did ensures' transitive callees change | Detects "syntactic-only" ensures rewrites |

These are computed cheaply via `tree-sitter-verus` (already a dep of
spec-determinism). No prompt-level "layering rules" — the v0.1
template's prohibitions on dangling helpers and assume_specification
are removed (see Prompt Notes below).

---

## Axis C — Bypass detection (did the checker still check the same thing)

| Metric | Question | Why |
|---|---|---|
| `symbol_table_stable` | `det_spec.json.symbols` before/after equal | New `assume_specification` can re-point the instrumented symbol (case #3) |
| `equal_fn_def_stable` | `equal_fn` body unchanged when policy unchanged | If equal_fn shifted without a policy change, LLM edited a type that policy expands over |
| `schema_count_before → after` | Narrowing-dimension count | 519 → 0 is smoking gun; mild decrease is normal |
| `rounds==0 AND schemas==0` | Joint flag | Rounds=0 alone is fine (tight spec); combined with no schemas is bypass |
| **`no_new_admissions_in_impl`** | Did the patch add new `assume(...)` / `admit()` to any `exec` body / proof block | Symmetric counterpart to `ensures false` on the spec side. With Axis E relaxed to "workspace verifies", LLM could otherwise admit any spec by hand. Detect via git diff: only **newly introduced** admissions count; pre-existing `assume_specification` blocks and existing `assume(...)` are part of the design and untouched. Hard gate. |

Theme: "changed what is being checked" and "made the thing being
checked tighter" look identical on rounds/closed. Only a structural
before/after snapshot disambiguates them.

Per the hide-police principle, **none of these are exposed in the
prompt** — exposing the bypass detectors teaches the LLM how to
evade them.

---

## Axis D — Over-specification (DEMOTED to observation flags, 2026-04-27)

Same demotion as Axis B: recorded, not gated. We trust the LLM with
the freedom to make over-spec mistakes; the *outcome* axes (especially
new-witness emergence after rerun, plus impl-verifies) will catch
material problems, and we'd rather see the over-spec patterns LLM
produces than restrict them out of the data.

| Metric | Question | Why still recorded |
|---|---|---|
| `collateral_pinned_count` | Did LLM pin policy-ignored assumes | Diagnostic of prompt clarity, not a gate |
| `literal_bleed` | Are concrete `input_narrowing` literals copied into ensures | Subtle failure shape; flag for review |
| `requires_tightened` | Was `requires` strengthened | Often a fake fix; surface in report |

---

## Axis E — Feasibility (strongest anti-LLM-hallucination gate)

| Metric | Question | Why |
|---|---|---|
| **`impl_still_verifies`** | After patch, does `cargo verus verify` pass on the workspace as a whole | If LLM writes `ensures r is Ok` but impl can return Err, Verus rejects — kills a whole class of fake fixes. **Source code on the impl side is allowed to change** to add proof annotations (loop invariants, asserts, proof blocks) needed to discharge the new ensures; the constraint is that the existing exec logic can still be proven against the new spec, not that the source stays untouched. |
| `ensures_consistent` | Is the new ensures internally contradictory | Largely subsumed by `impl_still_verifies` |

Relaxing `impl_still_verifies` to "workspace verifies" opens a
symmetric cheat path on the impl side that did not exist before:
`assume(false)` / `admit()` inside an `exec` body or proof block makes
Verus accept anything. Caught by Axis C; see `no_new_admissions_in_impl`.

---

## Axis F — Stability across samples (§5.4)

| Metric | Question | Why |
|---|---|---|
| `layer_agreement@K` | Do K samples agree on `edit_layer` | Disagreement means the prompt hasn't locked direction |
| `driving_closed_agreement@K` | Std-dev of driving closure across samples | Tests whether single-shot is sufficient |
| `char_diff_pct@K` | Text-level variance | Cheap stability probe |

---

## Proposed composite score (revised 2026-04-27)

Outcome-only. Structural / over-spec axes do not enter ranking.

```
tier 1 (hard gates — must all pass):
    policy_verdict.kind == "valid"      (Axis A.1)
  ∧ impl_still_verifies                 (Axis E)
  ∧ no_bypass_flags                     (Axis C)

tier 2 (primary outcome score — higher better):
    (driving_closed_ratio,
     ¬new_witness_driving)              (Axis A)

tier 3 (stability — across K samples, when --n-samples enabled):
    layer_agreement / closure_agreement (Axis F)
```

Axis B (structural) and Axis D (over-spec) are recorded in
`report.json` as observation flags but do not appear here.

---

## Pipeline implications

Two concrete pipeline changes follow from the "free repair" principle.
Both are decisions to make with the user, not done yet.

1. **Patch scope = cargo workspace, not single `.spec.rs` file.**
   Hand Copilot the nanvix repo path with `--allow-all-tools
   --allow-all-paths`; it reads any `.rs` / `.spec.rs` it likes and
   edits in place. spec-debug wraps the whole call in `git stash` /
   `git reset --hard` for reversibility. Drops the
   `response.md → apply_patch` step and the whole-file overwrite.
   Solves case #3's inline-ensures problem at the pipeline level
   without needing any `spec_locus` field upstream.

2. **Prompt loses its layering rules.** v0.1's PROMPT_TEMPLATE
   "Layering rules" section (no dangling helpers, no
   `assume_specification`, no signature changes) is policing
   disguised as guidance. Per principle, remove. Keep only:
   gap statement, equal_fn, driving/collateral split, closure goal.

---

## Ruled out by v0 data (for record)

- ❌ `verify_pass` alone (all three patches pass)
- ❌ Patch size / minimality as primary signal (smallest was most misdirected)
- ❌ Raw `closed` count alone (case #3's 9/9 may be vacuous)
- ❌ LLM-self-reported confidence / response length
