# Architecture

This document walks through every file in `spec_determinism/` and explains how they
fit together. The pipeline is a straight line with one fork; there are
no legacy branches — everything described here is reachable from
`corpus/run_all.py`.

## One-line per module

```
spec_determinism/extract/extractor.py     Verus source → FunctionSpec (tree-sitter-verus)
spec_determinism/extract/types.py         FunctionSpec / DetCheckSpec / Assume / Witness dataclasses
spec_determinism/extract/predicates.py    Structured AssumePred classes; pred ↔ schema match
spec_determinism/extract/narrow.py        AssumeTree + narrow_* strategies + SearchContext Protocol
spec_determinism/extract/type_registry.py Type/field dependency graph (Phase 1 — feeds View resolver)
spec_determinism/codegen/equal_policy.py  Choose which equal_fn to use for a given function
spec_determinism/codegen/gen_det.py       Synthesize the det_fn proof template
spec_determinism/codegen/policy_llm.py    LLM-driven EqualPolicy + projection discovery
spec_determinism/verus/verify.py          One cargo-verus invocation; capture .smt2 transcript
spec_determinism/verus/single_file.py     Single-file verus driver (verusage style)
spec_determinism/verus/workspace.py       Workspace discovery / source-file IO
spec_determinism/view/                    Phase 2 — 4-layer view resolver
    prelude.py         L1 prelude container views (Vec/Option/Map/Ghost/&T)
    impl_scanner.py    L3 scan for raw `impl View for T` blocks
    registry.py        L1+L2+L3+L4 resolver, equal_expr + Resolution.prelude_decl
    llm.py             L4 offline LLM view synthesizer + cache (Copilot CLI)
spec_determinism/schema_search/
    schemas.py         Schema enumeration, guarded template, assume translation
    search.py          z3.Solver-driven search loop (the only driver today)
spec_determinism/corpus/
    run_all.py         End-to-end runner (workspace mode)
    verusage_run.py    Batch runner for verusage-style single-file corpora
    verusage_summary.py  Stats aggregator over verusage results
    regen_artifacts.py   Regen DetCheckSpec / proof files from cached config
```

## The pipeline, top to bottom

### 1. `extract/extractor.py` — source → FunctionSpec

Tree-sitter-verus parses the target crate and walks the CST to build
a `FunctionSpec`: parameter types (with full `TypeInfo` — struct
fields, variant payloads, Set/Seq element types), `requires` / `ensures`
expressions (as Rust source strings), and the selected return type.
Types recurse as deep as needed for nested generics (e.g.
`Option<Result<Seq<SlabView>, Error>>`).

### 2. `codegen/equal_policy.py` — equality selection

Given a `FunctionSpec`, decides which equality function to use for
`r1 != r2` in the distinctness goal. The default is a structural
equality over the return type; users can override per-function.

### 3. `codegen/gen_det.py` — det_fn template

Generates the proof function

```rust
proof fn det_<fn>(<params>, ..., guard_0: bool, k_0_0: int, ...)
    requires <original requires>, <guard-conditional assumes>
    ensures  !{fn}_equal((r1, post1s), (r2, post2s))
{
    let (r1, post1s) = <fn>(<pre, args>);
    let (r2, post2s) = <fn>(<pre, args>);
    if guard_0 { assume(<pred_0 using k_0_*>); }
    if guard_1 { assume(<pred_1 using k_1_*>); }
    ...
}
```

The template is parameterised by the schema set produced in step 5.
The combined output is a single `DetCheckSpec` (see `types.py`) that
contains the Rust source, the symbol table, and the `equal_fn` body.

### 4. `extract/types.py` — core data classes

- `FunctionSpec` — static description of the target function.
- `DetCheckSpec` — `FunctionSpec` + `det_fn` source + symbol table +
  `equal_fn` name and arg pairs.
- `Assume` — one narrowing commitment. `pred: AssumePred` is the
  structured form; `expression` is a `@property` that defers to
  `pred.to_rust()`. Constructed via `Assume.from_pred(var, pred, desc)`.
- `Witness` — the output: the tree of committed assumes, the per-round
  trace, and metadata.
- `Symbol` — a named SMT-level symbol the search tracks (inputs,
  outputs, post-state projections).

