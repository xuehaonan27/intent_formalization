# spec-determinism

A tool that decides whether a Verus `exec` function is *deterministic*
— i.e. whether two valid runs on the same input are forced to produce
the same result — and, when it is not, produces a **witness**: a set
of Rust-level assumptions under which two runs can still diverge.

A deterministic spec (under equivalence `equal_fn`) is a sign of a
sufficiently tight specification; a nondeterministic one points at a
missing `ensures` clause or an intentional underdetermination, and the
witness makes that gap concrete.

## TL;DR

- **Input**: a Verus `exec` function + its `requires` / `ensures` + an
  `equal_fn` (auto-generated from the return type, or user-supplied
  via an equality policy).
- **Output**: either *"deterministic"* or a witness of the form
  ```
  { pre_self_.set_bits.contains(0),
    r1 is Ok, r2 is Ok,
    post1_self_.set_bits.len() == 1,
    ... }
  ```
- **How**: one `cargo verus` call compiles a **guarded template** that
  encodes every possible narrowing dimension; all subsequent binary-
  search rounds run inside `z3-py` by toggling assumption-literal
  guards on the already-loaded solver.
- **Cost** on 14 `exec` functions (`bitmap`, `slab`, `kernel`):
  **~159 s end-to-end**, of which **~52 s is Verus compilation** and
  **~106 s is search** (dominated by `kernel::allocate` at ~100 s /
  3567 rounds). Zero per-round subprocess overhead.

See [`JOURNEY.md`](JOURNEY.md) for how the design got here, and
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the module-by-module walkthrough.

## Repository layout

```
spec-determinism/
├── README.md              ← this file
├── JOURNEY.md             ← two challenges with raw (get-model) and how we solved them
├── ARCHITECTURE.md        ← module walkthrough
├── docs/archive/          ← superseded docs kept for history
├── run_all.py             ← primary driver (schema-search pipeline)
├── results/
│   ├── full_run.json      ← latest per-function results + witnesses (gitignored)
│   └── artifacts/<crate>__<fn>/det_spec.json
│                          ← DetCheckSpec inputs, one per target function
└── src/
    ├── extract.py         ← tree-sitter-verus: source → FunctionSpec
    ├── equal_policy.py    ← equal_fn selection policy
    ├── gen_det.py         ← det_fn template synthesis
    ├── verify.py          ← single cargo-verus invocation + SMT capture
    ├── types.py           ← FunctionSpec / DetCheckSpec / Assume / Witness
    ├── predicates.py      ← structured AssumePred classes (pred ↔ schema match)
    ├── binary_search.py   ← AssumeTree + narrow_* strategies + SearchContext Protocol
    └── schema_search/
        ├── schemas.py     ← schema enumeration + guarded template rendering +
        │                    Rust-assume → (schema_id, k_bindings) translation
        └── search.py      ← z3-py driven schema search driver
```

## Pipeline

```
Verus source
    │
    ├─[extract.py]──────────→ FunctionSpec (types, requires, ensures)
    │
    ├─[equal_policy]────────→ equal_fn         (what counts as "same result")
    │
    ├─[gen_det.py]──────────→ DetCheckSpec     (det_fn template + symbol table
    │                                           + equal_fn def)
    │                            → results/artifacts/<crate>__<fn>/det_spec.json
    │
    ├─[schema_search.schemas.enumerate_schemas]
    │         ──────────────→ SchemaBinding[]  (a fixed, type-directed set of
    │                                           narrowing dimensions; each owns
    │                                           a `(guard_name, k_params)` slot)
    │
    ├─[schema_search.schemas.render_guarded_template]
    │         ──────────────→ single .rs file with every schema's
    │                         `if guard_i { assume(expr_i(k_i)); }` body
    │
    ├─[verify.run_cargo_verus]
    │         ──────────────→ ONE cargo-verus call, produces a single .smt2
    │
    ├─[schema_search.search.build_schema_ctx]
    │         ──────────────→ in-memory z3.Solver pre-loaded with the smt2
    │                         (prelude + det_fn), guard/k Z3 constants resolved
    │
    ├─[schema_search.search.run_schema_search]
    │         ──────────────→ drive binary_search.narrow() on an
    │                         `AssumeNode` tree; per round:
    │                           1. translate candidate Rust assume → (schema_id, k)
    │                           2. r = solver.check(*current_guards_and_ks)
    │                           3. unsat ⇒ commit assume ("pass")
    │                              sat/unknown ⇒ keep narrowing ("fail")
    │
    └─ Witness  (Rust-level assume list) + JSON trace + per-round timing
```

