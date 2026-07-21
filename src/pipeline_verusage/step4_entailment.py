#!/usr/bin/env python3
"""
Step 3: Run Verus entailment check on each candidate φ.

Reads:  workspace/<task_name>/candidates.json + original.rs
Writes: workspace/<task_name>/phi_<n>_<name>.rs  (test files)
        workspace/<task_name>/entailment_results.json

Usage:
  python3 step3_entailment.py [--limit N] [--offset N] [--timeout SECS] [--workspace DIR]
"""

import argparse
import json
import sys
from pathlib import Path

BASE = Path.home() / "intent_formalization"

sys.path.insert(0, str(BASE / "src" / "utils"))
from verus import run_verus
from pipeline_common import build_entailment_file

VERUS_BINARY = str(Path.home() / "intent_formalization" / "verus" / "verus")


def process_one(task_dir: Path, verus_timeout: int) -> dict:
    """Run entailment check for all candidates in a task."""
    candidates_file = task_dir / "candidates.json"
    original_file = task_dir / "original.rs"

    if not candidates_file.exists() or not original_file.exists():
        return {"task": task_dir.name, "status": "missing_files"}

    candidates = json.loads(candidates_file.read_text())
    if not candidates:
        return {"task": task_dir.name, "status": "no_candidates"}

    source_text = original_file.read_text()
    results = []
    verified_count = 0

    for i, phi in enumerate(candidates):
        entry = {
            "name": phi["name"],
            "target_fn": phi.get("target_fn", ""),
            "type": phi.get("type", ""),
            "source": phi.get("source", "spec_only"),
            "reason": phi.get("reason", ""),
        }

        try:
            test_code = build_entailment_file(source_text, phi["code"])
            test_file = task_dir / f"phi_{i+1}_{phi['name']}.rs"
            test_file.write_text(test_code)

            result = run_verus(str(test_file), verus_binary=VERUS_BINARY, timeout=verus_timeout)
            entry["entailed"] = result.success
            entry["verified"] = result.verified
            entry["errors"] = result.errors
            entry["output_tail"] = result.output[-300:] if result.output else ""

            if result.success:
                verified_count += 1
        except Exception as e:
            entry["entailed"] = False
            entry["error"] = str(e)

        results.append(entry)

    (task_dir / "entailment_results.json").write_text(json.dumps(results, indent=2))

    return {
        "task": task_dir.name,
        "total": len(results),
        "verified": verified_count,
        "status": "ok",
    }


def main():
    parser = argparse.ArgumentParser(description="Step 3: Verus entailment check")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=120, help="Verus timeout per file")
    parser.add_argument("--workspace", type=str, default=str(BASE / "verusage" / "workspace_v4"))
    args = parser.parse_args()

    workspace = Path(args.workspace)
    task_dirs = sorted([
        d for d in workspace.iterdir()
        if d.is_dir()
        and (d / "candidates.json").exists()
        and not (d / "entailment_results.json").exists()
    ])

    task_dirs = task_dirs[args.offset:]
    if args.limit:
        task_dirs = task_dirs[:args.limit]

    print(f"Step 3: Entailment check for {len(task_dirs)} tasks (timeout={args.timeout}s)")

    total_verified = 0
    for i, task_dir in enumerate(task_dirs):
        print(f"\n[{i+1}/{len(task_dirs)}] {task_dir.name}")
        try:
            r = process_one(task_dir, args.timeout)
            v = r.get("verified", 0)
            total_verified += v
            if r["status"] == "ok":
                print(f"  {r['verified']}/{r['total']} verified")
            else:
                print(f"  {r['status']}")
        except Exception as e:
            print(f"  [error] {e}")

    print(f"\n=== Done: {total_verified} total verified φ across {len(task_dirs)} tasks ===")


if __name__ == "__main__":
    main()
