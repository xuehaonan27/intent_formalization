"""Single-file Verus runner for corpora that are NOT cargo workspaces.

Handles verusage-style source files: each ``.rs`` is a self-contained Verus
program with one ``verus! { ... }`` block containing types, spec fns, and
one or more target exec fns. We don't use cargo — we shell out to
``verus <file>`` directly.

Usage:
    from spec_determinism.single_file import run_single_file
    result = run_single_file(Path("foo.rs"), "target_fn", verus_path="...")

The result dict matches the shape emitted by ``run_all.run_one`` so batch
runners can aggregate results across both backends uniformly.

LLM proof loop integration (opt-in)
-----------------------------------
When ``use_llm_proof=True`` (or env ``SPEC_DET_LLM_PROOF=1``) AND the
baseline schema search returns ``r0_z3='unknown'``, we invoke
:func:`spec_determinism.llm_proof.run_llm_proof_loop`. On success the
function is reclassified as ``ok_proved_llm`` (see
:mod:`spec_determinism.classify`) and the winning proof block is
persisted alongside the artifact. Independent of the schema search
result — the loop is opt-in and never runs by default.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path
from typing import Optional

from spec_determinism.extract.extractor import extract_spec
from spec_determinism.codegen.gen_det import build_det_check_spec
from spec_determinism.schema_search import enumerate_schemas, render_guarded_template
from spec_determinism.schema_search.search import build_schema_ctx, run_schema_search
from spec_determinism.extract.types import DetCheckSpec

logger = logging.getLogger(__name__)

_DEFAULT_VERUS = str(Path.home() / "nanvix/toolchain/verus")


# ---------------------------------------------------------------------------
# Target discovery: find candidate exec fns inside a single Verus file.
# ---------------------------------------------------------------------------

# Match `pub? unsafe? fn <name>(` at column 0 (with optional whitespace).
# Excludes `proof fn` / `spec fn` / `open spec fn` by requiring `fn` to be
# the first keyword on the line (no proof/spec/open prefix).
_FN_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:unsafe\s+)?fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*[<(]",
    re.MULTILINE,
)


def discover_exec_fns(source: str) -> list[str]:
    """Return exec fn names in ``source`` that *might* have ensures.

    Filters out ``fn main`` (Verus corpora wrap every file with a stub).
    Caller still needs ``extract_spec`` to confirm the fn has an
    ``ensures`` clause (empty list → nothing to check).
    """
    names: list[str] = []
    for m in _FN_RE.finditer(source):
        n = m.group("name")
        if n == "main":
            continue
        names.append(n)
    # Dedup, preserve order.
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


# ---------------------------------------------------------------------------
# Verus invocation.
# ---------------------------------------------------------------------------

def run_verus_file(
    file_path: Path,
    verus_path: str,
    log_dir: Path,
    timeout: int = 120,
) -> dict:
    """Invoke ``verus <file>`` with logging enabled.

    Returns dict with ``returncode, stdout, stderr, duration_ms``.
    """
    verus_bin = Path(verus_path) / "verus"
    env = os.environ.copy()
    env["PATH"] = verus_path + ":" + env.get("PATH", "")
    env["RUSTC_BOOTSTRAP"] = "1"

    cmd = [
        str(verus_bin), str(file_path),
        "--log-all", "--log-dir", str(log_dir),
    ]
    t0 = time.monotonic()
    try:
        p = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=timeout,
        )
        return {
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
            "duration_ms": int((time.monotonic() - t0) * 1000),
        }
    except subprocess.TimeoutExpired as e:
        return {
            "returncode": -1,
            "stdout": e.stdout or "",
            "stderr": (e.stderr or "") + f"\n[timeout after {timeout}s]",
            "duration_ms": int((time.monotonic() - t0) * 1000),
        }


# ---------------------------------------------------------------------------
# High-level: run determinism check on one (file, fn) pair.
# ---------------------------------------------------------------------------

_INJECT_BEGIN = "// === INJECTED DET CHECK ===\n"
_INJECT_END = "// === END INJECTED ===\n"


def _inject_into_source(source: str, code: str) -> str:
    """Insert det-check code just before the last `}` (end of ``verus!{}``)."""
    idx = source.rfind("}")
    if idx == -1:
        raise ValueError("No closing `}` found in source")
    return (
        source[:idx]
        + "\n" + _INJECT_BEGIN + code + "\n" + _INJECT_END + "\n"
        + source[idx:]
    )


def run_single_file(
    file_path: Path,
    fn_name: str,
    *,
    verus_path: str = _DEFAULT_VERUS,
    timeout: int = 120,
    artifact_dir: Path | None = None,
    keep_tmp: bool = False,
    view_registry=None,
    use_llm_proof: bool | None = None,
    llm_proof_max_attempts: int = 3,
    llm_proof_model: str | None = None,
    llm_proof_effort: str | None = None,
) -> dict:
    """Extract, gen_det, verus, parse SMT2, run schema search.

    Mirrors ``run_all.run_one`` shape for downstream aggregation.

    If ``artifact_dir`` is given, writes ``det_spec.json`` and the
    patched ``.det.rs`` alongside for debugging; otherwise uses a
    temp dir.

    ``view_registry`` (optional) is a Phase-2 L1+L2+L3 resolver. When
    provided, ``gen_det.build_equal_expr`` consults it for any struct
    / unknown type whose ``TypeInfo.spec_view`` is unset, before
    falling back to recursive structural equality. ``None`` preserves
    the legacy (pre-Phase-2) behaviour.

    ``use_llm_proof`` (opt-in): when True AND the baseline returns
    ``r0_z3='unknown'``, escalate to the LLM proof loop. Default is
    ``None``, which respects env ``SPEC_DET_LLM_PROOF`` (any truthy
    value enables). Successful runs set ``llm_assisted=True`` and
    ``r0_z3='unsat'`` in the returned dict; the winning proof block
    is persisted to ``artifact_dir/llm_proof_block.txt`` (when
    artifact_dir is given) and the per-attempt logs land under
    ``artifact_dir/llm_proof/``.
    """
    result: dict = {
        "file": str(file_path),
        "function": fn_name,
    }
    t0 = time.monotonic()
    source = Path(file_path).read_text()

    try:
        spec = extract_spec(source, fn_name, type_sources=[])
    except Exception as e:
        result["status"] = "extract_error"
        result["error"] = f"{type(e).__name__}: {e}"
        return result

    if not spec.ensures:
        result["status"] = "no_ensures"
        return result

    det_spec = build_det_check_spec(spec, view_registry=view_registry)
    fn_det_name = det_spec.check_fn_name

    # Write artifact for post-mortem.
    tmp_root = Path(tempfile.mkdtemp(prefix=f"specdet_sf_{fn_name}_"))
    try:
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "det_spec.json").write_text(det_spec.to_json())

        schemas = enumerate_schemas(det_spec)
        code = det_spec.equal_fn_def + "\n\n" + render_guarded_template(det_spec, schemas)
        injected = _inject_into_source(source, code)

        # Verus derives crate name from file stem — keep it stable.
        injected_path = tmp_root / f"{file_path.stem}.rs"
        injected_path.write_text(injected)
        if artifact_dir is not None:
            (artifact_dir / "injected.rs").write_text(injected)

        log_dir = tmp_root / "verus_log"
        log_dir.mkdir()

        result["n_schemas"] = len(schemas)
        result["n_params"] = sum(1 + len(s.k_params) for s in schemas)

        t_v = time.monotonic()
        raw = run_verus_file(injected_path, verus_path, log_dir, timeout=timeout)
        result["verus_ms"] = int((time.monotonic() - t_v) * 1000)

        if raw["returncode"] != 0:
            stderr = raw["stderr"]
            if ("postcondition not satisfied" not in stderr
                    and "assertion failed" not in stderr.lower()
                    and "error:" in stderr):
                result["status"] = "verus_error"
                result["stderr_tail"] = stderr[-2000:]
                return result

        smt2_candidates = list(log_dir.rglob("*.smt2"))
        smt2_candidates.sort(key=lambda p: (p.name == "root.smt2", p.stat().st_size))
        if not smt2_candidates:
            result["status"] = "no_smt2"
            return result
        smt2 = smt2_candidates[-1]
        result["smt2_bytes"] = smt2.stat().st_size

        try:
            t_c = time.monotonic()
            schema_ctx = build_schema_ctx(smt2, fn_det_name, schemas, file_path.stem)
            result["ctx_ms"] = int((time.monotonic() - t_c) * 1000)

            t_s = time.monotonic()
            witness = run_schema_search(det_spec, schema_ctx)
            result["search_ms"] = int((time.monotonic() - t_s) * 1000)
            result["n_rounds"] = len(witness.trace) if witness.trace else 0
            result["assumes"] = [a.expression for a in (witness.assumes or [])]
            result["r0_z3"] = witness.r0_z3
            result["status"] = "ok"
        except Exception as e:
            result["status"] = "search_error"
            result["error"] = (
                f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
            )

        # LLM proof loop escalation (opt-in). Triggered when baseline
        # returned r0_z3=unknown AND opt-in. On success we overwrite
        # r0_z3='unsat' and mark llm_assisted=True so the classifier
        # buckets this as ok_proved_llm rather than ok_proved.
        _llm_enabled = (
            use_llm_proof
            if use_llm_proof is not None
            else bool(os.environ.get("SPEC_DET_LLM_PROOF"))
        )
        if (
            _llm_enabled
            and result.get("status") == "ok"
            and result.get("r0_z3") == "unknown"
        ):
            try:
                from spec_determinism.llm_proof import run_llm_proof_loop

                proof_root = (
                    (artifact_dir / "llm_proof")
                    if artifact_dir is not None
                    else (tmp_root / "llm_proof")
                )
                pr = run_llm_proof_loop(
                    det_spec=det_spec,
                    fn_spec=spec,
                    source=source,
                    file_stem=file_path.stem,
                    verus_path=verus_path,
                    work_root=proof_root,
                    timeout=timeout,
                    max_attempts=llm_proof_max_attempts,
                    model=llm_proof_model,
                    reasoning_effort=llm_proof_effort,
                    artifact_dir=artifact_dir,
                )
                result["llm_proof_attempts"] = len(pr.attempts)
                result["llm_proof_total_ms"] = pr.total_ms
                if pr.success:
                    result["llm_assisted"] = True
                    result["r0_z3"] = "unsat"
                    result["llm_proof_block"] = pr.winning_proof_block
                    result["llm_proof_rationale"] = pr.winning_rationale
                    logger.info(
                        "llm_proof[%s]: succeeded after %d attempt(s) in %dms",
                        fn_name, len(pr.attempts), pr.total_ms,
                    )
                else:
                    result["llm_assisted"] = False
                    last = pr.attempts[-1] if pr.attempts else None
                    result["llm_proof_last_status"] = (
                        last.status if last else "no_attempts"
                    )
                    logger.info(
                        "llm_proof[%s]: exhausted %d attempt(s) without success",
                        fn_name, len(pr.attempts),
                    )
            except Exception as e:
                # Never crash the main pipeline on an LLM glitch.
                result["llm_proof_error"] = (
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
                )
                logger.warning(
                    "llm_proof[%s]: escalation crashed: %s", fn_name, e,
                )

    finally:
        if not keep_tmp:
            shutil.rmtree(tmp_root, ignore_errors=True)

    result["total_ms"] = int((time.monotonic() - t0) * 1000)
    return result
