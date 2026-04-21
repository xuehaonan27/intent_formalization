#!/usr/bin/env python3
"""
Prototype driver: Z3Backend on bitmap::new only.

This bypasses the binary_search loop entirely. It:

  1. Extracts the spec for bitmap::new (via existing extract.py).
  2. Generates the det_new template (via existing gen_det.py).
  3. Runs Z3Backend.check_with_model() once.
  4. Prints the Z3 model if the check fails.

Compare this to running test_all.py on bitmap::new, which takes
~20 Verus calls for the same witness.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.types import *
from src.extract import extract_spec
from src.gen_det import build_det_check_spec, render_template
from src.equal_policy import EqualPolicy
from src.z3_backend import Z3Backend, summarise_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

NANVIX = os.path.expanduser("~/nanvix")
VERUS_PATH = os.path.join(NANVIX, "toolchain/verus")

BITMAP_SRC = os.path.join(NANVIX, "src/libs/bitmap/src/lib.rs")
BITMAP_SPEC = os.path.join(NANVIX, "src/libs/bitmap/src/lib.spec.rs")
BITMAP_PROOF = os.path.join(NANVIX, "src/libs/bitmap/src/lib.proof.rs")

ERROR_SRC = os.path.join(NANVIX, "src/libs/error/src/lib.rs")


def main():
    print("=== spec-determinism Z3 backend prototype (bitmap::new) ===\n")

    with open(BITMAP_SRC) as f:
        src = f.read()
    with open(BITMAP_SPEC) as f:
        spec_src = f.read()
    with open(ERROR_SRC) as f:
        err_src = f.read()

    spec = extract_spec(src, "new", type_sources=[spec_src, err_src])
    print(f"extracted spec: {spec.name} ({len(spec.params)} params)")

    det_spec = build_det_check_spec(
        spec, equal_policy=EqualPolicy(errs_equivalent=True))
    code = render_template(det_spec, [])

    # The SMT-level names we want to read out of the model.
    # Verus mangles variables as `<name>!`; the input `number_of_bits`
    # and the synthetic outputs `r1`, `r2` are named exactly that.
    tracked = ["number_of_bits!", "r1!", "r2!"]

    backend = Z3Backend(
        crate_dir=NANVIX,
        crate_name="bitmap",
        verus_path=VERUS_PATH,
        proof_file=BITMAP_PROOF,
        tracked_symbols=tracked,
    )

    print("running Verus + extracting Z3 model...")
    res = backend.check_with_model(code, "det_new")
    print(f"\nstatus   : {res.status}")
    print(f"duration : {res.duration_ms} ms ({res.duration_ms/1000:.2f} s)")
    print(f"transcript: {res.transcript_path}")

    if res.status == "fail":
        if res.model:
            print("\nconcrete witness (from Z3 get-model):")
            for name, v in summarise_model(res.model).items():
                print(f"  {name:25s} = {v}")
        else:
            print("\n(no model extracted — fall back to binary search)")
    elif res.status == "pass":
        print("\ndeterministic at R0 (no witness needed).")
    else:
        print(f"\nstderr:\n{res.stderr[:500]}")


if __name__ == "__main__":
    main()
