# spec-determinism tool — Architecture Design

## Overview

Fully automated tool that detects spec incompleteness via nondeterminism checking.
Each module has a **parser path** (deterministic, fast) and an **LLM fallback**
(handles unknown patterns). The tool always tries parser first, falls back to LLM
only when parser returns `Unsupported`.

```
┌─────────────────────────────────────────────────────────┐
│                      Orchestrator                        │
│  (drives the pipeline, manages state, emits report)      │
└─┬───────┬───────┬──────────┬────────────┬───────────┬───┘
  │       │       │          │            │           │
  ▼       ▼       ▼          ▼            ▼           ▼
Extract  GenDet  Verify  BinarySearch  Witness   Reporter
```

---

## Module 1: `extract` — Spec Extraction

**Input:** Crate path + function name (or "all")
**Output:** `FunctionSpec` struct

```python
@dataclass
class Param:
    name: str           # e.g. "self", "index"
    type: TypeInfo      # resolved type
    is_mut_ref: bool    # &mut → split into pre/post
    
@dataclass
class FunctionSpec:
    name: str
    params: list[Param]
    return_type: TypeInfo
    requires: list[str]       # raw Verus clause strings
    ensures: list[str]        # raw Verus clause strings
    type_defs: dict[str, TypeDef]  # resolved struct/enum definitions
```

**Parser path:**
- Parse `.rs` / `.spec.rs` / `.proof.rs` with `tree-sitter-rust` or regex
- Identify `fn` signature, `requires`, `ensures` blocks
- Resolve type definitions (follow `type Foo = ...`, struct fields, enum variants)
- Detect `&mut` parameters

**LLM fallback:** When parser hits unknown macro, attribute, or complex type alias:
- Send source snippet → LLM extracts `FunctionSpec` as JSON
- Prompt: "Extract function signature, requires, ensures. Return JSON."

---

## Module 2: `gen_det` — Determinism Check Generator

**Input:** `FunctionSpec`
**Output:** Verus proof fn source code (string)

```
fn foo(&mut self, index: usize) -> Result<(), Error>
        │            │                    │
        ▼            ▼                    ▼
  (pre, post1, post2) (index)       (r1, r2)
         INPUT                       OUTPUT
```

**Variable mapping rules (deterministic):**
1. `&mut T` param → split into `pre_x: T` (input) + `post1_x: T, post2_x: T` (output)
2. `&self` / `&T` / value params → input only, shared by both runs
3. Return type → `r1: RetType, r2: RetType` (output)

**Template:**
```rust
proof fn det_{name}({inputs}, {output1_vars}, {output2_vars})
    requires {requires_on_inputs},
    ensures
        ({ensures_substituted_for_run1}
        && {ensures_substituted_for_run2})
        ==> ({all_outputs_equal})
{ }
```

**Substitution rules (deterministic):**
- `self` → `pre_self` in requires
- `self` → `post1_self` / `post2_self` in ensures (post-state refs)
- `old(self)` → `pre_self` in ensures
- `result` → `r1` / `r2`

**LLM fallback:** When ensures contains patterns the substitution engine
doesn't recognize (e.g. complex `match` with nested destructuring):
- Send ensures block + variable mapping → LLM produces substituted version
- Prompt: "Apply this substitution map to the ensures clause. Copy structure exactly."

---

## Module 3: `verify` — Verus Runner

**Input:** Proof fn source code + crate context
**Output:** `VerifyResult` (pass/fail/timeout/error)

```python
@dataclass
class VerifyResult:
    status: Literal["pass", "fail", "timeout", "error"]
    function: str         # which proof fn
    duration_ms: int
    stderr: str           # raw Verus output (for debugging)
```

**Injection strategy:**
- Inject proof fn into existing `.proof.rs` before `} // end verus!`
- Run `cargo verus verify -p <crate>`
- Parse output for `verification results:: X verified, Y errors`
- Grep for specific `det_` function names in error output

**No LLM fallback needed** — this is pure I/O.

**Extensibility:**
- `injection_strategy` can be swapped (e.g. standalone file with `use` imports)
- Timeout configurable (default 120s)

---

## Module 4: `binary_search` — Type-Guided Witness Narrowing

**Input:** `FunctionSpec` + initial `VerifyResult` (FAIL)
**Output:** `Witness` (concrete values for all variables)

This is the core module. Drives iterative narrowing.

### 4a: `type_strategy` — Search Strategy Generator

For each type, generates an ordered list of narrowing steps:

