#!/usr/bin/env python3
"""Batch driver for the tiny SpecGym determinism-feedback experiment."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ONE_SHOT = REPO_ROOT / "scripts" / "specgen_det_feedback.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(errors="replace"))


def task_dirs(tasks_root: Path) -> list[Path]:
    return sorted(p for p in tasks_root.iterdir() if p.is_dir() and p.name.startswith("verus-gym-"))


def final_label(summary: dict) -> str:
    final = summary.get("final") or {}
    return str(final.get("status_label", "missing"))


def run_one(task_dir: Path, out_dir: Path, args: argparse.Namespace) -> dict:
    task_out = out_dir / task_dir.name
    summary_path = task_out / "summary.json"
    if summary_path.is_file() and not args.force:
        summary = load_json(summary_path)
        return {
            "task": task_dir.name,
            "status": "skipped_existing",
            "final_label": final_label(summary),
            "summary_path": str(summary_path),
        }

    cmd = [
        sys.executable,
        str(ONE_SHOT),
        "--task-dir", str(task_dir),
        "--out-dir", str(task_out),
        "--feedback-rounds", str(args.feedback_rounds),
        "--det-timeout", str(args.det_timeout),
        "--llm-timeout", str(args.llm_timeout),
        "--copilot-bin", args.copilot_bin,
        "--call-llm-initial",
        "--call-llm-fix",
    ]
    if args.model:
        cmd += ["--model", args.model]

    started = time.monotonic()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=args.task_timeout,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    (task_out / "batch_stdout.txt").write_text(proc.stdout)
    (task_out / "batch_stderr.txt").write_text(proc.stderr)

    record = {
        "task": task_dir.name,
        "status": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "summary_path": str(summary_path),
    }
    if summary_path.is_file():
        summary = load_json(summary_path)
        record["final_label"] = final_label(summary)
        record["rounds"] = len(summary.get("rounds") or [])
    else:
        record["final_label"] = "no_summary"
        record["stderr_tail"] = proc.stderr[-2000:]
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks-root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "results" / "specgen_det_feedback_batch")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--feedback-rounds", type=int, default=3)
    ap.add_argument("--model", default=None)
    ap.add_argument("--copilot-bin", default="copilot")
    ap.add_argument("--llm-timeout", type=int, default=900)
    ap.add_argument("--det-timeout", type=int, default=120)
    ap.add_argument("--task-timeout", type=int, default=4200)
    ap.add_argument("--jobs", type=int, default=1,
                    help="Maximum number of tasks to run in parallel.")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    tasks = task_dirs(args.tasks_root.expanduser().resolve())
    tasks = tasks[args.start:]
    if args.limit is not None:
        tasks = tasks[: args.limit]

    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "batch_results.jsonl"

    records = []
    with jsonl_path.open("a") as jf:
        def _run_with_catch(task_dir: Path) -> dict:
            try:
                return run_one(task_dir, out_dir, args)
            except subprocess.TimeoutExpired as exc:
                return {
                    "task": task_dir.name,
                    "status": "timeout",
                    "final_label": "timeout",
                    "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
                }
            except Exception as exc:
                return {
                    "task": task_dir.name,
                    "status": "exception",
                    "final_label": "exception",
                    "error": f"{type(exc).__name__}: {exc}",
                }

        if args.jobs <= 1:
            for idx, task_dir in enumerate(tasks, start=1):
                print(f"[{idx}/{len(tasks)}] {task_dir.name}", flush=True)
                rec = _run_with_catch(task_dir)
                print(f"  -> {rec.get('status')} {rec.get('final_label')}", flush=True)
                records.append(rec)
                jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                jf.flush()
        else:
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                futs = {}
                for idx, task_dir in enumerate(tasks, start=1):
                    print(f"[submit {idx}/{len(tasks)}] {task_dir.name}", flush=True)
                    futs[pool.submit(_run_with_catch, task_dir)] = task_dir
                done = 0
                for fut in as_completed(futs):
                    done += 1
                    rec = fut.result()
                    print(
                        f"[done {done}/{len(tasks)}] {rec.get('task')} "
                        f"-> {rec.get('status')} {rec.get('final_label')}",
                        flush=True,
                    )
                    records.append(rec)
                    jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    jf.flush()

    counts: dict[str, int] = {}
    for rec in records:
        label = rec.get("final_label", "missing")
        counts[label] = counts.get(label, 0) + 1
    summary = {
        "n": len(records),
        "counts_by_final_label": counts,
        "records": records,
    }
    (out_dir / "batch_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary["counts_by_final_label"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
