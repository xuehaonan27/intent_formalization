# Two-Step Abstract Determinism Plan

## 0. Motivation

The current determinism check asks whether a method spec is complete
for a **fixed concrete input**: once the input is fixed, can the spec
still admit two observably different outputs?

The proposed extension keeps that first step unchanged, and then adds a
second step only for the cases where the first step already succeeds
and the input contains at least one object with a `view`. The second
step asks whether the complete spec is also **abstract-deterministic**:
if two concrete inputs look the same at the view layer, does the spec
force their outputs to look the same at the view layer too?

This separates two defects:

1. **Spec incompleteness** — the spec permits multiple outputs for one
   fixed concrete input.
2. **Abstract non-determinism** — the spec is complete per concrete
   input, but the result still depends on concrete representation
   details hidden by `view`.

---

## 1. Notation

Use notation consistent with the existing pipeline doc:

* Target function: `f(args) -> R`.
* `P(args)` — the function precondition / `requires`.
* `Q(args, r)` — the postcondition relation / `ensures`; `r` is the
  whole post-output tuple, including the return value and any
  post-state object that must be compared.
* `E_R(r1, r2)` — the output equivalence used by the current
  determinism pipeline, i.e. `det_<f>_equal(r1, r2)`.

For the second step, split the input into:

* `o` — the view-bearing object input. For a method receiver, this is
  the pre-state object (`old(self)` in Verus notation).
* `a` — all other arguments, kept syntactically identical across the
  two compared runs.
* `V(o1, o2)` — the input-view equivalence:

```text
V(o1, o2)  :=  view(o1) == view(o2)
```

For multiple view-bearing inputs, generalise `o` to a tuple and define:

```text
V((o1^1, ..., o1^k), (o2^1, ..., o2^k))
  :=  view_1(o1^1) == view_1(o2^1)
   ∧  ...
   ∧  view_k(o1^k) == view_k(o2^k)
```

The first implementation can start with the single-object case and
later lift to this product relation.

---

## 2. Step 1 — existing concrete-input determinism

For each target `f(args) -> R`, first run the existing obligation:

```text
P(args)
∧ Q(args, r1)
∧ Q(args, r2)
⇒
E_R(r1, r2)
```

This is the current "same concrete input" check. In Verus template
shape:

```rust
proof fn det_<f>(<args>, r1: R, r2: R)
    requires
        P(args),
        Q(args, r1),
        Q(args, r2),
    ensures
        E_R(r1, r2),
{
    // existing proof synthesis / LLM proof / SMT check path
}
```

Verdict:

* If this fails, the spec is incomplete. Do **not** run Step 2; the
  abstract-determinism question would be confounded by ordinary
  incompleteness.
* If this passes, the spec is complete for each fixed concrete input.
  Such targets become possible Step 2 candidates.

Candidate filter for Step 2:

```text
Step1Verdict(f) ∈ {complete, complete+LLM}
∧ input(f) contains a view-bearing object o
```

Skip `incomplete`, `unknown`, `crash`, and `verus_err` targets.
Also skip complete targets whose inputs contain no object with a
resolvable `view`.

---

## 3. Step 2 — abstract determinism

For a Step 2 candidate `f(o, a) -> R`, compare two runs with:

* different concrete objects `o1`, `o2`;
* the same non-object arguments `a`;
* view-equivalent object inputs: `V(o1, o2)`;
* spec-admissible outputs `r1`, `r2`.

The core obligation is:

```text
V(o1, o2)
∧ P(o1, a)
∧ P(o2, a)
∧ Q(o1, a, r1)
∧ Q(o2, a, r2)
⇒
E_R(r1, r2)
```

This says: after Step 1 has already established that each concrete
input has a unique abstract output, that unique abstract output must
be a function only of `view(o)` and `a`, not of hidden concrete
representation details inside `o`.

Template shape:

```rust
proof fn abstract_det_<f>(
    o1: T,
    o2: T,
    <shared_args>,
    r1: R,
    r2: R,
)
    requires
        V(o1, o2),
        P(o1, <shared_args>),
        P(o2, <shared_args>),
        Q(o1, <shared_args>, r1),
        Q(o2, <shared_args>, r2),
    ensures
        E_R(r1, r2),
{
    // same proof path as det_<f>, but with paired view-equal inputs
}
```

For `&mut self` methods:

* `o1`, `o2` are the two old receivers: `old(self1)`, `old(self2)`.
* `r1`, `r2` include both the post receivers and return values.
* `E_R(r1, r2)` should compare post receivers at the same level the
  existing equal-fn uses, usually through their `view`.

For pure `&self` methods:

* there is no post receiver;
* `r1`, `r2` are just return values;
* `E_R` is equality or the return type's existing view-aware equal-fn.

---

## 4. Optional but recommended: domain preservation

For a function to be genuinely defined on the view quotient, the
precondition should also respect `view`:

```text
V(o1, o2)
⇒
(P(o1, a) ⇔ P(o2, a))
```

This can be checked separately as:

```rust
proof fn domain_preserve_<f>(o1: T, o2: T, <shared_args>)
    requires
        V(o1, o2),
    ensures
        P(o1, <shared_args>) == P(o2, <shared_args>),
{
    // prove or refute with the same infrastructure
}
```

If domain preservation fails, then the operation is not cleanly
defined on the quotient even before talking about outputs: two objects
that are identical through `view` disagree on whether `f` is legal.

The first version can report this as a separate warning rather than
blocking the core Step 2 check, because the core check already assumes
both `P(o1, a)` and `P(o2, a)`.

---

## 5. Verdict table

