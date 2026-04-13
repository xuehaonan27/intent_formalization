# Skill Absorption Analysis: agentic-reasoning → spec-testing

**Date:** 2026-04-13

This document analyzes how the generic `agentic-reasoning` skill was adapted into the domain-specific `spec-testing` skill (v0.7.0), what was absorbed, what was modified, and what was dropped.

---

## 1. Architecture — Absorbed with Domain Mapping

### agentic-reasoning (generic)
```
Reasoner → Verifier → Meta-Prompter → Arbitrator
                  ↕ (challenge-response loop)
```

### spec-testing (domain-adapted)
```
Alpha/Meta-Prompter → Beta/Reasoner → Gamma/Verifier → Delta/Arbitrator
                              ↕ (review cycle)
```

**What happened:** The four-role architecture was absorbed **directly** — one-to-one mapping. The roles kept their generic names in the SKILL.md table but were instantiated as specific agents (Alpha/Beta/Gamma/Delta) in practice.

**Adaptation:** In agentic-reasoning, the Arbitrator is a distinct role that makes procedural decisions. In spec-testing, the Arbitrator role is merged with the orchestrating agent (Lem/self) or Delta, since the procedural decisions are simpler (linear pipeline, not iterative problem-solving).

---

## 2. Core Workflow — Partially Absorbed, Significantly Simplified

### agentic-reasoning workflow
```
Meta-Prompter pre-analysis → Reasoner plan (3-10 steps) →
  [Step N: execute → Verifier review → ACCEPT/CHALLENGE/TRACE_BACK] → repeat →
  Final solution → Post-check
```

### spec-testing workflow
```
Meta-Prompter strategy → Reasoner brainstorm → Verifier review →
  (optional: Reasoner round 2) → Formalize → Entailment (Verus) → Critic debate
```

**Absorbed:**
- Meta-Prompter pre-analysis → became "spec structure analysis + brainstorm strategy"
- Reasoner-Verifier review loop → became brainstorm review cycle
- Challenge-response format → became adversarial FP detection

**Simplified/Dropped:**
- **Step-by-step plan (3-10 steps)** — dropped. Spec testing is not a sequential problem; it's a generate-and-filter pipeline. No need for a multi-step plan.
- **TRACE_BACK** — dropped. No step dependencies to trace back through. If a candidate is bad, just drop it.
- **Final solution post-check** — replaced by Verus mechanical verification. No "drift" risk because Verus is deterministic.
- **Re-planning on fundamental approach failure** — not needed. The attack strategy (entailment checking) is fixed; only the candidates vary.

---

## 3. Verification Tags — Adapted to Domain Equivalents

### agentic-reasoning tags
| Tag | Meaning | Strength |
|-----|---------|----------|
| `[verified]` | Code executed, output confirmed | Strongest |
| `[easy-verify]` | Code written, not yet run | Medium |
| `[hard-verify]` | Logical argument, no code | Weakest |

