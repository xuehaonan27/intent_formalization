"""Batch runner for single-file Verus corpora (verusage-style).

Walks a directory tree, discovers ``.rs`` files with exec fn + ensures,
and runs the single-file determinism pipeline on each target function.

Usage:
    spec-determinism-verusage --project vest --roots ~/.../verusage/source-projects \\
        --out results-verusage

Writes:
    <out>/full_run.json                            — aggregated results list
    <out>/artifacts/<proj>__<relpath>__<fn>/       — per-target artifacts
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

from .extract import extract_spec
from .single_file import (
    _DEFAULT_VERUS,
    discover_exec_fns,
    run_single_file,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("spec_determinism.verusage")


_ENSURES_RE = re.compile(r"\bensures\b")


def _has_ensures(source: str) -> bool:
    return bool(_ENSURES_RE.search(source))


def _artifact_key(project: str, rel_path: Path, fn: str) -> str:
    flat = str(rel_path).replace("/", "__").replace(".rs", "")
    return f"{project}__{flat}__{fn}"


def _discover_targets(
    roots: list[Path],
    project: str,
    subdir: str,
) -> list[tuple[Path, str, str]]:
    """Return (file_path, fn_name, artifact_key) tuples for every exec fn
    with ensures found under ``<root>/<project>/<subdir>``.
    """
    out: list[tuple[Path, str, str]] = []
    for root in roots:
        base = root / project / subdir
        if not base.exists():
            log.warning("missing: %s", base)
            continue
        for rs in sorted(base.rglob("*.rs")):
            src = rs.read_text(errors="replace")
            if not _has_ensures(src):
                continue
            fn_names = discover_exec_fns(src)
            if not fn_names:
                continue
            rel = rs.relative_to(root / project)
            for fn in fn_names:
                # Filter at extract time: only keep fns that actually
                # carry ensures in their signature/attribute. This is
                # cheap (no subprocess), but still catches the case
                # where a file has both a proof fn with ensures and an
                # exec fn without.
                try:
                    spec = extract_spec(src, fn, type_sources=[])
                except Exception as e:
                    log.debug("extract skip %s::%s: %s", rs.name, fn, e)
                    continue
                if not spec.ensures:
                    continue
                out.append((rs, fn, _artifact_key(project, rel, fn)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True,
                    help="Project name under --roots (e.g. vest, storage)")
    ap.add_argument("--roots", type=Path, required=True,
                    help="Directory containing projects (e.g. "
                         "~/intent_formalization/verusage/source-projects)")
    ap.add_argument("--subdir", default="verified",
                    help="Subdirectory to walk (default: verified)")
    ap.add_argument("--out", type=Path, default=Path("results-verusage"),
                    help="Output root (default: results-verusage)")
    ap.add_argument("--verus-path", default=_DEFAULT_VERUS,
                    help=f"Path to verus dir (default: {_DEFAULT_VERUS})")
    ap.add_argument("--timeout", type=int, default=120,
                    help="Per-target Verus timeout (s, default: 120)")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only run first N targets (for smoke testing)")
    ap.add_argument("--filter", default=None,
                    help="Only run targets whose artifact key matches this "
                         "substring")
    ap.add_argument("--keep-tmp", action="store_true",
                    help="Preserve the injected .rs / verus_log tmpdirs per "
                         "target (debug).")
    args = ap.parse_args()

    roots = args.roots.expanduser().resolve()
    out_root = args.out.expanduser().resolve()
    artifacts_dir = out_root / "artifacts"
    out_root.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    targets = _discover_targets([roots], args.project, args.subdir)
    if args.filter:
        targets = [t for t in targets if args.filter in t[2]]
    if args.limit:
        targets = targets[: args.limit]

    log.info("Discovered %d target(s) under %s/%s/%s",
             len(targets), roots, args.project, args.subdir)

    results: list[dict] = []
    t0 = time.monotonic()
    for i, (file_path, fn, key) in enumerate(targets, 1):
        log.info("[%d/%d] %s :: %s", i, len(targets), key, fn)
        art_dir = artifacts_dir / key
        try:
            r = run_single_file(
                file_path, fn,
                verus_path=args.verus_path,
                timeout=args.timeout,
                artifact_dir=art_dir,
                keep_tmp=args.keep_tmp,
            )
        except Exception as e:
            r = {"file": str(file_path), "function": fn,
                 "status": "runner_crash",
                 "error": f"{type(e).__name__}: {e}"}
        r["artifact_key"] = key
        results.append(r)
        log.info("  → %s  rounds=%s  assumes=%s",
                 r.get("status"), r.get("n_rounds"), len(r.get("assumes", [])))

    full = out_root / "full_run.json"
    full.write_text(json.dumps(results, indent=2, default=str))

    # Summary
    total_ms = int((time.monotonic() - t0) * 1000)
    by_status: dict[str, int] = {}
    with_witness = 0
    for r in results:
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
        if r.get("status") == "ok" and r.get("assumes"):
            with_witness += 1

    print("\n" + "=" * 80)
    print(f"verusage run: project={args.project}  subdir={args.subdir}  "
          f"n={len(results)}  wall={total_ms/1000:.1f}s")
    print(f"by status: {by_status}")
    print(f"ok-with-witness: {with_witness}")
    print(f"full → {full}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
