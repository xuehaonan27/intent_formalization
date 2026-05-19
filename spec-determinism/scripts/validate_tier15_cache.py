#!/usr/bin/env python3
"""Standalone Tier 1.5 cache re-baseline validator.

Bug B (the gen_det compile probe) is no longer in the main funnel — it added
~0 steady-state value because cached entries skip the probe and "wins"
attributed to it were indistinguishable from LLM variance. The probe still
matters at *re-baseline* time: when capturing a new pinned cache snapshot
(``verusage/cache_snapshots/<project>/``), stale or shape-mismatched entries
must be caught before they're committed.

This script runs the probe across an entire corpus against a candidate cache,
WITHOUT modifying the main funnel. It reports every target whose gen_det
output fails ``verus --no-verify`` and, for each failure, the inferred
shape-mismatch gaps so a human can decide whether to (a) invalidate the
offending cache entry, (b) hand-edit it, or (c) re-prompt the LLM with
``--repair`` (TODO; not yet implemented — currently the script only
detects, it does not auto-fix).

Usage::

    python -m scripts.validate_tier15_cache \\
        --project ironkv \\
        --roots ~/intent_formalization/verusage/source-projects \\
        --cache-dir ~/intent_formalization/verusage/cache_snapshots/ironkv \\
        --out /tmp/tier15_validate_ironkv.json

The script never calls the LLM and never writes to the cache directory.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Make spec-determinism importable when run as ``python scripts/...``
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from spec_determinism.corpus.verusage_run import _discover_targets  # noqa: E402
from spec_determinism.extract.extractor import extract_spec  # noqa: E402
from spec_determinism.llm_type.apply import apply_patches  # noqa: E402
from spec_determinism.llm_type.cache import TypeCompletionCache  # noqa: E402
from spec_determinism.llm_type.gaps import (  # noqa: E402
    REASON_SHAPE_MISMATCH,
    gaps_from_compile_stderr,
)
from spec_determinism.llm_type.probe import probe_gen_det_compile  # noqa: E402

log = logging.getLogger("validate_tier15_cache")


def _apply_cache_to_spec(spec, cache: TypeCompletionCache) -> dict[str, str]:
    """Pre-apply every cache entry referenced by ``spec`` into ``spec.type_defs``.

    Returns a per-name map ``{type_name: "live"|"pinned"|"miss"}`` so the
    report can attribute failures to the layer they came from.

    The probe doesn't run Tier 1.5 — it just exercises the cache as it
    would be served on a normal verusage_run. Misses are left alone
    (the gap detector will report them separately).
    """
    sources: dict[str, str] = {}

    def _names_in(ti) -> list[str]:
        out = [ti.name]
        for arg in getattr(ti, "type_args", []) or []:
            out.extend(_names_in(arg))
        return out

    candidates: set[str] = set()
    for p in spec.params:
        candidates.update(_names_in(p.type))
    if spec.return_type is not None:
        candidates.update(_names_in(spec.return_type))
    for ti in (spec.type_defs or {}).values():
        for f in getattr(ti, "fields", []) or []:
            candidates.update(_names_in(f.type))
        for v in getattr(ti, "variants", []) or []:
            for it in getattr(v, "inner_types", []) or []:
                candidates.update(_names_in(it))

    seen: set[str] = set()
    while candidates:
        name = candidates.pop()
        if name in seen:
            continue
        seen.add(name)
        entry, source = cache.get_with_source(name)
        sources[name] = source
        if entry is None:
            continue
        try:
            apply_patches(spec, [entry.patch])
        except Exception as e:
            log.debug("apply_patches failed for %s: %s", name, e)
            continue
        # Newly-applied type may reference further types; widen the worklist.
        ti = spec.type_defs.get(name)
        if ti is not None:
            for f in getattr(ti, "fields", []) or []:
                candidates.update(n for n in _names_in(f.type) if n not in seen)
            for v in getattr(ti, "variants", []) or []:
                for it in getattr(v, "inner_types", []) or []:
                    candidates.update(n for n in _names_in(it) if n not in seen)
    return sources


def _probe_one_target(
    file_path: Path,
    fn: str,
    artifact_key: str,
    cache: TypeCompletionCache,
    *,
    verus_path: str,
    probe_timeout: int,
    work_root: Path,
) -> dict:
    """Probe a single corpus target. Returns a JSON-friendly result dict."""
    rec: dict = {
        "artifact_key": artifact_key,
        "fn": fn,
        "file": str(file_path),
        "status": "skipped",
        "skip_reason": "",
        "applied_sources": {},
        "probe_returncode": None,
        "probe_skipped": False,
        "probe_skip_reason": "",
        "probe_ms": 0,
        "shape_mismatch_count": 0,
        "shape_mismatch_types": [],
        "stderr_tail": "",
    }

    try:
        source = file_path.read_text(errors="replace")
    except OSError as e:
        rec["skip_reason"] = f"read failed: {e}"
        return rec

    try:
        spec = extract_spec(source, fn, type_sources=[])
    except Exception as e:
        rec["skip_reason"] = f"extract_spec failed: {type(e).__name__}: {e}"
        return rec

    rec["applied_sources"] = _apply_cache_to_spec(spec, cache)

    work_dir = work_root / artifact_key.replace("/", "_").replace("::", "__")
    work_dir.mkdir(parents=True, exist_ok=True)

    result = probe_gen_det_compile(
        spec, source,
        file_stem=f"validate_{fn}",
        verus_path=verus_path,
        timeout=probe_timeout,
        work_dir=work_dir,
    )
    rec["probe_returncode"] = result.returncode
    rec["probe_skipped"] = result.skipped
    rec["probe_skip_reason"] = result.skip_reason
    rec["probe_ms"] = result.duration_ms

    if result.skipped:
        rec["status"] = "skipped"
        return rec

    if result.returncode == 0:
        rec["status"] = "ok"
        return rec

    shape_gaps = gaps_from_compile_stderr(result.stderr, spec)
    rec["shape_mismatch_count"] = len(shape_gaps)
    rec["shape_mismatch_types"] = sorted({g.name for g in shape_gaps})
    rec["stderr_tail"] = "\n".join(result.stderr.splitlines()[-40:])
    rec["status"] = "shape_mismatch" if shape_gaps else "verus_error"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True,
                    help="Project name under <roots>/, e.g. ironkv")
    ap.add_argument("--roots", required=True, type=Path,
                    help="verusage/source-projects root directory")
    ap.add_argument("--subdir", default="src",
                    help="Subdirectory of the project to scan (default: src)")
    ap.add_argument("--cache-dir", required=True, type=Path,
                    help="Candidate cache directory to validate")
    ap.add_argument("--out", required=True, type=Path,
                    help="Write per-target JSON report here")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only probe first N targets (smoke test)")
    ap.add_argument("--filter", default="",
                    help="Only probe targets whose artifact key contains this")
    ap.add_argument("--verus-path", default=str(Path.home() / "nanvix" / "toolchain" / "verus"),
                    help="Path to verus toolchain directory")
    ap.add_argument("--probe-timeout", type=int, default=30,
                    help="Per-target verus --no-verify timeout (seconds)")
    ap.add_argument("--work-dir", type=Path,
                    default=Path("/tmp") / f"validate_tier15_{int(time.time())}",
                    help="Where to drop per-target probe artifacts")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not args.cache_dir.is_dir():
        log.error("cache-dir does not exist: %s", args.cache_dir)
        return 2

    log.info("validating cache=%s against %s/%s",
             args.cache_dir, args.project, args.subdir)
    targets = _discover_targets([args.roots], args.project, args.subdir)
    if args.filter:
        targets = [t for t in targets if args.filter in t[2]]
    if args.limit is not None:
        targets = targets[: args.limit]
    log.info("discovered %d targets", len(targets))

    project_root = args.roots / args.project
    # NB: we pass the cache dir as the *pinned* layer with an unwritable live
    # layer underneath. That way every read hits the snapshot we're
    # validating; writes are impossible (we never call LLM).
    live_only_dir = args.work_dir / "_unused_live_cache"
    live_only_dir.mkdir(parents=True, exist_ok=True)
    cache = TypeCompletionCache(
        str(project_root),
        cache_root=str(live_only_dir),
        pinned_cache_dir=str(args.cache_dir),
    )

    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    counts: dict[str, int] = {
        "ok": 0, "shape_mismatch": 0, "verus_error": 0, "skipped": 0,
    }
    bad_entries: dict[str, int] = {}  # type name -> #targets affected

    for i, (file_path, fn, key) in enumerate(targets, 1):
        log.info("[%d/%d] %s :: %s", i, len(targets), key, fn)
        rec = _probe_one_target(
            file_path, fn, key, cache,
            verus_path=args.verus_path,
            probe_timeout=args.probe_timeout,
            work_root=args.work_dir,
        )
        results.append(rec)
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        for name in rec.get("shape_mismatch_types") or []:
            bad_entries[name] = bad_entries.get(name, 0) + 1

    summary = {
        "project": args.project,
        "cache_dir": str(args.cache_dir),
        "n_targets": len(targets),
        "counts": counts,
        "offending_cache_entries": dict(
            sorted(bad_entries.items(), key=lambda kv: -kv[1])
        ),
    }
    payload = {"summary": summary, "results": results}
    args.out.write_text(json.dumps(payload, indent=2))
    log.info("wrote %s", args.out)
    log.info("counts=%s", counts)
    if bad_entries:
        log.warning("OFFENDING CACHE ENTRIES (type -> #targets):")
        for name, n in summary["offending_cache_entries"].items():
            log.warning("  %s  %d", name, n)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
