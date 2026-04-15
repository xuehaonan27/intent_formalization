"""
Run the spec-fuzzing pipeline on a single source file.

  step1_extract  → exec_functions.json
  step2_template → templates.json
  step3_enumerate→ seed_cases.json
  step4_diversify→ cases_diversified.json  (LLM)
  step5_oracle   → cases_labeled.json      (LLM)
  step6_assemble → verus/<case>.rs
  step7_verus    → verus_results.json
  step8_report   → findings.json + findings.md

Usage:
  python -m src.pipeline_fuzz.run_task \\
      --source nanvix/workspace/bitmap/src/bitmap.rs \\
      --workspace workspace_fuzz_test \\
      [--model MODEL] [--jobs N] [--verus-timeout SECS]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

# The existing pipeline modules use old-style sys.path imports (e.g., `from llm import ...`).
# Add required paths before any downstream imports.
_SRC_ROOT = Path(__file__).resolve().parents[2]
if str(_SRC_ROOT / "src" / "utils") not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT / "src" / "utils"))
if str(_SRC_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT / "src"))

from src.utils.llm import LLMClient
from src.pipeline_fuzz.step1_extract import process_one as step1_process
from src.pipeline_fuzz.step2_template import process_one as step2_process
from src.pipeline_fuzz.step3_enumerate import process_one as step3_process
from src.pipeline_fuzz.step4_diversify import process_one as step4_process
from src.pipeline_fuzz.step5_oracle import process_one as step5_process
from src.pipeline_fuzz.step6_assemble import process_one as step6_process
from src.pipeline_fuzz.step7_verus import process_one as step7_process
from src.pipeline_fuzz.step8_report import process_one as step8_process


def run_task(
    source_path: Path,
    workspace: Path,
    model: str = "claude-opus-4.6",
    jobs: int | None = None,
    verus_timeout: int = 60,
) -> dict:
    """
    Run the full spec-fuzzing pipeline on one source file.

    Returns a summary dict suitable for aggregation by run_pipeline.py.
    """
    # Determine task name (use file stem; avoids VERUSAGE path dep)
    task_name = source_path.stem

    task_dir = workspace / "pipeline_fuzz" / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    print(f"[fuzz] Task: {task_name}")
    print(f"[fuzz] Source: {source_path}")
    print(f"[fuzz] Task dir: {task_dir}")

    llm = LLMClient(timeout=600)

    # -------------------------------------------------------------------
    # Step 1: Extract
    # -------------------------------------------------------------------
    print(f"\n  [step1] extract exec functions")
    try:
        entry = step1_process(source_path, task_dir)
    except ValueError as e:
        print(f"  [step1] SKIP: {e}")
        return {"task": task_name, "status": "no_exec_functions", "source": str(source_path)}

    fn_names = [f["name"] for f in entry["exec_functions"]]
    print(f"  [step1] Found {len(fn_names)} exec fns: {fn_names}")

    # -------------------------------------------------------------------
    # Step 2: Template
    # -------------------------------------------------------------------
    print(f"\n  [step2] generate scenario templates")
    templates = step2_process(task_dir)
    print(f"  [step2] {len(templates)} templates")

    # -------------------------------------------------------------------
    # Step 3: Enumerate
    # -------------------------------------------------------------------
    print(f"\n  [step3] enumerate seed cases")
    seeds = step3_process(task_dir)
    print(f"  [step3] {len(seeds)} seed cases")

    if not seeds:
        return {
            "task": task_name,
            "status": "no_seeds",
            "source": str(source_path),
            "templates": len(templates),
        }

    # -------------------------------------------------------------------
    # Step 4: Diversify (LLM)
    # -------------------------------------------------------------------
    print(f"\n  [step4] diversify cases (LLM)")
    try:
        diversified = step4_process(task_dir, llm, model, workspace)
    except Exception as e:
        print(f"  [step4] ERROR (continuing with seeds only): {e}")
        # Fall back: copy seed_cases.json as cases_diversified.json
        import shutil as _shutil
        _shutil.copy2(task_dir / "seed_cases.json", task_dir / "cases_diversified.json")
        from src.pipeline_fuzz.schemas import Case
        diversified = [Case.from_dict(d)
                       for d in json.loads((task_dir / "seed_cases.json").read_text())]
    print(f"  [step4] {len(diversified)} cases after diversification")

    # -------------------------------------------------------------------
    # Step 5: Oracle (LLM)
    # -------------------------------------------------------------------
    print(f"\n  [step5] oracle labeling (LLM)")
    try:
        labeled = step5_process(task_dir, llm, model, workspace)
    except Exception as e:
        print(f"  [step5] ERROR (continuing with unlabeled cases): {e}")
        # Fall back: copy diversified as labeled (no labels)
        import shutil as _shutil
        _shutil.copy2(task_dir / "cases_diversified.json", task_dir / "cases_labeled.json")
        from src.pipeline_fuzz.schemas import Case
        labeled = [Case.from_dict(d)
                   for d in json.loads((task_dir / "cases_diversified.json").read_text())]

    accept = sum(1 for c in labeled if c.oracle == "ACCEPT")
    reject = sum(1 for c in labeled if c.oracle == "REJECT")
    print(f"  [step5] ACCEPT={accept}  REJECT={reject}")

    # -------------------------------------------------------------------
    # Step 6: Assemble proof fns
    # -------------------------------------------------------------------
    print(f"\n  [step6] assemble proof-fn source files")
    try:
        step6_process(task_dir)
    except Exception as e:
        print(f"  [step6] ERROR: {e}")
        return {
            "task": task_name,
            "status": "assemble_error",
            "error": str(e),
            "source": str(source_path),
        }
    print(f"  [step6] done")

    # -------------------------------------------------------------------
    # Step 7: Verus
    # -------------------------------------------------------------------
    print(f"\n  [step7] run Verus (jobs={jobs}, timeout={verus_timeout}s)")
    try:
        verus_results = step7_process(task_dir, jobs=jobs, verus_timeout=verus_timeout)
    except Exception as e:
        print(f"  [step7] ERROR: {e}")
        return {
            "task": task_name,
            "status": "verus_error",
            "error": str(e),
            "source": str(source_path),
        }

    verifies = sum(1 for r in verus_results if r.get("verus_outcome") == "verifies")
    fails = sum(1 for r in verus_results if r.get("verus_outcome") == "fails")
    timeouts = sum(1 for r in verus_results if r.get("verus_outcome") == "timeout")
    print(f"  [step7] verifies={verifies}  fails={fails}  timeouts={timeouts}")

    # -------------------------------------------------------------------
    # Step 8: Report
    # -------------------------------------------------------------------
    print(f"\n  [step8] generate report")
    try:
        report = step8_process(task_dir)
    except Exception as e:
        print(f"  [step8] ERROR: {e}")
        report = {"findings": 0, "incorrectness": 0, "incompleteness": 0}

    print(f"  [step8] findings={report.get('findings', 0)} "
          f"(INCORRECTNESS={report.get('incorrectness', 0)}, "
          f"INCOMPLETENESS={report.get('incompleteness', 0)})")

    result = {
        "task": task_name,
        "status": "complete",
        "source": str(source_path),
        "exec_fns": len(fn_names),
        "seed_cases": len(seeds),
        "total_cases": len(labeled),
        "oracle_accept": accept,
        "oracle_reject": reject,
        "verus_verifies": verifies,
        "verus_fails": fails,
        "verus_timeouts": timeouts,
        "findings": report.get("findings", 0),
        "incorrectness": report.get("incorrectness", 0),
        "incompleteness": report.get("incompleteness", 0),
    }

    (task_dir / "task_result.json").write_text(json.dumps(result, indent=2))
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Spec-fuzz pipeline: run all stages on a single source file"
    )
    parser.add_argument("--source", type=str, required=True,
                        help="Path to Rust source file")
    parser.add_argument("--workspace", type=str, default="workspace_fuzz",
                        help="Workspace directory (default: workspace_fuzz)")
    parser.add_argument("--model", type=str, default="claude-opus-4.6",
                        help="LLM model name")
    parser.add_argument("--jobs", type=int, default=None,
                        help="Verus worker pool size (default: cpu_count//2)")
    parser.add_argument("--verus-timeout", type=int, default=60,
                        help="Verus timeout per case in seconds (default: 60)")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    if not source.exists():
        print(f"ERROR: source file not found: {source}", file=sys.stderr)
        sys.exit(1)

    start = time.time()
    result = run_task(
        source_path=source,
        workspace=workspace,
        model=args.model,
        jobs=args.jobs,
        verus_timeout=args.verus_timeout,
    )
    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"Task:          {result.get('task')}")
    print(f"Status:        {result.get('status')}")
    print(f"Exec fns:      {result.get('exec_fns', 0)}")
    print(f"Total cases:   {result.get('total_cases', 0)}")
    print(f"Findings:      {result.get('findings', 0)} "
          f"(INCORRECTNESS={result.get('incorrectness', 0)}, "
          f"INCOMPLETENESS={result.get('incompleteness', 0)})")
    print(f"Time:          {elapsed:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
