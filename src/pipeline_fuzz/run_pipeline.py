"""
Run the spec-fuzzing pipeline across multiple source files.

Discovers .rs source files from the workspace's exec_functions.json
(if present) or by globbing a source directory, then runs run_task()
on each with task-level parallelism.

Writes: <workspace>/fuzz_findings_summary.md

Usage:
  python -m src.pipeline_fuzz.run_pipeline \\
      --workspace workspace_fuzz \\
      [--source-dir nanvix/workspace] \\
      [--workers N] [--model MODEL] \\
      [--limit N] [--offset N] \\
      [--verus-timeout SECS]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from src.pipeline_fuzz.run_task import run_task


# ---------------------------------------------------------------------------
# Source discovery
# ---------------------------------------------------------------------------

def _discover_sources(workspace: Path, source_dir: Path | None) -> list[Path]:
    """
    Return a list of .rs source files to fuzz.

    Priority:
    1. exec_functions.json in workspace (pipeline step1 output)
    2. Glob *.rs from source_dir (excluding test/lib.*.rs)
    3. Glob *.rs from workspace itself
    """
    exec_fns_path = workspace / "exec_functions.json"
    if exec_fns_path.exists():
        entries = json.loads(exec_fns_path.read_text())
        return [Path(e["file_path"]) for e in entries if Path(e["file_path"]).exists()]

    search_root = source_dir or workspace
    paths = []
    for p in sorted(search_root.rglob("*.rs")):
        name = p.name
        # Skip test/lib/spec support files
        if any(name.startswith(pfx) for pfx in ("lib.", "test", "build")):
            continue
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# Worker wrapper (ProcessPoolExecutor needs a picklable callable)
# ---------------------------------------------------------------------------

def _worker(source_str: str, workspace_str: str, model: str,
            jobs: int | None, verus_timeout: int) -> dict:
    result = run_task(
        source_path=Path(source_str),
        workspace=Path(workspace_str),
        model=model,
        jobs=jobs,
        verus_timeout=verus_timeout,
    )
    return result


# ---------------------------------------------------------------------------
# Summary markdown
# ---------------------------------------------------------------------------

def _write_summary_md(workspace: Path, results: list[dict], elapsed: float) -> None:
    complete = [r for r in results if r.get("status") == "complete"]
    total_findings = sum(r.get("findings", 0) for r in results)
    total_incorr = sum(r.get("incorrectness", 0) for r in results)
    total_incompl = sum(r.get("incompleteness", 0) for r in results)

    lines = [
        "# Spec-Fuzz Pipeline Summary",
        "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        f"Elapsed: {elapsed:.0f}s",
        "",
        "## Totals",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Tasks run | {len(results)} |",
        f"| Tasks complete | {len(complete)} |",
        f"| Total cases | {sum(r.get('total_cases', 0) for r in results)} |",
        f"| Findings | {total_findings} |",
        f"| INCORRECTNESS | {total_incorr} |",
        f"| INCOMPLETENESS | {total_incompl} |",
        "",
        "## Per-task findings",
        "",
        "| Task | Status | Cases | Findings | INCORR | INCOMPL |",
        "|------|--------|-------|----------|--------|---------|",
    ]

    for r in sorted(results, key=lambda x: -x.get("findings", 0)):
        task = r.get("task", "?")
        status = r.get("status", "?")
        cases = r.get("total_cases", 0)
        findings = r.get("findings", 0)
        incorr = r.get("incorrectness", 0)
        incompl = r.get("incompleteness", 0)
        lines.append(f"| `{task}` | {status} | {cases} | {findings} | {incorr} | {incompl} |")

    lines.append("")

    (workspace / "fuzz_findings_summary.md").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Spec-fuzz pipeline: run across multiple source files"
    )
    parser.add_argument("--workspace", type=str, default="workspace_fuzz",
                        help="Workspace directory")
    parser.add_argument("--source-dir", type=str, default=None,
                        help="Directory to glob for .rs files (fallback if no exec_functions.json)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Task-level parallelism (default: 4)")
    parser.add_argument("--model", type=str, default="claude-opus-4.6")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--jobs", type=int, default=None,
                        help="Verus worker pool size per task (default: cpu_count//2)")
    parser.add_argument("--verus-timeout", type=int, default=60)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    source_dir = Path(args.source_dir).resolve() if args.source_dir else None
    sources = _discover_sources(workspace, source_dir)
    sources = sources[args.offset:]
    if args.limit:
        sources = sources[:args.limit]

    if not sources:
        print("No source files found. Provide --source-dir or a workspace with exec_functions.json")
        sys.exit(1)

    # Skip already-complete tasks
    todo = []
    for p in sources:
        task_name = p.stem
        task_result = workspace / "pipeline_fuzz" / task_name / "task_result.json"
        if task_result.exists():
            print(f"  [skip] {task_name} (already done)")
            continue
        todo.append(p)

    print(f"Spec-fuzz pipeline: {len(todo)} tasks to run "
          f"({len(sources) - len(todo)} already done)")
    print(f"  Workers={args.workers}  Model={args.model}  Workspace={workspace}")

    results: list[dict] = []
    start = time.time()

    if args.workers <= 1:
        for i, src in enumerate(todo):
            print(f"\n[{i+1}/{len(todo)}] {src.name}")
            try:
                r = run_task(src, workspace, args.model, args.jobs, args.verus_timeout)
                results.append(r)
                print(f"  → {r.get('status')}  findings={r.get('findings', 0)}")
            except Exception as e:
                print(f"  → ERROR: {e}")
                results.append({"task": src.stem, "status": "error", "error": str(e)})
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    _worker,
                    str(src), str(workspace),
                    args.model, args.jobs, args.verus_timeout
                ): src
                for src in todo
            }
            done_count = 0
            for future in as_completed(futures):
                done_count += 1
                src = futures[future]
                try:
                    r = future.result()
                    results.append(r)
                    print(f"[{done_count}/{len(todo)}] {src.name} → "
                          f"{r.get('status')}  findings={r.get('findings', 0)}")
                except Exception as e:
                    print(f"[{done_count}/{len(todo)}] {src.name} → ERROR: {e}")
                    results.append({"task": src.stem, "status": "error", "error": str(e)})

    elapsed = time.time() - start
    _write_summary_md(workspace, results, elapsed)

    total_findings = sum(r.get("findings", 0) for r in results)
    print(f"\n{'='*60}")
    print(f"Spec-fuzz complete in {elapsed:.0f}s")
    print(f"  Tasks: {len(results)} run")
    print(f"  Total findings: {total_findings}")
    print(f"  Summary: {workspace / 'fuzz_findings_summary.md'}")
    print(f"{'='*60}")

    # Save machine-readable summary
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": args.model,
        "tasks_run": len(results),
        "total_findings": total_findings,
        "total_incorrectness": sum(r.get("incorrectness", 0) for r in results),
        "total_incompleteness": sum(r.get("incompleteness", 0) for r in results),
        "elapsed_seconds": elapsed,
        "results": results,
    }
    (workspace / "fuzz_pipeline_summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
