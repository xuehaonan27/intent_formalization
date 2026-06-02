# Spec Obligations — Taxonomy and Roadmap (v1.0)

## Context

After the Spec Determinism paper, we want to chart the broader space of
**specification obligations** — properties a specification ought to satisfy
in order to be trustworthy.

This document deliberately organizes obligations **by the kind of failure
they prevent**, not by methodology (i.e., not by whether they admit
reduction to SMT). The intent-free / intent-related distinction is recorded
as a property of each obligation, not as the organizing axis. The point is
to first decide *what is important for a spec to satisfy*; methodology
comes after.

---

## Organizing Principle

A specification lives at the intersection of three actors:

```
   User Intent  ←→  Spec  ←→  Implementation
        ↑                         ↑
      humans                   machines
```

Failures are organized into three groups by which side of the spec they
occur on:

* **Group 1 — Spec ↔ Implementation**: how the spec shapes the admissible
  implementation space `A(S)`. Intent-free properties.
* **Group 2 — Spec ↔ Intent**: how faithfully the spec captures, evolves
  with, and remains traceable to what the user actually wants.
  Intent-related properties.
* **Group 3 — Global / Meta**: cross-cutting accountability of the claims
  we make about Groups 1 and 2.

This is a re-organization from an earlier 5-group taxonomy:

* Old Group 1 (self-consistency) + old Group 2 (constraining power)
  → new Group 1.
* Old Group 3 (faithfulness) + old Group 4 (readability / maintenance)
  → new Group 2.
* Old Group 5 (meta) → new Group 3.

Within Group 2, the former obligations "Intent Traceability" (old 3.5)
and "Drift Sensitivity" (old 4.3) have been **mechanism-merged** under
new 2.1: they share the same coverage matrix `M` as the underlying
artifact. Static checks (row/column scans) and drift checks (matrix
diff with expected blast radius) are two views of the same `M`, not
two separate pipelines.

---

## Group 1 — Spec ↔ Implementation

Intent-free obligations: properties of the spec considered in relation
to its admissible implementation space `A(S)`, with no reference to user
intent.

| # | Obligation | Failure Prevented | Status |
|---|---|---|---|
| 1.1 | **Determinism** | Spec admits multiple observably different implementations | ✅ Completed (current paper) |
| 1.2 | **Attributive Non-Vacuity** | Some clause is syntactically present but not load-bearing in shaping `A(S)` | ⏸ **Parked — direction TBD** |

### Notes on 1.2 (Attributive Non-Vacuity)

The question is:

> For each clause `C` in spec `S`, does `C` actually do work in defining
> the admissible implementation space `A(S)`?

Concretely: evaluate the role of every condition in the spec.

This is **distinct** from "is the clause meaningful relative to user
intent" — that would be intent-related and belongs to Group 2.
Attributive non-vacuity is intent-free: it asks whether clauses are
syntactically present but semantically inert *with respect to `A(S)`
itself*, not with respect to what the user wanted.

Methodological candidates already on the table:

* **Redundancy check** — `A(S) == A(S − C)`. Too weak: a clause like
  `ensures result > -1000000` is not redundant but is intuitively vacuous.
* **Mutation-based** — `C` can be replaced by a wide class `C'` without
  changing `A(S)`. Requires defining the mutation class.
* **Witness-based** — there exists an admissible impl under `S − C` that
  is rejected by `S`. Equivalent to redundancy unless witness
  "meaningfulness" is added.

**Interaction with existing verification artifact.** A proof that some
implementation `I` satisfies `S` already provides a partial signal:
clauses actually invoked by the proof are demonstrably load-bearing
*for that particular `I`*. The gap is that an unused clause may still be
ruling out *other* implementations. So the proof gives partial evidence
about 1.2 but does not discharge it.

---

## Group 2 — Spec ↔ Intent

Intent-related obligations: properties of the spec considered in relation
to what the user actually wants, including the evolution of that intent
over time.

| # | Obligation | Failure Prevented | Status |
|---|---|---|---|
| 2.1 | **Intent Traceability & Drift Sensitivity** | Per-method: requirements and that method's spec clauses cannot be mapped, **and** small intent change breaks an unpredictable set of clauses | 🔴 **Active — Plan v1** |
| 2.2 | **Compositional Sufficiency** | Top method's spec properties cannot be justified by composing callee specs along the call graph | 🟡 **Planned — Plan v1 drafted** |
| 2.3 | **Correctness** | `A(S)` contains unintended implementations | ⏸ Worth doing, skipped for now |

**Note on 2.1.** Mechanism-merge of the former 3.5 (Intent Traceability)
and 4.3 (Drift Sensitivity): both share the same coverage-matrix
artifact `M` and the same decomposition pipeline. Static checks
(row/column zero detection) and drift checks (matrix diff across
versions, plus expected blast-radius bounds) are two views of the same
`M`. 2.1 is **single-method**: rows are intent atoms for one function,
columns are that function's spec clauses.

**Note on 2.2.** 2.2 is **multi-method**: it composes the top method's
spec properties top-down along the call graph, asking at each level
"does this method's spec follow from its callees' specs?". 2.1 and 2.2
share the matrix mechanism (LLM-filled binary matrices) but stay
conceptually separate — they detect different gaps (intent vs spec
layering).

**Related but unscheduled.** A "Meaningful Non-Vacuity" concept (the
intent-relative analogue of 1.2) is referenced in 2.1 as a downstream
consumer of column-zero detection on `M`. It is not on the current
roadmap, but is signalled when 2.1 produces column-orphan clauses.

---

## Group 3 — Global / Meta