### 5. `schema_search/schemas.py` — schema enumeration + template

`enumerate_schemas(det_spec) → list[SchemaBinding]`. Each binding
carries:

- `id`             — stable integer id
- `kind`           — one of SCALAR_EQ, SCALAR_RANGE, VARIANT_IS,
                     BOOL_EQ, STR_EQ, SET_EMPTY, SET_LEN_GT/EQ/RANGE,
                     SEQ_LEN_EQ/RANGE, SET_CONTAINS, NOT_EQUAL_FN
- `guard_name`     — Rust-level (and SMT-level) Boolean parameter
- `k_params`       — 0..n integer parameters (e.g. `SCALAR_EQ` has
                     one `k`; `SCALAR_RANGE` has `lo, hi`)
- `var` / `variant` / `field_path` — what this schema talks about
- `parent_guard`   — activation chain: this schema's assume is only
                     meaningful when the parent guard is on

`render_guarded_template(det_spec, schemas) → str` produces the full
Rust source with every `if guard_i { assume(...); }` wired up.

`translate_assume(assume, schemas, equal_fn_name) → Optional[(schema_id, k_bindings)]`
— called per round. Iterates schemas and asks `assume.pred.match_and_bind(schema)`
on each; the first non-None match wins. Returns `None` if no schema
covers this pred (caller falls through as `pass_untranslatable`).

### 6. `extract/predicates.py` — structured preds + pred↔schema dispatch

Each `AssumePred` subclass is a small frozen dataclass with two methods:

- `to_rust() → str` — Rust rendering (consumed by the template generator,
  the witness output, and any future Verus-subprocess driver).
- `match_and_bind(schema) → Optional[dict[str, int]]` — structural
  match against a `SchemaBinding`; returns k-bindings on success.

The twelve pred classes today: `EqPred`, `RangePred`, `VariantIsPred`,
`BoolPred`, `StrEqPred`, `SetEmptyPred`, `SetLenGtPred`, `LenEqPred`,
`LenRangePred`, `SetContainsPred`, `SetLiteralPred`, `NotEqualFnPred`.

To add a 13th: append one dataclass with the two methods and add it
to the `AssumePred` union at the bottom of the file. No other file
needs editing.

### 7. `verus/verify.py` — single cargo-verus call

`run_cargo_verus(crate, fn_name)` wraps the `cargo +<toolchain> verus
verify` invocation with the right target, features, log-dir flags,
and path filters. The side effect is a `mm__<module>.smt2` dumped
under `/tmp/aprime_<crate>_<fn>_XXXX/`. Returns a `VerifyResult` with
status, stdout, stderr, and the smt2 path.

### 8. `extract/narrow.py` — AssumeTree + narrow_* strategies

#### `AssumeNode` (the tree)

Each node holds one `Assume` and children keyed by string
(field name, element index, `@view`, etc.). The search tree shape
follows the type structure of each tracked symbol: a `Result<Ok<T>,
E>` node has an `Ok_0` child that itself recurses into `T`, and so on.

#### `narrow_*` strategies

Decorator-registered per `TypeKind`:

- `narrow_integer` → `_bisect_range` (classic lo/hi bisect)
- `narrow_bool`    → two `BoolPred`s
- `narrow_str`     → three literal candidates
- `narrow_set`     → empty? → length bisect → contains-enum
- `narrow_seq`     → length bisect + per-element recursion
- `narrow_option`  → two `VariantIsPred`s + recurse
- `narrow_result`  → ditto for `Ok` / `Err`
- `narrow_enum`    → per-variant `VariantIsPred` + recurse into payload
- `narrow_struct`  → recurse into each field

Every strategy calls `ctx.test_and_set(node, Assume.from_pred(...))`
and does **not** care which concrete context is driving them.

#### `SearchContext` (Protocol)

A thin structural type declared at the top of the file:

```python
class SearchContext(Protocol):
    tree: AssumeNode
    det_spec: DetCheckSpec
    trace: list[dict]
    def test_and_set(self, node, assume, phase="") -> bool: ...
```

The only concrete implementation today is `SchemaSearchContext` in
`schema_search/search.py`. `narrow_*` function signatures carry
`ctx: "SearchContext"` as a forward reference against this Protocol.

