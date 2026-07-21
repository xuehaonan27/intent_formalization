#!/usr/bin/env bash
# Overnight full-corpus rerun with everything ON:
#   - Phase 2 view-aware equal-fn (PR-N + C-patch, via per-project view registry)
#   - Tier 1.5: LLM type-completion (gap-filling between extract and gen_det)
#   - Tier 3: LLM proof annotation loop on z3=unknown targets
#
# This is the "full funnel" rerun — all unsat-direction tools landed as of
# 2026-05-18 (commits 9b88cfd → 9a480346). Used after the Bug A/B work on
# Tier 1.5 to capture a clean global picture across the corpus.
#
# Usage:
#   bash scripts/rerun_corpus_full_funnel.sh                 # all projects
#   ONLY="ironkv vest" bash scripts/rerun_corpus_full_funnel.sh   # subset
set -u

cd /home/xuehaonan/intent_formalization/spec-determinism

ROOTS=${ROOTS:-/home/xuehaonan/intent_formalization/verusage/source-projects}
VIEW_CACHE_BASE=results-verusage/view_registry
TS=$(date +%Y%m%d_%H%M%S)
OUT=${OUT:-/tmp/full_funnel_${TS}}
LOG_DIR=${LOG_DIR:-/home/xuehaonan/.copilot/session-state/7214e2c5-243b-424d-a1db-cc2f2b274210/files/full_funnel_${TS}}

MAX_ATTEMPTS=${MAX_ATTEMPTS:-2}
LLM_PROOF_TIMEOUT=${LLM_PROOF_TIMEOUT:-600}
LLM_TYPE_TIMEOUT=${LLM_TYPE_TIMEOUT:-600}
LLM_PROOF_MODE=${LLM_PROOF_MODE:-single_shot}
SESSION_TIMEOUT=${SESSION_TIMEOUT:-1800}
TARGET_TIMEOUT=${TARGET_TIMEOUT:-180}

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
echo "=== full-funnel rerun started $(date -Is) ===" | tee -a "$SUMMARY"
echo "  out=$OUT  log_dir=$LOG_DIR" | tee -a "$SUMMARY"
echo "  view-registry + tier-1.5 + tier-3 all ENABLED" | tee -a "$SUMMARY"

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
    echo "[$proj] note: no view cache at $view_cache; view-eq off" | tee -a "$SUMMARY"
  fi

  echo "=== [$proj] start $(date -Is) ===" | tee -a "$SUMMARY"
  proj_out="$OUT/$proj"
  mkdir -p "$proj_out"

  python -u -m spec_determinism.corpus.verusage_run \
    --project "$proj" \
    --roots   "$ROOTS" \
    --out     "$proj_out" \
    "${view_flag[@]}" \
    --llm-type-completion \
    --llm-type-completion-timeout "$LLM_TYPE_TIMEOUT" \
    --use-llm-proof \
    --llm-proof-max-attempts "$MAX_ATTEMPTS" \
    --llm-proof-cache-mode   use \
    --llm-proof-timeout      "$LLM_PROOF_TIMEOUT" \
    --llm-proof-mode         "$LLM_PROOF_MODE" \
    --llm-proof-session-timeout "$SESSION_TIMEOUT" \
    --timeout "$TARGET_TIMEOUT" \
    > "$LOG_DIR/${proj}.log" 2>&1
  rc=$?

  if [[ -f "$proj_out/full_run.json" ]]; then
    python3 -c "
import json
from collections import Counter
d = json.load(open('$proj_out/full_run.json'))
c = Counter(r.get('status','?') for r in d)
proved     = sum(1 for r in d if r.get('status')=='ok' and r.get('r0_z3')=='unsat' and not r.get('llm_assisted'))
proved_llm = sum(1 for r in d if r.get('status')=='ok' and r.get('llm_assisted'))
witness    = sum(1 for r in d if r.get('status')=='ok' and r.get('r0_z3')=='sat')
inconc     = sum(1 for r in d if r.get('status')=='ok' and r.get('r0_z3')=='unknown')
t15_inv    = sum(1 for r in d if (r.get('tier15') or {}).get('llm_invoked'))
t15_acc    = sum((r.get('tier15') or {}).get('patches_accepted',0) for r in d)
t15_shape  = sum((r.get('tier15') or {}).get('shape_mismatch_detected',0) for r in d)
t15_repair = sum((r.get('tier15') or {}).get('shape_mismatch_repaired',0) for r in d)
print(f'[$proj] n={len(d)} by_status={dict(c)} proved={proved} proved_llm={proved_llm} witness={witness} inconc={inconc} t15_llm={t15_inv} t15_acc={t15_acc} shape_det={t15_shape} shape_rep={t15_repair}')
" | tee -a "$SUMMARY"
  fi
  echo "=== [$proj] done rc=$rc $(date -Is) ===" | tee -a "$SUMMARY"
done

python -u -m spec_determinism.corpus.verusage_summary \
  --results "$OUT" \
  --out     "$OUT/SUMMARY.md" \
  >> "$SUMMARY" 2>&1 || true

echo "=== full-funnel rerun finished $(date -Is) ===" | tee -a "$SUMMARY"
echo "Results: $OUT" | tee -a "$SUMMARY"
echo "Summary: $OUT/SUMMARY.md" | tee -a "$SUMMARY"
