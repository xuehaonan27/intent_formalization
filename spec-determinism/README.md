# spec-determinism

A tool that decides whether a Verus `exec` function is *deterministic*
— i.e. whether two valid runs on the same input are forced to produce
the same result — and, when it is not, produces a **witness**: a set
of Rust-level assumptions under which two runs can still diverge.

A deterministic spec (under equivalence `equal_fn`) is a sign of a
sufficiently tight specification; a nondeterministic one points at a
missing `ensures`-clause or an intentional underdetermination, and
the witness makes that gap concrete.

## TL;DR

- **Input**: Verus `exec` function + its `requires`/`ensures` +
  `equal_fn` (either auto-generated or chosen by a policy).
- **Output**: either "deterministic" or a witness of the form
  `{pre_self_.set_bits.contains(0), r1 is Ok, r2 is Ok,
  post1_self_.set_bits.len() == 1, ...}`.
- **How**: the current pipeline (`A'`, schema-driven) calls Verus
  **once** to compile a guarded template, then runs all binary-search
  rounds inside `z3-py` via assumption toggling.
- **Cost** (14 `exec` functions across `bitmap`, `slab`, `kernel`):
  ~187 s total, vs ~1756 s on the old per-round-subprocess pipeline
  — ≈ 9.4× speedup with strictly richer witnesses.

See `JOURNEY.md` for the story of how we got here, and
`ARCHITECTURE.md` for the detailed module-by-module walkthrough.

## Repository layout

```
spec-determinism/
├── README.md           ← this file
├── JOURNEY.md          ← two challenges + resolution, narrative
├── ARCHITECTURE.md     ← per-module walkthrough + code-review notes
├── DESIGN.md / STATUS.md / CHANGES.md / RESULTS.md
│                       ← older design docs, kept for context
├── run_a_prime_all.py  ← primary driver (A', schema-driven)
├── test_all.py         ← legacy driver (per-round subprocess pipeline)
├── results/
│   ├── a_prime_full_run.json   ← latest per-function results + witness
│   ├── artifacts/<crate>__<fn>/det_spec.json
│   │                           ← DetCheckSpec inputs consumed by A'
│   └── ...                     ← older run logs
├── scripts/legacy/     ← earlier POCs / smoke tests (see its README)
└── src/
    ├── a_prime/        ← current search backend
    │   ├── schemas.py  ← schema enumeration + template rendering
    │   └── search.py   ← z3-py driven binary_search
    ├── binary_search.py, gen_det.py, extract.py, verify.py,
    │   types.py, equal_policy.py, equal_llm.py, report.py,
    │   orchestrator.py, llm_fallback.py, llm_refine.py
    │                   ← shared pipeline (extraction, template, etc.)
    ├── z3_backend.py, model_eval.py, z3py_search.py
    │                   ← earlier backends; still importable, used by
    │                     scripts/legacy/ and for comparison
    ├── legacy/, legacy_pre_z3py/
    │                   ← frozen snapshots of pre-A' code
    └── backend.py      ← `DetBackend` / `ModelProvidingBackend` Protocols
```

## High-level pipeline

```
Verus source
    │
    ├─[extract.py]───────────→ FunctionSpec (types, requires, ensures)
    │
    ├─[equal_policy / equal_llm]──→ equal_fn   (what counts as "same result")
    │
    ├─[gen_det.py]──────────→ DetCheckSpec  (det_fn template + symbol table
    │                                        + equal_fn def)
    │                          → results/artifacts/<crate>__<fn>/det_spec.json
    │
    │      ┌── (A', current) ──┐
    │      │ a_prime.schemas   │  enumerate (guard, k) schemas for each
    │      │                   │  narrowing dimension, inject into template
    │      │ verify.py         │  ONE cargo verus call → <module>.smt2
    │      │ a_prime.search    │  load smt2 into z3-py;
    │      │                   │  reuse existing binary_search narrow
    │      │                   │  strategies but dispatch via
    │      │                   │  solver.check(*assumptions)
    │      └───────────────────┘
    │
    └─[report.py]──────────→ Witness (Rust-level assumes) + JSON trace
```

The two ideas that make A' work are spelled out in `JOURNEY.md`:

1. Drive the whole search at the SMT / model level — one Verus call,
   then add/remove assumes on the in-memory model via `z3-py`.
2. Fuse binary search with witness generation — `unsat` records a
   must-hold condition; `sat` / `unknown` / still-abstract value
   keeps narrowing.

## Running it

Prerequisites:

- Nanvix workspace at `~/nanvix` (Rust nightly-2025-12-08 + Verus
  bundled at `toolchain/verus/`).
- `z3-solver==4.12.5.0` (matching Verus's bundled Z3).
- `tree-sitter-verus` (used by `src/extract.py`).

```bash
# Full A' run over all 15 exec functions (bitmap / slab / kernel)
python run_a_prime_all.py

# Single function
python run_a_prime_all.py kernel::allocate

# Old per-round pipeline (subprocess-Verus per round — slow, for
# comparison only)
python test_all.py
```

Results are appended to `results/a_prime_full_run.json` and printed as
a per-function table:

```
fn                                  status    verus    ctx  search rounds  schemas
bitmap::alloc                       ok         2561     64     665     65      280
slab::allocate                      ok         2975     72    1991     94      303
kernel::allocate                    ok         5151    104  175937   3567      395
...
```

Each `results[i].assumes` is the Rust-level witness; see
`JOURNEY.md` §"Results" or `results/a_prime_full_run.json` for
concrete examples (e.g. the full slab-size ladder
`slabs[0..6].block_size ∈ {8, 16, 32, 64, 128, 256, 512}` produced for
`kernel::allocate`).

## Current status (14 / 15 functions)

| Crate · function | Rounds | Search (ms) | Notes |
|---|---:|---:|---|
| `bitmap::number_of_bits` | 1 | 152 | deterministic at R0 |
| `bitmap::new` | 20 | 431 | Ok / Err branching |
| `bitmap::from_raw_array` | 1 | 253 | deterministic at R0 |
| `bitmap::alloc` | 65 | 665 | free-bit choice |
| `bitmap::alloc_range` | 72 | 665 | free-range choice |
| `bitmap::set / clear / test` | 1 | ~270 | deterministic at R0 |
| `slab::from_raw_parts` | 67 | 910 | `free_addrs` population |
| `slab::allocate` | 94 | 1991 | allocation order |
| `slab::deallocate` | 1 | 286 | deterministic at R0 |
| `kernel::from_raw_parts` | 65 | 4552 | `Err.reason` string |
| `kernel::allocate` | 3567 | 175937 | full 7-slab witness |
| `kernel::deallocate` | 1 | 508 | deterministic at R0 |
| `kernel::layout_to_allocator` | — | — | stale `det_spec.json` (pre-existing, unrelated) |

## Further reading

- `JOURNEY.md` — two challenges we hit with raw `(get-model)` parsing
  and the two-idea resolution (≤ 800 words).
- `ARCHITECTURE.md` — every file in `src/` explained top-down, plus
  code-review findings.
- `DESIGN.md`, `STATUS.md`, `RESULTS.md`, `CHANGES.md` — older
  iterations; kept for context, superseded by the above where they
  disagree.
- `scripts/legacy/README.md` — index of the prototypes that led to
  A'.
