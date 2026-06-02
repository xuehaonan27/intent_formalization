# Spec Obligations — Overview (v1.0)

## 1. Purpose

This document is a high-level synthesis of the *Spec Obligations*
research line. It answers two questions:

1. What is the overall picture — what failures of a specification do we
   want to prevent, and how do those failures organize?
2. For each obligation we plan to tackle, what is the approach in one
   paragraph — what artifact, what failure modes, what mechanism?

It is the **front-door** document. The companion file
[`spec-obligations-1.0.md`](./spec-obligations-1.0.md) is the working
document: full per-obligation plans, locked design choices, formal
objects, methodology details, and open questions. When in doubt about
a detail, that file is the authority; this one is the map.

---

## 2. The Question

Specifications are tightening as deductive verifiers (Verus, Dafny, F*)
become practical and as code-synthesis tools generate against natural-
language intent. Two forces follow:

* The spec is the **interface** between the user and the machine.
  Whatever the spec says becomes ground truth for code synthesis,
  proof, and audit.
* The spec is **authored under uncertainty**: NL intent is fuzzy, the
  formal language is precise, the gap is bridged by humans (and LLMs)
  with no systematic check that the bridge is sound.

A spec that the verifier accepts is not necessarily a spec that *should
have been written*. We need a taxonomy of the failures a spec can
have, even when it type-checks and verifies, so each can be argued
about separately.

---

## 3. Big Picture

A specification lives at the intersection of three actors:

```
   User Intent  ←→  Spec  ←→  Implementation
        ↑                         ↑
      humans                   machines
```

Failures live on the **sides** and at the **meta** level:

* **Group 1 — Spec ↔ Implementation** (*intent-free*). How the spec
  shapes the admissible implementation space `A(S)`. These obligations
  are statements about the spec alone, against the machine.
* **Group 2 — Spec ↔ Intent** (*intent-related*). How faithfully the
  spec captures, evolves with, and remains traceable to what the user
  actually wants. These obligations require an explicit model of intent.
* **Group 3 — Global / Meta**. Cross-cutting accountability of the
  claims we make in Groups 1 and 2 — what trusted base supports them.

---

## 4. Obligations at a Glance

| # | Obligation | Group | Question | Status |
|---|---|---|---|---|
| 1.1 | Determinism | 1 | Does `S` admit two observably different impls? | Done |
| 1.2 | Attributive Non-Vacuity | 1 | Is every clause of `S` load-bearing in shaping `A(S)`? | Planned |
| 2.1 | Intent Traceability & Drift Sensitivity | 2 | Per method: do intent atoms and spec clauses align, and stay aligned under edits? | Planned |
| 2.2 | Compositional Sufficiency | 2 | Does the top spec follow from the composition of callee specs along the call graph? | Planned |
| 2.3 | Correctness | 2 | Does `A(S)` contain only intended implementations? | Deferred |
| 3.1 | Assumption Accountability | 3 | What trusted base does every claim ride on, and is any of it hidden? | Planned |

The next concrete moves are on **1.2** and **2.1**; 2.2 and 3.1 stay
as drafted plans, activating once 1.2 / 2.1 produce concrete
artifacts to feed them. 2.3 is acknowledged and held.

---

## 5. Recurring Design Patterns

Three patterns appear across multiple obligations and explain why the
plans look structurally alike. They align directly with the three
groups: one design move per group, with Group 3 splitting into two
dual sub-patterns.

**Pattern 1 (Group 1 — Spec ↔ Implementation): spec's value is how
much it compresses the uncertainty of `A(S)`.**

Every Group-1 obligation asks "does `S` shrink `A(S)` enough / does
each piece of `S` participate in that shrinking?":

* **1.1 Determinism** — does `S` shrink `A(S)` down to a single point
  modulo the chosen equivalence relation `eq_f`? If not, two
  observably-different implementations are both admissible.
* **1.2 Attributive Non-Vacuity** — does every clause `C` in `S`
  actually contribute to that compression? If `A(S − C) = A(S)`, then
  `C` is dead weight.

