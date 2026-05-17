# Single-Shot LLM-Proof Run (Idea A, mode = single-shot)

Pipeline: `copilot -p <prompt.md>` per attempt; one prompt → one
response (fenced JSON `proof_block`) → patched into the synthetic
det-check `.rs` → `verus` → if fail and retries left, re-prompt with
the verus stderr tail. Max attempts = 1 for atmosphere/ironkv (the
big projects); cache reused on retry.

Configuration: `--use-view-registry --use-llm-proof
--llm-proof-max-attempts 1 --llm-proof-timeout 600`.

## Project-level results

| Project           | Total | baseline `unsat` | `verus_error` | LLM-attempted | LLM-success | Hit rate |
|-------------------|------:|-----------------:|--------------:|--------------:|------------:|---------:|
| vest              |     2 |                2 |             0 |             0 |           0 |      n/a |
| memory-allocator  |    16 |               14 |             1 |             1 |           0 |     0/1  |
| nrkernel          |     8 |                6 |             2 |             0 |           0 |      n/a |
| ironkv            |   214 |               99 |            45 |            71 |       **1** |  1.4%    |
| atmosphere*       |   319 |              220 |            15 |            99 |           0 |  0.0%    |
| **Total**         |   559 |              341 |            63 |       **171** |       **1** |  **0.58%** |

\* atmosphere run was stopped at 319/1363 targets (23% through) after 17h
when single-shot hit rate stabilized at 0%. The remaining 1044 targets
were not executed.

## Failure breakdown (ironkv + atmosphere)

| Last status   |  count |  notes |
|---------------|-------:|--------|
| `verus_fail`  |    164 | LLM wrote a proof block, but Verus still rejected the postcondition (most common: trigger never lined up, or the LLM cited a lemma it couldn't justify). |
| `llm_failure` |      5 | Response not parseable / did not contain a fenced JSON `proof_block` (mostly ironkv). |
| `verus_pass`  |      1 | `ironkv::delegation_map_v::greatest_lower_bound_index` — invoked `K::cmp_properties()` / `K::zero_properties()` axioms and case-split on the iterator value. |

## Cost

* Total LLM wall time observed: **27.7 h** (ironkv 10.3 h + atmosphere 17.4 h + memory-allocator/vest/nrkernel negligible).
* Average single-shot LLM duration: ~9.7 min/call (range 1-25 min depending on file size).
* Total cache entries: **272 verus_fail + 5 llm_failure + 1 verus_pass = 278** — every failed proof block is on disk under
  `results-verusage-llmproof/<proj>/llm_proof_cache/<key>.json` and will be reused for A/B against agentic mode.

## Why this score is so low (and what we do next)

Single-shot has a fundamental disadvantage: the model has to write a
correct proof on the first guess from a static prompt. It never sees
Verus's actual error, never gets to try a candidate and refine.

**Next step (todo `llm-proof-agentic-mode`)**: switch to one
`copilot -p ... --allow-all-tools` *agentic* session per target.
The CLI will be told to edit the synthetic `.rs` in place, run
`verus` itself, read the error, and iterate inside a single model
session — keeping reasoning context across edits. Same 278 cache
keys will get re-run with `cache_mode=refresh` for an apples-to-apples
comparison.
