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
  6. Verus accepts → success (``complete_llm`` at the caller's level).
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
from .sandbox import (
    SandboxViolation, format_violations, scan_helper_lemmas, scan_proof_block,
)
from .cache import (
    CacheMode, CachedProof, compute_cache_key, compute_shape_key,
    default_artifact_key, default_safe_name,
    find_by_shape, load as cache_load, save as cache_save, utc_now_iso,
)

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
    helper_lemmas: str = ""
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
    winning_helper_lemmas: str = ""
    total_ms: int = 0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "attempts": [a.to_dict() for a in self.attempts],
            "winning_proof_block": self.winning_proof_block,
            "winning_rationale": self.winning_rationale,
            "winning_helper_lemmas": self.winning_helper_lemmas,
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


def _find_verus_block_close(source: str) -> int:
    """Return index of the closing ``}`` of the outermost ``verus! { ... }``.

    Returns ``-1`` if no ``verus! { ... }`` block is found. The scanner is
    aware of line comments, block comments, string literals, char literals
    and raw strings so braces inside those constructs do not perturb the
    balance count.
    """
    m = re.search(r"\bverus\s*!\s*\{", source)
    if not m:
        return -1
    i = m.end()
    depth = 1
    n = len(source)
    while i < n and depth > 0:
        c = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            nl = source.find("\n", i + 2)
            i = n if nl == -1 else nl + 1
            continue
        if c == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if c == "r" and (nxt == '"' or nxt == "#"):
            j = i + 1
            hashes = 0
            while j < n and source[j] == "#":
                hashes += 1
                j += 1
            if j < n and source[j] == '"':
                close = '"' + ("#" * hashes)
                end = source.find(close, j + 1)
                i = n if end == -1 else end + len(close)
                continue
        if c == '"':
            j = i + 1
            while j < n:
                if source[j] == "\\":
                    j += 2
                    continue
                if source[j] == '"':
                    j += 1
                    break
                j += 1
            i = j
            continue
        if c == "'":
            j = i + 1
            if j < n and source[j] == "\\":
                j += 2
            else:
                j += 1
            if j < n and source[j] == "'":
                i = j + 1
                continue
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _inject_into_source(source: str, code: str) -> str:
    """Insert det-check code just before the closing ``}`` of ``verus!{}``.

    Falls back to the last ``}`` in the source if no ``verus! { ... }``
    block is found (some files put everything at module scope).
    """
    cleaned = _strip_injected(source)
    idx = _find_verus_block_close(cleaned)
    if idx == -1:
        idx = cleaned.rfind("}")
    if idx == -1:
        raise ValueError("No closing `}` found in source")
    return (
        cleaned[:idx]
        + "\n" + _INJECT_BEGIN + code + "\n" + _INJECT_END + "\n"
        + cleaned[idx:]
    )


# ---------------------------------------------------------------------------
# Helper-lemma injection (Pattern A).
# ---------------------------------------------------------------------------
# When the LLM emits one or more ``proof fn lemma_*(...)`` declarations as
# helpers, they must be inserted at module scope (inside ``verus!{ ... }``)
# alongside ``det_<f>``, NOT inside ``det_<f>``. The det-check ``proof_block``
# can then ``call lemma_*(args)`` directly.
#
# The block we splice in lives in its own marker section so a later run on
# the same source is idempotent. We inject it just before the existing
# INJECTED DET CHECK block (so reading top-to-bottom: helpers, then the
# det-check that uses them).

_HELPER_BEGIN = "// === INJECTED HELPER LEMMAS ===\n"
_HELPER_END = "// === END INJECTED HELPERS ===\n"


def _strip_helper_lemmas(source: str) -> str:
    """Idempotently remove any prior helper-lemma block."""
    pat = re.compile(
        r"\n*"
        + re.escape(_HELPER_BEGIN)
        + r".*?"
        + re.escape(_HELPER_END)
        + r"\n*",
        re.DOTALL,
    )
    return pat.sub("\n", source)


def _inject_helper_lemmas(source: str, lemmas: str) -> str:
    """Insert helper proof fn declarations at module scope inside verus!{}.

    Empty ``lemmas`` is a no-op (returns ``_strip_helper_lemmas`` of the
    input to keep idempotency).
    """
    cleaned = _strip_helper_lemmas(source)
    if not lemmas or not lemmas.strip():
        return cleaned
    # Splice before the closing `}` of `verus!{ ... }`. The det-check
    # marker (if already present) lives later in the file; we land
    # before it. Find the verus! block close and back up over any prior
    # INJECTED DET CHECK block so helpers come first.
    idx = _find_verus_block_close(cleaned)
    if idx == -1:
        idx = cleaned.rfind("}")
    if idx == -1:
        raise ValueError("No closing `}` found in source")
    inj_marker = cleaned.rfind(_INJECT_BEGIN)
    insert_at = inj_marker if 0 <= inj_marker < idx else idx
    return (
        cleaned[:insert_at]
        + "\n" + _HELPER_BEGIN + lemmas.strip() + "\n" + _HELPER_END + "\n"
        + cleaned[insert_at:]
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
# Agentic mode adapter — keeps the rest of single_file.py mode-agnostic.
# ---------------------------------------------------------------------------


def _run_agentic_and_wrap(
    *,
    det_spec: DetCheckSpec,
    fn_spec: Optional[FunctionSpec],
    source: str,
    verus_path: str,
    work_root: Path,
    artifact_dir: Optional[Path],
    artifact_key: Optional[str],
    session_timeout: int,
    verus_timeout: int,
    cache_dir: Optional[Path],
    cache_mode: CacheMode,
    file: str,
    t_total: float,
    source_project_root: Optional[Path] = None,
    source_file_path: Optional[Path] = None,
) -> ProofResult:
    """Run one agentic Copilot CLI session and project the outcome into
    the existing :class:`ProofResult` shape so downstream tooling
    (single_file.py, summary builders) is mode-agnostic.
    """
    from .agentic import run_agentic_session  # local import to avoid cycle

    outcome = run_agentic_session(
        det_spec=det_spec,
        fn_spec=fn_spec,
        source=source,
        verus_path=verus_path,
        work_root=work_root,
        session_timeout=session_timeout,
        verus_timeout=verus_timeout,
        sandbox_scan=scan_proof_block,
        file_stem=file,
        source_project_root=source_project_root,
        source_file_path=source_file_path,
    )

    # Project into the existing single-shot record types so the rest of
    # the pipeline doesn't have to special-case mode.
    sess = outcome.session
    attempt = ProofAttempt(
        iteration=1,
        proof_block=outcome.final_proof_block,
        rationale=sess.agent_notes,
        sandbox_violations=outcome.sandbox_violations,
        verus_returncode=outcome.verus_returncode,
        verus_stderr_tail=outcome.verus_stderr_tail,
        verus_ms=outcome.verus_ms,
        llm_ms=sess.cli_ms,
        status=outcome.status,
    )
    success = (outcome.status == "verus_pass")
    result = ProofResult(
        success=success,
        attempts=[attempt],
        winning_proof_block=outcome.final_proof_block if success else "",
        winning_rationale=sess.agent_notes if success else "",
        total_ms=int((time.monotonic() - t_total) * 1000),
        notes=(
            "agentic_session"
            + (f":iters={sess.agent_iterations}" if sess.agent_iterations is not None else "")
        ),
    )

    # Persist the agent's own session record for post-mortem debugging.
    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "agentic_outcome.json").write_text(
            __import__("json").dumps(outcome.to_dict(), indent=2, default=str)
        )
        if outcome.final_proof_block:
            (artifact_dir / "llm_proof_block.txt").write_text(outcome.final_proof_block)
    (work_root / "result.json").write_text(
        __import__("json").dumps(result.to_dict(), indent=2, default=str)
    )

    # Cache write (mirrors the single-shot post-loop write).
    if cache_dir is not None and cache_mode is not CacheMode.BYPASS:
        try:
            cache_key = compute_cache_key(det_spec, source)
            shape_key = compute_shape_key(det_spec)
            entry = CachedProof(
                cache_key=cache_key,
                shape_key=shape_key,
                function=det_spec.function or "",
                file=file,
                status=outcome.status,
                proof_block=outcome.final_proof_block,
                rationale=sess.agent_notes,
                attempts=1,
                saved_at=utc_now_iso(),
                verus_ms=outcome.verus_ms,
                verus_stderr_tail=outcome.verus_stderr_tail[-2000:] if outcome.verus_stderr_tail else "",
            )
            cache_save(cache_dir, entry)
        except Exception as e:
            logger.warning("agentic cache write failed for %s: %s", det_spec.function, e)

    return result


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
    cache_dir: Optional[Path] = None,
    cache_mode: CacheMode = CacheMode.USE,
    artifact_key: Optional[str] = None,
    llm_timeout: Optional[int] = None,
    mode: str = "single_shot",
    session_timeout: int = 1800,
    source_project_root: Optional[Path] = None,
    source_file_path: Optional[Path] = None,
) -> ProofResult:
    """Run the LLM proof loop in either single-shot or agentic mode.

    Returns a :class:`ProofResult`. The caller decides how to fold the
    result into its existing per-target dict (e.g. set ``r0_z3='unsat'``
    on success and add ``llm_assisted=True``).

    Persistent cache
    ----------------
    When ``cache_dir`` is provided and ``cache_mode != BYPASS`` we store
    the final outcome (pass or fail) to
    ``<cache_dir>/<artifact_key>.json`` keyed by
    ``hash(det_spec, source)``. A subsequent run with mode ``USE`` and
    a cache hit:

      * **status=verus_pass**: re-verify the cached proof_block against
        the current source via Verus. If Verus still accepts → return
        a single synthetic ``ProofAttempt`` with status=verus_pass and
        skip the LLM. If Verus rejects → log "stale cache", fall through
        to a fresh LLM loop.
      * **status != verus_pass**: trust the prior negative result and
        return immediately without spending LLM tokens. Use mode
        ``REFRESH`` to bypass this and retry.

    ``cache_mode = REFRESH`` always ignores prior entries and overwrites.
    ``cache_mode = BYPASS`` neither reads nor writes the cache.
    """
    t_total = time.monotonic()
    work_root.mkdir(parents=True, exist_ok=True)

    # --- cache check ---
    cache_key = compute_cache_key(det_spec, source)
    shape_key = compute_shape_key(det_spec)
    if artifact_key is None:
        artifact_key = default_artifact_key(det_spec, source)
    cache_hit: Optional[CachedProof] = None
    if cache_dir is not None and cache_mode is not CacheMode.BYPASS:
        cache_hit = cache_load(cache_dir, artifact_key)
        if cache_hit is not None and cache_hit.cache_key != cache_key:
            logger.info(
                "llm_proof[%s] cache: key mismatch (artifact_key=%s, stale entry); ignoring",
                det_spec.function, artifact_key,
            )
            cache_hit = None

    def _try_cached_proof(
        cached: CachedProof,
        label: str,
        work_subdir: str,
    ) -> Optional[ProofResult]:
        """Re-verify a cached proof against the current source.

        Returns a SUCCESS :class:`ProofResult` if Verus accepts (also
        promotes the entry into ``cache_dir`` under the current
        ``artifact_key`` if a shape-fallback replay succeeds, so future
        runs can hit the fast path). Returns ``None`` on stale/sandbox
        failure so the caller can fall through to the LLM loop.
        """
        # Sandbox scan first (in case allowlist tightened).
        violations = scan_proof_block(cached.proof_block)
        if violations:
            logger.warning(
                "llm_proof[%s] %s: cached proof now fails sandbox; falling through",
                det_spec.function, label,
            )
            return None
        helper_lemmas = (cached.helper_lemmas or "").strip()
        if helper_lemmas:
            # Pattern A re-verify path: lemmas live as module-scope
            # siblings of det_<f>, so they go directly into the
            # source before re-injecting det_<f> into the same slot.
            inj_source = _inject_helper_lemmas(source, helper_lemmas)
        else:
            inj_source = source
        try:
            code = _render_det_body_with_proof(det_spec, cached.proof_block)
            injected_text = _inject_into_source(inj_source, code)
        except Exception as e:
            logger.warning(
                "llm_proof[%s] %s render failed: %s; falling through",
                det_spec.function, label, e,
            )
            return None
        verify_dir = work_root / work_subdir
        verify_dir.mkdir(exist_ok=True)
        rs_path = verify_dir / f"{file_stem}.rs"
        rs_path.write_text(injected_text)
        log_dir = verify_dir / "verus_log"
        log_dir.mkdir(exist_ok=True)
        try:
            rc, tail, dur = _run_verus(
                rs_path, verus_path, log_dir, timeout=timeout,
            )
        except Exception as e:
            logger.warning(
                "llm_proof[%s] %s verus run crashed: %s; falling through",
                det_spec.function, label, e,
            )
            return None
        if rc != 0:
            logger.info(
                "llm_proof[%s] %s stale (Verus rc=%d); falling through",
                det_spec.function, label, rc,
            )
            return None
        att = ProofAttempt(
            iteration=0,
            proof_block=cached.proof_block,
            rationale=cached.rationale,
            verus_returncode=0,
            verus_stderr_tail=tail,
            verus_ms=dur,
            status="verus_pass",
        )
        result = ProofResult(
            success=True,
            attempts=[att],
            winning_proof_block=cached.proof_block,
            winning_rationale=cached.rationale,
            total_ms=int((time.monotonic() - t_total) * 1000),
            notes=label,
        )
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "llm_proof.verus_pass.rs").write_text(injected_text)
            (artifact_dir / "llm_proof_block.txt").write_text(cached.proof_block)
            if helper_lemmas:
                (artifact_dir / "llm_proof_helpers.txt").write_text(helper_lemmas)
        (work_root / "result.json").write_text(
            __import__("json").dumps(result.to_dict(), indent=2, default=str)
        )
        logger.info(
            "llm_proof[%s] %s re-verified in %dms (LLM skipped)",
            det_spec.function, label, dur,
        )
        # If this was a shape-fallback hit, promote it to a real entry
        # under the current artifact_key so the direct path catches it
        # next time. Use the current cache_key / shape_key.
        if (
            cache_dir is not None
            and cache_mode is not CacheMode.BYPASS
            and label.startswith("shape_fallback")
        ):
            promoted = CachedProof(
                cache_key=cache_key,
                shape_key=shape_key,
                function=det_spec.function,
                file=file_stem,
                status="verus_pass",
                proof_block=cached.proof_block,
                rationale=cached.rationale,
                attempts=1,
                saved_at=utc_now_iso(),
                verus_ms=dur,
                helper_lemmas=helper_lemmas,
            )
            try:
                cache_save(cache_dir, promoted)
            except Exception as e:
                logger.warning(
                    "llm_proof[%s] cache promote failed: %s",
                    det_spec.function, e,
                )
        return result

    if cache_hit is not None and cache_mode is CacheMode.USE:
        if cache_hit.status == "verus_pass":
            logger.info("llm_proof[%s] cache hit (verus_pass) — re-verifying",
                        det_spec.function)
            try:
                r = _try_cached_proof(cache_hit, "cache_hit_verified", "cache_verify")
            except Exception as e:
                logger.warning(
                    "llm_proof[%s] cache re-verify crashed: %s; re-running LLM",
                    det_spec.function, e,
                )
                r = None
            if r is not None:
                return r
        else:
            # Negative cache hit on the exact artifact_key — skip LLM
            # entirely (use mode=refresh to retry). Pattern E still gets
            # a chance below to find a same-shape pass from another target.
            logger.info(
                "llm_proof[%s] cache hit (status=%s) — checking shape fallback before giving up",
                det_spec.function, cache_hit.status,
            )

    # --- Pattern E: shape-key fallback ---
    # Trigger when we have no positive direct hit yet. Specifically:
    #   * direct hit missing or non-verus_pass; AND
    #   * mode is USE (REFRESH explicitly wants a fresh LLM call).
    # Soundness rests on the re-verify inside ``_try_cached_proof``: we
    # never accept a shape-matched proof without Verus checking it
    # against THIS source.
    if (
        cache_dir is not None
        and cache_mode is CacheMode.USE
    ):
        try:
            hit = find_by_shape(
                cache_dir, shape_key,
                function=det_spec.function, require_pass=True,
            )
        except Exception as e:
            logger.warning(
                "llm_proof[%s] shape fallback scan crashed: %s",
                det_spec.function, e,
            )
            hit = None
        if hit is not None and hit.entry.cache_key != cache_key:
            logger.info(
                "llm_proof[%s] shape fallback: trying proof from %s (cache_key=%s)",
                det_spec.function, hit.path.name, hit.entry.cache_key[:16],
            )
            try:
                r = _try_cached_proof(
                    hit.entry, "shape_fallback_verified", "shape_verify",
                )
            except Exception as e:
                logger.warning(
                    "llm_proof[%s] shape fallback re-verify crashed: %s",
                    det_spec.function, e,
                )
                r = None
            if r is not None:
                return r

    # No fast path worked. If the negative direct hit was the reason we
    # got here AND mode is USE (no shape pass either), respect the
    # original "negative cache short-circuit" semantics.
    if (
        cache_hit is not None
        and cache_mode is CacheMode.USE
        and cache_hit.status != "verus_pass"
    ):
        logger.info(
            "llm_proof[%s] no shape fallback found; honouring negative cache",
            det_spec.function,
        )
        att = ProofAttempt(
            iteration=0,
            proof_block=cache_hit.proof_block,
            rationale=cache_hit.rationale,
            verus_returncode=None,
            verus_stderr_tail=cache_hit.verus_stderr_tail,
            verus_ms=cache_hit.verus_ms,
            status=cache_hit.status,
        )
        result = ProofResult(
            success=False,
            attempts=[att],
            total_ms=int((time.monotonic() - t_total) * 1000),
            notes="cache_hit_negative",
        )
        (work_root / "result.json").write_text(
            __import__("json").dumps(result.to_dict(), indent=2, default=str)
        )
        return result

    # ===========================================================
    # Mode dispatch: single_shot (default, the original loop) or
    # agentic (one Copilot-CLI session per target, the new path).
    # ===========================================================
    if mode == "agentic":
        return _run_agentic_and_wrap(
            det_spec=det_spec, fn_spec=fn_spec, source=source,
            verus_path=verus_path, work_root=work_root,
            artifact_dir=artifact_dir, artifact_key=artifact_key,
            session_timeout=session_timeout, verus_timeout=timeout,
            cache_dir=cache_dir, cache_mode=cache_mode, file=file_stem,
            t_total=t_total,
            source_project_root=source_project_root,
            source_file_path=source_file_path,
        )
    if mode != "single_shot":
        raise ValueError(
            f"unknown llm_proof mode: {mode!r} (allowed: single_shot, agentic)"
        )

    # Build LLM client lazily; CLI cost is one process spawn per attempt.
    client = CopilotCLI(
        model=model,
        reasoning_effort=reasoning_effort,
        timeout=llm_timeout if llm_timeout is not None else max(timeout, 600),
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
        attempt.helper_lemmas = parsed.helper_lemmas

        # ----- 4. sandbox -----
        violations = scan_proof_block(parsed.proof_block)
        if parsed.helper_lemmas.strip():
            violations += scan_helper_lemmas(parsed.helper_lemmas)
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
        # Splice helper lemmas (Pattern A) at module scope first if present.
        if parsed.helper_lemmas.strip():
            inj_source = _inject_helper_lemmas(source, parsed.helper_lemmas)
        else:
            inj_source = source
        injected_text = _inject_into_source(inj_source, code)
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
            result.winning_helper_lemmas = parsed.helper_lemmas
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
                if parsed.helper_lemmas.strip():
                    (artifact_dir / "llm_proof_helpers.txt").write_text(
                        parsed.helper_lemmas
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

    # Persist to cache (USE / REFRESH; never on BYPASS).
    if cache_dir is not None and cache_mode is not CacheMode.BYPASS:
        last = result.attempts[-1] if result.attempts else None
        entry = CachedProof(
            cache_key=cache_key,
            shape_key=shape_key,
            function=det_spec.function,
            file=file_stem,
            status=(last.status if last else "init"),
            proof_block=(
                result.winning_proof_block
                if result.success
                else (last.proof_block if last else "")
            ),
            rationale=(
                result.winning_rationale
                if result.success
                else (last.rationale if last else "")
            ),
            helper_lemmas=(
                result.winning_helper_lemmas
                if result.success
                else (last.helper_lemmas if last else "")
            ),
            attempts=len(result.attempts),
            saved_at=utc_now_iso(),
            verus_ms=(last.verus_ms if last else 0),
            verus_stderr_tail=(
                "" if result.success
                else (last.verus_stderr_tail if last else "")
            ),
        )
        try:
            cache_save(cache_dir, entry)
        except Exception as e:
            logger.warning(
                "llm_proof[%s] cache write failed: %s", det_spec.function, e,
            )

    return result
