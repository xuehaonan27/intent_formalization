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

---

# Part 2: lean4-autoformalization → spec-testing

## Overview

`lean4-autoformalization` is a domain-specific multi-agent skill for formalizing math textbooks into Lean 4. While the domain is different (theorem proving vs spec testing), the **multi-agent orchestration patterns** overlap significantly.

## Key Differences in Domain

| Dimension | lean4-autoformalization | spec-testing |
|-----------|------------------------|-------------|
| Goal | Fill `sorry` placeholders with proofs | Find spec gaps via entailment checking |
| Verification | `lake env lean` (compile = correct) | `verus` (verified = gap exists) |
| Success criterion | Zero sorry, zero errors | Verified phi = confirmed gap |
| Worker task | Write one proof for one theorem | Write one phi test for one gap |
| Failure mode | Can't prove theorem | Phi test rejected (spec is complete) |

## Absorbed Patterns

### 1. Dual-Agent Cycle → Alpha/Beta/Gamma Protocol

**lean4-autoformalization:**
```
Plan Agent (strategic) ↔ Lean Agent(s) (execution)
  Plan Agent diagnoses failures, proposes strategies
  Lean Agent executes focused tasks in clean context
```

**spec-testing:**
```
Alpha/Meta-Prompter (strategic) → Beta/Reasoner (execution) → Gamma/Verifier (review)
  Alpha proposes brainstorm strategy
  Beta executes focused candidate generation
  Gamma reviews adversarially
```

**How absorbed:** The separation of **strategic reasoning** from **task execution** is the same core pattern. lean4-autoformalization calls it "Plan Agent vs Lean Agent"; spec-testing calls it "Meta-Prompter vs Reasoner". The key insight — that the strategic agent should never directly solve, only guide — transferred directly.

**Difference:** lean4-autoformalization has a 2-agent cycle (Plan ↔ Lean), while spec-testing has a 3-agent pipeline (Alpha → Beta → Gamma). The Verifier (Gamma) role doesn't exist in lean4-autoformalization because Lean compilation serves as the verifier. In spec-testing, Verus plays that role for entailment, but FP detection requires an LLM adversary — hence Gamma.

### 2. Context Explosion Prevention → Focused Sub-agent Tasks

**lean4-autoformalization:**
> "Lean Agents get focused tasks in clean context, not a full repository of accumulated analysis and failed attempts"

**spec-testing:**
Each sub-agent (temp or Task Force) receives a focused prompt:
- Alpha gets: source file + "analyze structure"
- Beta gets: Alpha's strategy + source + "generate candidates"
- Gamma gets: Beta's candidates + source + "review adversarially"

**How absorbed:** The principle of **clean context per task** was absorbed directly. Each agent starts fresh without the accumulated history of other agents' work. This is why `sessions_spawn(mode=run)` was used — one-shot sessions with no prior context.

### 3. Task-Aversion Mitigation → Fresh Agents for Retry

**lean4-autoformalization:**
> "When an agent fails and accumulates pessimistic context, it becomes reluctant to retry. A fresh Lean Agent with the Plan Agent's revised strategy avoids this trap."

**spec-testing:**
When Beta's v1 phi tests had the wrong structure (bad property in ensures), rather than asking Beta to fix in the same conversation, the correction came from outside (Tianyu) and Beta rewrote from scratch. The Task Force agents, running in Docker containers, effectively had "fresh context" for each task since their Discord sessions don't accumulate heavy context.

**How absorbed:** Implicitly. The protocol doesn't formally say "spawn fresh agent on failure," but the architecture naturally achieves this because each task is dispatched as a new message, not a continuation.

### 4. Model Specialization → Not Absorbed

**lean4-autoformalization:**
> "Plan Agent can use Claude Opus for strategic reasoning; Informal Agent uses Gemini for mathematical reasoning; Lean Agent uses Claude Opus for code"

**spec-testing:** All agents use the same model (Claude Opus 4.6). No model specialization was attempted.

