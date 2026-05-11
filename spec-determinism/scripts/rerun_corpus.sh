#!/usr/bin/env bash
# Rerun the verusage corpus with --use-view-registry so gen_det can
# inject the prefilled L4 impl-View blocks before the equal-fn. Writes
# results to results-verusage-viewreg/ so we can diff against the
# baseline (results-verusage/) without clobbering it.
set -u

cd /home/chentianyu/intent_formalization/spec-determinism

ROOTS=/home/chentianyu/intent_formalization/verusage/source-projects
BASELINE=results-verusage
OUT=results-verusage-viewreg
VIEW_CACHE=$BASELINE/view_registry

LOG_DIR=/home/chentianyu/.copilot/session-state/7214e2c5-243b-424d-a1db-cc2f2b274210/files/corpus_rerun_logs
mkdir -p "$LOG_DIR"

mkdir -p "$OUT"

declare -a PROJECTS=(
  anvil-library
  memory-allocator
  vest
  nrkernel
  storage
  ironkv
  atmosphere
)

# Allow callers to limit to a subset (whitespace-separated), useful for
# resuming a partial rerun without redoing the long projects.
if [[ "${ONLY:-}" != "" ]]; then
  read -r -a PROJECTS <<< "$ONLY"
fi

SUMMARY="$LOG_DIR/_run_summary.log"
echo "=== rerun batch started $(date -Is) ===" >> "$SUMMARY"

for proj in "${PROJECTS[@]}"; do
  if [[ ! -d "$ROOTS/$proj" ]]; then
    echo "[$proj] SKIP — source not at $ROOTS/$proj" | tee -a "$SUMMARY"
    continue
  fi
  cache="$VIEW_CACHE/$proj"
  if [[ ! -d "$cache" ]]; then
    echo "[$proj] SKIP — no view cache at $cache" | tee -a "$SUMMARY"
    continue
  fi
  echo "=== [$proj] start $(date -Is) ===" | tee -a "$SUMMARY"

  # Write to $OUT/$proj so verusage_summary.load_per_project can find
  # $OUT/<proj>/full_run.json. Without the subdir the per-project file
  # was overwritten by each subsequent project (bug fixed 2026-05-11).
  proj_out="$OUT/$proj"
  mkdir -p "$proj_out"

  python -u -m spec_determinism.corpus.verusage_run \
    --project "$proj" \
    --roots   "$ROOTS" \
    --out     "$proj_out" \
    --use-view-registry \
    --view-cache-dir "$cache" \
    > "$LOG_DIR/${proj}.log" 2>&1
  rc=$?
  if [[ -f "$proj_out/full_run.json" ]]; then
    python3 -c "
import json
from collections import Counter
d = json.load(open('$proj_out/full_run.json'))
c = Counter(r.get('status','?') for r in d)
w = sum(1 for r in d if r.get('status')=='ok' and r.get('assumes'))
print(f'[$proj] n={len(d)}  by_status={dict(c)}  ok_with_witness={w}')
" | tee -a "$SUMMARY"
  fi
  echo "=== [$proj] done rc=$rc $(date -Is) ===" | tee -a "$SUMMARY"
done

# Regenerate the SUMMARY.json / .md for the new output tree
python -u -m spec_determinism.corpus.verusage_summary \
  --results "$OUT" \
  --out     "$OUT/SUMMARY.md" \
  >> "$SUMMARY" 2>&1 || true

echo "=== rerun batch finished $(date -Is) ===" >> "$SUMMARY"