### spec-testing equivalents
| Equivalent | Meaning | Mapping |
|-----------|---------|---------|
| Verus verified ✅ | phi test passes — gap confirmed mechanically | `[verified]` |
| Verus error ❌ | phi test fails — spec rejects bad scenario | `[verified]` (negative) |
| Algebraic witness | Manual witness construction without Verus | `[easy-verify]` |
| Counting argument | Logical argument (e.g., Gamma's N+1 counting) | `[hard-verify]` |

**What happened:** The verification tag system was NOT explicitly absorbed into the SKILL.md, but the **underlying principle** (every claim needs evidence, stronger evidence preferred) was absorbed implicitly:
- The SKILL.md says "If Verus is available → mechanized check. If not → algebraic witness."
- Gamma's FP kills used `[hard-verify]`-equivalent reasoning (counting arguments, invariant reasoning)
- The hierarchy (Verus > witness > logical argument) matches `[verified]` > `[easy-verify]` > `[hard-verify]`

**Not absorbed explicitly:** The SKILL.md does not require tagging claims with these labels. This could be an improvement — requiring Gamma to tag each verdict as `[verified by Verus]`, `[killed by witness]`, or `[killed by argument]` would improve traceability.

---

## 4. Challenge-Response Protocol — Absorbed as Critic Debate

### agentic-reasoning
- Verifier issues CHALLENGE with specific concerns
- Reasoner responds with evidence or acknowledges error
- Up to 10 rounds
- Meta-Prompter mediates deadlocks

### spec-testing
- Gamma reviews candidates adversarially
- Beta can defend or withdraw
- If disagreement, Alpha (Meta-Prompter) mediates
- No formal round limit (Discord conversation naturally converges)

**Absorbed:** The core concept of structured disagreement → resolution. In practice, the "debate" was informal (Discord messages) rather than the rigid CHALLENGE/ACCEPT/TRACE_BACK format.

**Not absorbed:** The formal verdict types (ACCEPT/CHALLENGE/TRACE_BACK). Instead, Gamma used natural language ("✅ confirmed", "❌ killed", "⚠️ needs review"). The formality was lost but the substance was preserved.

---

## 5. Step Report Format — Not Absorbed

### agentic-reasoning
Requires structured reports per step:
```markdown
# Step N: [Title]
## Objective
## Context from Previous Steps
## Reasoning (with verification tags)
## Step Conclusion
```

### spec-testing
No structured per-step format. Each pipeline step has its own output format:
- Step 2: JSON array of negative properties
- Step 3: Verus proof fn code
- Step 5: Verdicts JSON + summary markdown

**Why not absorbed:** Spec testing has domain-specific output formats (JSON, Rust code, Verus results) that don't fit a generic markdown template. The step report format solves a problem (structured reasoning) that spec-testing solves differently (pipeline stages with typed outputs).

---

## 6. Error Recovery — Partially Absorbed

### agentic-reasoning
- Code timeout → Meta-Prompter suggests optimization
- Stalemate → Arbitrator declares, Meta-Prompter mediates
- Trace-back → return to earlier step
- Re-planning → new plan with limited retries

### spec-testing
- Verus timeout → increase timeout or simplify phi test (implicit)
- Stalemate → not observed (Discord debates converge fast)
- Formalize error → Beta rewrites (observed: v1→v2 after Tianyu's correction)
- No re-planning needed (pipeline is fixed)

**Absorbed:** The concept of error → correction cycle. When Beta's v1 phi tests had wrong structure, the protocol naturally triggered a correction: Tianyu flagged → Alpha agreed → Beta rewrote → Gamma re-reviewed.

**Not absorbed:** Formal stalemate detection (3+ rounds same arguments) and trace-back. These weren't needed because (a) the agents converged quickly and (b) the pipeline has no step dependencies to trace back through.

---

## 7. Meta-Prompter Constraints — Absorbed and Strengthened

### agentic-reasoning
"Never solve the problem, write proofs, or modify files. Only suggests, warns, mediates."

### spec-testing
Alpha was explicitly instructed: "You MUST NOT generate specific test cases or phi candidates. Only provide strategic guidance."

**Absorbed:** The read-only constraint was preserved and actually more strictly enforced. Alpha's output was purely strategic ("focus on sv_eq vs == mismatch", "check totality in inv").

---

## 8. Arbitrator Constraints — Weakened

### agentic-reasoning
"Makes ONLY procedural decisions. NEVER performs domain reasoning. NEVER reveals expected answers."

### spec-testing
Delta in practice did light domain reasoning ("C5 is a coverage gap not a spec gap", "C6 is downstream of C1-C3"). The Arbitrator role was less strictly separated.

**Why:** In a 4-agent Discord chat, strict role separation is hard to enforce. Delta naturally contributed substantive comments alongside procedural ones. This may actually be fine — the key constraint (Verifier is adversarial) was maintained.

---

## Summary Table

| agentic-reasoning Component | spec-testing Absorption | How |
|------------------------------|------------------------|-----|
| 4-role architecture | ✅ Fully absorbed | 1:1 mapping to Alpha/Beta/Gamma/Delta |
| Meta-Prompter pre-analysis | ✅ Fully absorbed | Spec structure analysis + strategy |
| Challenge-response debate | ✅ Core absorbed | Informal Discord debate instead of rigid format |
| Verification tags | ⚠️ Implicitly absorbed | Verus/witness/argument hierarchy exists but not labeled |
| Step-by-step plan | ❌ Dropped | Pipeline stages replace sequential steps |
| Step report format | ❌ Dropped | Domain-specific outputs (JSON, Rust, Verus) |
| TRACE_BACK | ❌ Dropped | No step dependencies in generate-and-filter pipeline |
| Stalemate detection | ❌ Dropped | Not needed (fast convergence) |
| Error recovery | ⚠️ Partially absorbed | Correction cycles exist but no formal protocol |
| Meta-Prompter read-only | ✅ Strengthened | Explicit "no phi generation" constraint |
| Arbitrator strict separation | ⚠️ Weakened | Delta contributed domain reasoning |
| Post-check (answer vs steps) | ✅ Replaced by Verus | Mechanical verification eliminates drift risk |
