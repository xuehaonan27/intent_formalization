# Determinism funnel — bucket lifecycle & pipeline framework

> **Status**: methodology note (2026-05-18). Locked after Bug A/B work on Tier 1.5.
> **Audience**: anyone running, interpreting, or extending the determinism pipeline.
> **Companion**: `unknown-handling-strategy-2026-05-15.md` (Idea A schema-search rationale).

---

## 1. Why this doc exists

The natural reading of `r0_z3 ∈ {sat, unsat, unknown}` is to treat them as three
parallel outcomes. **That reading is wrong** for our purposes:

- `sat` and `unsat` are **terminal** verdicts.
- `unknown` is **not** a verdict — it is "z3 has not decided", i.e. the
  formula is still logically *either* sat or unsat, just unresolved.

The whole point of the pipeline downstream of the z3 baseline is to *reduce*
the `unknown` bucket. Reporting "0 sat" on a corpus while ignoring how many
unknowns are left masks the actual finding. This note formalises the funnel.

---

## 2. The funnel

```
                                     extract_spec
                                          │
                                       gen_det
                                          │
                                    z3 baseline
                                          │
                ┌─────────────────────────┼─────────────────────────┐
                ▼                         ▼                         ▼
            UNSAT                       SAT                       UNKNOWN
        terminal — det.          terminal — non-det.             ▼
                                     (real witness)        ──────────────
                                                            unsat-side
                                                            funnel:
                                                            ──────────────
                                                            view-equal
                                                            (PR-N, C-patch,
                                                             Phase-2 L1/L3)
                                                            Tier 1.5 type
                                                              completion
                                                            Tier 2 equal_fn
                                                              relax
                                                            Tier 3 LLM
                                                              proof annot.
                                                            deep schema
                                                              narrowing
                                                            ──────────────
                                                                 │
                                                                 ▼
                                                            UNKNOWN_RESIDUAL
                                                            ──────────────
                                                            sat-side funnel:
                                                            ──────────────
                                                            portfolio solver
                                                              (cvc5, alt-ergo)
                                                            sat-mode k-sampling
                                                              (find any sat
                                                               schema)
                                                            manual witness
                                                              injection /
                                                              hand replay
                                                            ──────────────
                                                                 │
                                                ┌────────────────┼─────────────────┐
                                                ▼                ▼                 ▼
                                             SAT              PRESUMED_SAT       RESIDUAL_UNKNOWN
                                          (witness)         (all tools tried,    (provers
                                                             still no witness;     genuinely
                                                             likely sat but        incomplete)
                                                             unwitnessed)
```

**Key property:** every tool in the unsat-side funnel is **monotone toward
`unsat`**. None of them can flip an `unsat` to `sat` or vice versa, because
they only add semantically-equivalent assumptions / sharper view-equal /
proof annotations. So:

> After all unsat-side tools have been exhausted, anything **still** in
> `unknown` is much more likely to be `sat`-but-z3-incomplete than `unsat`.
> Call this bucket **`presumed_sat`**.

---

## 3. Tool-by-tool: where each lives in the funnel

| Tool | Direction | Status (2026-05-18) | What it does |
|---|---|---|---|
| PR-A..PR-N: view-equal rewrite | →unsat | ✅ landed | Stop comparing structurally where spec uses `@`/`.view()` |
| C-patch: spec_view from `impl T { spec fn view }` | →unsat | ✅ landed | Auto-populate `TypeInfo.spec_view` from the source |
| **Tier 1.5: LLM type-completion (gap-filling)** | →unsat | ✅ landed `baf8347a` | Kind/fields/spec_view via LLM when extractor can't infer |
| Bug A: ambiguous struct-form variant fields | →unsat | ✅ landed `08e98116` | gen_det fallback for `r->v` ambiguity |
| Bug B: gen_det compile probe (shape-mismatch) | →unsat | ✅ landed `9a480346`, refactored out of main path | Detects LLM patches whose gen_det output doesn't type-check. **No longer on the verusage_run hot path** — moved into `scripts/validate_tier15_cache.py` as a re-baseline-only validator. Measured contribution at steady state was indistinguishable from LLM variance (every "win" had `shape_det=0` once the cache was warm). |
| Tier 2: equal_fn relaxation (multiset / sort / ignore_fields) | →unsat | 🟡 designed, not implemented | Relax the *semantic* model so legitimate impl variants count as equal |
| Tier 3: LLM proof annotation | →unsat | ✅ landed (corpus-integrated 2026-05-16) | Add lemma / forall hints to guide z3 past quantifier walls |
| Deep schema narrowing (k-sampling, more rounds) | →unsat | 🟡 partial | Search for narrower assume that makes z3 decide |
| Portfolio solver (cvc5 / alt-ergo) | bi-dir | ❌ not done | Different decision heuristics; can produce both sat *and* unsat where z3 unknown |
| Sat-mode k-sampling | →sat | ❌ not done | Same schema infra, look for sat models rather than refinements |
| Manual witness injection | →sat | ❌ not done | Human-supplied candidate counterexamples on remaining `presumed_sat` |

