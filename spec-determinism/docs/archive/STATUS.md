# spec-determinism — Project Status

*Last updated: 2026-04-17*

## Core Idea

Detect spec incompleteness via nondeterminism checking. Given a Verus spec Q(x,y):

```
Q(x, y1) ∧ Q(x, y2) ⟹ y1 == y2
```

If SMT can't prove this → spec is nondeterministic → binary search for a concrete witness (specific input x + two valid but different outputs y1, y2). Pure SMT, no LLM needed.

## Architecture

8 Python modules in `src/`:

```
extract → gen_det → verify → binary_search → witness → report
                                    ↑
                              AssumeTree (tree-structured assumes)
```

- **extract.py** — tree-sitter-verus AST parsing, zero regex
- **gen_det.py** — generates determinism proof fn (splits `&mut` into pre/post, duplicates outputs)
- **verify.py** — injects proof fn into Verus source, runs `verus`
- **binary_search.py** — type-specific strategies (int/set/seq/option/result), AssumeTree for assume management
- **report.py** — formats witnesses

### Key Design Decisions

- `&mut` params (not just self) split into pre (input) + post (output)
- Binary search order: input first, then output (output depends on input)
- All fields must be concrete in final witness
- AssumeTree: lazy construction, same-node replaces, different-node accumulates
- Integer bisection: `[lo, mid]` + `[mid+1, hi]`, small range PASS → skip entirely

## Test Results

| Function | Result | Rounds | Notes |
|----------|--------|--------|-------|
| `bitmap::number_of_bits` | ✅ Deterministic | 1 | `&self` → input only, no mutation |
| `bitmap::alloc` | ❌ Nondeterministic | 61 | Empty 8-bit bitmap → Ok(0) vs Ok(1) |
| `bitmap::test` | ❌ Nondeterministic | 19 | `index==8` OOB → Err, Error inner unconstrained |
| `bitmap::new` | ⚠️ Verify error | — | Match arm binding collision |
| `bitmap::set` | ⚠️ Verify error | — | `@` deref type mismatch |
| `bitmap::clear` | ⚠️ Verify error | — | Same as `set` |
| `bitmap::alloc_range` | ⚠️ Extract fail | — | Function body contains `proof!` blocks |
| `slab::allocate` | ⚠️ Verify error | — | Proof fn name collision |

## Blocking Issues (P0)

### 1. Match arm binding collision (`bitmap::new`)

`new`'s ensures: `result matches Ok(bitmap) ==> bitmap.inv()`. After substitution both runs share the `bitmap` binding. Verus rejects duplicate names.

**Fix:** In `gen_det.py`, rename match arm bindings per run (e.g. `_r1_bitmap` / `_r2_bitmap`). Requires parsing `matches`/`match` patterns in ensures clauses.

### 2. `@` deref type mismatch (`bitmap::set`, `bitmap::clear`)

`self@` becomes `post1_self_@`, but `post1_self_` is typed as exec `Bitmap`, not spec `BitmapView`. The `@` operator expects exec types to produce spec views, but the proof fn parameters should use the view type directly.

**Fix:** Detect `@` usage in ensures → use the spec view type (e.g. `BitmapView`) for proof fn parameters, and strip `@` from the substituted expression.

### 3. `alloc_range` extraction failure

Function body contains `proof! {}` blocks and `#[cfg_attr(verus_keep_ghost, verus_spec(invariant ...))]` on while loops. Text-level brace matching in `_extract_fn_chunk` breaks.

**Fix:** Use tree-sitter's ERROR-tolerant node children instead of text-level brace matching. Or improve the grammar to handle `proof!` blocks inside function bodies.

### 4. Proof fn name collision (`slab::allocate`)

The slab proof file already has a function named `det_allocate`.

**Fix:** Append unique suffix: `det_allocate_check` or `det_allocate_{hash}`.

## Quality Issues (P1)

### 5. Weak witness for `bitmap::test`

Finds `index==8` (OOB for 8-bit bitmap), both runs return `Err`, but `Error` inner value isn't narrowed because `Error` is `TypeKind.UNKNOWN`.

**Fix:** Register `Error` as a known type, or add `custom_equality` so Err results with any inner value are treated as equivalent.

### 6. No `requires` functions may be slow

Functions like `new` with no preconditions force Z3 to reason over all inputs. Correct but potentially slow for complex specs.

## Plan

1. **Fix P0 bugs** → get all 8 bitmap functions + slab running end-to-end
2. **Run nanvix full coverage** → bitmap + slab + sorted-vec, all functions, produce complete witness report
