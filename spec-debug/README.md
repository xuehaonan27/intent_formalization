# spec-debug

Observation-first debugging pipeline for spec incompleteness. Sibling to
[`spec-determinism/`](../spec-determinism/).

## Status: v0 (no strategy, no metrics)

The v0 goal is end-to-end plumbing so we can *watch* what LLM fixes look
like on real nondeterminism witnesses, and then design a strategy and
metrics based on observation.

Pipeline:

```
witness (from spec-determinism)  →  prompt  →  LLM (manual paste)
  →  whole-file patch to .spec.rs  →  cargo verus + spec-det rerun
  →  observation report
```

## Install

```sh
cd spec-debug
pip install -e .
```

Depends on `spec-determinism` being installed in the same env.

## Run

```sh
spec-debug run bitmap::new
```

The CLI will:

1. Load the most recent witness for `bitmap::new` from spec-determinism's
   `results/full_run.json` + `results/artifacts/bitmap__new/det_spec.json`.
2. Write a prompt to `runs/<ts>/bitmap__new/prompt.md`.
3. Wait for you to drop a reply into `runs/<ts>/bitmap__new/response.md`
   (paste from GitHub Copilot CLI, or any LLM).
4. Apply the replacement `.spec.rs`, re-run Verus + spec-determinism,
   revert, and emit `report.{json,md}`.

## Scope boundaries for v0

Explicitly out of scope until we have observation data:

- Any fix-quality metric (structural locality, literal bleed, etc.)
- Pareto / weighted scoring
- Template-based or Z3-based generators
- Iterative refinement loops
- "Refuse to fix" detection
- Automated LLM API calls (manual-paste only for v0)