---

## 4. When to declare `presumed_sat`

A target enters `presumed_sat` when **all** of the following are true:

1. Baseline z3 returned `unknown`.
2. Tier 1.5 either applied no patches OR applied patches and `r0_z3` is still `unknown`.
3. Tier 2 ran and produced no `r0_z3 = unsat` (when Tier 2 lands).
4. Tier 3 ran and `llm_assisted` was False or its proof didn't flip `unknown→unsat`.
5. Deep schema narrowing exhausted its budget without flipping.
6. (Future) Portfolio solver returned `unknown` from at least one alt solver.

In practice it's easier to report it as a *separate* terminal bucket alongside
`ok_unsat` / `verus_error` / etc., and gate the label on a `funnel_exhausted: bool`
field that the corpus runner sets.

**Important corollary:** `presumed_sat` is a *hypothesis*, not a verdict. It
should trigger sat-side tools (portfolio, sat-mode search, manual review), not
be reported as "non-deterministic".

---

## 5. Misreading guard: "0 sat" ≠ "fully deterministic"

The 2026-05-18 ironkv result (`r0_z3 ∈ {unsat=99, unknown=70, verus_err=45}`)
must be reported as:

> "z3 baseline + Tier 1.5 + Tier 3 found **99 mechanised determinism proofs**
> and **0 z3-confirmed witnesses**. **70 targets remain unknown** — they are
> candidates for `presumed_sat` once Tier 2 + portfolio solver pass land."

It should **never** be reported as "ironkv is fully deterministic" until the
funnel is fully exhausted.

This is also why a "0 sat" corpus is *not* evidence that our sat-finding
machinery works — sat-side tools have never been exercised on a hand-verified
deterministic codebase, because most candidates were filtered out by the
unsat-side funnel before any sat-direction tool ran.

---

## 6. Operational implications

### 6.1 Reporting

The corpus runner should emit, per target:

```json
{
  "r0_z3": "unknown",
  "funnel": {
    "view_equal_active": true,
    "tier15": {"applied": 3, "rounds_run": 2},
    "tier2": {"applied": 0, "skipped": "not_implemented"},
    "tier3": {"invoked": true, "proof_accepted": false},
    "narrowing": {"n_rounds": 19, "n_schemas": 13, "exhausted": false}
  },
  "funnel_exhausted": false,
  "terminal_bucket": "unknown"
}
```

When `funnel_exhausted=true`, label `terminal_bucket = "presumed_sat"`.

### 6.2 A/B testing

Always report the **bucket transition matrix** when shipping a funnel tool:

|             | →unsat | →unknown | →verus_err | →sat |
|-------------|-------:|---------:|-----------:|-----:|
| was unsat   |    n   |    0     |     0      |  0   |
| was unknown |    n   |    n     |     n      |  n   |
| was verus_err |  n   |    n     |     n      |  0   |

A monotone unsat-side tool should have **0 in `unsat→unknown`, `unsat→sat`,
`unsat→verus_err`**. Any non-zero entries there are regressions and must
be investigated. This is exactly how Bug A / Bug B were caught.

#### 6.2.1 LLM cache stability (Tier 1.5 / Tier 3)

Any tool that calls an LLM has **two** sources of variance an A/B can be
contaminated by:

1. **Code logic** — the thing you actually want to measure.
2. **LLM non-determinism** — the same prompt yields different outputs across
   runs. This was the root cause of the Bug B "regression" mis-diagnosis on
   2026-05-18: clearing the Tier 1.5 cache before the Bug B run forced
   LLM rebuild, and 15 ironkv targets received *different* patches than the
   Bug A run had, producing 11 false-positive verus_error regressions
   that vanished once the Bug A cache was restored.

**Protocol** (canonical for Tier 1.5 / Tier 3 A/B):

