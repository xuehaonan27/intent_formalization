"""Replay ok_with_witness atmosphere targets to capture R0 z3 status."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path("/home/xuehaonan/intent_formalization")
sys.path.insert(0, str(ROOT / "spec-determinism"))

from spec_determinism.extract.types import DetCheckSpec
from spec_determinism.schema_search.schemas import enumerate_schemas
from spec_determinism.schema_search.search import build_schema_ctx
import z3

VERUS = Path.home() / "nanvix/toolchain/verus" / "verus"
# Project + paths configurable via CLI args; see main()
DEFAULT_PROJECT = "atmosphere"
DEFAULT_FULL_RUN = "/tmp/atmosphere-after/full_run.json"


def replay_one(art_dir: Path) -> dict:
    art_key = art_dir.name
    inj = art_dir / "injected.rs"
    spec = art_dir / "det_spec.json"
    if not inj.exists() or not spec.exists():
        return {"artifact_key": art_key, "status": "missing_inputs"}

    det_spec = DetCheckSpec.from_dict(json.loads(spec.read_text()))
    fn_name = det_spec.check_fn_name

    tmp = Path(tempfile.mkdtemp(prefix=f"replay_{art_key[:30]}_"))
    try:
        rs_path = tmp / "injected.rs"
        shutil.copy(inj, rs_path)
        log_dir = tmp / "verus_log"
        log_dir.mkdir()
        t0 = time.monotonic()
        proc = subprocess.run(
            [str(VERUS), str(rs_path), "--log-all", "--log-dir", str(log_dir)],
            capture_output=True, text=True, timeout=120,
        )
        verus_ms = int((time.monotonic() - t0) * 1000)

        smt2s = list(log_dir.rglob("*.smt2"))
        smt2s.sort(key=lambda p: (p.name == "root.smt2", p.stat().st_size))
        if not smt2s:
            return {"artifact_key": art_key, "status": "no_smt2",
                    "stderr": proc.stderr[-500:]}
        smt2 = smt2s[-1]

        schemas = enumerate_schemas(det_spec)
        crate = rs_path.stem
        try:
            ctx = build_schema_ctx(smt2, fn_name, schemas, crate)
        except Exception as e:
            return {"artifact_key": art_key, "status": "ctx_err",
                    "error": f"{type(e).__name__}: {e}"}

        t1 = time.monotonic()
        r0 = ctx.solver.check()
        r0_ms = int((time.monotonic() - t1) * 1000)
        return {
            "artifact_key": art_key,
            "status": "ok",
            "r0_z3": str(r0),
            "verus_ms": verus_ms,
            "r0_ms": r0_ms,
            "smt2_bytes": smt2.stat().st_size,
            "n_schemas": len(schemas),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=DEFAULT_PROJECT)
    ap.add_argument("--full-run", default=DEFAULT_FULL_RUN)
    ap.add_argument("--out", default=None)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--stop", type=int, default=-1)
    args = ap.parse_args()

    art_root = ROOT / f"spec-determinism/results-verusage/{args.project}/artifacts"
    full = json.loads(Path(args.full_run).read_text())
    ow = [t for t in full if t.get("status") == "ok" and t.get("assumes")]
    print(f"# {args.project}: total ok_with_witness: {len(ow)}", file=sys.stderr)

    stop = args.stop if args.stop >= 0 else len(ow)
    out_path = Path(args.out) if args.out else \
        Path(f"/tmp/{args.project}-after/replay_{args.start}_{stop}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for i, t in enumerate(ow[args.start:stop]):
        art_dir = art_root / t["artifact_key"]
        r = replay_one(art_dir)
        results.append(r)
        z = r.get("r0_z3", r.get("status"))
        print(f"[{args.start+i+1}/{stop}] {t['artifact_key'][-60:]:<60s} r0={z} "
              f"verus_ms={r.get('verus_ms','-')} r0_ms={r.get('r0_ms','-')}",
              file=sys.stderr, flush=True)

    out_path.write_text(json.dumps(results, indent=2))
    print(f"# written → {out_path}", file=sys.stderr)

    # Summary
    bk = {}
    for r in results:
        z = r.get("r0_z3", r.get("status"))
        bk[z] = bk.get(z, 0) + 1
    print("\n# === SUMMARY ===", file=sys.stderr)
    for z, n in sorted(bk.items(), key=lambda x: -x[1]):
        print(f"#   {z:15s}  {n:4d}  ({100*n/max(len(results),1):.1f}%)", file=sys.stderr)


if __name__ == "__main__":
    main()