Shared mental model: **the spec is a constraint generator**; a Group-1
failure is "the spec failed to constrain where it should have" or "a
clause was syntactically present without doing constraining work".

**Pattern 2 (Group 2 — Spec ↔ Intent): decompose intent into atomic,
non-ambiguous sub-intents, then match against the formal spec.**

This is *decompose-then-map* applied to the intent side:

* **2.1** — apex case: rows = atomic user intent `r_i`, cols = method
  spec atoms `c_j`; the binary matrix `M` is scanned for row-zero
  (intent uncovered) and col-zero (clause without intent).
* **2.2** — recursion: at every non-apex node, the "intent" is no
  longer the user's — it is the **parent spec acting as intent for
  its callees**. The same decompose-then-map pattern recurses; each
  level is a per-node matrix `M_n` with the same two scans.

Shared insight: **decomposition quality is the bottleneck**. If the
demand side is atomic and non-overlapping, the coverage check
collapses to trivial row/col scans. If atoms are fragmented (multiple
cells jointly cover one row), the framework explicitly pushes that
back as a decomposition obligation rather than tolerating partial
cells. This is why 2.1 makes "atomic irreducibility of `R`" a hard
locked choice.

**Pattern 3 (Group 3 — Global ↔ Local): two dual stitchings.**

Group 3 is not a single pattern but a *pair of dual moves* that
together let the framework move between local checks and global
properties.

* **3a. Top-down decomposition** (the 2.2 style). Start with a
  *global* goal — a property of the apex spec — and decompose it
  along the call graph until every layer becomes a *local* matrix
  check. The framework's job is structural: produce locally-checkable
  obligations from globally-stated goals. SCCs become condensed nodes;
  termination of self/peer references is delegated to Verus, not
  duplicated.
* **3b. Bottom-up aggregation** (the 3.1 style). Each obligation
  declares its *local* Trusted Base in its own plan. 3.1 unions them
  by node id into a single *global* Trust Provenance Graph; the
  outermost layer (sources) becomes the developer-asserted boundary
  spanning the whole project. Navigation is reverse — from any claim
  back to its source closure — so per-claim audit is a sub-DAG query.

The two are dual:

| | 3a (top-down) | 3b (bottom-up) |
|---|---|---|
| Entry point | Global goal | Local declarations |
| Direction | Decomposed downwards along call graph | Aggregated upwards by id collapse |
| Output | Local matrix per node | Global graph; per-claim sub-DAG |
| Failure shape | Row/col-zero per local matrix | Hidden / orphan / unjustified / drifted |

The framework relies on **both**: top-down keeps every check local
enough to be tractable, bottom-up keeps every local claim reconnected
to a global accountability ledger. Neither alone closes the loop.

---

## 6. The Obligations, One Section Each

Full plans, locked choices, formal objects, and methodology live in
`spec-obligations-1.0.md`.

---

### 6.1 Determinism (1.1)

**Question.** Given spec `S` and an equivalence relation `eq_f` on
observable outcomes, does every pair of admissible implementations
`I_1, I_2 ∈ A(S)` produce `eq_f`-equivalent observations on every
input? If not, the spec under-constrains: two equally "correct"
implementations can behave observably differently.

**Artifact.** The spec itself + the chosen `eq_f`. No new
decomposition required.

**Detection.** Constructive: find a witness input on which two
admissible impls disagree under `eq_f`. Encoded via SMT in the paper.

---

### 6.2 Attributive Non-Vacuity (1.2)

