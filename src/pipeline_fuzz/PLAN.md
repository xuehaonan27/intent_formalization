# Spec-Fuzzing Pipeline (`src/pipeline_fuzz/`)

## Context

The existing formalization pipeline (`src/pipeline/step1..step3`) turns
natural-language intents + Rust source into Verus `spec`/`exec` pairs and
checks entailment. Entailment only tells us *the exec body satisfies the
written spec* — it says nothing about whether the spec itself captures what
the function is *supposed* to do. Two failure modes slip through today:

- **Incorrectness** — the spec is overconstrained and rejects behavior the
  function should be allowed to produce. (The exec body happens to avoid the
  forbidden region so entailment still passes.)
- **Incompleteness** — the spec is underconstrained and admits behavior the
  function must never produce. (Classic example already observed on
  `bitmap::alloc`: spec lets `alloc` always return `0`.)

This plan adds a parallel pipeline `src/pipeline_fuzz/` that fuzzes specs
with concrete (pre-state, args, post-state, return) cases, uses an LLM
oracle to label each case as intended-good/intended-bad, and uses Verus to
check whether the spec admits/rejects the case. Oracle × Verus disagreement
surfaces spec bugs.

## Core idea: proof-fn shell reuse

`src/pipeline/step3_formalize.assemble_proof_fn` already knows how to turn
an exec declaration into a proof fn whose body is a list of `assume(...)`
statements over `old(self)`, the arguments, `self`, and `result`, with the
spec's `ensures` clause attached. We reuse this verbatim: a *case* is just
a bag of concrete `assume`s. Verus result → spec admits-or-rejects this
case.

### Verdict matrix

| oracle label | Verus result | verdict        |
|--------------|--------------|----------------|
| ACCEPT       | verifies     | OK             |
| ACCEPT       | fails        | INCORRECTNESS  |
| REJECT       | verifies     | INCOMPLETENESS |
| REJECT       | fails        | OK             |

Cases whose inputs violate the spec's `requires` are discarded (they would
verify vacuously and give a false INCOMPLETENESS).

## Pipeline stages

```
step1_extract  → exec_functions.json   (reuse src/pipeline/step1_extract)
step2_template → per-fn symbolic template of state scenarios + arg domains
step3_enumerate→ Cartesian product → seed cases
step4_diversify→ LLM adds domain-specific / edge cases; dedup
step5_oracle   → LLM labels each case ACCEPT/REJECT with justification
step6_assemble → case → proof-fn source via assemble_proof_fn
step7_verus    → run Verus on each proof fn (parallel)
step8_report   → quadrant analysis → findings.json + findings.md
```

`run_task.py` drives one source file; `run_pipeline.py` parallelizes across
tasks the same way `src/pipeline/run_pipeline.py` does today.

## Files to create

All new, under `src/pipeline_fuzz/`:

- `__init__.py`
- `schemas.py` — dataclasses: `Case`, `OracleLabel`, `VerusOutcome`, `Finding`
- `step1_extract.py` — thin wrapper importing `src/pipeline/step1_extract`
- `step2_template.py` — per-fn scenario template from struct field types
- `step3_enumerate.py` — symbolic → concrete seed cases
- `step4_diversify.py` — LLM diversification + semantic dedup
- `step5_oracle.py` — per-case LLM label (batched, cached)
- `step6_assemble.py` — `Case` → proof-fn source
- `step7_verus.py` — run Verus per case in a worker pool
- `step8_report.py` — verdict matrix → JSON + Markdown
- `run_task.py`
- `run_pipeline.py`

## Reuse (do not reimplement)

- `src/utils/verus_parser.py` — `verus_parser`, `extract_exec_functions`,
  `node_to_text`
- `src/utils/pipeline_common.py` — `build_entailment_file`,
  `extract_spec_portion`
- `src/utils/verus.py` — `run_verus`
- `src/utils/llm.py` — `LLMClient`
- `src/pipeline/step1_extract.py` — `strip_body`, `extract_fn_name`,
  `extract_from_file`, `task_name_for`
- `src/pipeline/step3_formalize.py` —
  `_rewrite_declaration_to_proof_fn`, `assemble_proof_fn`

## Case representation

```python
@dataclass
class Case:
    task: str                 # e.g. "bitmap__bitmap"
    fn:   str                 # e.g. "alloc"
    pre_assumes:  list[str]   # e.g. "old(self)@.num_bits == 8"
    arg_assumes:  list[str]   # e.g. "n == 3"
    post_assumes: list[str]   # e.g. "self@.set_bits == old(self)@.set_bits.insert(0)"
    result_assume: str | None # e.g. "result is Ok && result.unwrap() == 0"
    oracle: Literal["ACCEPT","REJECT"] | None
    oracle_justification: str | None
```

`step6_assemble` concatenates these into the proof-fn body expected by
`assemble_proof_fn`.

## LLM usage

- **Diversifier prompt** (step4): sees spec + seed cases, asks for additional
  cases that stress edges (empty/full state, boundary args, error paths).
- **Oracle prompt** (step5): sees the original Rust source + the intent +
  the concrete case, must output `ACCEPT|REJECT` + one-sentence justification.
  The oracle does **not** see the Verus spec — it reasons from intent alone,
  otherwise it would just parrot the spec.

Both prompts go through `LLMClient` with on-disk response caching keyed by
prompt hash (same pattern as existing pipeline).

## Output

Per task: `<workspace>/pipeline_fuzz/<task>/`
- `cases.json` — all generated cases with oracle labels
- `verus/<fn>_<case_id>.rs` + `.log`
- `findings.json` — only INCORRECTNESS / INCOMPLETENESS rows
- `findings.md` — human-readable summary

Top-level: `<workspace>/fuzz_findings_summary.md` aggregating across tasks.

## Verification

1. Run `run_task.py` on `nanvix/workspace/bitmap` alone.
2. Confirm it rediscovers the known `bitmap::alloc` incompleteness (spec
   admits always-returns-0).
3. Spot-check 5 random ACCEPT/verifies and REJECT/fails cases to confirm
   they are true negatives (not noise).
4. Scale to full workspace via `run_pipeline.py --workspace workspace_fuzz`.
5. Manually audit the top-10 highest-confidence findings; require at least
   one additional true bug beyond the bitmap baseline before declaring
   the pipeline useful.

## Out of scope

- Fixing any spec bug the pipeline finds.
- Extending beyond `&mut self` / `&self` / constructor exec functions in
  this first pass (generic/trait methods deferred).
- Auto-repair of specs from findings.
