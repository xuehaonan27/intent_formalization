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

from spec_determinism.classify import (
    BUCKET_INCONCLUSIVE,
    BUCKET_PROVED,
    BUCKET_PROVED_LLM,
    BUCKET_UNKNOWN_KIND,
    BUCKET_WITNESS,
    OK_BUCKETS,
    classify_ok,
)
from spec_determinism.extract.extractor import extract_spec
from spec_determinism.verus.single_file import (
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
    ap.add_argument("--use-view-registry", action="store_true",
                    help="Phase-2: build a per-project L1+L2+L3+L4 "
                         "ViewRegistry (prelude / alias / impl-View / "
                         "LLM cache) and consult it from "
                         "gen_det.build_equal_expr. No LLM is called at "
                         "run time — L4 only reads the pre-populated cache "
                         "(see `view.llm prefill`). Uncovered types still "
                         "fall through to structural ==.")
    ap.add_argument("--view-cache-dir", type=Path, default=None,
                    help="Path to an L4 view cache (overrides the canonical "
                         "results-verusage/view_registry/<project>/ "
                         "location). Pass an empty/nonexistent path to "
                         "explicitly disable L4.")
    ap.add_argument("--use-llm-proof", action="store_true",
                    help="Escalate to LLM proof loop when the baseline z3 "
                         "check returns `unknown`. Requires the `copilot` "
                         "CLI on PATH. Disabled by default; can also be "
                         "toggled via the env var SPEC_DET_LLM_PROOF=1.")
    ap.add_argument("--llm-proof-max-attempts", type=int, default=3,
                    help="Maximum LLM iterations per target before giving "
                         "up and reporting ok_inconclusive (default: 3).")
    ap.add_argument("--llm-proof-model", default=None,
                    help="Copilot CLI --model passthrough.")
    ap.add_argument("--llm-proof-effort", default=None,
                    help="Copilot CLI --effort passthrough (e.g. low/medium/high).")
    ap.add_argument("--llm-proof-cache-dir", type=Path, default=None,
                    help="Directory to persist LLM-authored proof blocks "
                         "across runs. On hit the loop re-verifies the "
                         "cached proof against current Verus and skips the "
                         "LLM. Default: <results-root>/llm_proof_cache/<proj>/ "
                         "computed from --out.")
    ap.add_argument("--llm-proof-cache-mode", default="use",
                    choices=["use", "refresh", "bypass"],
                    help="`use` (default): read+write; `refresh`: ignore "
                         "prior hits and overwrite; `bypass`: don't touch "
                         "the cache.")
    ap.add_argument("--llm-proof-timeout", type=int, default=None,
                    help="Per-LLM-invocation timeout in seconds (default: "
                         "max(--timeout, 600)). Separate from Verus timeout.")
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

    view_registry = None
    if args.use_view_registry:
        from spec_determinism.view.registry import ViewRegistry
        from spec_determinism.view.llm import ViewCache
        proj_root = roots / args.project
        log.info("Building ViewRegistry from %s ...", proj_root)
        t_reg = time.monotonic()
        # PR-D2: attach the L4 LLM cache if one exists on disk.  We
        # look under the same default path that ``view.llm prefill``
        # writes to.  Absence is fine — registry falls back to
        # L1+L2+L3 only.
        cache_root = (out_root.parent / "view_registry" / args.project
                      if out_root.name != "view_registry"
                      else out_root / args.project)
        # Default canonical location matches the prefill CLI:
        #   <repo_root>/results-verusage/view_registry/<project>/
        # The repo root is the package's grandparent — `parents[2]` from
        # this file is `spec-determinism/` (the repo root); using
        # `parent.parent` would give `spec_determinism/` (the *package*
        # directory) and silently miss the real cache (ISSUES #11).
        canonical = (Path(__file__).resolve().parents[2]
                     / "results-verusage" / "view_registry"
                     / args.project)
        llm_cache = None
        if args.view_cache_dir is not None:
            llm_cache = ViewCache(args.view_cache_dir)
        elif canonical.exists():
            llm_cache = ViewCache(canonical)
        elif cache_root.exists():
            llm_cache = ViewCache(cache_root)
        if llm_cache is not None:
            log.info("Attaching L4 view cache from %s", llm_cache.root)
        else:
            # User asked for the registry but no L4 cache is reachable.
            # Be explicit so reproductions don't silently degrade to
            # L1+L2+L3 only (ISSUES #11).
            log.warning(
                "--use-view-registry set but no L4 cache attached "
                "(checked --view-cache-dir, canonical=%s, fallback=%s); "
                "proceeding with L1+L2+L3 only.",
                canonical, cache_root,
            )
        view_registry = ViewRegistry.from_project(proj_root,
                                                  llm_cache=llm_cache)
        log.info("ViewRegistry: %d types, %d view impls, %d L4 cache "
                 "entries, built in %.2fs",
                 len(view_registry.types_by_short),
                 sum(len(v) for v in view_registry.scan.views.values()),
                 (len(llm_cache.all_entries()) if llm_cache else 0),
                 time.monotonic() - t_reg)

    # Resolve LLM proof cache dir. Default: <out_root>/llm_proof_cache/
    # (note: out_root already includes the project subdir in the rerun
    # script's invocation, so this is per-project automatically).
    llm_proof_cache_dir = None
    if args.use_llm_proof:
        if args.llm_proof_cache_dir is not None:
            llm_proof_cache_dir = args.llm_proof_cache_dir.expanduser().resolve()
        else:
            # Co-locate cache with results so the same `--out` tree owns
            # everything for a given experiment.
            llm_proof_cache_dir = out_root / "llm_proof_cache"
        llm_proof_cache_dir.mkdir(parents=True, exist_ok=True)
        log.info("LLM-proof cache: %s (mode=%s)",
                 llm_proof_cache_dir, args.llm_proof_cache_mode)

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
                view_registry=view_registry,
                use_llm_proof=args.use_llm_proof,
                llm_proof_max_attempts=args.llm_proof_max_attempts,
                llm_proof_model=args.llm_proof_model,
                llm_proof_effort=args.llm_proof_effort,
                llm_proof_cache_dir=llm_proof_cache_dir,
                llm_proof_cache_mode=args.llm_proof_cache_mode,
                llm_proof_timeout=args.llm_proof_timeout,
                artifact_key=key,
            )
        except Exception as e:
            r = {"file": str(file_path), "function": fn,
                 "status": "runner_crash",
                 "error": f"{type(e).__name__}: {e}"}
        r["artifact_key"] = key
        results.append(r)
        log.info(
            "  → %s  rounds=%s  assumes=%s  llm=%s",
            r.get("status"), r.get("n_rounds"), len(r.get("assumes", [])),
            "yes" if r.get("llm_assisted") else
            (str(r.get("llm_proof_attempts")) if r.get("llm_proof_attempts") else "-"),
        )

    full = out_root / "full_run.json"
    full.write_text(json.dumps(results, indent=2, default=str))

    # Summary
    total_ms = int((time.monotonic() - t0) * 1000)
    by_status: dict[str, int] = {}
    ok_buckets: dict[str, int] = {b: 0 for b in OK_BUCKETS}
    for r in results:
        s = r.get("status", "?")
        by_status[s] = by_status.get(s, 0) + 1
        if s == "ok":
            ok_buckets[classify_ok(r)] += 1

    print("\n" + "=" * 80)
    print(f"verusage run: project={args.project}  subdir={args.subdir}  "
          f"n={len(results)}  wall={total_ms/1000:.1f}s")
    print(f"by status: {by_status}")
    print(f"  {BUCKET_PROVED:18s}: {ok_buckets[BUCKET_PROVED]:4d}  (R0=unsat, deterministic)")
    if ok_buckets[BUCKET_PROVED_LLM]:
        print(f"  {BUCKET_PROVED_LLM:18s}: {ok_buckets[BUCKET_PROVED_LLM]:4d}  (R0=unknown → LLM proof closed it)")
    print(f"  {BUCKET_WITNESS:18s}: {ok_buckets[BUCKET_WITNESS]:4d}  (R0=sat, real nondeterminism witness)")
    print(f"  {BUCKET_INCONCLUSIVE:18s}: {ok_buckets[BUCKET_INCONCLUSIVE]:4d}  (R0=unknown / legacy, z3 undecided)")
    if ok_buckets[BUCKET_UNKNOWN_KIND]:
        print(f"  {BUCKET_UNKNOWN_KIND:18s}: {ok_buckets[BUCKET_UNKNOWN_KIND]:4d}  (unexpected r0_z3 value)")
    print(f"full → {full}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