**Question.** For each clause `C` of spec `S`, is `C` actually doing
work in defining `A(S)`? A clause that can be deleted (or replaced by
a wide class of weaker clauses) without changing `A(S)` is
syntactically present but semantically inert. Distinct from the
intent-relative analogue ("does this clause correspond to any user
intent?"), which is a Group-2 concern.

**What we'd want.** A per-clause verdict that is stronger than
"redundant w.r.t. `A(S)`" — `result > -1000000` is not redundant but
is intuitively vacuous — but does not require a full enumeration of
the input space.

**What was explored.** Two families:

* **Direction A — entropy over the I/O space.** Measure how much
  information the clause contributes to constraining `A(S)`. Stalled
  on the #P-complete counting underneath and the input-space-infinity
  problem (a Z3 witness solver is not in general capable of summing
  log-probabilities over an infinite input domain).
* **Direction B — clause-level structural analysis.** Six sub-options
  (B1–B6) ranging from mutation tests through constructive content to
  normalization audits. None emerged as a satisfying primary direction.

---

### 6.3 Intent Traceability & Drift Sensitivity (2.1)

**Question.** *Per method.* Given the user's intent (NL doc and
optionally a reference implementation) and the method's spec, can we
verify (a) every requirement is covered by some spec clause, (b)
every clause exists for some requirement, and (c) when the user
edits intent, the spec changes correspondingly — and only
correspondingly?

**Central artifact.** Let `R = {r_1, ..., r_m}` be the set of
*atomic intent requirements* decomposed from the user's
natural-language intent (one requirement per row, irreducible and
non-overlapping by construction). Let `S = {c_1, ..., c_n}` be the
set of *formal spec clauses* of the method (one clause per column).
The central artifact is the binary coverage matrix
`M ∈ {0,1}^{|R| × |S|}` defined by `M[i, j] = 1` iff `c_j` alone
entails `r_i`. The matrix is LLM-filled with grounded citations and
human-reviewed; both `R` and `M` are frozen as versioned artifacts.

**Failure modes.**

* *Static (snapshot view of `M`):*
  * **F1 Orphan requirement** — `row_sum(i) = 0`: `r_i` has no spec
    clause covering it.
  * **F2 Orphan clause** — `col_sum(j) = 0`: `c_j` exists without any
    intent justification (this is reported as the "Meaningful
    Non-Vacuity" signal — the intent-relative analogue of 1.2).
  * **F3 Mis-mapping** — wrong LLM judgments; mitigated by grounded
    citations and human override.

* *Drift (cross-version view, two snapshots labelled by edit channel
  `intent-led` / `spec-led` / `joint`):*
  * **D1 Drift leakage** — intent edit affects *more* clauses than
    the user declared expected.
  * **D2 Stale spec** — intent edit fails to propagate to dependent
    clauses.
  * **D3 Shadow intent change** — spec-led edit that should have come
    paired with an intent change.
  * **D4 Sensitivity anomaly** — disproportionate `|ΔM| / |ΔR ∪ ΔS|`
    relative to expected.

**Mechanism.** LLM proposes, human reviews, framework scans. The
static checks are O(|R|·|S|) trivial scans of `M`; the drift checks
are diffs of consecutive frozen `M`'s against user-declared expected
blast radius. *No* new methodology beyond decomposition + matrix
fill + diff is needed — that is the merge insight that brought the
old "Intent Traceability" (static) and "Drift Sensitivity" (dynamic)
under one umbrella.

---

### 6.4 Compositional Sufficiency (2.2)

**Question.** Even if every individual method's spec is "good" in
isolation, the top method's behavior is delivered by *composing*
callee specs along the call graph. Does the top spec's properties
follow from the callees'? Is some parent property unsupported by any
callee guarantee? Is some callee guarantee never used?

**Central artifact.** A *family* of binary matrices, one per non-leaf
node of the call graph (after SCC condensation): for each node `n`,
`M_n ∈ {0,1}^{|parent_atoms(n)| × |child_atoms(n)|}`. Rows are atoms
of `n`'s spec; columns are atoms of `n`'s direct callees' specs (with
self/peer references inside an SCC allowed and marked **inductive**).
Cell `M_n[i, j] = 1` iff child atom `j` *contributes to* parent atom
`i` — a weaker condition than entailment, judged by LLM with
grounded citation.

**Failure modes.**

* **CompFail-1** — `row_sum_n(i) = 0`: parent clause `i` of node `n`
  is not supported by any callee or peer. Either `S_n` is too strong,
  a callee is under-specified, or a callee is missing.
