#!/usr/bin/env python3
"""Run schema-driven determinism search on all bitmap/slab/kheap exec functions, compare against old pipeline."""
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from src.types import DetCheckSpec
from src.verify import inject_proof_fn, restore_file, run_cargo_verus
from src.schema_search import enumerate_schemas, render_guarded_template, run_schema_search
from src.schema_search.search import build_schema_ctx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("a_runner")

NANVIX = os.path.expanduser("~/nanvix")
VERUS_PATH = os.path.join(NANVIX, "toolchain/verus")
ROOT = Path(__file__).parent


def _nanvix(p): return os.path.join(NANVIX, p)


CRATES = {
    "bitmap": {
        "proof": _nanvix("src/libs/bitmap/src/lib.proof.rs"),
        "features": ["std"], "extra_args": [], "use_build": True, "timeout": 180,
        "functions": ["number_of_bits", "new", "from_raw_array",
                      "alloc", "alloc_range", "set", "clear", "test"],
        "check_overrides": {"alloc_range": "det_alloc_range_chk"},
    },
    "slab": {
        "proof": _nanvix("src/libs/slab/src/lib.proof.rs"),
        "features": ["std"], "extra_args": [], "use_build": True, "timeout": 180,
        "functions": ["from_raw_parts", "allocate", "deallocate"],
        "check_overrides": {"allocate": "det_allocate_chk"},
    },
    "kernel": {
        "proof": _nanvix("src/kernel/src/mm/kheap.proof.rs"),
        "features": ["microvm", "error"],
        "extra_args": ["-Z", "build-std=core,alloc,compiler_builtins",
                       "-Z", "build-std-features=compiler-builtins-mem",
                       "--target", _nanvix("build/targets/x86-kernel.json")],
        "use_build": False, "timeout": 600,
        "functions": ["from_raw_parts", "allocate", "deallocate", "layout_to_allocator"],
        "check_overrides": {},
        "verify_module": "mm::kheap",
    },
}


def artifact_key(crate, fn):
    return f"{crate}__{fn}"


def run_one(crate: str, fn: str) -> dict:
    cfg = CRATES[crate]
    fn_name = cfg["check_overrides"].get(fn, f"det_{fn}")
    art = ROOT / "results" / "artifacts" / artifact_key(crate, fn) / "det_spec.json"

    result = {"crate": crate, "function": fn, "det_fn": fn_name}
    if not art.exists():
        result.update({"status": "no_artifact"}); return result

    det_spec = DetCheckSpec.from_dict(json.loads(art.read_text()))
    t0 = time.monotonic()

    schemas = enumerate_schemas(det_spec)
    code = det_spec.equal_fn_def + "\n\n" + render_guarded_template(det_spec, schemas)
    result["n_schemas"] = len(schemas)
    result["n_params"] = sum(1 + len(s.k_params) for s in schemas)

    log_dir = Path(tempfile.mkdtemp(prefix=f"aprime_{crate}_{fn}_"))
    original = inject_proof_fn(cfg["proof"], code)
    try:
        t_v = time.monotonic()
        raw = run_cargo_verus(
            NANVIX, crate, VERUS_PATH,
            features=cfg["features"], timeout=cfg["timeout"],
            verify_function=fn_name, use_build=cfg["use_build"],
            verify_module=cfg.get("verify_module"),
            extra_args=cfg.get("extra_args", []),
            verus_extra_args=["--log-all", "--log-dir", str(log_dir)],
        )
        result["verus_ms"] = int((time.monotonic() - t_v) * 1000)
        if raw["returncode"] != 0:
            stderr = raw["stderr"]
            if "postcondition not satisfied" not in stderr and \
               "assertion failed" not in stderr.lower() and \
               "error:" in stderr:
                result["status"] = "verus_error"
                result["stderr_tail"] = stderr[-2000:]
                return result
    except Exception as e:
        result["status"] = "exception"
        result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
        return result
    finally:
        restore_file(cfg["proof"], original)

    smt2_candidates = list(log_dir.rglob("*.smt2"))
    # Prefer the module-specific one (e.g. mm__kheap.smt2) if present
    smt2_candidates.sort(key=lambda p: (p.name == "root.smt2", p.stat().st_size))
    if not smt2_candidates:
        result["status"] = "no_smt2"; return result
    smt2 = smt2_candidates[-1]  # largest / most specific
    result["smt2_bytes"] = smt2.stat().st_size

    try:
        t_c = time.monotonic()
        schema_ctx = build_schema_ctx(smt2, fn_name, schemas, crate)
        result["ctx_ms"] = int((time.monotonic() - t_c) * 1000)

        t_s = time.monotonic()
        witness = run_schema_search(det_spec, schema_ctx)
        result["search_ms"] = int((time.monotonic() - t_s) * 1000)
        result["n_rounds"] = len(witness.trace) if witness.trace else 0
        result["assumes"] = [a.expression for a in (witness.assumes or [])]
        result["status"] = "ok"
    except Exception as e:
        result["status"] = "search_error"
        result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
    finally:
        shutil.rmtree(log_dir, ignore_errors=True)

    result["total_ms"] = int((time.monotonic() - t0) * 1000)
    return result


def main():
    targets: list[tuple[str, str]] = []
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for crate, cfg in CRATES.items():
        for fn in cfg["functions"]:
            if only and f"{crate}::{fn}" not in only:
                continue
            targets.append((crate, fn))

    results = []
    for crate, fn in targets:
        log.info(f"\n{'='*70}\n=== {crate}::{fn} ===\n{'='*70}")
        try:
            r = run_one(crate, fn)
        except Exception as e:
            r = {"crate": crate, "function": fn, "status": "runner_crash",
                 "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        log.info(f"RESULT: {json.dumps(r, default=str)[:500]}")

    out = ROOT / "results" / "full_run.json"
    out.write_text(json.dumps(results, indent=2, default=str))

    print("\n\n" + "=" * 80)
    print(f"{'fn':<35} {'status':<14} {'verus':>7} {'ctx':>6} {'search':>7} {'rounds':>6} {'schemas':>8}")
    print("=" * 80)
    for r in results:
        name = f"{r['crate']}::{r['function']}"
        status = r.get("status", "?")
        v = r.get("verus_ms", "-")
        c = r.get("ctx_ms", "-")
        s = r.get("search_ms", "-")
        n = r.get("n_rounds", "-")
        sc = r.get("n_schemas", "-")
        print(f"{name:<35} {status:<14} {str(v):>7} {str(c):>6} {str(s):>7} {str(n):>6} {str(sc):>8}")
    print(f"\nFull results → {out}")


if __name__ == "__main__":
    sys.exit(main() or 0)
