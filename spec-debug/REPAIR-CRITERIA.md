# Spec Repair Quality Criteria

*Last updated: 2026-04-27*

## Context

We have a spec-determinism tool that detects incompleteness in Verus specifications via nondeterminism checking. Once a gap is found (with a concrete witness), the next step is **repair**: strengthening the spec to eliminate the nondeterminism.

We use an LLM-based coding agent (e.g., GitHub Copilot CLI) to generate candidate repairs. Without quality criteria, the agent will overfit — e.g., adding `ensures result == 0` just because the witness happened to show `Ok(0) vs Ok(1)`.

This document defines the criteria, the ranking metric (MDL), and the end-to-end pipeline.

---

## Running Example: sorted-vec `insert` (replace case)

When inserting a value that is `sv_eq` (Ord-equal) to an existing element, the spec doesn't say whether the stored element is the new value, the old value, or a third `sv_eq`-equivalent value.

```rust
// Original spec (simplified)
ensures
    self@.len() == old(self)@.len(),
    spec_contains(self@, value),       // sv_eq match exists
    result.is_some(),
    sv_eq(result.unwrap(), value),
```

**Nondeterminism witness:**
```
input: value = {key: 5, data: "new"}, existing = {key: 5, data: "old"}
run1: stores {key:5, data:"new"}, returns {key:5, data:"old"}  ✅
run2: stores {key:5, data:"old"}, returns {key:5, data:"new"}  ✅
```

Both satisfy the spec. The spec is nondeterministic — it doesn't pin which element ends up stored.

**Three candidate repairs:**

```rust
// R1: Concise structural property (GOOD)
ensures self@.contains(value)  // structural ==, not just sv_eq

// R2: Equivalent but more verbose (ACCEPTABLE)
ensures exists|i: int| 0 <= i < self@.len() && self@[i] == value

// R3: Overfitting — mirrors implementation details (BAD)
ensures {
    let idx = binary_search_idx(self@, value);
    self@[idx] == value
    && forall|j: int| j != idx ==> self@[j] == old(self)@[j]
}
```

---

## Criteria Overview

| # | Criterion | Type | Automatable? | Description |
|---|-----------|------|-------------|-------------|
| 1 | Soundness | Hard gate | ✅ | Repaired spec is still satisfied by the implementation |
| 2 | Determinism resolved | Hard gate | ✅ | Nondeterminism witness no longer exists |
| 3 | No witness constants | Hard gate | ✅ | Repair doesn't reference concrete values from the witness |
| 4 | Vocabulary subset | Hard gate | ✅ | Repair uses only symbols already in the spec vocabulary |
| 5 | Minimality (MDL) | Soft ranking | ✅ | Repair has the shortest description length |

**Hard gates** are pass/fail — any candidate that fails is immediately rejected.
**Soft ranking** is used to order the surviving candidates.

---

## Criterion 1: Soundness

**Definition:** The repaired spec S' must still be satisfiable by the implementation. Formally: if the original implementation verifies against S, it must also verify against S'.

**Verification:** Run `verus` on the crate with the repaired spec. Pass → sound. Fail → the repair over-constrained.

**Implementation:**
```bash
# Replace the original ensures with the repaired version, then:
cd $CRATE_DIR
cargo +nightly verus build --package $PKG -- --verify-root
# Exit code 0 → soundness passes
```

**This is the most important gate** — any repair that fails soundness is immediately rejected, regardless of how elegant it looks.

---

## Criterion 2: Determinism Resolved

**Definition:** Re-run the spec-determinism tool on the repaired spec. The previously-found nondeterminism must be eliminated (UNSAT on the determinism query).

**Verification:** Run the spec-determinism tool's determinism check (the `Q(x,y1) ∧ Q(x,y2) ⟹ y1==y2` query). Must return UNSAT.

**Implementation:**
```bash
python3 spec-determinism/test_bitmap_v2.py --function $FN_NAME --check-only
# "Deterministic" → passes
# "Nondeterministic" → fails
```

**Note:** The repair might introduce *new* nondeterminism on a different input. A full re-check (not just the original witness) is needed — the tool does this automatically since the determinism query is ∀-quantified over inputs.

---

## Criterion 3: No Witness Constants

