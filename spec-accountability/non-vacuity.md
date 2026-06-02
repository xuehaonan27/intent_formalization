Here's how I would frame the discussion. I intentionally wrote it as a research memo rather than a paper proposal, since I think the key question is still whether "non-vacuity" is actually a meaningful problem rather than whether it fits an existing methodology.

---

# Towards Non-Vacuity as the Next Obligation after Spec Determinism

## Context

Our current work on **Spec Determinism** starts from an intent-level notion of specification completeness and derives a checkable semantic property:

> Under spec correctness, specification completeness is equivalent to specification determinism.

This addresses one major failure mode of specifications:

> The specification admits multiple observably different implementations for the same input.

However, determinism only captures one dimension of specification quality. A specification may be deterministic while still being weak, uninformative, or misleading.

This motivates investigating a second obligation:

> **Non-Vacuity / Meaningfulness**

The challenge is to define this rigorously.

---

# What We Do Not Want

A natural first idea is clause redundancy:

Given

```text
S = C1 ∧ C2 ∧ ... ∧ Cn
```

declare a clause vacuous if removing it does not change the specification.

Formally:

```text
Admissible(S)
=
Admissible(S - Ci)
```

While useful, this is fundamentally a redundancy criterion rather than a meaningfulness criterion.

Example:

```rust
ensures result > -1000000
```

may not be redundant, because removing it changes the admissible implementation set.

Yet intuitively it contributes almost nothing to the intended behavior.

Therefore:

> Non-vacuity should not collapse into redundancy detection.

---

# Core Question

The deeper question is:

> How much semantic restriction does a specification actually impose on the space of admissible behaviors?

Determinism asks:

> Does the specification permit too many different outputs?

Non-vacuity may instead ask:

> Does the specification meaningfully eliminate undesirable behaviors?

---

# Candidate Direction 1:

## Constraint Contribution

Let

```text
A(S)
```

denote the set of implementations admitted by specification S.

For a constraint C:

```text
Contribution(C)
=
A(S - C) \ A(S)
```

This measures the set of behaviors excluded solely because of C.

Properties:

* Empty contribution ⇒ redundancy.
* Larger contribution ⇒ stronger semantic impact.
* Provides a quantitative notion of importance.

Potential research question:

> Can contribution be computed, approximated, or witnessed symbolically?

Limitation:

Contribution measures restriction, but not necessarily relevance to user intent.

---

# Candidate Direction 2:

## Witness-Based Non-Vacuity

Rather than asking whether a clause changes the implementation space, ask whether there exists an observable behavior whose admissibility depends on that clause.

For a constraint C, seek:

* a behavior admitted under S
* a behavior admitted under S−C but rejected by S

If such a witness exists, then C has observable semantic force.

This resembles how divergence witnesses certify non-determinism.

Advantages:

* Constructive.
* Produces actionable explanations.
* Naturally integrates with existing SMT workflows.

Open question:

Does every meaningful specification obligation admit such witnesses?

---

# Candidate Direction 3:

## Information Content of Specifications

A more ambitious direction is to define meaningfulness at the specification level rather than the clause level.

Intuition:

A specification should reduce uncertainty about acceptable behavior.

Consider:

```rust
ensures true
```

This conveys almost no information.

By contrast:

```rust
ensures result == max(a,b)
```

conveys substantial information.

One possible abstraction:

```text
Meaningfulness(S)
=
Information reduction induced by S
```

or equivalently

```text
Meaningfulness(S)
=
Restriction of admissible implementation space
```

This connects non-vacuity to information theory rather than syntactic structure.

Potential benefit:

It generalizes beyond individual clauses and naturally handles highly coupled specifications.

Major challenge:

How to define and estimate information content in a verifier-friendly way.

---

# A More Fundamental Question

The most important issue may be:

> What failure are we actually trying to prevent?

For determinism, the answer is clear:

> Under-specification allows multiple observably different implementations.

For non-vacuity, we still need a similarly precise statement.

Possibilities include:

1. Specifications that appear informative but do not meaningfully constrain behavior.
2. Specifications whose constraints contribute negligibly to the intended semantics.
3. Specifications that cannot distinguish correct implementations from incorrect ones.
4. Specifications that fail to provide evidence that each requirement matters.

Before searching for a formalization, it may be worth identifying which of these failures is truly fundamental.

---

# Current Assessment

Among the potential "post-determinism" directions, three appear the most promising:

### 1. Non-Vacuity / Meaningfulness

Can we formally characterize when a specification meaningfully constrains behavior rather than merely containing syntactic assertions?

### 2. Assumption Accountability

Can we expose the trusted base underlying claims about specification quality (equality relations, intended implementations, environmental assumptions, etc.)?

### 3. Compositional Sufficiency

Can individually adequate specifications fail to support system-level intent when composed?

Of these, non-vacuity currently seems the least understood conceptually but potentially the most foundational, because it asks what it means for a specification to actually contain information rather than merely assertions.

---

One thing I'd explicitly tell Fan is that I no longer think the right question is:

> "How do we check non-vacuity?"

but rather:

> **"What is the semantic failure mode that non-vacuity is supposed to rule out?"**

Determinism succeeded because it was tied to a very crisp failure mode (multiple admissible behaviors). I think the next breakthrough will come from finding an equally crisp failure mode for meaningfulness.
