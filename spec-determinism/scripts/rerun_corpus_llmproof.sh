#!/usr/bin/env bash
# Rerun the verusage corpus with --use-llm-proof so the LLM proof loop
# escalates on every r0_z3='unknown' target. Caches every LLM-authored
# proof block (pass or fail) under <OUT>/llm_proof_cache/ so subsequent
# runs are cheap.
#
# Reuses results-verusage/view_registry/ (Phase-2 view-aware equal-fn)
# so the LLM proof has a chance at end-to-end closure on real targets;
# the worked example shows the two fixes are independent and both
# required.
#
# Usage:
#   bash scripts/rerun_corpus_llmproof.sh               # all 7 projects
#   ONLY="memory-allocator vest" bash scripts/...        # subset
#   MAX_ATTEMPTS=2 bash scripts/...                     # cap LLM iterations
#   CACHE_MODE=refresh bash scripts/...                  # force re-LLM
set -u

cd /home/xuehaonan/intent_formalization/spec-determinism

ROOTS=${ROOTS:-/home/xuehaonan/intent_formalization/verusage/source-projects}
VIEW_CACHE_BASE=results-verusage/view_registry
OUT=results-verusage-llmproof
LOG_DIR=/home/xuehaonan/.copilot/session-state/7214e2c5-243b-424d-a1db-cc2f2b274210/files/llmproof_corpus_logs

MAX_ATTEMPTS=${MAX_ATTEMPTS:-2}
CACHE_MODE=${CACHE_MODE:-use}
LLM_TIMEOUT=${LLM_TIMEOUT:-600}
LLM_MODE=${LLM_MODE:-single_shot}
SESSION_TIMEOUT=${SESSION_TIMEOUT:-1800}
MODEL=${MODEL:-}
EFFORT=${EFFORT:-}

mkdir -p "$LOG_DIR" "$OUT"

declare -a PROJECTS=(
  vest
  memory-allocator
  nrkernel
  anvil-library
  ironkv
  atmosphere
  storage
)

if [[ "${ONLY:-}" != "" ]]; then
  read -r -a PROJECTS <<< "$ONLY"
fi

SUMMARY="$LOG_DIR/_run_summary.log"
echo "=== llm-proof rerun started $(date -Is) max_attempts=$MAX_ATTEMPTS cache_mode=$CACHE_MODE ===" \
  | tee -a "$SUMMARY"

for proj in "${PROJECTS[@]}"; do
  if [[ ! -d "$ROOTS/$proj" ]]; then
    echo "[$proj] SKIP — source not at $ROOTS/$proj" | tee -a "$SUMMARY"
    continue
  fi

  view_cache="$VIEW_CACHE_BASE/$proj"
  view_flag=()
  if [[ -d "$view_cache" ]]; then
    view_flag=(--use-view-registry --view-cache-dir "$view_cache")
  else
    echo "[$proj] note: no view cache at $view_cache; running without view-eq" \
      | tee -a "$SUMMARY"
  fi

  echo "=== [$proj] start $(date -Is) ===" | tee -a "$SUMMARY"
  proj_out="$OUT/$proj"
  mkdir -p "$proj_out"

  model_flag=()
  [[ -n "$MODEL" ]]  && model_flag+=(--llm-proof-model "$MODEL")
  [[ -n "$EFFORT" ]] && model_flag+=(--llm-proof-effort "$EFFORT")

  python -u -m spec_determinism.corpus.verusage_run \
    --project "$proj" \
    --roots   "$ROOTS" \
    --out     "$proj_out" \
    "${view_flag[@]}" \
    --use-llm-proof \
    --llm-proof-max-attempts "$MAX_ATTEMPTS" \
    --llm-proof-cache-mode   "$CACHE_MODE" \
    --llm-proof-timeout      "$LLM_TIMEOUT" \
    --llm-proof-mode         "$LLM_MODE" \
    --llm-proof-session-timeout "$SESSION_TIMEOUT" \
    "${model_flag[@]}" \
    > "$LOG_DIR/${proj}.log" 2>&1
  rc=$?

  if [[ -f "$proj_out/full_run.json" ]]; then
    python3 -c "
import json
from collections import Counter
d = json.load(open('$proj_out/full_run.json'))
c = Counter(r.get('status','?') for r in d)
proved      = sum(1 for r in d if r.get('status')=='ok' and r.get('r0_z3')=='unsat' and not r.get('llm_assisted'))
proved_llm  = sum(1 for r in d if r.get('status')=='ok' and r.get('llm_assisted'))
witness     = sum(1 for r in d if r.get('status')=='ok' and r.get('r0_z3')=='sat')
inconc      = sum(1 for r in d if r.get('status')=='ok' and r.get('r0_z3')=='unknown')
llm_atts    = sum(r.get('llm_proof_attempts',0) for r in d)
print(f'[$proj] n={len(d)} by_status={dict(c)} proved={proved} proved_llm={proved_llm} witness={witness} inconc={inconc} total_llm_attempts={llm_atts}')
" | tee -a "$SUMMARY"
  fi
  echo "=== [$proj] done rc=$rc $(date -Is) ===" | tee -a "$SUMMARY"
done

# Aggregate report
python -u -m spec_determinism.corpus.verusage_summary \
  --results "$OUT" \
  --out     "$OUT/SUMMARY.md" \
  >> "$SUMMARY" 2>&1 || true

echo "=== llm-proof rerun finished $(date -Is) ===" | tee -a "$SUMMARY"
