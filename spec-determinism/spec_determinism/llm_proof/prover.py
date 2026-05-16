"""LLM proof loop driver.

Single entry point: :func:`run_llm_proof_loop`. Called from
:mod:`spec_determinism.verus.single_file` after the baseline schema
search returns ``r0_z3 == "unknown"``.

Workflow per attempt:

  1. Build a prompt with current det_spec / proof-fn body / prior failure
     (if any). The prior failure is either a Verus stderr tail or a
     formatted list of :class:`SandboxViolation` entries.
  2. Spawn the Copilot CLI (via :class:`CopilotCLI`) and read its
     response.
  3. Parse the response into a :class:`ParsedProof`.
  4. Run :func:`scan_proof_block` over the proof body. Any violation
     short-circuits this attempt with ``status="sandbox_reject"``.
  5. Re-render the synthetic det-check, this time with the proof block
     appended at the bottom of the proof fn body. Write the modified
     ``.rs`` to a fresh path; run Verus.
  6. Verus accepts → success (``ok_proved_llm`` at the caller's level).
     Verus rejects → record stderr tail and loop.

Results are persisted under ``<artifact_dir>/llm_proof/attempt_N/`` so
post-mortem inspection and replay are cheap.

The loop is **stateless across runs**: no on-disk cache yet. Adding one
is straightforward (key by det_fn_name + source hash) once we have a
sense of token cost; the strategy doc tracks this as a TODO.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import time
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from spec_determinism.extract.types import DetCheckSpec, FunctionSpec
from spec_determinism.schema_search import enumerate_schemas, render_guarded_template
from spec_determinism.llm.copilot import CopilotCLI

from .parser import ParsedProof, ProofParseError, parse_proof_response
from .prompt import PromptInputs, build_proof_prompt
from .sandbox import SandboxViolation, format_violations, scan_proof_block

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result records (json-serializable for persistence).
# ---------------------------------------------------------------------------


@dataclass
class ProofAttempt:
    """A single LLM round-trip + verus re-run."""

    iteration: int
    proof_block: str = ""
    rationale: str = ""
    sandbox_violations: list[dict] = field(default_factory=list)
    verus_returncode: Optional[int] = None
    verus_stderr_tail: str = ""
    verus_ms: int = 0
    llm_ms: int = 0
    status: str = "init"     # see _STATUSES below

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# Possible per-attempt status values.
_STATUSES = (
    "init",
    "llm_failure",        # copilot subprocess never produced a response
    "parse_failure",      # response had no fenced verus block
    "sandbox_reject",     # proof block contained a forbidden construct
    "verus_pass",         # Verus accepted with the proof appended (SUCCESS)
    "verus_fail",         # Verus still rejected → loop or exhaust
)


@dataclass
class ProofResult:
    """Aggregate of N attempts. ``success`` is True iff some attempt was verus_pass."""

    success: bool = False
    attempts: list[ProofAttempt] = field(default_factory=list)
    winning_proof_block: str = ""
    winning_rationale: str = ""
    total_ms: int = 0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "attempts": [a.to_dict() for a in self.attempts],
            "winning_proof_block": self.winning_proof_block,
            "winning_rationale": self.winning_rationale,
            "total_ms": self.total_ms,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# The template emitted by gen_det wraps the body in `{ {ASSUMES} }`. We need
# to recover the rendered body, append the proof block, and re-render.
# Easiest path: call render_guarded_template with the new proof_prelude.


_INJECT_BEGIN = "// === INJECTED DET CHECK ===\n"
_INJECT_END = "// === END INJECTED ===\n"


def _strip_injected(source: str) -> str:
    """Remove any prior INJECTED DET CHECK block (idempotent)."""
    pat = re.compile(
        r"\n*"
        + re.escape(_INJECT_BEGIN)
        + r".*?"
        + re.escape(_INJECT_END)
        + r"\n*",
        re.DOTALL,
    )
    return pat.sub("\n", source)


def _inject_into_source(source: str, code: str) -> str:
    """Insert det-check code just before the last `}` (end of ``verus!{}``)."""
    cleaned = _strip_injected(source)
    idx = cleaned.rfind("}")
    if idx == -1:
        raise ValueError("No closing `}` found in source")
    return (
        cleaned[:idx]
        + "\n" + _INJECT_BEGIN + code + "\n" + _INJECT_END + "\n"
        + cleaned[idx:]
    )


def _run_verus(
    rs_path: Path,
    verus_path: str,
    log_dir: Path,
    *,
    timeout: int,
) -> tuple[int, str, int]:
    """Invoke ``verus <rs_path>``. Returns ``(rc, stderr, duration_ms)``."""
    verus_bin = Path(verus_path) / "verus"
    env = os.environ.copy()
    env["PATH"] = verus_path + ":" + env.get("PATH", "")
    env["RUSTC_BOOTSTRAP"] = "1"
    cmd = [
        str(verus_bin), str(rs_path),
        "--log-all", "--log-dir", str(log_dir),
    ]
    t0 = time.monotonic()
    try:
        p = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=timeout,
        )
        return (
            p.returncode,
            (p.stdout + "\n" + p.stderr)[-4000:],
            int((time.monotonic() - t0) * 1000),
        )
    except subprocess.TimeoutExpired as e:
        tail = ((e.stderr or "")
                + f"\n[verus timeout after {timeout}s]")[-4000:]
        return -1, tail, int((time.monotonic() - t0) * 1000)


def _render_det_body_with_proof(
    det_spec: DetCheckSpec,
    proof_block: Optional[str],
) -> str:
    """Render the synthetic det-check, optionally appending a proof block."""
    schemas = enumerate_schemas(det_spec)
    inner = render_guarded_template(det_spec, schemas, proof_prelude=proof_block)
    return det_spec.equal_fn_def + "\n\n" + inner


def _render_det_fn_body_only(det_spec: DetCheckSpec) -> str:
    """Render the synthetic proof fn (without the equal-fn def) for prompt display."""
    schemas = enumerate_schemas(det_spec)
    return render_guarded_template(det_spec, schemas)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def run_llm_proof_loop(
    *,
    det_spec: DetCheckSpec,
    fn_spec: Optional[FunctionSpec],
    source: str,
    file_stem: str,
    verus_path: str,
    work_root: Path,
    timeout: int = 180,
    max_attempts: int = 3,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    artifact_dir: Optional[Path] = None,
    crate_name: str = "",
) -> ProofResult:
    """Run K LLM round-trips trying to close a z3-unknown det check.

    Returns a :class:`ProofResult`. The caller decides how to fold the
    result into its existing per-target dict (e.g. set ``r0_z3='unsat'``
    on success and add ``llm_assisted=True``).
    """
    t_total = time.monotonic()
    work_root.mkdir(parents=True, exist_ok=True)

    # Build LLM client lazily; CLI cost is one process spawn per attempt.
    client = CopilotCLI(
        model=model,
        reasoning_effort=reasoning_effort,
        timeout=timeout,
    )

    det_body_for_prompt = _render_det_fn_body_only(det_spec)

    result = ProofResult()
    prior_block: Optional[str] = None
    prior_failure_kind: Optional[str] = None
    prior_failure_detail: Optional[str] = None

    for i in range(1, max_attempts + 1):
        attempt = ProofAttempt(iteration=i)
        result.attempts.append(attempt)

        attempt_dir = work_root / f"attempt_{i:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        # ----- 1. build prompt -----
        prompt = build_proof_prompt(PromptInputs(
            det_spec=det_spec,
            det_body=det_body_for_prompt,
            fn_spec=fn_spec,
            source_excerpt=source,
            crate_name=crate_name,
            prior_proof_block=prior_block,
            prior_failure_kind=prior_failure_kind,
            prior_failure_detail=prior_failure_detail,
        ))
        (attempt_dir / "prompt.md").write_text(prompt)

        # ----- 2. call LLM -----
        t_llm = time.monotonic()
        try:
            raw = client.query(prompt, attempt_dir / "llm")
        except Exception as e:
            attempt.llm_ms = int((time.monotonic() - t_llm) * 1000)
            attempt.status = "llm_failure"
            attempt.verus_stderr_tail = f"{type(e).__name__}: {e}"
            logger.warning(
                "llm_proof[%s] attempt %d: copilot failed: %s",
                det_spec.function, i, e,
            )
            break
        attempt.llm_ms = int((time.monotonic() - t_llm) * 1000)
        (attempt_dir / "response.md").write_text(raw)

        # ----- 3. parse -----
        try:
            parsed = parse_proof_response(raw)
        except ProofParseError as e:
            attempt.status = "parse_failure"
            attempt.verus_stderr_tail = str(e)
            prior_block = None
            prior_failure_kind = "parse"
            prior_failure_detail = str(e)
            logger.info(
                "llm_proof[%s] attempt %d: parse error %s",
                det_spec.function, i, e,
            )
            continue
        attempt.proof_block = parsed.proof_block
        attempt.rationale = parsed.rationale

        # ----- 4. sandbox -----
        violations = scan_proof_block(parsed.proof_block)
        if violations:
            attempt.sandbox_violations = [v.__dict__ for v in violations]
            attempt.status = "sandbox_reject"
            formatted = format_violations(violations)
            prior_block = parsed.proof_block
            prior_failure_kind = "sandbox"
            prior_failure_detail = (
                "The proof block was rejected because it contains "
                "axiom-style constructs:\n" + formatted
            )
            logger.info(
                "llm_proof[%s] attempt %d: sandbox rejected (%d violations)",
                det_spec.function, i, len(violations),
            )
            continue

        # ----- 5. inject + re-run Verus -----
        try:
            code = _render_det_body_with_proof(det_spec, parsed.proof_block)
        except Exception as e:
            attempt.status = "verus_fail"
            attempt.verus_stderr_tail = (
                f"render error: {type(e).__name__}: {e}\n"
                + traceback.format_exc()[-800:]
            )
            prior_block = parsed.proof_block
            prior_failure_kind = "render"
            prior_failure_detail = attempt.verus_stderr_tail
            continue
        injected_text = _inject_into_source(source, code)
        rs_path = attempt_dir / f"{file_stem}.rs"
        rs_path.write_text(injected_text)
        log_dir = attempt_dir / "verus_log"
        log_dir.mkdir(exist_ok=True)

        rc, tail, dur = _run_verus(
            rs_path, verus_path, log_dir, timeout=timeout,
        )
        attempt.verus_returncode = rc
        attempt.verus_stderr_tail = tail
        attempt.verus_ms = dur

        if rc == 0:
            attempt.status = "verus_pass"
            result.success = True
            result.winning_proof_block = parsed.proof_block
            result.winning_rationale = parsed.rationale
            logger.info(
                "llm_proof[%s] attempt %d: Verus PASSED in %dms",
                det_spec.function, i, dur,
            )
            # Optionally promote into artifact_dir for post-mortem.
            if artifact_dir is not None:
                artifact_dir.mkdir(parents=True, exist_ok=True)
                (artifact_dir / "llm_proof.verus_pass.rs").write_text(injected_text)
                (artifact_dir / "llm_proof_block.txt").write_text(
                    parsed.proof_block
                )
            break

        attempt.status = "verus_fail"
        prior_block = parsed.proof_block
        prior_failure_kind = "verus"
        prior_failure_detail = tail
        logger.info(
            "llm_proof[%s] attempt %d: Verus rejected (%d, %dms)",
            det_spec.function, i, rc, dur,
        )

    result.total_ms = int((time.monotonic() - t_total) * 1000)

    # Always dump the result json for post-mortem.
    (work_root / "result.json").write_text(
        __import__("json").dumps(result.to_dict(), indent=2, default=str)
    )

    return result
