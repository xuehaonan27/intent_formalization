"""
Step 7 (fuzz): Run Verus on each assembled proof-fn file in a worker pool.

For each case in assembled_cases.json, runs Verus on the corresponding
.rs file and records the outcome (verifies / fails / timeout).

Outputs: <task_dir>/verus_results.json  (cases + verus_outcome populated)

Uses concurrent.futures.ThreadPoolExecutor sized by --jobs
(default: os.cpu_count() // 2).

Usage:
  python -m src.pipeline_fuzz.step7_verus --task-dir <path> [--jobs N] [--timeout SECS]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.utils.verus import run_verus, VerusResult
from src.pipeline_fuzz.schemas import Case, VerusOutcome

logger = logging.getLogger(__name__)

DEFAULT_VERUS_TIMEOUT = 60  # seconds per case


# ---------------------------------------------------------------------------
# Single-case runner
# ---------------------------------------------------------------------------

def _run_one(case_dict: dict, verus_timeout: int) -> dict:
    """
    Run Verus on one case and return the updated case dict.

    This function is called in a worker thread — no shared mutable state.
    """
    verus_source = case_dict.get("verus_source", "")
    case_id = case_dict.get("case_id", "?")

    if not verus_source or not Path(verus_source).exists():
        logger.warning(f"[step7] No source file for case {case_id}")
        case_dict["verus_outcome"] = "fails"
        case_dict["verus_log"] = f"Source file missing: {verus_source}"
        return case_dict

    try:
        result: VerusResult = run_verus(
            file_path=verus_source,
            timeout=verus_timeout,
        )
    except Exception as e:
        case_dict["verus_outcome"] = "fails"
        case_dict["verus_log"] = f"run_verus exception: {e}"
        return case_dict

    # Map VerusResult → VerusOutcome
    outcome: VerusOutcome
    if "TIMEOUT" in result.output.upper():
        outcome = "timeout"
    elif result.success:
        outcome = "verifies"
    else:
        outcome = "fails"

    # Also write a .log file alongside the .rs file for inspection
    log_path = Path(verus_source).with_suffix(".log")
    try:
        log_path.write_text(result.output)
    except Exception:
        pass

    case_dict["verus_outcome"] = outcome
    case_dict["verus_log"] = result.output[:2000]  # cap to avoid huge JSON
    return case_dict


# ---------------------------------------------------------------------------
# process_one
# ---------------------------------------------------------------------------

def process_one(task_dir: Path, jobs: int | None = None,
                verus_timeout: int = DEFAULT_VERUS_TIMEOUT) -> list[dict]:
    """
    Run Verus in parallel on all assembled cases.

    Reads: assembled_cases.json
    Writes: verus_results.json
    Returns: list of updated case dicts
    """
    assembled_path = task_dir / "assembled_cases.json"
    if not assembled_path.exists():
        raise FileNotFoundError(f"assembled_cases.json not found in {task_dir}")

    case_dicts = json.loads(assembled_path.read_text())

    n_workers = jobs if jobs and jobs > 0 else max(1, (os.cpu_count() or 2) // 2)
    logger.info(f"[step7] Running Verus on {len(case_dicts)} cases with {n_workers} workers")

    results: list[dict] = [None] * len(case_dicts)  # type: ignore[list-item]

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        future_to_idx = {
            executor.submit(_run_one, dict(case_dicts[i]), verus_timeout): i
            for i in range(len(case_dicts))
        }
        done_count = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            done_count += 1
            try:
                results[idx] = future.result()
            except Exception as e:
                d = dict(case_dicts[idx])
                d["verus_outcome"] = "fails"
                d["verus_log"] = f"Worker exception: {e}"
                results[idx] = d

            if done_count % 20 == 0:
                logger.info(f"[step7] {done_count}/{len(case_dicts)} done")

    (task_dir / "verus_results.json").write_text(json.dumps(results, indent=2))
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 7 (fuzz): Run Verus on assembled proof-fn files"
    )
    parser.add_argument("--task-dir", type=str, required=True)
    parser.add_argument("--jobs", type=int, default=None,
                        help="Worker pool size (default: os.cpu_count()//2)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_VERUS_TIMEOUT,
                        help="Verus timeout per case in seconds (default: 60)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    task_dir = Path(args.task_dir).resolve()

    print(f"[step7] Running Verus for {task_dir.name}  (jobs={args.jobs}, timeout={args.timeout}s)")

    try:
        results = process_one(task_dir, jobs=args.jobs, verus_timeout=args.timeout)
    except FileNotFoundError as e:
        print(f"[step7] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    verifies = sum(1 for r in results if r.get("verus_outcome") == "verifies")
    fails = sum(1 for r in results if r.get("verus_outcome") == "fails")
    timeouts = sum(1 for r in results if r.get("verus_outcome") == "timeout")

    print(f"[step7] Outcomes: verifies={verifies}  fails={fails}  timeouts={timeouts}")
    print(f"[step7] Wrote verus_results.json → {task_dir / 'verus_results.json'}")


if __name__ == "__main__":
    main()
