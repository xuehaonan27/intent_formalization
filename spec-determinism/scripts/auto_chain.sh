#!/usr/bin/env bash
# Wait for the in-flight prefill batch (or whatever set of prefill
# python processes are running right now) to finish, then run the
# corpus rerun, then emit the comparison. Survives session compaction
# because it polls by name, not by PID.
set -u

LOG_DIR=/home/chentianyu/.copilot/session-state/7214e2c5-243b-424d-a1db-cc2f2b274210/files/auto_chain_logs
mkdir -p "$LOG_DIR"
GLOBAL_LOG="$LOG_DIR/_chain.log"

log() { echo "[$(date -Is)] $*" | tee -a "$GLOBAL_LOG"; }

cd /home/chentianyu/intent_formalization/spec-determinism

log "auto-chain start: waiting for any 'spec_determinism.view.llm prefill' to finish"
while pgrep -f "spec_determinism.view.llm prefill" > /dev/null 2>&1; do
  sleep 60
done
log "all prefill processes done"

log "launching rerun_corpus.sh"
./scripts/rerun_corpus.sh > "$LOG_DIR/rerun.out" 2>&1
log "rerun_corpus.sh exit=$?"

log "launching compare_runs.py"
python3 scripts/compare_runs.py \
  --baseline results-verusage \
  --candidate results-verusage-viewreg \
  --out results-verusage-viewreg/COMPARE.md \
  > "$LOG_DIR/compare.out" 2>&1
log "compare_runs.py exit=$?"

log "auto-chain done"
