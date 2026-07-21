#!/usr/bin/env python3
"""
Pipeline runner — run all tasks with task-level parallelism.

Imports run_task() from run_task.py and orchestrates across all entries.

Usage:
  python3 run_pipeline.py [--workers N] [--limit N] [--offset N] [--model MODEL] [--workspace DIR]
"""

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

BASE = Path.home() / "intent_formalization"

sys.path.insert(0, str(BASE / "src" / "utils"))
sys.path.insert(0, str(BASE / "src"))

from pipeline.run_task import run_task


def main():
    parser = argparse.ArgumentParser(description="Run full pipeline with task-level parallelism")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--model", type=str, default="claude-opus-4.6")
    parser.add_argument("--workspace", type=str, default=str(BASE / "verusage" / "workspace_v4"))
    parser.add_argument("--verus-timeout", type=int, default=120)
    args = parser.parse_args()

    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    entries = json.loads((workspace / "exec_functions.json").read_text())
    entries = entries[args.offset:]
    if args.limit:
        entries = entries[:args.limit]

    # Skip already-completed tasks
    todo = []
    for e in entries:
        td = workspace / e["task_name"]
        if (td / "verdicts.json").exists() or (td / "entailment_results.json").exists():
            continue
        todo.append(e)

    print(f"Pipeline v4: {len(todo)} tasks to run ({len(entries) - len(todo)} already done)")
    print(f"  Workers: {args.workers} | Model: {args.model} | Workspace: {workspace}")

    results = []
    start = time.time()

    if args.workers <= 1:
        for i, entry in enumerate(todo):
            print(f"\n[{i+1}/{len(todo)}] {entry['task_name']}")
            try:
                r = run_task(entry, args.model, workspace, args.verus_timeout)
                results.append(r)
                tp = r.get("true_positives", 0)
                print(f"  → {r.get('status', '?')} | {r.get('candidates', 0)} φ | {r.get('verified', 0)} verified | {tp} TP")
            except Exception as e:
                print(f"  → ERROR: {e}")
                results.append({"task": entry["task_name"], "status": "error", "error": str(e)})
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(run_task, e, args.model, workspace, args.verus_timeout): e
                for e in todo
            }
            done_count = 0
            for future in as_completed(futures):
                done_count += 1
                entry = futures[future]
                try:
                    r = future.result()
                    results.append(r)
                    tp = r.get("true_positives", 0)
                    print(f"[{done_count}/{len(todo)}] {entry['task_name']} → {r.get('status', '?')} | {tp} TP")
                except Exception as e:
                    print(f"[{done_count}/{len(todo)}] {entry['task_name']} → ERROR: {e}")
                    results.append({"task": entry["task_name"], "status": "error", "error": str(e)})

    elapsed = time.time() - start

    complete = [r for r in results if r.get("status") == "complete"]
    total_tp = sum(r.get("true_positives", 0) for r in results)
    total_taut = sum(r.get("tautologies", 0) for r in results)
    total_candidates = sum(r.get("candidates", 0) for r in results)
    total_verified = sum(r.get("verified", 0) for r in results)

    print(f"\n{'='*60}")
    print(f"Pipeline v4 complete in {elapsed:.0f}s")
    print(f"  Tasks: {len(results)} run, {len(complete)} complete")
    print(f"  Candidates: {total_candidates} generated")
    print(f"  Verified: {total_verified}")
    print(f"  Tautologies filtered: {total_taut}")
    print(f"  True positives: {total_tp}")
    print(f"{'='*60}")

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": args.model,
        "tasks_run": len(results),
        "complete": len(complete),
        "total_candidates": total_candidates,
        "total_verified": total_verified,
        "total_tautologies": total_taut,
        "total_true_positives": total_tp,
        "elapsed_seconds": elapsed,
        "results": results,
    }
    (workspace / "pipeline_summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