**Why not absorbed:** Spec testing is less sensitive to model choice — all tasks (brainstorm, formalize, review) are within one model's capabilities. lean4-autoformalization benefits from specialization because Lean syntax is niche (Opus) while informal math reasoning is broader (Gemini).

**Potential improvement:** Using a faster/cheaper model for Alpha (strategy analysis is simpler) and Opus only for Gamma (adversarial review needs the strongest reasoning).

### 5. Informal Agent → Not Absorbed (but could be)

**lean4-autoformalization:**
> "Dedicated Informal Agent (Gemini) to produce step-by-step sub-proof before dispatching Lean workers"

**spec-testing:** No informal reasoning step. Beta goes directly from natural-language property to Verus proof fn.

**Potential improvement:** An "Informal Witness Agent" could produce a step-by-step algebraic witness before Beta formalizes. This would catch witness errors earlier — analogous to how the Informal Agent catches proof strategy errors before the Lean Agent wastes cycles on a bad approach.

### 6. Worker Task Format → Partially Absorbed

**lean4-autoformalization** requires each worker task to include:
1. File path + project root
2. Exact sorry locations
3. Proof strategy hints
4. Mathlib imports needed
5. Verification command
6. Constraint: don't modify outside targets

**spec-testing** task messages include:
1. ✅ Source file path
2. ✅ Known gaps (context)
3. ✅ Focus areas (from Alpha)
4. ❌ No import hints
5. ❌ Verification command was missing initially (added after Delta requested it)
6. ❌ No constraint on what to modify

**How partially absorbed:** The structured task format principle was absorbed but not the rigor. lean4-autoformalization's format is a checklist; spec-testing's is free-form Discord messages. This led to issues (Beta not knowing where to find files, needing multiple rounds to get the verification command).

### 7. Memory Management → Not Absorbed

**lean4-autoformalization:**
> "Before each context compression, agent persists to shared memory file: architecture decisions, failed approaches, techniques learned, sorry status map"

**spec-testing:** No formal memory persistence between agents. Each agent's analysis is transient (Discord messages). The shared knowledge directory (`/knowledge/`) serves as a crude equivalent, but agents don't systematically write to it during the task.

**Potential improvement:** After each module analysis, write a `module_memory.md` to `/knowledge/` capturing: confirmed gaps, killed FPs, techniques used (counting arguments, inv analysis). This would help when analyzing similar modules later.

### 8. Polish Pass → Not Absorbed (but relevant)

**lean4-autoformalization:**
> "Dedicated polish pass: extract reusable lemmas, remove maxHeartbeats, library compatibility, style conformance"

**spec-testing:** No polish pass. The phi tests are functional but not clean — multiple versions (v1→v5), verbose assume blocks, no deduplication of common patterns.

**Potential improvement:** A post-analysis pass could: (a) deduplicate phi tests that test the same gap, (b) extract common assume patterns into helper proof fns, (c) standardize naming conventions.

## Summary Table

| lean4-autoformalization Pattern | spec-testing Absorption | Status |
|--------------------------------|------------------------|--------|
| Dual-agent cycle (Plan ↔ Lean) | Alpha/Beta/Gamma pipeline | ✅ Absorbed (extended to 3 roles) |
| Context explosion prevention | Clean sub-agent sessions | ✅ Absorbed |
| Task-aversion mitigation | Fresh agents on failure | ⚠️ Implicitly absorbed |
| Model specialization | Not used (all Claude Opus) | ❌ Not absorbed |
| Informal Agent pre-reasoning | No informal witness step | ❌ Not absorbed |
| Structured worker task format | Free-form Discord messages | ⚠️ Partially absorbed |
| Memory persistence across sessions | Shared /knowledge/ dir (crude) | ⚠️ Partially absorbed |
| Polish pass for quality | No post-analysis cleanup | ❌ Not absorbed |
| Progress reporting to human | Delta status tables in Discord | ✅ Absorbed |
| Failure handling (3-5 retries then stop) | Correction cycles but no formal limit | ⚠️ Partially absorbed |
