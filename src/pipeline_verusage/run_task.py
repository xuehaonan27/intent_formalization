#!/usr/bin/env python3
"""
Run full pipeline on a single task by calling each step's process_one().

  step2 (generate) → step3 (entailment) → step4 (tautology + critic)

Usage:
  python3 run_task.py --task <task_name> [--workspace DIR] [--model MODEL] [--verus-timeout SECS]
  python3 run_task.py --file <source.rs> [--workspace DIR] [--model MODEL]
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

BASE = Path.home() / "intent_formalization"

sys.path.insert(0, str(BASE / "src" / "utils"))
sys.path.insert(0, str(BASE / "src"))

from llm import LLMClient
from pipeline.step1_extract import extract_from_file
from pipeline.step2_brainstorm import process_one as step2_process
from pipeline.step3_formalize import process_one as step3_process
from pipeline.step4_entailment import process_one as step4_process
from pipeline.step5_critic import process_one as step5_process


def run_task(entry: dict, model: str, workspace: Path, verus_timeout: int) -> dict:
    """Run full pipeline for one task by delegating to each step."""
    task_name = entry["task_name"]
    task_dir = workspace / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    # Copy source file into task dir
    fpath = Path(entry["file_path"])
    shutil.copy2(fpath, task_dir / "original.rs")
    (task_dir / "exec_functions.json").write_text(
        json.dumps(entry["exec_functions"], indent=2))

    llm = LLMClient(timeout=600)

    # Step 2: Brainstorm negative properties (natural language)
    print(f"  [step2] brainstorm")
    r2 = step2_process(entry, llm, model, workspace)

    if r2.get("status") != "ok":
        return {"task": task_name, "status": r2.get("status", "no_properties"),
                "properties": r2.get("total", 0)}

    # Step 3: Formalize into Verus proof fns
    print(f"  [step3] formalize")
    r3 = step3_process(task_dir, llm, model)

    if r3.get("candidates", 0) == 0:
        return {"task": task_name, "status": "no_candidates",
                "properties": r2.get("total", 0), "candidates": 0}

    # Step 4: Entailment check
    print(f"  [step4] entailment")
    r4 = step4_process(task_dir, verus_timeout)

    if r4.get("verified", 0) == 0:
        return {"task": task_name, "status": "no_verified",
                "properties": r2.get("total", 0),
                "candidates": r3.get("candidates", 0), "verified": 0}

    # Step 5: Tautology check + LLM critic
    print(f"  [step5] critic")
    r5 = step5_process(task_dir, llm, model)

    return {
        "task": task_name,
        "status": r5.get("status", "complete"),
        "properties": r2.get("total", 0),
        "properties_2a": r2.get("props_2a", 0),
        "properties_2b": r2.get("props_2b", 0),
        "candidates": r3.get("candidates", 0),
        "verified": r4.get("verified", 0),
        "tautologies": r5.get("tautologies", 0),
        "true_positives": r5.get("true_positives", 0),
        "false_positives": r5.get("false_positives", 0),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run full pipeline on a single task")
    parser.add_argument("--task", type=str, help="Task name (from exec_functions.json)")
    parser.add_argument("--file", type=str, help="Source file path (alternative to --task)")
    parser.add_argument("--workspace", type=str, default=str(BASE / "verusage" / "workspace_v4"))
    parser.add_argument("--model", type=str, default="claude-opus-4.6")
    parser.add_argument("--verus-timeout", type=int, default=120)
    args = parser.parse_args()

    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    if args.task:
        entries = json.loads((workspace / "exec_functions.json").read_text())
        entry = next((e for e in entries if e["task_name"] == args.task), None)
        if not entry:
            print(f"Task '{args.task}' not found in {workspace / 'exec_functions.json'}")
            sys.exit(1)
    elif args.file:
        fpath = Path(args.file).resolve()
        entry = extract_from_file(fpath)
        if not entry:
            print(f"No exec functions found in {fpath}")
            sys.exit(1)
    else:
        print("Must specify --task or --file")
        sys.exit(1)

    print(f"Running pipeline on: {entry['task_name']}")
    print(f"  File: {entry['file_path']}")
    print(f"  Exec functions: {[f['name'] for f in entry['exec_functions']]}")
    print(f"  Model: {args.model}")
    print(f"  Workspace: {workspace}")
    print()

    start = time.time()
    result = run_task(entry, args.model, workspace, args.verus_timeout)
    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"Task: {result.get('task')}")
    print(f"Status: {result.get('status')}")
    print(f"Properties: {result.get('properties', 0)} (2a={result.get('properties_2a', 0)}, 2b={result.get('properties_2b', 0)})")
    print(f"Candidates: {result.get('candidates', 0)}")
    print(f"Verified: {result.get('verified', 0)}")
    print(f"Tautologies: {result.get('tautologies', 0)}")
    print(f"True positives: {result.get('true_positives', 0)}")
    print(f"False positives: {result.get('false_positives', 0)}")
    print(f"Time: {elapsed:.1f}s")
    print(f"{'='*60}")

    task_dir = workspace / entry["task_name"]
    (task_dir / "task_result.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
