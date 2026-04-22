#!/usr/bin/env python3
"""A/B compare binary_search() with VerusRunner vs Z3Backend on bitmap."""

import logging, os, sys, time, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.types import *
from src.extract import extract_spec
from src.gen_det import build_det_check_spec
from src.equal_policy import EqualPolicy
from src.verify import VerusRunner
from src.z3_backend import Z3Backend
from src.binary_search import binary_search

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

NANVIX = os.path.expanduser("~/nanvix")
VERUS_PATH = os.path.join(NANVIX, "toolchain/verus")
SRC   = os.path.join(NANVIX, "src/libs/bitmap/src/lib.rs")
SPEC  = os.path.join(NANVIX, "src/libs/bitmap/src/lib.spec.rs")
PROOF = os.path.join(NANVIX, "src/libs/bitmap/src/lib.proof.rs")
ERR   = os.path.join(NANVIX, "src/libs/error/src/lib.rs")

FNS = ["number_of_bits", "new", "from_raw_array",
       "alloc", "alloc_range", "set", "clear", "test"]

CHECK_OVERRIDES = {"alloc_range": "det_alloc_range_chk"}

def make_backend(kind):
    if kind == "verus":
        return VerusRunner(
            crate_dir=NANVIX, crate_name="bitmap",
            proof_file=PROOF, verus_path=VERUS_PATH,
            features=["std"], timeout=120, use_build=True,
        )
    return Z3Backend(
        crate_dir=NANVIX, crate_name="bitmap",
        verus_path=VERUS_PATH, proof_file=PROOF,
        features=["std"], timeout=120,
    )

def run(fn, backend_kind, src, spec_src, err_src):
    s = extract_spec(src, fn, type_sources=[spec_src, err_src])
    check_name = CHECK_OVERRIDES.get(fn)
    det = build_det_check_spec(
        s, check_name=check_name,
        equal_policy=EqualPolicy(errs_equivalent=True))
    b = make_backend(backend_kind)
    t0 = time.time()
    try:
        w = binary_search(det, b)
        elapsed = time.time() - t0
        calls = getattr(b, "call_count", None)
        if calls is None and hasattr(b, "_call_count"):
            calls = b._call_count
        status = "det" if not (w.inputs or w.output1 or w.output2 or w.assumes) else "nondet"
        return {
            "fn": fn, "backend": backend_kind,
            "elapsed": round(elapsed, 1),
            "rounds": len(w.trace),
            "calls": calls,
            "status": status,
            "gap": w.gap_description or "",
            "inputs": {k: v.raw for k, v in w.inputs.items()},
            "output1": {k: v.raw for k, v in w.output1.items()},
            "output2": {k: v.raw for k, v in w.output2.items()},
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {"fn": fn, "backend": backend_kind, "elapsed": round(elapsed, 1),
                "error": str(e)[:200]}


def main():
    with open(SRC) as f: src = f.read()
    with open(SPEC) as f: spec_src = f.read()
    with open(ERR) as f: err_src = f.read()

    only = sys.argv[1:] or FNS
    results = []
    for fn in only:
        for kind in ("z3", "verus"):
            print(f">>> {fn:18s} [{kind}]", flush=True)
            r = run(fn, kind, src, spec_src, err_src)
            results.append(r)
            print(f"    elapsed={r.get('elapsed')}s  rounds={r.get('rounds')}  "
                  f"status={r.get('status')}  err={r.get('error','')}")
    with open("results/ab_z3_vs_verus.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== Summary ===")
    print(f"{'fn':18s} {'z3 s':>8s} {'z3 R':>5s} {'verus s':>9s} {'verus R':>8s} speedup")
    for fn in only:
        z = next((r for r in results if r["fn"] == fn and r["backend"] == "z3"), None)
        v = next((r for r in results if r["fn"] == fn and r["backend"] == "verus"), None)
        ze = z.get("elapsed", "-") if z else "-"
        zr = z.get("rounds", "-") if z else "-"
        ve = v.get("elapsed", "-") if v else "-"
        vr = v.get("rounds", "-") if v else "-"
        sp = f"{v['elapsed']/z['elapsed']:.1f}x" if (z and v and z.get('elapsed',0)>0 and v.get('elapsed',0)>0) else "-"
        print(f"{fn:18s} {str(ze):>8s} {str(zr):>5s} {str(ve):>9s} {str(vr):>8s}  {sp}")


if __name__ == "__main__":
    main()
