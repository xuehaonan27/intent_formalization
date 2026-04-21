# Pre-z3py-loop Backup

Snapshot of the orchestrator/loop files **before** the refactor that moves
the binary-search loop from "re-invoke Verus per round" to "load Verus
SMT once, drive search via z3-py push/pop".

Files captured (all from one consistent snapshot):
- `binary_search.py` — old loop (one Verus call per round)
- `verify.py`        — `cargo verus` runner
- `z3_backend.py`    — Z3 fast-path + witness from model
- `model_eval.py`    — pure-Python SMT s-expr evaluator
- `orchestrator.py`  — entry point that wired all the above together

Kept as a fallback / reference. Do not import from here in production code.
