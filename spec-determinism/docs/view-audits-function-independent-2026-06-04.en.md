# Function-Independent View Audits

## Motivation

`view` is the spec-only projection `view : V → A` from a concrete
impl-level type `V` to an abstract spec-level type `A`. Today our
spec-quality audits operate at the *method* level: we sweep `ensures`
clauses to find determinism failures, then optionally ask "could this
also have been a view problem?". That is **function-specific** view
auditing — view is judged in the context of one method's spec.

There is a second, complementary line of audit: **function-independent**
properties of `view` itself, evaluated on the (type, view) pair alone
without reference to any single method's spec. Findings here are
defects of the abstraction layer; they show up *before* any method
spec is written, and they explain a class of method-level
incompleteness ahead of time.

This doc lists five such audits and then drills into the third
(operation–view congruence), which is the one with the most
operational leverage and closest mechanical kinship with the
existing determinism harness.

## Notation

* `V` — the concrete (impl-level) type.
* `A` — the abstract (spec-level) type.
* `view : V → A` — the projection (a `spec fn`).
* `op : V × Args → V × Out` — a concrete operation on `V`. `Args` is
  the input tuple; `Out` is whatever op returns besides its
  (possibly mutated) receiver.
* `≡_view` — the equivalence relation on `V` induced by view:
  `c1 ≡_view c2  iff  view(c1) == view(c2)`.

---

## The five function-independent view audits

### 1. View fiber / information loss

What does view actually throw away? The fiber structure of view
(how many `c ∈ V` map to a given `a ∈ A`) quantifies its abstraction
strength.

* Check: search `c1 ≠ c2 ∧ view(c1) == view(c2)`; the smallest
  witness pair is the "information-loss certificate".
* Read 1: large fibers ⇒ view is genuinely abstracting.
  Read 2: fibers are all singletons ⇒ view is essentially the
  identity and is buying nothing.
* This is the structural dual of determinism: determinism asks "do
  two impls produce the same view?", fiber asks "do two states
  share the same view?". Both interrogate the fiber structure of
  view.

### 2. Field-visibility audit

For each field `f_i` of the concrete type, scan view's body:

* **read-blind**: view never reads `f_i`. Then `f_i` is invisible
  to the spec layer — any ensures that wants to constrain it has to
  route around view (e.g., a separate spec fn).
* **read-then-collapsed**: view reads `f_i` but the abstract output
  does not depend on `f_i` (verifiable by SMT:
  `∀c, c' agree-except-on-f_i. view(c) == view(c')`).

Output: a per-type visibility table — a structural inventory of
which fields are observable in spec and which are not. Trivially
mechanizable (mostly AST + cheap SMT).

### 3. Operation–view congruence

Detailed below. Slogan: view should be a congruence w.r.t. every
operation on the type — otherwise the spec layer cannot host that
operation.

### 4. View hygiene

Static / syntactic checks, no SMT:

* view must be total (no `Option<A>` return without justification).
* view must not call `closed` / `uninterp` / opaque spec functions —
  these hide view's actual semantics behind a black box.
* view must not use `choose` / `arbitrary`.
* view must not depend on exec-only constructs (interior mutability,
  global state, external calls).
* Every call site of view must already have established the type's
  invariant (`well_formed(self)`); otherwise view's behaviour on
  malformed values becomes spec-visible.

### 5. Canonical-view comparison

Maintain a registry of "this concrete type ↔ this canonical
abstract view":

| concrete type     | canonical view  |
|-------------------|-----------------|
| `Vec<T>`          | `Seq<T>`        |
| `HashMap<K,V>`    | `Map<K,V>`      |
| `BTreeMap<K,V>`   | `OrderedMap<K,V>` |
| `BitVec`          | `Set<int>`      |

When the user-defined view differs from the canonical one, emit a
finding and require justification. Similarly, when one type carries
multiple view-shaped spec fns (`view`, `to_seq`, `as_set`), demand
either a mutual-derivability proof or mark the situation as a
hazard.

---

## Operation–View Congruence: principle and procedure

### 3.1 The principle

view induces an equivalence relation `≡_view` on `V`. For an
operation `op : V × Args → V × Out` to be expressible purely
abstractly, `≡_view` must be a **congruence** w.r.t. op:

```
view(c1) == view(c2)  ⟹  view(op(c1, x).0) == view(op(c2, x).0)
                       ∧  op(c1, x).1 == op(c2, x).1
```

Equivalently: there exists a well-defined abstract operation
`op_A : A × Args → A × Out` such that the following diagram commutes:

```
    V × Args  ───op────►  V × Out
       │                      │
   view×id                 view×id
       ▼                      ▼
    A × Args  ──op_A──►   A × Out
```

Why the equivalence matters:

* If two states look identical through view but `op` makes them look
  different, then the spec layer (which only sees view) cannot
  describe op's behaviour precisely on view-equivalent inputs. Any
  ensures clause for op written purely in terms of view will be
  vacuous on at least one of the two branches.
* Congruence failure is a structural defect of the `(view, op)`
  pair. It surfaces **before** anyone writes a spec for op, which
  is exactly the function-independent property the user asked for.

When congruence fails, the spec author has three repair options:

