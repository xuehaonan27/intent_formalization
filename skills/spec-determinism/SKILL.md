---
name: spec-determinism
version: 0.1.0
description: >
  Detect specification incompleteness via nondeterminism checking. Given a Verus
  function spec, automatically determine whether the spec uniquely determines the
  output for each valid input. If not, use type-guided binary search to construct
  a concrete witness (input + two valid but different outputs). No LLM needed —
  pure SMT-based.
---

# Spec Determinism — Nondeterminism-Based Incompleteness Detection

## Core Idea

A complete specification uniquely determines the output for every valid input.
If the same input admits two different valid outputs → the spec is incomplete.

```
∀x. P(x) → ∃!y. Q(x, y)     — complete (deterministic)
∃x. P(x) ∧ ∃y1,y2. Q(x,y1) ∧ Q(x,y2) ∧ y1≠y2   — incomplete (nondeterministic)
```

## Step 1: Determinism Check

For each function `fn foo(x) -> y` with `requires P(x)` and `ensures Q(x, y)`:

```rust
proof fn det_foo(x: InputType, y1: OutputType, y2: OutputType)
    requires P(x),
    ensures Q(x, y1) && Q(x, y2) ==> y1 == y2
{
    // empty body — let SMT decide
}
```

**Important:** Output includes both the return value AND any mutated state.
For `fn foo(&mut self, arg) -> result`:
- Input = `(old_self, arg)`
- Output = `(new_self, result)`

```rust
proof fn det_foo(pre: T, arg: ArgType, post1: T, post2: T,
                 result1: RetType, result2: RetType)
    requires P(pre, arg),
    ensures Q(pre, arg, post1, result1) && Q(pre, arg, post2, result2)
            ==> (result1 == result2 && post1 == post2)
```

### Interpretation
- **Verus PASSES** → spec is deterministic for this function → no gap
- **Verus FAILS** → nondeterminism exists → proceed to Step 2

## Step 2: Type-Guided Binary Search

When Step 1 fails, construct a concrete witness `(x, y1, y2)` by progressively
adding `assume()` constraints. **Binary search input first, then output.**

### Variable Mapping for Mutable References

Any `&mut` parameter is both input and output — its pre-call value is input,
its post-call value is output. Split each `&mut` into two variables:

| Parameter | Input variable | Output variable |
|-----------|---------------|----------------|
| `&mut self` | `pre_self` | `post_self` |
| `&mut buf: Buffer` | `pre_buf` | `post_buf` |
| `val: usize` (not mut) | `val` | — (not output) |
| return value | — (not input) | `result` |

For `fn foo(&mut self, &mut buf: Buffer, arg: usize) -> Result<(), Error>`:
- **Input** = `(pre_self, pre_buf, arg)`
- **Output** = `(post_self, post_buf, result)`

Binary search Phase 1 narrows all input variables.
Phase 2 narrows all output variable pairs `(out1_i, out2_i)`.

### Phase 1: Narrow Input (x)

Fix the input to a specific concrete value. Search order by type:

**Level 1: Enum variant (first)**
```
Result<T, E>  → assume(x is Ok) or assume(x is Err)
Option<T>     → assume(x is Some) or assume(x is None)
```

**Level 2: Struct fields (one by one)**
```
BitmapView { num_bits, set_bits, ... }
  → assume(x@.num_bits == 8)
  → assume(x@.usage() == 0)
```

**Level 3: Integer values (range then exact)**
```
assume(n < 100)   → FAIL → trigger in [0, 100)
assume(n < 10)    → FAIL → trigger in [0, 10)
assume(n < 5)     → PASS → trigger in [5, 10)
assume(n == 8)    → FAIL → found!
```

**Level 4: Set/Seq (length then elements)**
```
assume(set.len() == 0)  → FAIL → empty set triggers
assume(seq.len() == 1)  → then assume(seq[0] == ...)
```

**Level 5: Generic T (construct distinct witnesses)**
```
assume(sv_eq(a, b) && a != b)   — Ord-equal but structurally different
```

### Phase 2: Narrow Output (y1, y2)

With input fixed, narrow the two different outputs:

**Same order as Phase 1, but applied to y1 and y2:**
```
Level 1: assume(result1 is Ok && result2 is Err)  → FAIL? liveness gap
Level 1: assume(result1 is Ok && result2 is Ok)    → FAIL? value gap
Level 2: assume(post1@.field == post2@.field)       → which field differs?
Level 3: assume(result1 == Ok(0) && result2 == Ok(1))  → concrete!
```

### Decision at each round

```
Add constraint → run Verus:
  FAIL → constraint is compatible with nondeterminism → keep it, go deeper
  PASS → constraint eliminated the nondeterminism → backtrack, try other branch
```

## Step 3: Verify Witness

Once fully concrete `(x, y1, y2)` found, verify it's a valid witness:

```rust
proof fn witness_foo(x: InputType, y1: OutputType, y2: OutputType)
    ensures Q(x, y1) && Q(x, y2) ==> false
{
    assume(x == <concrete_x>);
    assume(y1 == <concrete_y1>);
    assume(y2 == <concrete_y2>);
}
// FAIL (postcondition not satisfied) → witness is valid
// Both y1 and y2 satisfy Q, confirming the gap
```

## Properties

### Completeness
Every spec gap that manifests as nondeterminism will be detected by Step 1.
This covers: liveness gaps, frame condition gaps, totality gaps, error wildcards,
type abstraction gaps (sv_eq vs ==).

### Soundness
If Step 1 passes, the spec is deterministic — no gap of this type exists.
(Caveat: SMT timeout = inconclusive, not "no gap".)

### No LLM Required
The entire pipeline is mechanical:
1. Generate proof fn from function signature (AST-based)
2. Run Verus
3. Binary search with assume() constraints
4. Report concrete witness

### Comparison with spec-testing (LLM-based)

| | spec-testing | spec-determinism |
|---|---|---|
| Gap detection | LLM brainstorm | SMT query |
| Witness construction | LLM assume() | Binary search |
| Bias | Error-driven (liveness) | Uniform (all nondeterminism) |
| False positives | Need critic/review | Design choices flagged |
| Scalability | LLM cost per function | SMT cost per function |

### Limitation: Intentional Nondeterminism
Some nondeterminism is by design (e.g., allocator bit selection).
Use custom equality to filter:
```rust
==> my_equal(y1, y2)  // instead of y1 == y2
```

## External Tools

### Verus
- **Source:** <https://github.com/verus-lang/verus>
- **Usage:** `verus path/to/file.rs` or `cargo verus verify -p <crate>`
- **Required for:** All steps

### z3 (optional)
- For extracting raw SMT model when binary search is insufficient
- `verus --log smt` → `z3 output.smt2` → `(get-model)`
