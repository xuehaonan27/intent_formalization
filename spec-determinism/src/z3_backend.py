"""
Z3Backend — determinism oracle built on Verus's SMT transcript.

Pipeline per `check()` call:

  1. Inject the generated `det_<name>` proof fn into the target crate
     (same as VerusRunner).
  2. Run `cargo verus verify ... --log smt-transcript`. This forces
     Verus to log the full SMT session (declarations, axioms, the
     negated proof goal, `(check-sat)`, and — if the check fails —
     the `(get-model)` response that Z3 produced).
  3. Parse the transcript. If the transcript contains a sat/unknown
     check-sat followed by a non-empty model, extract the concrete
     values for our tracked symbols (`number_of_bits!`, `r1!`, `r2!`,
     `old(self)!`, `post1_*!`, `post2_*!`, etc.).
  4. Return a VerifyResult augmented with a raw `.model` dict so the
     search driver can short-circuit the narrowing loop when a full
     witness is already available.

This backend is *strictly a fast path*:

  - If the proof obligation passes → VerifyResult(status="pass",
    model=None). Search terminates normally.
  - If it fails and a usable model was extracted → VerifyResult(
    status="fail", model=<witness dict>). Caller can publish the
    witness directly instead of narrowing.
  - If it fails but no model could be parsed (e.g. Z3 returned
    `unknown` without dumping one) → VerifyResult(status="fail",
    model=None). Caller falls back to structural narrowing.

The backend does NOT re-run Z3 itself for the first cut; Verus's own
get-model response is reused verbatim. Later iterations may add
targeted `(get-value)` probes for payloads left as uninterpreted
constants (e.g. `Poly!val!4` inside `Err(_)`).
"""

import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .types import VerifyResult
from .verify import inject_proof_fn, restore_file, run_cargo_verus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------

_RE_RESPONSE = re.compile(
    r";;;>>> RESPONSE\n(.*?)\n;;;<<<", re.DOTALL
)
_RE_GET_MODEL_RESPONSE = re.compile(
    r";;;>>> QUERY\n\(get-model\)\n;;;<<<\n;;;>>> RESPONSE\n(.*?)\n;;;<<<",
    re.DOTALL,
)
_RE_CHECK_SAT_RESPONSE = re.compile(
    r"\(check-sat\)\n;;;<<<\n;;;>>> RESPONSE\n(sat|unsat|unknown)\n",
)


def _lookup_model_value(model_body: str, name: str) -> tuple[str, str] | None:
    """
    Find `(define-fun NAME () SORT VALUE)` in a Z3 model body and return
    `(sort, value_string)`. `VALUE` may be a nested s-expression.
    """
    pat = rf"\(define-fun {re.escape(name)} \(\) (\S+)\s+"
    m = re.search(pat, model_body)
    if not m:
        return None
    sort = m.group(1)
    i = m.end()
    # skip leading whitespace
    while i < len(model_body) and model_body[i] in " \n\t":
        i += 1
    if i >= len(model_body):
        return None
    if model_body[i] == "(":
        depth = 1
        j = i + 1
        while depth and j < len(model_body):
            if model_body[j] == "(":
                depth += 1
            elif model_body[j] == ")":
                depth -= 1
            j += 1
        value = model_body[i:j]
    else:
        j = i
        while j < len(model_body) and model_body[j] not in " )\n\t":
            j += 1
        value = model_body[i:j]
    return (sort, value.strip())


def parse_check_result(transcript: str) -> str:
    """
    Return 'sat', 'unsat', 'unknown', or 'missing' based on the last
    (check-sat) response in the transcript.
    """
    responses = _RE_CHECK_SAT_RESPONSE.findall(transcript)
    if not responses:
        return "missing"
    # Return the first non-unsat if any (Verus often has a cache warm-up
    # check that is unsat, followed by the real check).
    for r in responses:
        if r != "unsat":
            return r
    return "unsat"


def extract_model(transcript: str, symbols: list[str]) -> dict[str, tuple[str, str]]:
    """
    Find the (get-model) response in the transcript and look up each
    symbol name in it. Missing symbols are silently dropped.

    Returns dict {symbol_name: (sort, value_string)}.
    """
    m = _RE_GET_MODEL_RESPONSE.search(transcript)
    if not m:
        return {}
    body = m.group(1)
    out: dict[str, tuple[str, str]] = {}
    for name in symbols:
        r = _lookup_model_value(body, name)
        if r is not None:
            out[name] = r
    return out


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

@dataclass
class Z3VerifyResult:
    """VerifyResult + raw Z3 model for tracked symbols."""

    status: str
    function: str
    duration_ms: int = 0
    stderr: str = ""
    model: dict[str, tuple[str, str]] = field(default_factory=dict)
    transcript_path: str = ""