| Step 1 concrete determinism | Step 2 abstract determinism | Meaning |
|---|---|---|
| fail | skipped | Ordinary spec incompleteness: `Q` allows multiple outputs for one concrete input. |
| pass | N/A | Complete spec, but no view-bearing input object exists. |
| pass | pass | Complete spec and abstract-deterministic: the specified output descends to the view quotient. |
| pass | fail | Complete per concrete input, but not abstract-deterministic: hidden concrete state affects the specified observable output. |
| pass | unknown | Complete, but the abstract-determinism proof is inconclusive. |

The interesting new bucket is:

```text
Step1 = pass
Step2 = fail
```

This means the existing determinism pipeline says the spec is complete,
but the new abstract-determinism check says the complete spec is not a
function of `view(o)`.

---

## 6. Failure interpretation

When Step 2 fails, the witness shape is:

```text
V(o1, o2)
∧ P(o1, a)
∧ P(o2, a)
∧ Q(o1, a, r1)
∧ Q(o2, a, r2)
∧ ¬E_R(r1, r2)
```

That is, two inputs are identical at the view layer but the spec
allows outputs that differ at the output-observation layer.

Likely diagnoses:

1. **view-too-coarse.** `view` hides a concrete field/bit/element that
   the spec's result depends on. Repair: refine `view`.
2. **Q-depends-on-hidden-state.** The postcondition mentions, directly
   or indirectly, concrete representation detail not exposed by view.
   Repair: rewrite `Q` at the view level or justify the hidden
   dependency.
3. **P-depends-on-hidden-state.** The optional domain-preservation
   check fails: legality itself depends on hidden state.
   Repair: either expose that state in view or tighten the abstraction
   boundary.
4. **equal-fn-too-strict.** `E_R` compares more than the intended
   observation. This is the existing false-positive class: fix the
   output equal-fn before blaming view.

The Step 1 precondition is what makes the diagnosis clean: once a spec
is complete for each concrete input, a Step 2 failure cannot be
ordinary "two outputs for one input" incompleteness. It specifically
points to a mismatch between the concrete input representation and
the chosen view quotient.

---

## 7. Implementation plan

### 7.1 Candidate enumeration

Reuse the existing corpus rows and `FunctionSpec` extraction:

1. Run the normal determinism pipeline.
2. Select rows whose verdict is `complete` or `complete+LLM`.
3. For each selected function, inspect inputs for a view-bearing object:
   * receiver `self` / `&self` / `&mut self`;
   * explicit parameter whose type has a native `View` impl;
   * explicit parameter whose type has a registry-resolved view.
4. Start with exactly one view-bearing object per target. If multiple
   exist, either:
   * choose the receiver first; or
   * mark `multi-view-input` and defer to the product relation.

### 7.2 Template generation

Generate a second proof file per candidate:

```text
det_<f>.rs                  // existing Step 1
abstract_det_<f>.rs         // new Step 2
domain_preserve_<f>.rs      // optional Step 2a
```

Substitution rules:

* Duplicate only the view-bearing object: `o1`, `o2`.
* Keep ordinary arguments shared: `a`.
* Instantiate `P` twice: `P(o1, a)` and `P(o2, a)`.
* Instantiate `Q` twice: `Q(o1, a, r1)` and `Q(o2, a, r2)`.
* Add one input relation: `view(o1) == view(o2)`.
* Reuse the existing output equal-fn: `E_R(r1, r2)`.

### 7.3 Reporting

Add columns to the per-target result:

| column | meaning |
|---|---|
| `step1_verdict` | existing determinism verdict |
| `view_object` | selected input object (`self`, `arg_name`, etc.) |
| `view_source` | native `View`, registry view, prelude view, unknown |
| `domain_preserve_verdict` | optional domain check |
| `abstract_det_verdict` | Step 2 verdict |
| `abstract_det_bucket` | `pass`, `view-too-coarse`, `Q-hidden-state`, `P-hidden-state`, `equal-fn-too-strict`, `unknown`, `not-checkable` |

Aggregate tables should be per-project and per-view-bearing type, not
only per-function. The type-level view is what is being audited.

### 7.4 Minimal first milestone

Implement the smallest useful slice:

1. Only receiver methods (`&self` / `&mut self`) with exactly one
   view-bearing receiver.
2. Only Step 1 `complete` targets.
3. Only the core Step 2 obligation, no domain preservation yet.
4. Reuse existing `det_<f>_equal` as `E_R`.
5. Report `pass / fail / unknown / not-checkable`.

After that works, add:

1. `complete+LLM` targets.
2. explicit view-bearing parameters.
3. product relation for multiple view-bearing inputs.
4. domain preservation.
5. failure-shape classification.

---

## 8. Relationship to operation–view congruence

The earlier operation–view congruence idea is body-level:

```text
view(o1) == view(o2)
⇒
view(op(o1, a)) == view(op(o2, a))
```

This plan is spec-level:

```text
view(o1) == view(o2)
∧ Q(o1, a, r1)
∧ Q(o2, a, r2)
⇒
E_R(r1, r2)
```

They are complementary:

* **operation–view congruence** checks whether the executable
  operation respects the view quotient;
* **abstract determinism** checks whether the written spec
  respects the view quotient.

For the next iteration, prioritize the spec-level plan because it is a
direct extension of the existing determinism pipeline and requires no
new executable semantics model.

```text
proof fn check(x, y1, y2)
    requires P(x)
    ensures Q(x, y1) && Q(x, y2) ==> y1 == y2
```

```text
proof fn check(x1, x2, y1, y2)
    requires P(x1) && P(x2) && x1@ == x2@
    ensures Q(x1, y1) && Q(x2, y2) ==> y1@ == y2@
```