#!/usr/bin/env bash
# Drive a full L4 prefill across all 7 verusage projects, with the
# codex critic enabled. Sequential — both copilot and codex are
# globally rate-limited.
set -u

cd /home/xuehaonan/intent_formalization/spec-determinism

LOG_DIR=/home/xuehaonan/.copilot/session-state/7214e2c5-243b-424d-a1db-cc2f2b274210/files/prefill_logs
mkdir -p "$LOG_DIR"

ROOT=../verusage/source-projects
CACHE=results-verusage/view_registry

declare -a PROJECTS=(
  anvil-library
  memory-allocator
  vest
  storage
  nrkernel
  ironkv
  atmosphere
)

SUMMARY="$LOG_DIR/_run_summary.log"
echo "=== prefill batch started $(date -Is) ===" >> "$SUMMARY"

for proj in "${PROJECTS[@]}"; do
  if [[ ! -d "$ROOT/$proj" ]]; then
    echo "[$proj] SKIP — source not at $ROOT/$proj" | tee -a "$SUMMARY"
    continue
  fi
  echo "=== [$proj] start $(date -Is) ===" | tee -a "$SUMMARY"
  python -u -m spec_determinism.view.llm prefill \
    --project "$proj" \
    --root   "$ROOT/$proj" \
    --cache-dir "$CACHE/$proj" \
    --force \
    > "$LOG_DIR/${proj}.log" 2>&1
  rc=$?
  tail -1 "$LOG_DIR/${proj}.log" | tee -a "$SUMMARY"
  echo "=== [$proj] done rc=$rc $(date -Is) ===" | tee -a "$SUMMARY"
done

echo "=== prefill batch finished $(date -Is) ===" >> "$SUMMARY"
