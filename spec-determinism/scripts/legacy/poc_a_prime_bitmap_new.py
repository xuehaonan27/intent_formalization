#!/usr/bin/env python3
"""A' end-to-end POC on bitmap::new.

Flow:
  1. Load bitmap::new det_spec.
  2. Enumerate schemas (integer + variant for v1).
  3. Render guarded template.
  4. Inject into bitmap proof file + cargo verus --log-all (ONCE).
  5. Load smt2 into APrimeCtx.
  6. Run binary_search_a_prime.
  7. Compare final trace shape against expected (from full_test_run.log).
"""
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.types import DetCheckSpec
from src.verify import inject_proof_fn, restore_file, run_cargo_verus
from src.a_prime import (
    enumerate_schemas, render_guarded_template,
    binary_search_a_prime,
)
from src.a_prime.search import build_a_prime_ctx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("poc_a")

NANVIX = os.path.expanduser("~/nanvix")
VERUS_PATH = os.path.join(NANVIX, "toolchain/verus")
PROOF_FILE = os.path.join(NANVIX, "src/libs/bitmap/src/lib.proof.rs")

ARTIFACT = Path(__file__).parent / "results" / "artifacts" / "bitmap__new" / "det_spec.json"


def main():
    t0 = time.monotonic()
    det_spec = DetCheckSpec.from_dict(json.loads(ARTIFACT.read_text()))
    fn_name = det_spec.check_fn_name or f"det_{det_spec.function}"
    log.info(f"Target: {det_spec.function} -> {fn_name}")

    schemas = enumerate_schemas(det_spec)
    log.info(f"Schemas enumerated: {len(schemas)}")
    for s in schemas[:20]:
        log.info(f"  {s.id:40} kind={s.kind.value:15} var={s.rust_var}")
    if len(schemas) > 20:
        log.info(f"  ... and {len(schemas) - 20} more")

    code = render_guarded_template(det_spec, schemas)
    # Also need equal_fn_def prepended (like normal render_template does).
    full_code = det_spec.equal_fn_def + "\n\n" + code
    log.info(f"Rendered guarded template: {len(full_code)} bytes")

    log_dir = Path(tempfile.mkdtemp(prefix="poc_aprime_"))
    log.info(f"Verus log dir: {log_dir}")

    original = inject_proof_fn(PROOF_FILE, full_code)
    try:
        t_v0 = time.monotonic()
        raw = run_cargo_verus(
            NANVIX, "bitmap", VERUS_PATH,
            features=["std"], timeout=180,
            verify_function=fn_name, use_build=True,
            verus_extra_args=["--log-all", "--log-dir", str(log_dir)],
        )
        verus_ms = int((time.monotonic() - t_v0) * 1000)
        log.info(f"cargo verus: {verus_ms}ms, rc={raw['returncode']}")
        if raw["returncode"] != 0:
            # Non-zero is expected (postcondition fails when all guards are
            # off) BUT compile errors are not. Check stderr for compile issues.
            if "error: could not compile" in raw["stderr"] and \
               "postcondition not satisfied" not in raw["stderr"]:
                log.error("COMPILE ERROR in guarded template:")
                log.error(raw["stderr"][-3000:])
                log.error("\n----- generated code -----\n" + full_code)
                return 2
    finally:
        restore_file(PROOF_FILE, original)

    smt2 = log_dir / "root.smt2"
    if not smt2.exists():
        # Try to find it.
        cands = list(log_dir.rglob("root.smt2"))
        if not cands:
            log.error(f"No root.smt2 in {log_dir}")
            return 3
        smt2 = cands[0]
    log.info(f"SMT2: {smt2} ({smt2.stat().st_size} bytes)")

    t_load = time.monotonic()
    a_ctx = build_a_prime_ctx(smt2, fn_name, schemas, "bitmap")
    load_ms = int((time.monotonic() - t_load) * 1000)
    log.info(f"APrimeCtx built in {load_ms}ms")

    t_search = time.monotonic()
    witness = binary_search_a_prime(det_spec, a_ctx)
    search_ms = int((time.monotonic() - t_search) * 1000)
    log.info(f"Search completed in {search_ms}ms ({len(witness.trace)} trace entries)")

    log.info("=" * 70)
    log.info("FINAL ASSUMES:")
    for a in (witness.assumes or []):
        log.info(f"  - {a.expression}")
    log.info("=" * 70)

    total_ms = int((time.monotonic() - t0) * 1000)
    log.info(f"TOTAL: {total_ms}ms (verus={verus_ms}ms, ctx_load={load_ms}ms, search={search_ms}ms)")

    shutil.rmtree(log_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
