"""Tier 1.5 — gen_det compile probe.

After Tier 1.5 has applied a round of LLM patches to ``spec.type_defs``,
this probe synthesises the would-be det fn / equal fn via ``gen_det`` and
asks Verus to type-check (but not verify) the result. The probe catches a
specific bug class that the static V1+V2+V3 gates miss:

   The LLM patches a type ``T`` with ``kind=STRUCT, fields=[],
   spec_view=Map<K,V>`` (or Seq / Set), but the actual ``T`` in source
   is a type alias ``pub type T<K,V> = Map<K, V>;``. Verus resolves
   ``T`` post-alias to the container itself, then rejects gen_det's
   ``(lhs)@`` projection with::

      error[E0599]: no method named `view` found for struct
      `vstd::map::Map<K, V>` in the current scope

The probe surface error message goes back through
:func:`spec_determinism.llm_type.gaps.gaps_from_compile_stderr` to
produce ``REASON_SHAPE_MISMATCH`` gaps for the next Tier 1.5 round.

Use ``verus --no-verify`` so we get rustc-level type-checking
(name resolution, E0599 etc.) without paying for z3.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from spec_determinism.extract.types import FunctionSpec


_DEFAULT_VERUS = str(Path.home() / "nanvix/toolchain/verus")
_INJECT_BEGIN = "// === TIER1.5 SHAPE PROBE ===\n"
_INJECT_END = "// === END SHAPE PROBE ===\n"


@dataclass
class ProbeResult:
    returncode: int
    stderr: str
    duration_ms: int
    skipped: bool = False
    skip_reason: str = ""


def _inject(source: str, code: str) -> str:
    """Insert ``code`` just before the trailing ``}`` of the verus! { }
    block, mirroring :func:`spec_determinism.verus.single_file._inject_into_source`."""
    idx = source.rfind("}")
    if idx == -1:
        raise ValueError("no trailing `}` in source")
    return (
        source[:idx]
        + "\n" + _INJECT_BEGIN + code + "\n" + _INJECT_END + "\n"
        + source[idx:]
    )


def probe_gen_det_compile(
    spec: FunctionSpec,
    source_text: str,
    *,
    file_stem: str = "tier15_probe",
    verus_path: str = _DEFAULT_VERUS,
    view_registry=None,
    timeout: int = 30,
    work_dir: Optional[Path] = None,
) -> ProbeResult:
    """Render the current gen_det output for ``spec`` against ``source_text``
    and run ``verus --no-verify``. Returns the captured stderr so the
    caller can extract shape-mismatch gaps.

    ``source_text`` is the original ``.rs`` content the target lives in
    (we inject after the trailing ``}`` of ``verus! { … }``).

    When ``spec.ensures`` is empty (no determinism check to build), the
    probe is skipped — there's nothing for gen_det to emit, so a probe
    is meaningless. ``ProbeResult.skipped`` is set accordingly.
    """
    if not spec.ensures:
        return ProbeResult(
            returncode=0, stderr="", duration_ms=0,
            skipped=True, skip_reason="spec has no ensures",
        )

    # Lazy imports to avoid pulling codegen at module-import time.
    from spec_determinism.codegen.gen_det import build_det_check_spec
    from spec_determinism.schema_search.schemas import (
        enumerate_schemas, render_guarded_template,
    )

    t0 = time.monotonic()
    try:
        det_spec = build_det_check_spec(spec, view_registry=view_registry)
    except Exception as e:  # codegen blew up — no shape-mismatch surfacable
        return ProbeResult(
            returncode=-2, stderr=f"gen_det raised: {e}", duration_ms=0,
            skipped=True, skip_reason="gen_det exception",
        )

    schemas = enumerate_schemas(det_spec)
    code = det_spec.equal_fn_def + "\n\n" + render_guarded_template(det_spec, schemas)
    try:
        injected = _inject(source_text, code)
    except ValueError as e:
        return ProbeResult(
            returncode=-3, stderr=f"inject failed: {e}", duration_ms=0,
            skipped=True, skip_reason="inject failed",
        )

    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix=f"tier15probe_{file_stem}_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    probe_path = work_dir / f"{file_stem}.rs"
    probe_path.write_text(injected)

    verus_bin = Path(verus_path) / "verus"
    env = os.environ.copy()
    env["PATH"] = verus_path + ":" + env.get("PATH", "")
    env["RUSTC_BOOTSTRAP"] = "1"

    cmd = [str(verus_bin), str(probe_path), "--no-verify"]
    try:
        p = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=timeout,
        )
        return ProbeResult(
            returncode=p.returncode,
            stderr=p.stderr or "",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
    except subprocess.TimeoutExpired as e:
        return ProbeResult(
            returncode=-1,
            stderr=(e.stderr or "") + f"\n[probe timeout after {timeout}s]",
            duration_ms=int((time.monotonic() - t0) * 1000),
            skipped=True,
            skip_reason=f"verus timeout after {timeout}s",
        )


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    from spec_determinism.extract.types import (
        FunctionSpec, Param, TypeInfo as TI, TypeKind as TK,
    )

    ok = True

    # 1) Empty-ensures spec → skipped.
    bare = FunctionSpec(
        name="f",
        params=[Param(name="x", type=TI(TK.UNIT, "()"))],
        return_type=TI(TK.UNIT, "()"),
        requires=[], ensures=[],
        type_defs={},
    )
    r = probe_gen_det_compile(bare, "verus! { }")
    if not (r.skipped and r.skip_reason == "spec has no ensures"):
        print(f"FAIL: empty-ensures probe should be skipped, got {r}")
        ok = False

    # 2) Bad inject (no trailing `}`) → skipped.
    spec2 = FunctionSpec(
        name="f",
        params=[Param(name="x", type=TI(TK.U32, "u32"))],
        return_type=TI(TK.U32, "u32"),
        requires=[], ensures=["pub spec fn det_f_ensures(x: u32, r: u32) -> bool { true }"],
        type_defs={},
    )
    r2 = probe_gen_det_compile(spec2, "// no braces here")
    if not r2.skipped or "inject" not in r2.skip_reason:
        # Some gen_det paths may raise earlier than the inject step; accept either.
        if not r2.skipped:
            print(f"FAIL: malformed source should produce skipped/error probe, got {r2}")
            ok = False

    print("probe self-test:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        raise SystemExit(0 if _self_test() else 1)
    print("usage: python -m spec_determinism.llm_type.probe test")
    raise SystemExit(2)
