# spec-determinism — Changes & Remaining Issues

## Summary

Improved three core modules (`binary_search`, `extract`, `gen_det`) and ran the tool on all bitmap functions + slab::allocate. The pipeline now works end-to-end from real Verus source (no manual FunctionSpec construction needed).

## Test Results (bitmap + slab)

| Function | Result | Rounds | Notes |
|----------|--------|--------|-------|
| `bitmap::number_of_bits` | ✅ Deterministic | 1 | `&self` → input only, no mutation |
| `bitmap::alloc` | ❌ Nondeterministic | 61 | Empty 8-bit bitmap → Ok(0) vs Ok(1) |
| `bitmap::test` | ❌ Nondeterministic | 19 | `index==8` out of bounds → Err, but Error inner value unconstrained |
| `bitmap::new` | ⚠️ Verify error | — | Match arm binding `bitmap` shared across runs |
| `bitmap::set` | ⚠️ Verify error | — | `@` deref outside `verus!{}` block |
| `bitmap::clear` | ⚠️ Verify error | — | Same as `set` |
| `bitmap::alloc_range` | ⚠️ Extract fail | — | Function body has nested `proof!` + `cfg_attr` |
| `slab::allocate` | ⚠️ Verify error | — | Name collision with existing proof fn |

---

## Changes Made

### 1. `binary_search.py` — Strategy Improvements

**`_bisect_range`**: Returns `int | None`. When `lo == mid` and FAIL, returns immediately instead of recursing to `(lo, lo)` — eliminates duplicate Verus calls (the R14/R15 issue from README).

**`_narrow_length`** (new): Shared by Set and Seq for length narrowing. Exact probes for `[0..4]`, then full-range bisect. Replaces hardcoded `[1, 2, 3, 4]`.

**`narrow_set`**: No more separate empty-set fast path; starts from `_narrow_length(start=0)`. After finding all elements via `contains()` probing, does a single final `s == Set::empty().insert(e0).insert(e1)...` confirmation instead of N per-element confirmations. Clears intermediate child nodes (`len`, `elem_*`) after confirmation to avoid redundant assumes in subsequent rounds.

**`_bisect_set_element` / `_bisect_contains`**: Takes `skip_vals: frozenset[int]` to avoid rediscovering already-found elements.

**`narrow_seq`**: Uses `_narrow_length` instead of hardcoded loop.

**`narrow_result`**: When Ok PASS, now tries Err (previously just `pass`). Recurses into Err inner type if available.

**`narrow_option`**: When Some PASS, now tries None.

**`narrow_integer`**: Small range → full type range → bisect. No exponential doubling (rare case, not worth the complexity).

**Removed `is_resolved()`**: The phase-boundary resolution checks cost 1 Verus call each (~10-30s) but almost never succeed (once `r1 ≠ r2` is established, the conclusion `r1 == r2` is always false).

### 2. `extract.py` — Rewritten with tree-sitter-verus

Completely replaced regex-based extraction with tree-sitter-verus AST parsing. Zero regex patterns remain for function/type parsing.

**Type parsing** (`_parse_type_node`): Handles `primitive_type`, `generic_type` (Result/Option/Set/Seq), `type_identifier`, `reference_type`, `unit_type`. Automatically populates `variants` for Result/Option.

**Parameter extraction** (`_extract_params`): Correctly detects `&mut` on non-self params by checking for `reference_type` → `mutable_specifier` (previously only checked direct children).

**Return type** (`_extract_return_type`): Handles both `-> Type` and `-> (name: Type)` named return syntax.

**Spec extraction**: Handles three attribute forms:
- `#[verus_spec(result => requires ..., ensures ...)]` — `verus_spec_attribute` node
- `#[cfg_attr(verus_keep_ghost, verus_spec(...))]` — `cfg_attr_verus_spec` node
- Inline `fn_qualifier` in `verus!{}` blocks — `requires_clause`/`ensures_clause` nodes

**Robustness against ERROR recovery**:
- `_find_verus_spec_for_fn`: When parent chain is broken (ERROR node), finds nearest `verus_spec_attribute` by byte proximity (within 200 bytes).
- `_extract_fn_chunk`: When function not found in full-file tree, extracts the `#[verus_spec(...)] pub fn ...{}` chunk via text search and re-parses it in isolation.
- `_find_impl_type` strategy 3: When tree-sitter splits `impl Bitmap { ... }` into flat top-level tokens due to `#[verus_verify]`, scans for `impl` → `type_identifier` → `{`...`}` token pattern and checks containment.