Not parallel to Groups 1 and 2. Concerns the *claims we make* about the
preceding obligations and what trusted base supports those claims.

| # | Obligation | Failure Prevented | Status |
|---|---|---|---|
| 3.1 | **Assumption Accountability** | Trusted base behind a correctness / quality claim is hidden | 📌 **Placeholder — Plan v1 drafted** |

Typical hidden trust includes: equality relations (`eq_f`), reference
implementations, environmental assumptions, modeling decisions, mutation
classes if the methodology uses them, and LLM identities used for
decomposition / matrix fill (cross-link to 2.1).

---

## Current Roadmap

| Phase | Obligation | Notes |
|---|---|---|
| Done | 1.1 Determinism | Current paper |
| Parked | 1.2 Attributive Non-Vacuity | Direction explored (entropy + clause-level); no satisfying primary direction yet |
| **Active** | **2.1 Intent Traceability & Drift Sensitivity** | Plan v1: atomic `R` + binary entailment matrix `M`; static + drift views |
| Planned | 2.2 Compositional Sufficiency | Plan v1: top-down recursive matrix over the call graph; contribution-style cells; SCCs handled via fixed-point |
| Deferred | 2.3 Correctness | Worth doing, not immediate |
| Placeholder | 3.1 Assumption Accountability | Plan v1: Trust Provenance Graph; sources = developer-asserted boundary; static checks for hidden / orphan / unjustified / drifted trust |

---

## 1.2 Attributive Non-Vacuity — Status and Open Questions (Parked)

**Status.** Explored two families of approaches (entropy-style measure
over the I/O space; clause-level structural analysis). Neither produced a
satisfying primary direction. Parked indefinitely; will revisit if a new
framing emerges. See "Explored Direction A" and "Explored Direction B"
below for full design notes.

### Open Questions

1. What is the right notion of "load-bearing" for a clause? Pure
   redundancy is too weak; intent-relative meaningfulness escapes Group 1.
2. Is a single binary criterion enough, or do we need a **spectrum**
   (redundant → trivially contributing → strongly contributing)?
3. Can the criterion be witnessed constructively, in the style of the
   divergence witnesses used for determinism?
4. How does the obligation interact with the existing verification
   artifact? Does the proof of an implementation already provide partial
   evidence that specific clauses are load-bearing? Where is the gap?
5. If a mutation-class approach is used, that class itself becomes part of
   the trusted base — this immediately raises a hook into 3.1 (Assumption
   Accountability).

---

## 1.2 Attributive Non-Vacuity — Explored Direction A: Entropy / Log-Ratio over I/O Space

Recorded for completeness. **Not chosen as the primary direction** because
of fundamental tractability limits on real Verus specs, but the framing is
clean and worth preserving for later use (case studies, theoretical
sections, or restricted fragments).

### Definition

Let `A(S) ⊆ F` be the admissible implementation set. Define

```
H(S)        = log μ(A(S))
ΔH(C; S)    = H(S − C) − H(S)  ≥ 0     -- C's information contribution
```

Under spec independence across inputs:

```
log μ(A(S))      = Σ_x log μ_x(A(S)(x))
ΔH(C; S, x)     = log |A(S − C)(x)| − log |A(S)(x)|
```

This positions Determinism as the **zero-point** of the same quantity:
Determinism ⟺ ∀x. H(S, x) = 0. Non-Vacuity becomes the differential
decomposition of that quantity over clauses.

### Locked design choices (within this direction)

* **Unit**: function-space (sum-over-inputs under independence).
* **Measure**: log-ratio (entropy-style).
* **Attribution (proposed)**: marginal LOO default + Shapley optional.

### Why it is not the primary direction

`ΔH(C; S, x) = log |A(S − C)(x)| − log |A(S)(x)|` requires **counting**
satisfying assignments, which is **#P-complete** and outside the class of
problems Z3 / standard SMT solves. Z3 finds witnesses, it does not count
them.

Tractable model-counting tools cover only narrow fragments:

| Fragment | Tool | Status for typical Verus spec |
|---|---|---|
| Propositional / bitvector (bounded) | sharpSAT, D4, ApproxMC | Reachable via bit-blast for some specs |
| Presburger / linear integer | Barvinok, LattE | Closed-form counts possible |
| Quantifiers, recursion, user functions, heap | — | Not available |

Most real Verus specs use quantifiers, user-defined recursive functions,
ghost state, etc., and do not bit-blast into a fragment a model counter
can handle. So this direction is theoretically clean but engineering-wise
narrow.

### Salvageable pieces

* **Binary version (Layer 0)** — `∀x. ∃y. (S − C)(x, y) ∧ ¬C(x, y)`. A
  pure SAT-decision query, structurally identical to the Determinism
  check. Z3-doable on the full Verus spec language. This is the deployable
  residue of the entropy framing.
* **Layered fallback for quantitative cases**:
  * Layer 0 — binary load-bearing check (Z3, full spec language).
  * Layer 0.5 — bounded enumeration via blocking-clause loop on Z3
    (sample-based, hard cap K, hacky but tool-agnostic).
  * Layer 1 — true `ΔH` via #SAT / Barvinok (case-study scope only).
* The entropy framing remains the natural way to present case studies on
  restricted spec fragments, e.g. Presburger arithmetic examples.

### Hooks into other obligations

* The Layer 0 binary check is structurally the Determinism check applied
  to `(S, S − C)`. This supports presenting Determinism and Attributive
  Non-Vacuity as two faces of the same SMT pattern.
* Any move to Layer 1 (counting, distributional, asymptotic) brings in a
  trusted base (input distribution, bit-blast modeling, length bounds) —
  hook into 3.1 (Assumption Accountability).