The two ideas that make this work are detailed in `JOURNEY.md`:

1. **Do all search at the model level**, not by spawning Verus. One
   Verus call is spent compiling a template that pre-declares every
   narrowing dimension as a guarded assume; rounds become z3-py
   `solver.check(*bools)` calls (sub-ms each).
2. **Fuse binary search with witness generation.** `unsat` records a
   must-hold condition; `sat` / `unknown` keeps narrowing. The witness
   is the set of committed assumes, not a parsed Z3 model — this
   side-steps `Poly!val!N` abstract universe elements entirely.

## Running it

Prerequisites:

- Nanvix workspace at `~/nanvix` (Rust `nightly-2025-12-08` + Verus
  bundled at `toolchain/verus/`).
- `z3-solver==4.12.5.0` (matching Verus's bundled Z3).
- `tree-sitter-verus` Python binding (consumed by `src/extract.py`).

```bash
# All target functions (bitmap / slab / kernel)
python run_all.py

# Single function
python run_all.py kernel::allocate
```

Results land in `results/full_run.json` and are printed as a table:

```
fn                                  status    verus    ctx  search rounds  schemas
bitmap::alloc                       ok         2617     68     572     65      280
slab::allocate                      ok         2974     67    1780     94      303
kernel::allocate                    ok         5161    103   95057   3567      395
...
```

- `verus` — one-shot `cargo verus verify` (ms)
- `ctx`   — parse the emitted `.smt2` into a `z3.Solver` (ms)
- `search` — all `solver.check(...)` rounds combined (ms)
- `rounds` — number of narrowing rounds (1 means deterministic at R0)
- `schemas` — total candidate narrowing dimensions emitted into the template

## Current status (14 / 15 functions)

| Crate · function | Rounds | Search | Notes |
|---|---:|---:|---|
| `bitmap::number_of_bits`    |    1 |  152 ms | deterministic at R0 |
| `bitmap::new`               |   20 |  426 ms | Ok / Err branching |
| `bitmap::from_raw_array`    |    1 |  266 ms | deterministic at R0 |
| `bitmap::alloc`             |   65 |  572 ms | free-bit choice |
| `bitmap::alloc_range`       |   72 |  577 ms | free-range choice |
| `bitmap::set` / `clear` / `test` | 1 | ~270 ms | deterministic at R0 |
| `slab::from_raw_parts`      |   67 |  888 ms | `free_addrs` population |
| `slab::allocate`            |   94 | 1780 ms | allocation order |
| `slab::deallocate`          |    1 |  287 ms | deterministic at R0 |
| `kernel::from_raw_parts`    |   65 | 4483 ms | `Err.reason` string |
| `kernel::allocate`          | 3567 |   95 s  | full 7-slab witness |
| `kernel::deallocate`        |    1 |  510 ms | deterministic at R0 |
| `kernel::layout_to_allocator` | — | — | pre-existing `Slab1024` stale artifact, unrelated |

## Adding a new pred kind

Everything lives in one place: `src/predicates.py`. Define

```python
@dataclass(frozen=True)
class MyPred:
    var: str
    ...
    def to_rust(self) -> str:
        """Rust rendering — used by the witness output and the guarded template."""
    def match_and_bind(self, schema: SchemaBinding) -> Optional[dict[str, int]]:
        """Return the k-bindings if this pred matches `schema`; else None."""
```

and add it to the `AssumePred` union at the bottom of the file. The
schema-search translator iterates schemas and calls
`pred.match_and_bind(schema)` — the first non-`None` result wins. No
regex parsing, no string sniffing, no changes elsewhere.

## Further reading

- [`JOURNEY.md`](JOURNEY.md) — the two Z3-model challenges and the
  resolution (≤ 800 words).
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — per-module walkthrough of `src/`.
- [`FINDINGS.md`](FINDINGS.md) — what the witnesses on the 14 target
  functions actually say: three real spec gaps, seven tight specs,
  four loose-by-design allocator patterns.
- [`docs/archive/`](docs/archive/) — older design / status / changes
  notes; superseded by the above.