**Definition:** The AST of the repair clause must not contain any literal constant that appears in the witness **and** is not already present in the original spec.

**Example:** If the witness is `{num_bits: 8, index: 0}` and the original spec already uses `0` (e.g., `len >= 0`), then `0` is allowed but `8` is not.

**Rationale:** Constants from the witness are a strong signal of overfitting. A correct repair should be parametric over all valid inputs.

**Implementation:**
```python
def check_no_witness_constants(repair_ast, witness_values, original_spec_ast):
    """Returns True if the repair passes this criterion."""
    original_literals = extract_literals(original_spec_ast)
    repair_literals = extract_literals(repair_ast)
    witness_literals = set(witness_values.values())  # e.g., {8, 0, "new"}
    
    # Flag literals that are in the witness AND not in the original spec
    overfitting_literals = (repair_literals & witness_literals) - original_literals
    return len(overfitting_literals) == 0
```

---

## Criterion 4: Vocabulary Subset

**Definition:** Every function symbol, type name, and spec fn referenced in the repair must already appear in the **allowed vocabulary**.

**Allowed vocabulary sources:**
- The function's own requires/ensures
- The View trait implementation for involved types
- `inv()` predicates on involved types
- Standard library spec fns (e.g., `Seq::contains`, `Set::insert`, `Seq::len`)

**Rationale:** Introducing new `uninterp spec fn` or inventing helper predicates makes the repair unverifiable without additional axioms. It also signals that the repair is encoding implementation knowledge that doesn't belong in the spec.

**Implementation:**
```python
def check_vocabulary_subset(repair_ast, allowed_vocab):
    """Returns True if the repair passes this criterion."""
    repair_symbols = extract_identifiers(repair_ast)
    # Bound variables (quantifier vars like i, j) are always allowed
    bound_vars = extract_bound_variables(repair_ast)
    novel_symbols = repair_symbols - allowed_vocab - bound_vars
    return len(novel_symbols) == 0
```

**Building the allowed vocabulary:**
```python
def build_allowed_vocab(crate_path, target_fn):
    vocab = set()
    # From the function's own spec
    vocab |= extract_spec_identifiers(target_fn.requires)
    vocab |= extract_spec_identifiers(target_fn.ensures)
    # From the type's View and inv()
    for ty in target_fn.involved_types:
        vocab |= extract_spec_identifiers(ty.view_impl)
        vocab |= extract_spec_identifiers(ty.inv)
    # From vstd standard library
    vocab |= VERUS_STDLIB_VOCAB
    return vocab
```

---

## Criterion 5: Minimality via Minimum Description Length (MDL)

This is the most nuanced criterion. The goal: among all repairs that pass criteria 1–4, prefer the **simplest** one.

### Why minimality matters

Without a minimality criterion, the agent might generate repairs that are technically correct but unnecessarily complex — encoding implementation details, adding redundant quantifiers, or over-specifying behavior that should remain abstract.

### Why not semantic minimality?