---

## 1.2 Attributive Non-Vacuity — Explored Direction B: Clause-Level Alternatives (no I/O enumeration)

Family of approaches that operate on the clauses themselves rather than
on the admissible I/O space. All recorded as **candidates pending a
satisfying primary direction**; none chosen yet.

### B1 — Logical Redundancy / Implication Structure

Use SMT-decidable queries among clauses:

```
Σ_C := S \ {C}
C redundant     ⟺  Σ_C ⊨ C
C tautological  ⟺  ⊤   ⊨ C
C contradictory ⟺  C   ⊨ ⊥
C load-bearing  ⟺  none of the above
```

Tooling: MUS / MSS / MCS extraction. Z3-decidable on full Verus spec
language. **Weakness:** purely binary 3-way classification, well-trodden
ground, not a novel research contribution.

### B2 — Mutation Stability of the Clause

Define `C`'s "stability radius" as the largest family of replacements
`C'` for which `A(S[C ← C']) = A(S)`. Large radius → clause has low
semantic content.

Tooling: SAT decision for each candidate mutation. **Weakness:** the
mutation class itself becomes part of the trusted base (hook to 3.1) and
the approach degenerates into testing-style methodology.

### B3 — Constraint Signature / Dependency Footprint

Purely syntactic: extract `read(C)`, `write(C)`, `shape(C)` and build a
matrix of which output components each clause constrains and in which
direction.

Tooling: pure AST analysis, no SMT. **Weakness:** too coarse, cannot
distinguish overlapping clauses; semantic-blind.

### B4 — Proof-Trace Mining (Verus-native)

For each verified implementation `I`, partition spec clauses by whether
they appear in any VC's dependency set. `dead(C, I)` clauses are
demonstrably non-load-bearing for `I` (their only function is excluding
other implementations).

Tooling: Verus's existing VC generation. **Weakness:** depends on having
verified implementations; not an intrinsic property of the spec alone.

### B5 — Unique Guarantee Extraction (constructive content)

For each clause C ∈ S, constructively find a property `φ_C` such that:

```
1. S     ⊨ φ_C        -- S guarantees φ_C
2. S − C ⊭ φ_C        -- without C the guarantee disappears
3. φ_C is irreducible -- not just a restatement of C
```

`φ_C` is the **content** of C. Structurally analogous to Determinism's
divergence witness `(x, y₁, y₂)`: instead of two diverging executions
witnessing non-determinism, here a single formula witnesses C's
contribution.

Tooling: Craig interpolation, prime implicant extraction, abductive
reasoning. SMT decision level, no counting.