class Z3Backend:
    """
    Drop-in replacement for VerusRunner that captures Z3's model on failure.

    Same constructor signature as VerusRunner plus `tracked_symbols`
    (the set of SMT-level names whose values we want to read out of any
    get-model response).
    """

    def __init__(
        self,
        crate_dir: str,
        crate_name: str,
        verus_path: str,
        proof_file: str,
        marker: str = "} // end verus!",
        features: list[str] | None = None,
        timeout: int = 180,
        verify_module: str | None = None,
        log_dir: str | None = None,
        tracked_symbols: list[str] | None = None,
    ):
        self.crate_dir = crate_dir
        self.crate_name = crate_name
        self.verus_path = verus_path
        self.proof_file = proof_file
        self.marker = marker
        self.features = features
        self.timeout = timeout
        self.verify_module = verify_module
        self.log_dir = log_dir or "/tmp/verus-log"
        self.tracked_symbols = tracked_symbols or []
        self.call_count = 0
        self._last_result: Z3VerifyResult | None = None

    # -------------------------------------------------------------------
    # DetBackend.check
    # -------------------------------------------------------------------

    def check(self, code: str, fn_name: str) -> VerifyResult:
        """
        Run Verus on the injected det_<fn> and return a VerifyResult.
        The Z3 model (if any) is stashed on self._last_result for the
        search driver to pick up.
        """
        z3res = self.check_with_model(code, fn_name)
        self._last_result = z3res
        return VerifyResult(
            status=z3res.status,
            function=z3res.function,
            duration_ms=z3res.duration_ms,
            stderr=z3res.stderr,
        )

    @property
    def last_model(self) -> dict[str, tuple[str, str]]:
        """Model captured by the most recent `check()` call (empty if pass)."""
        return self._last_result.model if self._last_result else {}

    # -------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------

    def check_with_model(self, code: str, fn_name: str) -> Z3VerifyResult:
        self.call_count += 1

        # Clean the log dir so we don't mis-parse a previous run.
        log_dir = Path(self.log_dir)
        if log_dir.exists():
            for f in log_dir.iterdir():
                if f.is_file():
                    f.unlink()
        log_dir.mkdir(parents=True, exist_ok=True)

        original = inject_proof_fn(self.proof_file, code, marker=self.marker)
        t0 = time.monotonic()
        try:
            raw = run_cargo_verus(
                crate_dir=self.crate_dir,
                crate_name=self.crate_name,
                verus_path=self.verus_path,
                features=self.features,
                timeout=self.timeout,
                extra_args=None,
                verus_extra_args=[
                    "--log-dir", str(log_dir),
                    "--log", "smt-transcript",
                ],
                verify_module=self.verify_module,
                verify_function=fn_name,
                use_build=False,   # build does not emit smt-transcript reliably
            )
        finally:
            restore_file(self.proof_file, original)

        duration_ms = int((time.monotonic() - t0) * 1000)

        if raw["returncode"] == -1:
            return Z3VerifyResult(
                status="timeout", function=fn_name,
                duration_ms=duration_ms, stderr=raw["stderr"],
            )

        # Find the transcript. Verus names it `root.smt_transcript` for
        # root-module queries.
        transcripts = sorted(log_dir.glob("*.smt_transcript"),
                             key=lambda p: p.stat().st_size, reverse=True)
        if not transcripts:
            logger.warning("no smt_transcript produced")
            return Z3VerifyResult(
                status="error", function=fn_name,
                duration_ms=duration_ms,
                stderr="no smt_transcript produced",
            )
        transcript_path = transcripts[0]
        transcript = transcript_path.read_text()

        check_result = parse_check_result(transcript)
        # 'unsat' on the *final, rlimit-bounded* check means det proved.
        # 'sat' / 'unknown' both mean failure; the model is extractable.
        if check_result == "unsat":
            return Z3VerifyResult(
                status="pass", function=fn_name,
                duration_ms=duration_ms,
                transcript_path=str(transcript_path),
            )

        model = extract_model(transcript, self.tracked_symbols)
        return Z3VerifyResult(
            status="fail", function=fn_name,
            duration_ms=duration_ms,
            stderr=f"check-sat={check_result}",
            model=model,
            transcript_path=str(transcript_path),
        )


# ---------------------------------------------------------------------------
# Witness rendering
# ---------------------------------------------------------------------------

_RE_RESULT_VARIANT = re.compile(r"\((\S+/(?:Ok|Err))\s+")
_RE_INT = re.compile(r"^-?\d+$")


def summarise_model(model: dict[str, tuple[str, str]]) -> dict[str, str]:
    """
    Compress the raw `{name: (sort, value)}` Z3 model into a human-readable
    witness string per symbol. Currently recognises:
      - Int constants → decimal
      - Result variant discriminator → "Ok(..)" / "Err(..)"
      - Opaque Poly!val!N and core!result.Result./Ok/Err payloads are kept
        as-is (spec doesn't pin these; fall-through ok).

    Unknown values fall through as-is — they are still informative.
    """
    out: dict[str, str] = {}
    for name, (sort, value) in model.items():
        v = value
        if sort == "Int" and _RE_INT.match(v):
            out[name] = v
        elif "result.Result." in sort:
            m = _RE_RESULT_VARIANT.match(v)
            if m:
                tag = m.group(1).rsplit("/", 1)[-1]
                out[name] = f"{tag}(<opaque>)"
            else:
                out[name] = v
        else:
            out[name] = v
    return out