* **CompFail-2** — `col_sum_n(j) = 0`: callee atom `j` is never used
  by any parent clause. The composition-level mirror of 1.2.
* **Inductive cells** — `M_n[i, j] = 1` with `col_j ∈ parent_atoms(n)`
  (an SCC self/peer reference). Recorded as termination obligations
  to be discharged by Verus, not by the framework.

**Mechanism.** Parser extracts the call graph from the
implementation; Tarjan/Kosaraju condenses SCCs into a DAG; the
top-down traversal fills one matrix per non-leaf node; static scan
emits CompFail-1 / -2. Same mechanism as 2.1, recursed.

**Relation to 2.1.** 2.1 is *single-method*: intent atoms vs one
method's spec. 2.2 is *multi-method*: parent spec atoms vs callee
spec atoms, all the way down to leaves. They share the matrix
mechanism but stay conceptually separate — different gaps. 2.1's
`M_0` (the matrix at the apex) is the seed of 2.2's recursion.

**Out of scope.** Non-callgraph coupling (shared state, concurrency,
callbacks) — acceptable in the current Verus target.

---

### 6.5 Correctness (2.3)

**Question.** Does `A(S)` contain only implementations the user
*intended*, or does it admit "correct under the spec but wrong from
the user's view" implementations?

**Why this is structurally hard.** This is the deepest Group-2
obligation but also the hardest to operationalize without circular
reasoning (the user's "true" intended `A(S)` is precisely what `S` is
supposed to capture). Plausible practical handles — differential
testing against a reference implementation, equivalence checking
against a stronger oracle spec — are not framework-shaped problems.

---

### 6.6 Assumption Accountability (3.1)

**Question.** Every claim made by 1.1 / 1.2 / 2.1 / 2.2 rides on some
trusted base — solvers, LLMs, prompts, human reviewers, vendor
attestations, modeling choices, equality relations, parsers. What if
that trust were *first-class*: enumerated, version-stamped, audited,
and reusable across obligations?

**Central artifact.** A repository-wide **Trust Provenance Graph**
`T`:

```
T = (N, E)
  N = N_claim ⊎ N_derived ⊎ N_source
  (a, b) ∈ E  ⟺  "b depends on a for trust"
```

* **Sinks** are *claims* — one per (obligation × scope × version).
* **Internal nodes** are *derived* trust entries, themselves produced
  from named inputs (with the inputs enumerated as in-edges).
* **Sources** are nodes with no in-edges: the **outermost layer of
  the graph**, what the developer must vouch for out-of-band because
  it cannot be derived from anything else in the framework. Each
  source carries `{rationale, owner, justification_ref,
  last_reviewed}`.

The graph is built by **unioning** the "Trusted Base" subsections
already drafted in 1.1 / 1.2 / 2.1 / 2.2 — same id ⇒ same node, so
shared trust (e.g., an LLM used by both 2.1 and 2.2) is detected
automatically.

**Failure modes.**

* **TrustFail-1 hidden** — plan text references an artifact that has
  no node in `T`. *Blocking.*
* **TrustFail-2 orphan** — node not reverse-reachable from any
  claim. *Warning.*
* **TrustFail-3 unjustified source** — source node missing required
  metadata fields. *Warning.*
* **TrustFail-4 trust drift** — source set changes across versions
  without a labelled edit log entry. *Warning.* (Reuses 2.1's drift
  mechanism; adds a fourth edit channel `trust-led`.)

**Out of scope.** TrustFail-5 (semantic untenability of an assumption
— 3.1 audits structure, not content); automatic discovery of implicit
trust; cross-organization federated trust.

---

## 7. Where We Start

Concretely, the next moves are on **1.2 (Attributive Non-Vacuity)** and
**2.1 (Intent Traceability & Drift Sensitivity)**: 1.2 to land a
working primary direction for clause-level non-vacuity, and 2.1 to
validate the per-method matrix on a real Verus case study. The other
obligations (2.2, 3.1) stay as drafted plans and activate once 1.2/2.1
produce concrete artifacts to feed them.