| concern | mechanism |
|---|---|
| keep prompts deterministic | already done: per-type prompt depends only on `spec.type_defs` + extracted snippet |
| keep cache deterministic | use a **pinned (read-only) cache snapshot** for both A and B (`--llm-type-completion-pinned-dir`); writes from this run go to the **live** layer and never touch the pin |
| prove A and B used the same cache | each result records `tier15.pinned_hash`, `tier15.current_source_hash`, `tier15.pinned_hash_matches`, `tier15.gap_sources` (per-name `"live"\|"pinned"\|"miss"`) — diff these across A and B to verify byte-equality of the cache substrate |
| handle source drift | pin still serves matching types as warm-start; `pinned_hash_matches=False` is surfaced in telemetry so a stale pin gets flagged but doesn't silently mis-resolve. Pre-commit re-baseline validation against shape-mismatched entries is done out-of-band via `scripts/validate_tier15_cache.py` (see below). |

Pinned snapshots live at `verusage/cache_snapshots/<project>/` and are
auto-detected by `verusage_run`. The 49-entry ironkv pin captured from the
Bug A run is the current reference. To re-baseline (e.g., after a major
schema change), regenerate via:

```bash
# 1. clear live cache
rm -rf ~/.cache/spec_determinism/type_completion/<project_hash>/

# 2. let the corpus run fill live from LLM (this is the canonical re-baseline)
python -m spec_determinism.corpus.verusage_run --project ironkv \
  --llm-type-completion --no-llm-type-completion-pinned-autodetect ...

# 3. copy live → pin and refresh _meta.json
cp ~/.cache/spec_determinism/type_completion/<hash>/*.json \
   verusage/cache_snapshots/ironkv/
# update _meta.json: project_root, captured_at_iso, captured_run, notes
```

A re-baseline must be a deliberate decision (commit + PR), not a side
effect of any A/B test run.

#### 6.2.2 Re-baseline shape-mismatch validator

Before committing a refreshed `verusage/cache_snapshots/<project>/` snapshot,
run the standalone validator. It re-runs the gen_det compile probe (formerly
"Bug B", now off the main path) against every corpus target with the
candidate cache pre-applied. It never calls the LLM and never writes to the
cache. Failures surface the offending cache entry name + a stderr tail so
you can decide whether to delete, hand-edit, or re-prompt that entry.

```bash
python spec-determinism/scripts/validate_tier15_cache.py \
  --project ironkv --subdir verified \
  --roots verusage/source-projects \
  --cache-dir verusage/cache_snapshots/ironkv \
  --out /tmp/validate_tier15_ironkv.json
```

Exit code `0` = clean snapshot, `1` = at least one shape mismatch detected
(the `offending_cache_entries` summary lists them by frequency). This is
strictly a quality gate on the snapshot — main-path verusage_run still
never invokes the probe.

### 6.3 Roadmap priority

Inside the unsat-side funnel: prioritise tools that target the **largest
unconverted unknown subpopulation**. Per the 2026-05-18 ironkv counts:

| candidate next tool | expected impact |
|---|---|
| Tier 2 equal_fn relax | medium — addresses spec-loose unknowns (HashMap-key choice, sort-stability) |
| Portfolio solver (cvc5) | unknown but cheap to test — single rerun on existing .smt2 dumps |
| Deeper narrowing (more rounds / schemas) | low (already at median n_rounds=11) |
| LLM-proof multi-shot | medium (Tier 3 is already on but single-shot — multi-shot critic loop in plan.md) |

**Recommended next step**: run a 10-min portfolio cvc5 pass on the 24 ironkv
unknowns first (cheapest experiment), then plan Tier 2 accordingly.

---

## 7. Open questions

- **How to detect "spec is too loose"?** Some unknowns are sat because the
  user under-specified `ensures` (e.g. forgot to constrain `tombstones`).
  This is a spec quality issue, not a real non-determinism. Need a tier
  that **strengthens** ensures (auto-add closure constraints) — distinct
  from Tier 2's *relaxation* of the equal model.
- **Cross-target inference**: if 3 targets in the same file are all
  unsat-confirmed under Tier 2, can we lift that as a project-level
  invariant for the remaining unknowns?
- **When to stop**: at some point a `presumed_sat` target should be
  triaged either as "real non-determinism, file as project bug" or
  "spec under-specification, file as spec gap". Need a workflow for
  this triage (probably manual, human-in-the-loop).

---

*This doc is methodology; per-tool details live in their own design docs
(PHASE2_SUMMARY.md, unknown-handling-strategy-2026-05-15.md, plan.md in
the session workspace).*