**Self resolution** (`_resolve_self_in_type`): Replaces `Self` in return types (e.g., `Result<Self, Error>` → `Result<Bitmap, Error>`).

### 3. `gen_det.py` — Substitution Fixes

**`_substitute_input`**: Now handles `&self` (not just `&mut self`). Maps `self` → `self_` for `&self`, `self` → `pre_self_` for `&mut self`. Also handles `old(self)` in requires.

**`_substitute_run`**: Now handles `&self` parameters (maps to shared `self_` for both runs). Fixed `old(self)` regex to handle multiline `old(\n    self,\n)` with `\bold\s*\(\s*self\s*,?\s*\)`.

**Multiple ensures clauses**: Joined with `&&` instead of bare newline.

### 4. `verify.py` — Injection Flexibility

**`inject_proof_fn`**: Falls back to last `}` in file when `} // end verus!` marker not found (slab proof file has no comment marker).

---

## Remaining Issues

### P0 — Prevents functions from being checked

**1. Match arm bindings shared across runs** (`bitmap::new`)

`new`'s ensures contains `result matches Ok(bitmap) ==> bitmap.inv()`. After substitution, both runs use the same `bitmap` binding name inside match arms. Verus sees duplicate names.

Fix needed in `gen_det.py`: rename match arm bindings to `bitmap1`/`bitmap2` (or `_r1_bitmap`/`_r2_bitmap`) per run. This requires parsing the ensures expression to find `matches` and `match` patterns, or doing a text-level rename of binding variables introduced in the ensures clause.

**2. `@` deref only valid inside `verus!{}`** (`bitmap::set`, `bitmap::clear`)

The generated proof fn uses `post1_self_@.is_bit_set(...)` etc. The `@` operator is only valid inside a `verus!{}` macro block. Currently `inject_proof_fn` inserts code into `.proof.rs` which is already inside `verus!{}`, so this should work — but the generated code may have Bitmap (exec type) where BitmapView (spec type) is expected.

Likely root cause: the ensures clause uses `self@` which tree-sitter extracts as-is. After substitution it becomes `post1_self_@`, but `post1_self_` is typed as `Bitmap` (exec). The proof fn should use the spec view type or the `@` should be preserved as part of the expression.

**3. `alloc_range` extraction failure** (`bitmap::alloc_range`)

The function body contains `proof! {}` blocks, `#[cfg_attr(verus_keep_ghost, verus_spec(invariant ...))]` on while loops, and other Verus-specific constructs that cause brace-matching in `_extract_fn_chunk` to fail.

Fix options:
- Improve `_extract_fn_chunk` to use tree-sitter's ERROR-tolerant nodes instead of text-level brace matching
- Or improve the grammar to handle `proof!` blocks inside function bodies

**4. Name collision in proof file** (`slab::allocate`)

The slab proof file already contains a function named `det_allocate`. The injected proof fn collides.

Fix: use a unique suffix in the generated function name (e.g., `det_allocate_check` or `det_allocate_{hash}`).

### P1 — Correctness / quality improvements

**5. `bitmap::test` produces weak witness**

The search finds `index==8` (out of bounds for 8-bit bitmap), both runs return Err, but Error inner values are not narrowed because `Error` is `TypeKind.UNKNOWN`. This is technically a valid witness (two Err values that could differ), but the gap is trivial — the spec says `Err(e)` without constraining `e`.

Fix: register Error as a known type, or add `custom_equality` support so Err results with any inner value are treated as equivalent.

**6. `bitmap::new` has no `requires` clause**

The spec for `new` has no preconditions (any `number_of_bits` is valid input), which means the det check has no `requires` and Z3 must reason about all possible inputs. This is correct but may be slow for complex functions.

### P2 — Nice to have

**7. Grammar improvements**

The `#[verus_verify]` attribute on impl blocks causes tree-sitter to produce ERROR nodes, splitting the impl into flat tokens. Improving the grammar to handle `#[verus_verify]` would eliminate the need for strategy-3 in `_find_impl_type` and the chunk-fallback in extraction.

**8. `_extract_fn_chunk` robustness**

Currently uses text-level brace matching which can be confused by braces in strings, comments, or nested macros. Should use tree-sitter ERROR node children instead.
