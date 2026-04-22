#!/usr/bin/env python3
"""POC: end-to-end z3-py incremental search on bitmap::new.

Flow:
  1. Load bitmap__new/det_spec.json (already-extracted spec).
  2. Render template with NO assumes (= R0 case).
  3. Inject into nanvix bitmap proof file.
  4. Run `cargo verus build` ONCE with --log-all --log-dir <tmp> to
     produce root.smt2.
  5. Restore proof file.
  6. Locate the .smt2 file containing det_new's `(push)` block and load
     it into Z3PySearchContext.
  7. Call check() and verify the verdict matches the existing pipeline's
     "nondeterministic_no_witness".

Goal: prove the new path produces the same verdict, with the per-round
cost being z3-py (~1ms) instead of cargo-verus (~700ms).
"""
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import z3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.types import DetCheckSpec, Symbol, TypeInfo
from src.gen_det import render_template
from src.verify import inject_proof_fn, restore_file, run_cargo_verus
from src.z3py_search import Z3PySearchContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("poc")

NANVIX = os.path.expanduser("~/nanvix")
VERUS_PATH = os.path.join(NANVIX, "toolchain/verus")
PROOF_FILE = os.path.join(NANVIX, "src/libs/bitmap/src/lib.proof.rs")
CRATE_DIR = NANVIX
CRATE_NAME = "bitmap"

ARTIFACT = Path(__file__).parent / "results" / "artifacts" / "bitmap__new" / "det_spec.json"


def load_det_spec(path: Path) -> DetCheckSpec:
    return DetCheckSpec.from_dict(json.loads(path.read_text()))


def find_det_smt2(log_dir: Path, fn_name: str) -> Path:
    """Find the .smt2 file whose Function-Def block matches fn_name."""
    candidates = list(log_dir.rglob("*.smt2"))
    log.info(f"Found {len(candidates)} .smt2 file(s) under {log_dir}")
    needle_a = f"Function-Def {CRATE_NAME}::{fn_name}"
    needle_b = f"%{CRATE_NAME}!{fn_name}."
    for p in candidates:
        try:
            txt = p.read_text(errors="ignore")
        except Exception:
            continue
        if needle_a in txt or needle_b in txt:
            log.info(f"  match: {p} ({len(txt)} bytes)")
            return p
    raise FileNotFoundError(f"No .smt2 contains {needle_a!r} or {needle_b!r}")


def main():
    t0 = time.monotonic()
    det_spec = load_det_spec(ARTIFACT)
    fn_name = det_spec.check_fn_name or f"det_{det_spec.function}"
    log.info(f"Loaded det_spec for {det_spec.function}, check fn = {fn_name}")

    code = render_template(det_spec, [])
    log.info(f"Rendered template: {len(code)} bytes, {code.count(chr(10))} lines")

    log_dir = Path(tempfile.mkdtemp(prefix="poc_z3py_"))
    log.info(f"Verus log dir: {log_dir}")

    # ---- Step 1: inject + run cargo verus once with --log-all -------------
    original = inject_proof_fn(PROOF_FILE, code)
    try:
        t_v0 = time.monotonic()
        raw = run_cargo_verus(
            CRATE_DIR, CRATE_NAME, VERUS_PATH,
            features=["std"],
            timeout=180,
            verify_module=None,
            verify_function=fn_name,
            use_build=True,
            verus_extra_args=[
                "--log-all",
                "--log-dir", str(log_dir),
            ],
        )
        verus_ms = int((time.monotonic() - t_v0) * 1000)
        log.info(f"cargo verus: {verus_ms}ms, rc={raw['returncode']}")
        if raw["returncode"] != 0:
            log.warning(f"verus stderr (last 1k):\n{raw['stderr'][-1000:]}")
    finally:
        restore_file(PROOF_FILE, original)
        log.info("Proof file restored")

    # ---- Step 2: locate the smt2 ------------------------------------------
    smt2 = find_det_smt2(log_dir, fn_name)

    # ---- Step 3: load into Z3PySearchContext ------------------------------
    ctx = Z3PySearchContext.from_smt2_path(str(smt2))
    log.info(f"Prelude loaded into context")

    # ---- Step 4: re-run the full body (decls + goal) inside the ctx -------
    # Strategy: replay everything between the first (push) and (check-sat),
    # skipping nested (push)/(pop)/(check-sat)/(get-info)/(get-model)/(set-option).
    full = Path(smt2).read_text()
    # smt2 contains many (push)...(check-sat) blocks (one per fn).
    # Find the block whose Function-Def comment names our fn.
    marker = f";; Function-Def {CRATE_NAME}::{fn_name}"
    m_idx = full.find(marker)
    if m_idx < 0:
        # Fallback: any line referencing det_new in a Function-Def header.
        m_idx = full.find(f"Function-Def {CRATE_NAME}::{fn_name}")
    if m_idx < 0:
        raise RuntimeError(f"Could not find Function-Def marker for {fn_name} in {smt2}")
    push_idx = full.find("(push)", m_idx)
    cs_idx = full.find("(check-sat)", push_idx)
    body = full[push_idx + len("(push)"):cs_idx]
    log.info(f"Replaying body block at offset {push_idx}: {len(body)} bytes")

    # Strip nested push/pop/get-info/etc.
    skipped = 0
    kept_lines = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("(push)") or s.startswith("(pop)") or s.startswith("(check-sat)") \
           or s.startswith("(get-info") or s.startswith("(get-model)") \
           or s.startswith("(set-option") or s.startswith(";"):
            skipped += 1
            continue
        kept_lines.append(line)
    body_clean = "\n".join(kept_lines)
    log.info(f"Body cleaned: {len(body_clean)} bytes ({skipped} lines skipped)")

    # Feed body_clean into the ctx's main solver. We need to declare anything
    # new and assert the rest. Use solver.from_string since ctx already has
    # all prelude decls.
    ctx.solver.from_string(body_clean)
    ctx._side.from_string(body_clean)
    log.info(f"Body asserted into ctx; {len(ctx.solver.assertions())} total assertions")

    # ---- Step 5: check ----------------------------------------------------
    t_c0 = time.monotonic()
    res = ctx.check()
    check_ms = (time.monotonic() - t_c0) * 1000
    log.info(f"z3-py check(): {res} in {check_ms:.1f} ms")

    # Expected for bitmap::new:
    #   res in (sat, unknown)  → verdict "nondeterministic"
    #   res == unsat            → would mean "deterministic" (NOT expected)
    if res == z3.unsat:
        verdict = "deterministic (UNEXPECTED for bitmap::new!)"
    elif res == z3.sat:
        verdict = "nondeterministic_with_witness"
    else:  # unknown
        verdict = "nondeterministic_no_witness"
    log.info(f"=> verdict: {verdict}")

    expected = "nondeterministic_no_witness"
    ok = (verdict == expected)
    total_ms = int((time.monotonic() - t0) * 1000)
    log.info(f"=" * 60)
    log.info(f"TOTAL: {total_ms}ms (verus={verus_ms}ms, z3-py check={check_ms:.1f}ms)")
    log.info(f"Expected: {expected}")
    log.info(f"Got:      {verdict}")
    log.info(f"MATCH:    {ok}")
    log.info(f"=" * 60)

    # Cleanup log_dir
    shutil.rmtree(log_dir, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
