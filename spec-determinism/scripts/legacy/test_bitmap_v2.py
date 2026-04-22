#!/usr/bin/env python3
"""
Test: run spec-determinism on bitmap::alloc using the new pipeline.
Step 1: extract + gen_det → DetCheckSpec (JSON)
Step 2: binary_search with DetCheckSpec
"""

import sys, os, json, logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.types import *
from src.extract import extract_spec
from src.gen_det import build_det_check_spec, render_template
from src.verify import VerusRunner
from src.binary_search import binary_search

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

NANVIX = os.path.expanduser("~/nanvix")
BITMAP_SRC = os.path.join(NANVIX, "src/libs/bitmap/src/lib.rs")
BITMAP_SPEC = os.path.join(NANVIX, "src/libs/bitmap/src/lib.spec.rs")
BITMAP_PROOF = os.path.join(NANVIX, "src/libs/bitmap/src/lib.proof.rs")
VERUS_PATH = os.path.join(NANVIX, "toolchain/verus")

# Read sources
with open(BITMAP_SRC) as f:
    src = f.read()
with open(BITMAP_SPEC) as f:
    spec_src = f.read()

runner = VerusRunner(
    crate_dir=NANVIX,
    crate_name="bitmap",
    proof_file=BITMAP_PROOF,
    verus_path=VERUS_PATH,
    features=["std"],
    timeout=120,
)

# Functions to test
functions = ["number_of_bits", "alloc", "test", "new", "set", "clear"]

for fn_name in functions:
    print(f"\n{'='*60}")
    print(f"Function: {fn_name}")
    print(f"{'='*60}")

    # Step 1: Extract + Gen
    try:
        spec = extract_spec(src, fn_name, type_sources=[spec_src])
    except Exception as e:
        print(f"  ⚠️ Extract failed: {e}")
        continue

    det_spec = build_det_check_spec(spec)

    # Show symbols
    print(f"  Symbols ({len(det_spec.symbols)}):")
    for sym in det_spec.symbols:
        print(f"    [{sym.phase}] {sym.name}: {sym.type.kind.value}")

    # Save DetCheckSpec
    os.makedirs("results", exist_ok=True)
    with open(f"results/{fn_name}_spec.json", "w") as f:
        f.write(det_spec.to_json())
    print(f"  Saved: results/{fn_name}_spec.json")

    # Step 2: Binary search
    witness = binary_search(det_spec, runner)

    # Results
    print(f"\n  Trace ({len(witness.trace)} rounds):")
    for step in witness.trace:
        r = step["round"]
        status = "❌ FAIL" if step["result"] == "fail" else "✅ PASS"
        assume = step.get("new_assume", "—") or "—"
        print(f"    R{r}: {status}  {assume}")

    if witness.assumes:
        print(f"\n  Final assumes ({len(witness.assumes)}):")
        for a in witness.assumes:
            print(f"    {a.expression}")
    else:
        print(f"\n  ✅ Spec is deterministic")
