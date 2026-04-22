# scripts/legacy — prior experiments, kept for reference

These scripts drove earlier iterations of `spec-determinism`. They are
preserved verbatim so the checkpoints referenced in `JOURNEY.md` stay
reproducible, but **they are not the current driver**. Use
`run_a_prime_all.py` (at the repo root) instead.

| Script | Purpose | Status |
|---|---|---|
| `test_bitmap.py`, `test_bitmap_v2.py` | Per-case smoke tests on `bitmap::alloc` | Superseded by `run_a_prime_all.py` |
| `test_z3py_search.py` | Smoke tests for the initial `z3py_search` primitive | Kept for regression on `src/z3py_search.py` |
| `proto_z3.py` | First `Z3Backend` prototype on `bitmap::new` | Historical |
| `ab_compare.py` | A/B comparison of `VerusRunner` vs `Z3Backend` on bitmap | Historical |
| `poc_z3py_bitmap_new.py` | z3-py incremental search end-to-end POC | Historical |
| `poc_a_prime_bitmap_new.py` | First A' (schema-driven) end-to-end POC | Historical |

Run any of them from the `spec-determinism/` root, e.g.
```
python scripts/legacy/poc_a_prime_bitmap_new.py
```

The older codepaths they exercise (`VerusRunner`, `Z3Backend`,
`z3py_search`) are kept in `src/` and `src/legacy*/` for the same
reason.
