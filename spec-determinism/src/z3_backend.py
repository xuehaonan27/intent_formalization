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

from .types import VerifyResult, DetCheckSpec, Witness, ConcreteValue, Symbol
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

    def set_det_spec(self, det_spec: DetCheckSpec) -> None:
        """Derive `tracked_symbols` from a DetCheckSpec.

        Each top-level symbol (variables like `number_of_bits`, `r1`, `r2`,
        `pre_self_`, `post1_self_`, `post2_self_`) maps to a Verus SMT
        binding of the form `<name>!`. Projection-style symbols (those
        containing `@` or `.`) refer to sub-fields of a view and are not
        bound as their own SMT variable, so we skip them.
        """
        self.tracked_symbols = tracked_symbols_from_det_spec(det_spec)

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


# ---------------------------------------------------------------------------
# DetCheckSpec integration — binary_search short-circuit path
# ---------------------------------------------------------------------------

def tracked_symbols_from_det_spec(det_spec: DetCheckSpec) -> list[str]:
    """Derive the SMT-level symbol names to read out of a Z3 model.

    The `DetCheckSpec.symbols` list contains narrowing symbols; some are
    Verus-bound top-level vars (e.g. `number_of_bits`, `r1`, `r2`,
    `pre_self_`, `post1_self_`) and some are projections of those
    (e.g. `pre_self_@.num_bits`). Only the top-level ones have a
    `<name>!` binding in the SMT transcript, so we keep just those.
    """
    out: list[str] = []
    seen: set[str] = set()
    for s in det_spec.symbols:
        # Projection symbols contain "@" (view) or "." (field access).
        if "@" in s.name or "." in s.name:
            continue
        sym = s.name + "!"
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def _classify_symbol(name: str) -> tuple[str, str]:
    """Return (bucket, clean_var_name) for a DetCheckSpec symbol name.

    bucket ∈ {"input", "output1", "output2"}.
    """
    if name.startswith("post1_"):
        return ("output1", name[len("post1_"):])
    if name.startswith("post2_"):
        return ("output2", name[len("post2_"):])
    if name == "r1":
        return ("output1", "r1")
    if name == "r2":
        return ("output2", "r2")
    # `pre_self_`, plain params → input
    if name.startswith("pre_"):
        return ("input", name[len("pre_"):])
    return ("input", name)


def witness_from_model(
    det_spec: DetCheckSpec,
    model: dict[str, tuple[str, str]],
    trace: list[dict] | None = None,
) -> Witness | None:
    """Build a `Witness` from a Z3 model if it covers every top-level
    symbol in `det_spec`.

    Returns None if the model is missing any tracked symbol — in that
    case the caller should fall back to binary-search narrowing so
    that the witness is complete.
    """
    tracked = tracked_symbols_from_det_spec(det_spec)
    missing = [s for s in tracked if s not in model]
    if missing:
        logger.info(
            f"Z3 model missing {len(missing)}/{len(tracked)} symbols: "
            f"{missing[:5]}{'...' if len(missing) > 5 else ''}"
        )
        return None

    pretty = summarise_model(model)

    inputs: dict[str, ConcreteValue] = {}
    output1: dict[str, ConcreteValue] = {}
    output2: dict[str, ConcreteValue] = {}

    for s in det_spec.symbols:
        if "@" in s.name or "." in s.name:
            continue
        smt_name = s.name + "!"
        mv = model.get(smt_name)
        if mv is None:
            continue
        sort, raw = mv
        human = pretty.get(smt_name, raw)
        cv = ConcreteValue(
            var_name=s.name,
            type_name=s.type.name,
            fields={},
            raw=human,
        )
        bucket, clean = _classify_symbol(s.name)
        target = {"input": inputs, "output1": output1, "output2": output2}[bucket]
        target[clean] = cv

    # Identify whether the two outputs structurally differ in their
    # human-readable Z3 summary — this is a strong signal.
    gap_desc = ""
    # Pair r1↔r2 and post1_X↔post2_X (keyed under the same clean name
    # in output1 / output2).
    for key in list(output1):
        if key in output2 and output1[key].raw != output2[key].raw:
            gap_desc = (
                f"{key}: {output1[key].raw} vs {output2[key].raw}"
            )
            break
    if not gap_desc:
        # r1/r2 are bucketed under their own clean names ("r1" and "r2"
        # respectively). Compare them explicitly as a final resort.
        v1 = output1.get("r1")
        v2 = output2.get("r2")
        if v1 is not None and v2 is not None and v1.raw != v2.raw:
            gap_desc = f"return value: {v1.raw} vs {v2.raw}"

    return Witness(
        function=det_spec.function,
        inputs=inputs,
        output1=output1,
        output2=output2,
        trace=trace or [],
        gap_type="z3_model",
        gap_description=gap_desc,
    )