**Open issue:** "irreducible" needs a principled definition (e.g.,
relative to spec's own non-logical vocabulary). Hooks 3.1 if a probe
vocabulary is fixed externally.

### B6 — Spec Normalization Audit

Reformulate Attributive Non-Vacuity as **"is S in irreducible form?"**.
Define a canonical form `CF(·)` and compare `S` against `CF(S)`. Original
clauses that vanish under `CF` are vacuous; clauses that merge are
non-primitive; clauses that survive as atoms are primitive.

Tooling: QBF, SAT-based formula minimization, EPR, Z3 simplifier
pipelines. Decision-level.

Output is a **refactored spec plus a clause-mapping** — directly useful
to humans even when the spec is not vacuous. (Human-readability concerns
no longer have a dedicated group under the new 3-group taxonomy; this
cross-cutting benefit is recorded here for future reference.)

**Open issue:** canonical forms for full first-order specs do not exist;
this only works in restricted fragments.

### Cross-cutting observations

* B5 and B6 are the only candidates that produce **rich symbolic output**
  per clause rather than a number or a classification.
* B5 mirrors Determinism's constructive-witness style; B6 mirrors compiler
  optimization / refactoring style.
* All B-family approaches sidestep the #P-complete counting problem.
* Parked indefinitely (see Status section above). No B-family candidate
  emerged as a satisfying primary direction; B5 (constructive content) and
  B6 (normalization audit) remain the strongest residues should the
  question be revisited.

---

## 2.1 Intent Traceability & Drift Sensitivity — Plan v1

### Status

**Active.** Current focus. Mechanism-merge of the former 3.5 (Intent
Traceability) and 4.3 (Drift Sensitivity): both obligations share the
same coverage-matrix artifact `M` and the same decomposition pipeline.
Static checks (snapshot) and drift checks (cross-version diff) are two
views of the same `M`, not two separate pipelines.

### Pipeline

```
Step 1.  User provides intent source:
           - natural-language document (primary)
           - optional: reference implementation
Step 2.  Decompose source into atomic requirements
           R = { r_1, ..., r_n }
         (LLM proposes; user reviews; R is frozen as a versioned artifact)
Step 3.  Build coverage matrix
           M ∈ {0,1}^{n×k},  M[i,j] = 1 iff c_j (alone) covers r_i
         (LLM fills each cell with grounded citation; user can override)
Step 4.  Read off properties from M:
           - Static view : row/column sums    → Intent Traceability checks
           - Drift  view : M_v vs M_{v+1} diff → Drift Sensitivity checks
                           against user-declared expected blast radius
```

### Formal Object

```
Inputs (user-provided), per version v:
  Source_v ∈ { NL_doc, reference_impl, both }
  S_v = { c_1, ..., c_k }     -- formal spec clauses (Verus)

Derived artifacts (LLM + human review), per version v:
  R_v = { r_1, ..., r_n }     -- atomic, mutually irreducible decomposition
  M_v ∈ {0,1}^{n×k}           -- coverage matrix

Static signals (per snapshot v):
  row_sum(i) = 0  →  r_i orphan  (intent uncovered)            [F1]
  col_sum(j) = 0  →  c_j orphan  (clause serves no intent)     [F2 / Meaningful Non-Vacuity hook]

Drift signals (across v → v+1, user-labelled):
  channel ∈ { intent-led, spec-led, joint }
  ΔR = symmetric_diff(R_v, R_{v+1})
  ΔS = symmetric_diff(S_v, S_{v+1})
  ΔM = M_{v+1} ⊖ M_v                       -- cell-flip set
  expected_blast ⊆ S (for intent-led)       -- user-declared
  expected_blast ⊆ R (for spec-led)         -- user-declared
  actual_blast   = projection of ΔM onto the affected axis
  sensitivity(v→v+1) = |ΔM| / max(1, |ΔR ∪ ΔS|)
```

### Locked Definitional Choices

Static layer (inherited from former 3.5):

* **Cell semantics**: entailment-style — `M[i,j] = 1` iff `c_j` alone
  covers `r_i`, as judged by the oracle.
* **Cell value type**: binary `{0, 1}`.
* **Decomposition criterion**: **atomic irreducibility** — no `r_i` can
  be further split into `r_i', r_i''` with the same meaning.
* **Intent source**: natural language, optionally augmented by a
  reference implementation.
* **Fragmented coverage** (multiple clauses jointly covering one `r_i`):
  **out of scope**. Interpreted as evidence that decomposition is not
  atomic enough; the burden is pushed back to Step 2.

Drift layer (added by merging former 4.3):

* **Versioning is external**: user maintains `(R_v, S_v)` pairs in their
  own VCS; the framework only consumes pairs of snapshots.
* **Edit channel is user-declared**: each transition `(v → v+1)` is
  labelled `intent-led`, `spec-led`, or `joint`. The framework does not
  infer it.
* **Expected blast radius is user-declared** per labelled edit; the
  framework checks consistency between declaration and observed `ΔM`,
  it does not derive an expectation on its own.
* **Sensitivity metric** is **reported, not gated** on a fixed
  threshold — case-study dependent.
* **Joint edits are not natively supported**: users are expected to
  split joint edits into two sequential labelled transitions
  (intent-led then spec-led, or vice versa).

### Failure Modes Covered

| Layer | Mode | Description | Detection |
|---|---|---|---|
| Static | F1 | Orphan requirement (intent uncovered) | row scan: `row_sum(i) = 0` |
| Static | F2 | Orphan clause (clause without intent) | column scan: `col_sum(j) = 0` — reported as "Meaningful Non-Vacuity" signal, not a 2.1 failure per se |
| Static | F3 | Mis-mapping (LLM judges wrongly) | mitigated by grounded citation + user override; residual is LLM trust (3.1) |
| Drift  | D1 | Drift leakage (intent edit affects more clauses than expected) | `actual_blast ⊋ expected_blast` on intent-led edits |
| Drift  | D2 | Stale spec (intent edit did not propagate to dependent clauses) | `actual_blast ⊊ expected_blast` on intent-led edits |
| Drift  | D3 | Shadow intent change (spec edited without intent change, but intent should have changed) | `actual_blast` (in `R`) > 0 on spec-led edits |
| Drift  | D4 | Sensitivity anomaly (small Δ caused large blast or vice versa) | `sensitivity(v→v+1)` outside expected band |

**Explicitly out of scope:**

* F5 (Fragmented coverage) — pushed to Step 2 as a decomposition
  obligation.
* Automatic inference of expected blast radius — user must declare it.
* Resolving `joint` edits when the user fails to split them — flagged as
  unanalyzable.

### Methodology

**Static (per snapshot).**

* **Step 2 (decomposition).** LLM ingests `Source` and produces candidate
  atoms. User reviews, edits, and freezes `R` as a versioned artifact
  (e.g. `R.json`). Atomicity is enforced by user review (and optionally a
  secondary LLM audit).
* **Step 3 (matrix fill).** For each `(r_i, c_j)`, LLM emits a binary
  judgment together with a grounded citation: which part of `c_j`
  corresponds to which part of `r_i`. User can override any cell. Result
  frozen as `M.json`.
* **Step 4a (static check).** Trivial scan:
  * Flag rows with `row_sum = 0` → traceability failure for `r_i` (F1).
  * Separately report columns with `col_sum = 0` as input to the
    Meaningful Non-Vacuity signal (F2).

**Drift (across `v → v+1`).**

* **Inputs.** Two snapshots `(R_v, S_v, M_v)` and `(R_{v+1}, S_{v+1})`;
  edit channel label; optional expected blast radius.
* **Step A.** Re-run matrix fill on `(R_{v+1}, S_{v+1})` to obtain
  `M_{v+1}`.
* **Step B.** Compute `ΔM` and project per row / per column.
* **Step C.** Compare actual blast against expected; emit D1/D2/D3 as
  applicable.
* **Step D.** Report `sensitivity(v→v+1)` as a tracked metric.

**CI integration.** Re-run static checks whenever `R.json`, `M.json`,
or `S` changes. Re-run drift checks at every labelled transition. User
is responsible for keeping `R`, `S`, `M`, and the edit log coherent.

### Trusted Base (hooks into 3.1)

* The LLM used for decomposition (model identity, prompt, sampling).
* The LLM used for matrix fill (may be same or different model).
* The chosen cell semantics (entailment).
* The atomic-irreducibility criterion enforced on `R`.
* The identity and version of the source artifact (NL doc, optional
  reference implementation).
* The human reviewer's overrides on `R` and `M`.
* The user-declared edit channel label per transition.
* The user-declared expected blast radius per intent-led / spec-led
  edit.

### Cross-Obligation Reuse

* **Meaningful Non-Vacuity (unscheduled, intent-relative analogue of
  1.2)** consumes column-zero detection: `col_sum(j) = 0` means `c_j`
  is intent-relative vacuous (a stronger failure than 1.2's intent-free
  attribution).
* **2.2 Compositional Sufficiency** can lift `M` to a multi-component
  matrix `M_κ ∈ {0,1}^{n × Σ|S_κ|}` whose column blocks correspond to
  individual component specs; row-zero detection on the combined matrix
  then identifies system-level coverage gaps.
* **2.3 Correctness** consumes `R` as the authoritative intent
  reference; correctness becomes "every admissible impl under `S`
  satisfies every `r_i`", a stronger claim than coverage.

### Known Limitations

* **LLM hallucination on matrix fill** — mitigated by grounded citation
  and user override, not eliminated.
* **Circular trust** — if the same LLM both decomposes and fills the
  matrix, the two steps reinforce each other's errors. Mitigation:
  require different models, or require human review at least at one of
  the two steps.
* **Atomicity is itself an LLM/human judgment** — not formally checkable;
  treated as a trusted artifact (3.1).
* **Expected blast radius is user-declared** — its quality is the user's
  responsibility; the framework only checks consistency between
  declaration and observed `ΔM`.
* **Edit channel labelling depends on the user being honest about
  whether an edit was intent-led or spec-led**; mislabelling
  systematically hides D3 (shadow intent change).
* **Joint edits require user to split them** — true simultaneous
  intent + spec edits are unanalyzable without manual decomposition
  into two transitions.

### Open Questions for 2.1

1. Should the framework require the decomposition LLM and the matrix-fill
   LLM to be different models, to mitigate circular trust? Or is it
   sufficient to require human review at one step?
2. What is the right artifact format for `R`, `M`, and the per-edit
   drift annotations (channel + expected blast radius) to make them
   version-controllable, diff-readable, and CI-checkable?
3. When a reference implementation is supplied alongside the NL source,
   how does it factor in — only to validate `r_i` candidates, or also to
   extract implicit requirements the NL doc omits?
4. How does the framework behave when multiple intent sources disagree
   (NL doc says one thing, reference implementation does another)?
5. Is the "binary cell, atomic R" simplification stable, or will real
   case studies force a relaxation (partial scalar, group annotation)?
6. Should the sensitivity metric have a default threshold band, or is it
   always case-study calibrated?
7. For joint edits, is it tolerable to require users to split into two
   sequential labelled edits, or does the framework eventually need a
   true joint-edit semantics?

---

## 2.2 Compositional Sufficiency — Plan v1

### Status

**Planned. Plan v1 drafted.** The recursive extension of 2.1 down the
call graph: 2.1 checks one method's spec against its intent atoms;
2.2 checks each non-leaf method's spec against the union of its
callees' specs. Same matrix mechanism, different conceptual gap.

### Pipeline

```
Step 0.  Apex (= 2.1).
           Top method f_top has user-provided intent R; 2.1 produces
           M_0 ∈ {0,1}^{|R| × |atoms(S_{f_top})|}.
           This step is 2.1's responsibility, not 2.2's.

Step 1.  Extract call graph G from implementation.
           Nodes  = methods reachable from f_top.
           Edges  = direct call sites.
           Source = parser over the implementation (Verus source).

Step 2.  Compute SCCs, condense to a DAG cond(G).
           Each node n in cond(G) is either a singleton method or a
           strongly-connected group (mutual recursion).

Step 3.  Top-down traversal of cond(G).
           Recursion terminates at leaf nodes:
             leaf(n)  iff  no method in n has callees outside n
                            (i.e., all outgoing edges point inside the
                             SCC, or n's callees ⊆ trusted_base).

         For each non-leaf node n:
           rows    = ⋃_{f ∈ n} atoms(S_f)          -- parent atoms
           cols    = ⋃_{g ∈ callees(n) \ n} atoms(S_g)
                   ∪ rows                           -- self/peer refs
                                                     allowed inside SCC
           M_n ∈ {0,1}^{|rows| × |cols|}
           cell M_n[i,j] = 1
             iff atom_j contributes to atom_i being fulfilled
             (LLM judges; user reviews; grounded citation required)

Step 4.  Static scan per M_n:
           row_sum_n(i) = 0  → CompFail-1 at n (clause i unsupported)
           col_sum_n(j) = 0  → CompFail-2 at n (callee guarantee unused)

Step 5.  Mark cells whose column belongs to a same-SCC method as
         **inductive**. They represent inductive-hypothesis usage and
         require a well-foundedness / termination argument.
         The framework records the dependency; Verus is responsible for
         actually checking termination (not duplicated here).
```

### Formal Object

```
Inputs:
  I_top                                    -- top implementation
  S_f for every f reachable from I_top     -- per-method spec
  trusted_base ⊆ Methods                   -- libs / primitives
                                              (user-declared)

Derived structure:
  G        = call_graph(I_top)             -- via parser
  cond(G)  = DAG over SCCs of G

For each non-leaf node n ∈ cond(G):
  parent_atoms(n)   = ⋃_{f ∈ n} atoms(S_f)
                       where atoms(S_f) = split conjunctions at top level
                                          of each spec clause
  child_atoms(n)    = ⋃_{g ∈ direct_callees(n) \ n} atoms(S_g)
                       ∪ parent_atoms(n)         (self/peer for SCC)
  M_n               ∈ {0,1}^{|parent_atoms(n)| × |child_atoms(n)|}

Signals:
  row_sum_n(i) = 0           → CompFail-1 at (n, i)
  col_sum_n(j) = 0           → CompFail-2 at (n, j)
  M_n[i, j] = 1 ∧ col_j ∈ parent_atoms(n)
                             → inductive cell; termination obligation
                               delegated to Verus
```

### Locked Definitional Choices

* **Recursion termination**: at the bottom-most methods — methods whose
  callees are all in `trusted_base` (libraries / primitives) or empty.
  Inside an SCC, all members are treated as a single condensed node.
* **Call graph source**: extracted by a parser over the implementation.
  Pre-implementation design auditing is not supported in v1.
* **Cell semantics**: contribution-style — `M_n[i,j] = 1` iff atom `j`
  *contributes* to atom `i` being fulfilled (the same weak form used in
  2.1; LLM judges with grounded citation).
* **Atomization**: split top-level conjunctions inside spec clauses;
  otherwise treat each clause as a single atom (Verus already gives a
  clause-level decomposition).
* **Cycles / recursion**: handled via SCC condensation. Self/peer
  references inside an SCC are allowed in `M_n` and marked as
  inductive cells; the well-foundedness argument is the user's
  responsibility and is checked by Verus, not by 2.2.
* **Non-callgraph compositional coupling** (shared state, concurrency,
  cross-function invariants outside call edges): **out of scope** in
  the current Verus setting. To be revisited if the target language
  permits richer composition modes.
* **Relation to 2.1**: 2.1 is single-method (intent atoms ↔ one
  method's spec); 2.2 is cross-method (parent spec ↔ callee specs).
  They share the matrix mechanism but stay separate obligations
  because they catch different gaps. 2.1's `M_0` is the apex; 2.2's
  `M_n`'s extend below.

### Failure Modes Covered

| Mode | Description | Detection | Diagnostic interpretation |
|---|---|---|---|
| CompFail-1 | Parent clause not supported by any callee (or SCC peer) | `row_sum_n(i) = 0` | `S_n` too strong / callee under-specified / a needed callee is missing |
| CompFail-2 | Callee guarantee unused by parent | `col_sum_n(j) = 0` | Callee over-specified / parent under-uses; mirror of 1.2 at the composition level |

**Explicitly out of scope:**

* Non-callgraph coupling (see locked choice above).
* Higher-order callees decided at runtime (function pointers, dynamic
  dispatch): not handled in v1; the parser produces an under-approximate
  call graph.
* Pre-implementation design audit (no impl → no parser).
* Termination / well-foundedness of inductive cells: delegated to Verus.

### Methodology

* **Step A — call-graph extraction.** Parser ingests the Verus
  implementation, produces `G` (edges = direct calls; self-loops for
  direct recursion). Frozen as `G.json`.
* **Step B — SCC condensation.** Standard Tarjan / Kosaraju. Output
  `cond(G)` as DAG with SCC labels.
* **Step C — matrix fill, top-down.** For each non-leaf node `n` in a
  topological order of `cond(G)`:
  * Extract `parent_atoms(n)` and `child_atoms(n)`.
  * LLM emits a binary contribution judgment + grounded citation for
    each cell.
  * User reviews / overrides. Frozen as `M_n.json`.
* **Step D — static scan.** Report CompFail-1 (row-zero) and CompFail-2
  (col-zero) per node.
* **Step E — inductive-cell annotation.** Flag cells with same-SCC
  columns. Emit them as termination obligations for Verus to discharge.
* **Drift hook.** When `I_top` or any `S_f` changes, re-run parser,
  re-compute `cond(G)`, and re-fill only the affected `M_n`'s. Reuses
  2.1's drift machinery (channel labelling, expected blast radius)
  applied per matrix.

### Trusted Base (hooks into 3.1)

* The parser used to extract `G` (correctness of call-graph extraction,
  treatment of indirect calls).
* The `trusted_base` declaration (which methods are leaves).
* The LLM used for matrix fill (model, prompt, sampling).
* The contribution cell semantics.
* The atomization rule (top-level conjunction split, else atomic).
* The human reviewer's overrides on each `M_n`.
* The termination evidence for inductive cells (assumed checked by
  Verus; if Verus accepts the recursive definition, the inductive
  cells are considered discharged).

### Cross-Obligation Reuse

* **2.1** supplies `M_0` (apex) and the matrix-fill pipeline. 2.2
  inherits both directly.
* **1.2 (composition mirror)**: CompFail-2 is the composition-level
  analogue of 1.2's intent-free non-vacuity — a callee guarantee
  present in `S_g` but not contributing to any parent property. More
  actionable than 1.2 itself because the "consumer" is concretely
  identified.
* **Drift sensitivity (from 2.1)**: each `M_n` admits the same
  matrix-diff + expected-blast-radius treatment; drift checks
  generalize for free.
* **3.1**: the union of every `M_n`'s trusted artifacts plus the parser
  and trusted_base declaration is the aggregate trusted base for 2.2.

### Known Limitations

* **Pure call-graph view.** Misses shared-state, concurrency, and
  cross-function invariant coupling. Acceptable in the current Verus
  target; would need an addendum for concurrent / distributed settings.
* **Atomization heuristic.** Splitting conjunctions captures the
  syntactic structure but may miss semantic atomicity within a single
  clause (e.g., an existential whose body has multiple sub-properties).
* **LLM contribution judgment** is approximate; same circular-trust
  concerns as 2.1, magnified by being applied at every non-leaf node.
* **Indirect calls.** Function pointers, dispatch, callbacks produce an
  under-approximate `G`; missed edges manifest as spurious CompFail-1.
* **Implementation required.** No impl ⇒ no parser ⇒ no 2.2 check.
  Pre-implementation design audit deferred to a future "declarative
  call graph" mode.
* **Recursion termination is not the framework's concern**; if Verus
  cannot discharge the well-foundedness obligation, the corresponding
  inductive cells are effectively unjustified, but 2.2 itself will not
  flag this — it surfaces as a Verus failure.

### Open Questions for 2.2

1. For SCCs with more than one method, is the per-SCC consolidated
   matrix the right grain, or should each method retain its own matrix
   with explicit cross-references inside the SCC?
2. Should the framework auto-emit inductive cells as Verus-checkable
   termination lemmas, or just record them informationally?
3. How should higher-order / dispatched calls be handled — coerce the
   parser to over-approximate, require user declarations, or accept the
   under-approximation as a known blind spot?
4. Ghost / spec functions referenced inside `S_f` do not appear in the
   impl call graph but the LLM may need them as context — should they
   be added as virtual columns, or treated as part of `trusted_base`?
5. For partial implementations (stubs, `unimplemented!`), what is the
   expected behavior — skip the subtree, treat as leaf, or fail?
6. Atomization quality: does syntactic conjunction splitting suffice in
   practice, or do real Verus specs require a stronger atomization
   pass (and if so, by what oracle)?
7. Should 2.2 be runnable in "declarative call graph" mode, where the
   user provides `G` directly without an impl, enabling pre-impl
   design audit?

---

## 3.1 Assumption Accountability — Plan v1

### Status

**Placeholder → Plan v1 drafted.** Activates once 2.1 and 2.2 produce
real per-obligation trust lists to aggregate. 3.1 is meta: it does
not introduce new failure semantics of its own, but makes the
trust-supporting any claim explicit, structured, and auditable.

### Core Idea

A single repository-wide **Trust Provenance Graph** `T`:

* Nodes are trust entries.
* Edges encode "depends on for trust" — `(a, b) ∈ E` means
  *b depends on a*; equivalently, b's incoming edges enumerate b's
  trust sources.
* **Sinks** (no out-edges): **claims** — one per (obligation × scope
  artifact × version) — i.e., the assertions we want to make.
* **Internal nodes**: *derived* trust entries that are themselves
  produced from named sources (with the dependency enumerated as
  in-edges).
* **Sources** (no in-edges): trust entries that cannot be derived
  from anything else in the framework — they are the **trust
  boundary the developer is responsible for**. Each carries an
  out-of-band justification owned by a named developer.

Per-obligation "Trusted Base" subsections (already drafted in 1.1 /
1.2 / 2.1 / 2.2) become the source-of-truth fragments. 3.1 unions
them, identifies sources, and runs static checks.

### Pipeline

```
Step 1.  Collection.
           Each obligation plan emits a graph fragment T_i:
             nodes  = its claims + derived artifacts + sources
             edges  = "depends on for trust"
           Source: each plan's `trust.json` (the existing "Trusted
                   Base" subsections become machine-readable).

Step 2.  Union into global T.
           Same-id nodes across fragments collapse to a single node.
           This is how shared trust is detected automatically:
           if the same atomization rule is referenced by 2.1 and
           2.2, it appears as one node with multiple downstream
           dependents.

Step 3.  Source identification.
           N_source = { n ∈ N : in-degree(n) = 0 }
           For each n ∈ N_source require metadata:
             { rationale, owner, justification_ref, last_reviewed }
           Sources lacking these fields → TrustFail-3.

Step 4.  Static scans:
           TrustFail-1 (hidden):    claim c references an artifact
                                    not present in T (citation in
                                    plan text without a matching
                                    node).
           TrustFail-2 (orphan):    node n has no path to any claim
                                    (declared but contributes to
                                    nothing).
           TrustFail-3 (unjustified
                       source):     n ∈ N_source missing required
                                    metadata fields.
           TrustFail-4 (drift):     between versions of T, the source
                                    set diff is non-empty and not
                                    declared in a labelled edit log
                                    (reuses 2.1's drift mechanism).

Step 5.  Per-claim audit view.
           For any claim c, the reverse-reachable sub-DAG of c is
           rendered as c's trust certificate. The intersection of
           that sub-DAG with N_source is the developer-responsibility
           set for c.
```

### Formal Object

```
T = (N, E)
  N = N_claim ⊎ N_derived ⊎ N_source         -- partition
  E ⊆ N × N
    (a, b) ∈ E  ⟺  "b depends on a for trust"
                    equivalently: a is an in-source of b

  T is acyclic.

N_claim:    sinks (out-degree = 0)
            tags: { obligation, scope_artifact, version }
N_derived:  internal (in-degree ≥ 1 ∧ out-degree ≥ 1)
            tags: { kind (artifact | judgment | tool-output | ...),
                    producer, producer-inputs }
N_source:   sources (in-degree = 0)
            tags: { rationale, owner, justification_ref,
                    last_reviewed }

For a claim c:
  trust(c)          = ancestors(c) in T (reverse reachability)
  derived(c)        = trust(c) ∩ N_derived
  responsibility(c) = trust(c) ∩ N_source   -- what the developer
                                              must vouch for to back c
```

### Locked Definitional Choices

* **Edge convention**: `(a, b) ∈ E` ≡ "b depends on a"; b's in-edges
  enumerate b's trust sources. Sinks = claims, sources = developer-
  asserted boundary.
* **Granularity**: per-claim = (obligation × scope artifact × version).
* **Scope of trust**: formal + tooling + process (per Fork C3) —
  mirrors what 2.1 / 2.2's Trusted Base subsections already enumerate
  (LLM identity, prompt, human reviewer, parser, etc.).
* **Capture mode**: declarative (per Fork D1). Each plan owns a
  `trust.json` fragment; 3.1 unions and audits.
* **Failure policy** (per Fork F2): TrustFail-1 (hidden trust) is
  blocking; TrustFail-2 / -3 / -4 are warnings surfaced for review.
* **Decomposition depth**: the developer chooses where to stop
  decomposing. A node declared as `source` is final responsibility;
  any node declared as `derived` must enumerate its in-edges. This is
  how the framework stays agnostic to how deep an audit goes — the
  graph is grown by writing more in-edges, never by changing the
  framework.
* **Node identity**: same id ⇒ same node across all obligations. This
  is the mechanism that makes shared trust visible.
* **Acyclicity**: enforced. Cycles indicate id misuse and must be
  resolved by id refactoring; trust cannot be circular.
* **Inconsistent role across obligations** (the old Fork B3) is
  **not** auto-detected in v1 — it is surfaced to human reviewers as
  the node's downstream context.

### Failure Modes Covered

| Mode | Description | Detection |
|---|---|---|
| TrustFail-1 | Plan text references an artifact missing from T | Cross-check plan citations against `N`; blocking |
| TrustFail-2 | Node n unreachable in reverse from any claim | Reachability scan over `T`; warning |
| TrustFail-3 | Source node missing rationale / owner / justification | Metadata check on `N_source`; warning |
| TrustFail-4 | Source set changed between versions without ledger entry | `diff(T_v1.source, T_v2.source)` ∧ no labelled edit; warning |

**Explicitly out of scope:**

* TrustFail-5 (untenable trust): semantically checking whether a
  declared assumption actually holds. 3.1 audits **structure**, not
  **content**. A node labelled "Z3 is sound" passes 3.1 regardless of
  whether Z3 actually is.
* Automated discovery of implicit trust. If a plan secretly depends on
  an artifact but never textually cites it, 3.1 will not catch it.
* Cross-organization trust composition / federated trust — single
  repository / single dev team in v1.

### Methodology

* Each existing "Trusted Base" subsection (in 1.1, 1.2, 2.1, 2.2)
  becomes a machine-readable `trust.json` fragment co-located with
  that obligation's plan.
* A union tool produces global `T.json` per repo version.
* A scanner runs the four TrustFail checks on every CI run and on
  every freeze of `R.json`, `M.json`, `M_n.json`, `G.json`.
* For audit, the per-claim sub-DAG is rendered as the "trust
  certificate" attached to that claim.

### Trusted Base (hooks back into 3.1, recursively)

3.1 audits itself. Its own trust includes:

* The union algorithm + id-collision policy.
* The "developer chooses where to stop decomposing" convention.
* The source-vs-derived classification rule.
* The set of required metadata fields on `N_source`.
* The static-scan implementation.
* The plan-text → node-citation extractor (for TrustFail-1).

These appear as nodes in `T` themselves, with their own sources (e.g.,
"id-collision policy" → source = the dev team's id schema document).

### Cross-Obligation Reuse

* **Subsumes** the "Trusted Base" subsections in 1.1 / 1.2 / 2.1 /
  2.2 — those become the source-of-truth fragments rather than
  parallel inline lists.
* **Drift labelling reused from 2.1**: when `N_source` changes, the
  same edit-channel labels (`intent-led`, `spec-led`, `impl-led`)
  apply to trust-set deltas, plus a fourth label `trust-led` for
  pure trust-base edits (e.g., LLM upgrade).
* **Shared-trust visibility**: node identity collapse exposes when
  obligations ride on the same artifact. If LLM-X is upgraded, the
  set of claims affected is exactly the out-edge closure of the
  LLM-X node — no separate audit needed per obligation.
* **2.2 hook**: `trusted_base` (the leaf-method declaration used to
  terminate 2.2's recursion) is itself a source node in `T`. This
  ties 2.2's structural choice back into the global trust ledger.

### Known Limitations

* **Structure only**, not content — the framework cannot tell whether
  a declared assumption is actually true.
* **Discovery is purely declarative** — implicit trust escapes
  detection unless plan text cites the artifact.
* **Metadata quality is governance** — `rationale` and
  `justification_ref` fields are only as informative as the
  developer makes them.
* **Versioning required** — TrustFail-4 needs every plan + trust
  fragment to be version-stamped; depends on the same versioning
  hook 2.1 needs.
* **Inconsistent-role detection** is left to humans; the framework
  surfaces the multi-context view but does not auto-flag conflicts.
* **Per-claim granularity may be too fine** at scale; an aggregated
  "per-module" view may need to be derived on top.

### Open Questions for 3.1

1. Should `N_source` rationale follow a controlled vocabulary (e.g.,
   `{empirical, axiomatic, vendor-attested, formal-elsewhere}`) or
   stay free-form for v1?
2. Canonical id schema for shared trust entries (e.g.,
   `llm:gpt-4-turbo@2024-04`, `tool:verus@0.x`, `axiom:z3-sound`,
   `human:alice`) — defined now or after first case study?
3. Should the tool emit a diff-friendly "trust delta" per version
   stamp, to make code-review of trust changes tractable?
4. When a single source node weakens (e.g., narrower vendor
   attestation), should the framework auto-warn every downstream
   claim, or rely on the audit pass to surface it?
5. Per-claim granularity — `obligation × scope_artifact × version` —
   is it the right unit, or should the unit be per-spec-clause?
6. Should "inconsistent role across obligations" (the old Fork B3)
   be auto-detected once a role taxonomy exists, or left to human
   review long-term?
7. How are claim nodes versioned when only their *trust* changed but
   the obligation otherwise passes the same — re-issue a new claim
   id, or annotate the same id with a version list?


