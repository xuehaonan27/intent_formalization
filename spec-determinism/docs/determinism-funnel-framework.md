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
| Bug B: gen_det compile probe (shape-mismatch) | →unsat | ✅ landed `9a480346` | LLM revert-and-retry when its patch causes verus E0599 |
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