**Semantic minimality** (model-theoretic): S' is more minimal than S'' iff `Models(S') ⊃ Models(S'')` — S' admits more behaviors.

*Problem:* In practice, this leads to implementation-copying. The "semantically minimal" deterministic extension of a spec converges to the implementation itself, wrapped in `ensures result == impl(input)`. Users don't want this — they want *abstract* specs.

### Why not syntactic minimality?

**Syntactic minimality**: Minimize the number of new ensures clauses added.

*Problem:* Too coarse. One clause can be arbitrarily complex (`forall|i| forall|j| ... ==> ...`). Clause count doesn't reflect actual complexity.

### Why not Shannon entropy?

Shannon entropy `H = -Σ p(t) log p(t)` measures the **average** bits per token — the uniformity of the token distribution. This is the wrong quantity for two reasons:

1. **Insensitive to length.** Entropy is an average; it doesn't penalize longer clauses. A 20-token clause with common tokens can have lower entropy than a 3-token clause with rare tokens.

2. **Insensitive to structure.** Consider:

   ```rust
   // R1: 3 tokens
   self@.contains(value)

   // R2: 11 tokens
   forall|i: int| 0 <= i < self@.len() ==> ...
   ```

   R2 uses common tokens (`forall`, `i`, `self`, `==>`, `&&`) that repeat often, so its Shannon entropy may actually be *lower* than R1's. But R2 is structurally more complex — it introduces a quantifier, a bound variable, and a nested implication.

   **Entropy rewards repetition; we want to penalize structural complexity.**

### Our approach: MDL over AST

We adopt **Minimum Description Length** (Rissanen, 1978) as the theoretical foundation. MDL formalizes Occam's razor: the best model is the one that compresses the data most.

**MDL applied to spec repair:**

```
MDL(repair) = L(repair) + L(remaining_nondeterminism | repair)
```

Since criterion 2 forces the second term to 0 (determinism must be fully resolved), MDL reduces to minimizing **L(repair)** — the description length of the repair clause.

**Description length is computed over the AST, not over raw text.** It has two components:

```
L(repair) = Σ token_cost(token) + Σ structural_cost(node_type)
```

#### Token cost: tiered vocabulary model

Tokens that are already part of the spec's vocabulary are cheap to encode (the reader "expects" them), while novel tokens are expensive:

| Tier | Description | cost(token) | Example |
|------|-------------|-------------|---------|
| T1 | In current function's spec (requires/ensures) | 1.0 | `self@`, `value`, `contains` |
| T2 | In same module's spec vocabulary (other fns, inv(), View) | 2.0 | `num_bits`, `is_bit_set` |
| T3 | In Verus standard library (vstd) | 3.0 | `forall`, `exists`, `Seq`, `Set` |
| T4 | Not seen anywhere in the spec ecosystem | 10.0 | `binary_search_idx`, custom helpers |

This is a **flat-cost approximation** of the full MDL encoding. It is simpler to implement than interpolated smoothing over empirical frequencies, and likely sufficient in practice since the key distinction is: "is this token part of the spec vocabulary or not?"

**Implementation:**
```python
def token_cost(token: str, tiered_vocab: TieredVocab) -> float:
    if token in tiered_vocab.t1:  return 1.0
    if token in tiered_vocab.t2:  return 2.0
    if token in tiered_vocab.t3:  return 3.0
    return 10.0
```

#### Structural cost: quantifiers and binders

Certain AST node types carry inherent structural cost because they increase the complexity of the spec regardless of which tokens they contain:

| Node type | Structural cost | Rationale |
|-----------|----------------|------------|
| Quantifier (∀, ∃) | +3.0 | Introduces a new scope and bound variable |
| Let binding | +2.0 | Introduces a named intermediate value |
| Match/if | +2.0 | Introduces case splits |
| Function call | +1.0 | References a definition |
| Binary operator | +0.5 | Basic composition |
| Literal/variable | +0.0 | Free (already paid by token cost) |

#### Total description length

```
L(repair) = Σ_{tokens} token_cost(t) + Σ_{nodes} structural_cost(node_type)
```

**Implementation:**
```python
def compute_mdl(repair_ast, tiered_vocab: TieredVocab) -> float:
    total = 0.0
    for node in repair_ast.walk():
        # Token cost for identifiers and literals
        if node.is_identifier() or node.is_literal():
            total += token_cost(node.text, tiered_vocab)
        # Structural cost by node type
        total += STRUCTURAL_COSTS.get(node.type, 0.0)
    return total

STRUCTURAL_COSTS = {
    "quantifier_expr": 3.0,    # forall, exists
    "let_expr": 2.0,
    "match_expr": 2.0,
    "if_expr": 2.0,
    "call_expr": 1.0,
    "binary_expr": 0.5,
}
```

#### Worked example

For the sorted-vec `insert` repair candidates:

```
R1: self@.contains(value)
  Tokens: self@ (T1, 1.0) + contains (T1, 1.0) + value (T1, 1.0) = 3.0
  Structure: 1 function call (+1.0) = 1.0
  L(R1) = 4.0

R2: exists|i: int| 0 <= i < self@.len() && self@[i] == value
  Tokens: exists (T3, 3.0) + i (T3, 3.0) + 0 (T1, 1.0) + self@ (T1, 1.0)
          + len (T1, 1.0) + self@ (T1, 1.0) + i (T3, 3.0) + value (T1, 1.0) = 15.0
  Structure: 1 quantifier (+3.0) + 3 binary ops (+1.5) + 1 call (+1.0) = 5.5
  L(R2) = 20.5