#### `_add_distinctness_witnesses`

Final step in any driver: try to `assume(!equal_fn(r1, ..., r2, ...))`.
If this narrowing step is `pass` (i.e. the solver proves the equality
*must* hold given the accumulated narrows), nothing is added; if it
is `fail`, the pred `NotEqualFnPred(call=...)` joins the witness as a
strong distinctness assertion.

### 9. `schema_search/search.py` — the driver

`build_schema_ctx(det_spec, smt2_path, schemas) → SchemaCtx`:

- read the `.smt2`; split out prelude + `det_<fn>` body
- create a `z3.Solver`, load the prelude
- assert the det_fn goal (negated, per Verus convention: we want
  UNSAT to mean determinism)
- resolve each schema's `guard_name` and `k_*` names to Z3 constants
  by walking the parsed AST (string names survive Verus's mangling)
- return the `SchemaCtx` (solver + guards + k-consts + schemas + timing)

`SchemaSearchContext(det_spec, schema_ctx)` implements `SearchContext`:

- `_assumes_to_z3(assumes) → Optional[list[z3.BoolRef]]` translates
  each committed assume via `translate_assume` and collects the
  `guard == True` plus `k_i == value_i` literals.
- `test_and_set(node, assume, phase)`:
  1. tentatively set `node.assume = assume`
  2. build the full assumption list from the tree
  3. if any assume is untranslatable → revert, log
     `pass_untranslatable`, return False
  4. `r = solver.check(*bools)`
  5. `r == unsat` → revert, log `pass`, return False (dimension is
     strong enough; keep looking for other dimensions)
     else → keep `node.assume`, log `fail`, return True

`run_schema_search(det_spec, schema_ctx) → Witness`:

- R0 baseline check with no assumes (detects "deterministic at R0")
- for each tracked symbol: `narrow(sym.type, sym.name, sym_node, ctx)`
- `_add_distinctness_witnesses(ctx, det_spec)` (from `narrow`)
- return `Witness(assumes=tree.collect_assumes(), trace=..., ...)`

## Design invariants

1. **Predicates are the single source of truth.** `Assume` has no
   `expression: str` field; `expression` is derived from
   `pred.to_rust()`. Backends cannot accidentally disagree with the
   witness output.

2. **Pred ↔ schema matching has one home.** Every pred knows how to
   match itself against a schema. The translator is a 10-line generic
   loop. Adding a pred is a one-place change; adding a schema kind
   is at most a three-place change (pred method, schemas enumerator,
   template emitter).

3. **No string sniffing for length preds.** The old `if var.endswith(".len()")`
   branch is gone. Length narrowing is a distinct path
   (`_narrow_length → _bisect_len_range`) that emits `LenEq/LenRangePred`
   directly; `_bisect_range` is scalar-integer only.

4. **Z3 is a pure sat/unsat oracle.** We never call `solver.model()`.
   Witnesses come from the accumulated pred tree, not from parsing
   `(get-model)` responses. This is the resolution to the two problems
   documented in `JOURNEY.md`.

5. **One driver, one entry point.** `corpus/run_all.py` → `run_schema_search`.
   The old `binary_search()` driver, `Z3Backend`, `ModelProvidingBackend`,
   and `model_eval.py` are gone (see commit history if you need to
   recover them).

## Complexity / cost model

- Verus call: O(1) per function, dominated by Verus/Z3 compilation
  of the guarded template (~1–10 s depending on crate).
- Schema enumeration: O(total type tree size + MAX_SEQ_LEN · per-element schemas)
  — typically 25–520 schemas per function.
- `build_schema_ctx`: O(smt2 size) for parsing and loading;
  ~100–130 ms for `kernel::*` (5 MB smt2), 40–70 ms otherwise.
- Per round: one `solver.check(*bools)`. For the schema-search kernel
  functions, median round is ~30 ms; the worst case (`kernel::allocate`,
  3567 rounds) averages ~27 ms/round.
- Total wall clock on the 14-function suite: ~159 s, of which ~52 s
  is Verus and ~106 s is z3-py `check` (kernel::allocate alone is
  ~100 s of that).