```python
def strategy(ty: TypeInfo) -> list[NarrowingStep]:
    match ty:
        case Enum(variants):
            return [EnumVariant(v) for v in variants]
        case Struct(fields):
            return [StructField(f) for f in fields]
        case Int/Usize:
            return [Range(0, 100), Range(0, 10), ...]  # configurable
        case Set(elem_ty):
            return [SetLen(0), SetLen(1), ...] + [SetElem(i, strategy(elem_ty))]
        case Seq(elem_ty):
            return [SeqLen(0), SeqLen(1), ...] + [SeqElem(i, strategy(elem_ty))]
        case Bool:
            return [BoolVal(true), BoolVal(false)]
        case _:
            return [LLMNarrow(ty)]  # fallback
```

**LLM fallback (`LLMNarrow`):** When type is unknown/complex:
- Send type definition + current assume state
- LLM suggests next narrowing constraint
- Prompt: "Given type T and current constraints [...], suggest one assume() to narrow."

### 4b: `search_driver` — Binary Search Loop

```python
def search(spec, var, current_assumes):
    for step in type_strategy(var.type):
        assume = step.to_assume(var)
        result = verify(gen_det(spec, current_assumes + [assume]))
        if result == FAIL:
            current_assumes.append(assume)
            if step.has_children():     # struct fields, enum inner types
                search(spec, step.child_var, current_assumes)
        elif result == PASS:
            continue  # try next sibling
        elif result == TIMEOUT:
            # try LLM to suggest a different constraint
            ...
```

**Search order: input variables first, then output variables.**

### 4c: `assume_codegen` — Constraint Code Generator

Translates `NarrowingStep` → Verus `assume()` expression string:

```python
EnumVariant("Ok")     → "r1 is Ok"
StructField("num_bits", 8) → "pre@.num_bits == 8"
Range(0, 100)         → "index < 100"
SetLen(0)             → "pre@.set_bits == Set::<int>::empty()"
```

**LLM fallback:** When codegen doesn't know how to express a constraint in Verus:
- Send type + constraint intent → LLM generates Verus expression

---

## Module 5: `witness` — Witness Completion & Formatting

**Input:** All accumulated assumes (from binary search)
**Output:** Human-readable witness with all fields concrete

**Steps:**
1. Collect all `assume` constraints from search
2. For each variable, check if all fields are covered
3. **Missing fields** → derive from existing constraints if possible (e.g. `usage` from `set_bits`), or run one more `verify` to confirm a default value works
4. Format as structured document

```python
@dataclass
class ConcreteWitness:
    function: str
    inputs: dict[str, ConcreteValue]    # all input vars, all fields
    output1: dict[str, ConcreteValue]   # y1
    output2: dict[str, ConcreteValue]   # y2
    gap_type: str                       # liveness / design_choice / error_wildcard / ...
    gap_description: str
```

**LLM fallback:** For `gap_type` classification and `gap_description`:
- Send the witness → LLM classifies and describes
- This is the ONE place where LLM adds real value (semantic interpretation)

---

## Module 6: `reporter` — Output & Reporting

**Input:** List of `ConcreteWitness` per function
**Output:** Markdown report + optional JSON

Formats:
- `det_binary_search_traces.md` — step-by-step trace table
- `det_complete_witnesses.md` — full concrete witnesses
- `summary.json` — machine-readable results

---

## Orchestrator

```python
def run_pipeline(crate_path, functions="all"):
    specs = extract(crate_path, functions)        # Module 1
    
    results = []
    for spec in specs:
        det_code = gen_det(spec)                  # Module 2
        result = verify(det_code)                 # Module 3
        
        if result.status == "pass":
            results.append(Deterministic(spec.name))
            continue
        
        # Nondeterminism detected — binary search
        witness = binary_search(spec)             # Module 4
        witness = complete_witness(spec, witness)  # Module 5
        results.append(witness)
    
    report(results)                               # Module 6
```

---

## LLM Fallback Summary

| Module | Parser path | LLM fallback trigger |
|--------|-----------|---------------------|
| extract | tree-sitter AST parsing | unknown macro/attribute/type alias |
| gen_det | template + substitution rules | unrecognized ensures pattern |
| verify | pure I/O | (never) |
| binary_search.type_strategy | type-recursive strategy | unknown type constructor |
| binary_search.assume_codegen | pattern-matched codegen | can't express constraint in Verus |
| witness | constraint propagation | gap classification + description |

**Design principle:** LLM calls are always **scoped** (small prompt, single-purpose)
and **validated** (output is fed back into Verus — if it doesn't compile or doesn't
produce expected FAIL/PASS, retry or report error).

---

## Extensibility Points

1. **New type strategies** — register `TypeInfo → list[NarrowingStep]` handlers
2. **Custom equality** — `my_equal(y1, y2)` instead of `y1 == y2` for intentional nondeterminism
3. **Injection strategy** — swap between in-crate injection and standalone file
4. **Reporter plugins** — add LaTeX, HTML, or SARIF output formats
5. **Multi-function composition** — future: check determinism of `f(); g()` sequences
6. **Parallel search** — run multiple narrowing branches concurrently