R3: let idx = binary_search_idx(...); self@[idx] == value && forall|j| ...
  Tokens: binary_search_idx (T4, 10.0) + idx (T4, 10.0) + ... = 30+
  Structure: 1 let (+2.0) + 1 quantifier (+3.0) + ... = 8+
  L(R3) ≈ 40+
```

**Result:** R1 (4.0) ≪ R2 (20.5) ≪ R3 (40+). MDL correctly prefers the concise structural property.

#### Building the tiered vocabulary

```python
def build_tiered_vocab(crate_path: str, target_fn: str) -> TieredVocab:
    """Build the 4-tier vocabulary for MDL scoring.
    
    Uses tree-sitter-verus to parse spec blocks (reuses extract.py infrastructure).
    """
    # T1: tokens in the target function's requires + ensures
    t1 = extract_spec_tokens(crate_path, target_fn)
    
    # T2: tokens in all specs in the same module/impl block
    t2 = extract_module_spec_tokens(crate_path, target_fn)
    
    # T3: vstd standard library identifiers (pre-built constant)
    t3 = VERUS_STDLIB_VOCAB  # {Seq, Set, Map, contains, insert, len, ...}
    
    return TieredVocab(t1=t1, t2=t2, t3=t3)
```

#### Why MDL works for spec repair

| Failure mode | How MDL prevents it |
|-------------|--------------------| 
| Overfitting to witness constants | Constants not in T1/T2 → high token cost (also caught by criterion 3) |
| Encoding implementation details | Implementation symbols not in spec vocab → T4 cost (10.0 each) |
| Unnecessary quantifier nesting | Quantifiers have structural cost (+3.0) → penalized |
| Verbose but equivalent restatement | More AST nodes → higher total L |
| Trivially vacuous repair | Not MDL's job — caught by criterion 2 (determinism re-check) |

---

## Repair Pipeline

### Architecture

```
                    ┌─────────────────────────┐
                    │ spec-determinism tool    │
                    │ (detects nondeterminism, │
                    │  produces witness)       │
                    └────────┬────────────────┘
                             │ witness
                             ▼
              ┌──────────────────────────────┐
              │  N independent agent sessions │
              │  (Copilot CLI --yolo -p ...)  │
              │  Each produces one candidate  │
              └──────┬───┬───┬───┬───┬───────┘
                     │   │   │   │   │   N candidates
                     ▼   ▼   ▼   ▼   ▼
              ┌──────────────────────────────┐
              │       Hard Gates (filter)     │
              │  1. Soundness (verus)         │
              │  2. Determinism resolved      │
              │  3. No witness constants      │
              │  4. Vocabulary subset         │
              └──────────┬───────────────────┘
                         │  survivors
                         ▼
              ┌──────────────────────────────┐
              │    MDL Ranking (sort)         │
              │  Compute L(repair) for each   │
              │  Sort ascending               │
              └──────────┬───────────────────┘
                         │
                         ▼
              ┌──────────────────────────────┐
              │   Present top-k to user       │
              └──────────────────────────────┘
```

### Candidate generation: N independent agent sessions

Each candidate is generated by an independent Copilot CLI session. This is critical for diversity — the agent's non-determinism naturally produces different repairs across sessions.

**Why independent sessions, not one session with self-critique:**
- MDL is an **external evaluation metric**, not an internal optimization target for the agent
- If the agent can see the MDL score, it may learn to "game" the metric — generating repairs with low MDL but poor semantic quality
- Independent sessions ensure diversity without metric contamination

**Prompt for each session** (same prompt, all criteria included):

```
Fix the nondeterminism in the following Verus spec.

## Spec
[original function signature + requires + ensures]

## Nondeterminism Witness
[witness from spec-determinism tool]

## Type Definitions
[View type, inv(), relevant type definitions]