1. **Refine view** (make it finer) until congruence is restored.
   This is the natural fix when view was dropping information op
   genuinely needs.
2. **Restrict op's domain** (tighten `requires`) so that the
   troublesome `(c1, c2, x)` triples are excluded.
3. **Accept the defect** and add concrete-state machinery into op's
   spec — typically a smell that the type's abstract level is wrong.

### 3.2 The check, as an SMT query

The harness is exactly parallel to the determinism harness:

```text
declare c1, c2 : V
declare x      : Args

assume well_formed(c1) ∧ well_formed(c2)
assume requires_op(c1, x) ∧ requires_op(c2, x)
assume view(c1) == view(c2)

let (c1', r1) = op(c1, x)
let (c2', r2) = op(c2, x)

assert view(c1') == view(c2')  ∧  r1 == r2
```

A counter-model invalidates `assert` and yields a witness triple
`(c1, c2, x)` proving `op` distinguishes two view-equivalent states.

Three knobs to set per check:

1. **State domain restriction.** Restrict `c1, c2` to states
   satisfying the type invariant. Otherwise garbage states dominate
   the findings and bury real defects.
2. **Args restriction.** Restrict `x` by op's `requires`. Failures
   on inputs op was never meant to handle are not bugs.
3. **Output equivalence.** Use view-eq on the mutated receiver, and
   choose an explicit equivalence (often syntactic equality) on the
   return value `Out`. If `Out` itself has its own view, recurse.

### 3.3 Pipeline plumbing — reuse, don't rebuild

The current determinism harness already runs the shape:

```text
assume requires(I_1, x) ∧ requires(I_2, x)
assume ensures(I_1, x, r1) ∧ ensures(I_2, x, r2)
assert eq_f(r1, r2)
```

The congruence harness is:

```text
assume well_formed(c1) ∧ well_formed(c2)
assume requires_op(c1, x) ∧ requires_op(c2, x)
assume view(c1) == view(c2)
assert view(op(c1, x).0) == view(op(c2, x).0)
     ∧ op(c1, x).1 == op(c2, x).1
```

Same SMT backend, same artifact-dump infrastructure, same
counter-example shape, same `verdict ∈ {complete, incomplete, crash,
unknown, verus_err}` reporting. The only new piece is the
**enumerator** of `(V, op)` pairs over the corpus.

### 3.4 Enumeration over the corpus

For each project:

1. Walk the type table; pick each concrete type `V` that has a
   `view` defined.
2. For each such `V`, walk methods whose receiver is `&self` or
   `&mut self`. Each such method is an `op` on `V`.
3. For each `(V, op)` pair, emit one congruence query.
4. Aggregate verdicts per pair.

Skip lists:

* Methods that take no receiver (free functions) — not operations on
  a single type.
* Methods that touch external state with no Verus model (allocator,
  filesystem, time) — not modellable, mark as `not-checkable`.
* Types whose view body uses `closed` / `uninterp` — SMT cannot
  reason inside, mark as `unknown`.

### 3.5 Finding categorization

Each failure is one of two shapes:

* **view-too-coarse.** view drops information op genuinely depends
  on. Repair option 1 is indicated: enrich view to expose what op
  reads. Detect by checking which fields appear in op's body but
  not in view's body — if such fields exist, this is the likely
  shape.
* **op-too-leaky.** view does expose everything op reads, yet op
  still produces view-distinguishable outcomes from view-equivalent
  inputs — typically because op reads through some indirection
  (pointer, index) that view did not chase. Repair option 1 is
  still indicated, but the fix is on the indirection target, not
  the directly-read fields.

Output per failure: `(V, op, c1, c2, x, shape, suggested_fix)`.

### 3.6 What this audit buys us

* **Spec-quality findings without any spec.** Congruence is a
  property of `(view, op)`; it can flag abstraction defects before
  any human writes `ensures` for op. This is the strongest
  function-independent signal in the five.
* **Cleaner attribution at the method level.** Once congruence is
  established for every op on `V`, *every* remaining method-level
  determinism failure on those ops must be on the ensures side —
  not the view side. This decouples the two repair channels we have
  been conflating.
* **Direct input to the trust-boundary ledger (3.1).** view becomes
  an explicit, audited trust boundary; congruence verdicts are part
  of its evidence file.

### 3.7 Limitations

* `closed` / `uninterp` bodies inside view defeat the check; those
  pairs are unfalsifiable in SMT and have to be hand-justified.
* External-state ops need their environment modelled — same gap as
  the determinism harness has today.
* Congruence is **necessary** but **not sufficient** for view to be
  the right abstraction. A view can be congruent with every op and
  still be too coarse to capture user intent — that residue is
  picked up by the function-specific audit (the one we are already
  doing).

---

## Roadmap (priority order, cheapest first)

1. **Hygiene (#4)** — pure AST scan, ships immediately, zero SMT cost.
2. **Field visibility (#2)** — AST scan + light SMT, ships next.
3. **Operation–view congruence (#3)** — full SMT, parallels the
   existing determinism harness most closely. Highest signal.
4. **View fiber / information loss (#1)** — SMT search, more
   open-ended; useful as narrative evidence about how much view
   abstracts.
5. **Canonical-view comparison (#5)** — needs the canonical-view
   registry to be populated; do once #1–#4 are stable.