## Instructions
- Add or modify `ensures` clauses to eliminate the nondeterminism
- The repair must pass `verus` verification (soundness)
- Do NOT use literal constants from the witness (e.g., do not hardcode specific values)
- Only use spec functions and types already present in the spec or type definitions
- Prefer concise, abstract repairs over verbose, implementation-specific ones
- Write the repaired ensures clause to [output file]
- Run `verus` to verify your repair
```

**Execution:**

```python
def generate_candidates(witness, original_spec, crate_dir, n=5):
    candidates = []
    for i in range(n):
        # Create isolated workspace copy
        workspace = f"/tmp/repair_workspace_{i}"
        shutil.copytree(crate_dir, workspace)
        
        # Run Copilot CLI agent
        result = subprocess.run(
            ["copilot", "--yolo", "-p", prompt,
             "--add-dir", workspace],
            capture_output=True, timeout=300
        )
        
        # Extract the repaired ensures clause
        repair = extract_repair_diff(workspace, crate_dir)
        if repair:
            candidates.append(repair)
        
        # Clean up
        shutil.rmtree(workspace)
    
    return candidates
```

### Hard gate evaluation

```python
def evaluate_candidate(repair, original_spec, witness, crate_dir, tiered_vocab):
    """Run all criteria on a candidate repair. Returns (passed, mdl_score)."""
    
    repair_ast = parse_verus_clause(repair)
    
    # Gate 1: Soundness
    if not run_verus_check(crate_dir, repair):
        return False, None, "soundness_failed"
    
    # Gate 2: Determinism resolved
    if not run_determinism_check(crate_dir, repair):
        return False, None, "still_nondeterministic"
    
    # Gate 3: No witness constants
    if not check_no_witness_constants(repair_ast, witness, original_spec):
        return False, None, "contains_witness_constants"
    
    # Gate 4: Vocabulary subset
    if not check_vocabulary_subset(repair_ast, tiered_vocab.all()):
        return False, None, "vocabulary_violation"
    
    # Ranking: MDL score
    mdl = compute_mdl(repair_ast, tiered_vocab)
    return True, mdl, "passed"
```

### Full pipeline

```python
def repair_pipeline(fn_name, crate_dir, n_candidates=5, top_k=3):
    # Step 1: Detect nondeterminism
    witness = run_spec_determinism(crate_dir, fn_name)
    if not witness:
        print(f"{fn_name}: deterministic, no repair needed")
        return
    
    # Step 2: Build vocabulary
    vocab = build_tiered_vocab(crate_dir, fn_name)
    original_spec = extract_spec(crate_dir, fn_name)
    
    # Step 3: Generate N candidates
    candidates = generate_candidates(witness, original_spec, crate_dir, n=n_candidates)
    
    # Step 4: Evaluate
    results = []
    for i, repair in enumerate(candidates):
        passed, mdl, reason = evaluate_candidate(
            repair, original_spec, witness, crate_dir, vocab
        )
        if passed:
            results.append((repair, mdl))
        else:
            print(f"  Candidate {i}: REJECTED ({reason})")
    
    # Step 5: Rank by MDL
    results.sort(key=lambda x: x[1])
    
    # Step 6: Present top-k
    for rank, (repair, mdl) in enumerate(results[:top_k]):
        print(f"  #{rank+1} (MDL={mdl:.1f}): {repair}")
    
    return results[:top_k]
```

---

## Summary

- **Criteria 1–4 are automatable hard gates** that reject clearly bad repairs.
- **Criterion 5 (minimality) is a soft ranking** based on Minimum Description Length (MDL), used to prefer simpler repairs among valid candidates.
- MDL combines **token cost** (tiered by vocabulary familiarity: T1–T4) with **structural cost** (quantifiers, binders, case splits) to produce a single score.
- **Candidate generation uses N independent Copilot CLI agent sessions** with the same comprehensive prompt. Diversity comes from the agent's natural non-determinism, not from prompt variation or metric feedback.
- **MDL is an external evaluation metric**, deliberately kept outside the agent's knowledge to prevent metric gaming.
- The combination prevents both overfitting (criteria 3, 4) and over-constraining (criterion 5), while maintaining correctness (criteria 1, 2).
- **Semantic minimality is theoretically appealing but practically leads to implementation-copying.** MDL over AST is the right information-theoretic quantity: it penalizes both unfamiliar vocabulary and structural complexity, aligning with users' preference for concise, abstract specs.
