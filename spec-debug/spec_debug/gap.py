"""Witness / gap types.

v0 keeps this simple: a Witness bundles what spec-determinism emitted for a
single function run. No AST-level gap extraction yet — the prompt layer will
hand the raw assumes list to the LLM verbatim.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from spec_determinism.config import CorpusConfig, CrateConfig


@dataclass
class Witness:
    crate: str
    function: str
    det_fn: str
    assumes: list[str]
    n_rounds: int
    n_schemas: int
    status: str
    # Artifact context (best-effort; may be None if artifact is missing).
    symbols: list[Any] | None = None
    equal_fn_def: str | None = None
    equal_fn_name: str | None = None
    det_check_template: str | None = None
    equal_policy: dict[str, Any] = field(default_factory=dict)
    raw_full_run: dict[str, Any] = field(default_factory=dict)
    raw_det_spec: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        return f"{self.crate}::{self.function}"

    def has_gap(self) -> bool:
        return bool(self.assumes)


@dataclass
class ClassifiedAssumes:
    """Result of `classify_assumes`: assumes grouped by policy-relevance.

    Heuristic, string-based. Good enough for v0 prompting; not a replacement
    for SMT reasoning.
    """
    input_narrowing: list[str]       # no ref to r1/r2 — just example input values
    discriminant: list[str]          # `r{1,2} is {Ok,Err}`
    driving_ok: list[str]            # r*->Ok_0... that actually contributes to !equal
    driving_err: list[str]           # r*->Err_0... that actually contributes to !equal
    collateral_ok: list[str]         # r*->Ok_0... ignored by policy (opaque_ok=True)
    collateral_err: list[str]        # r*->Err_0... ignored by policy (errs_equivalent=True)
    result_assertion: list[str]      # `!det_*_equal(r1, r2)`
    gap_summary: str                 # one-line human description


def _refs_r(s: str, which: str) -> bool:
    # which in {"r1", "r2"} or "r". True if the assume references that symbol.
    import re
    return re.search(rf"\b{which}\b", s) is not None


def classify_assumes(assumes: list[str], policy: dict[str, Any]) -> ClassifiedAssumes:
    """Split a witness's committed assumes by whether the equal-fn policy
    actually consumes them.

    Logic:
      - `!det_*_equal(...)` → result_assertion.
      - No reference to r1 or r2 → input_narrowing.
      - `r{1,2} is Ok/Err` → discriminant (always driving).
      - `r{1,2}->Ok_0...` → driving_ok if opaque_ok=False, collateral_ok otherwise.
      - `r{1,2}->Err_0...` → driving_err if errs_equivalent=False, collateral_err otherwise.

    Additionally, if the discriminants show that r1 and r2 are on *different*
    sides (Ok vs Err), then !equal is forced by the discriminant alone and
    Ok/Err payload assumes become policy-collateral regardless of policy flags.
    We reflect that in gap_summary.
    """
    errs_eq = bool(policy.get("errs_equivalent", True))
    opaque_ok = bool(policy.get("opaque_ok", False))

    input_narrowing: list[str] = []
    discriminant: list[str] = []
    driving_ok: list[str] = []
    driving_err: list[str] = []
    collateral_ok: list[str] = []
    collateral_err: list[str] = []
    result_assertion: list[str] = []

    import re
    # discriminant patterns: "r1 is Ok", "r2 is Err"
    disc_re = re.compile(r"\br([12])\s+is\s+(Ok|Err)\b")
    r1_side: str | None = None
    r2_side: str | None = None

    for a in assumes:
        s = a.strip()
        if not s:
            continue
        if s.startswith("!") and "_equal" in s:
            result_assertion.append(a)
            continue
        m = disc_re.search(s)
        if m and "->" not in s:
            # pure discriminant line
            discriminant.append(a)
            if m.group(1) == "1":
                r1_side = m.group(2)
            else:
                r2_side = m.group(2)
            continue
        touches_r1 = _refs_r(s, "r1")
        touches_r2 = _refs_r(s, "r2")
        if not (touches_r1 or touches_r2):
            input_narrowing.append(a)
            continue
        # payload-level: check Ok_0 / Err_0 prefix
        if "->Ok_0" in s or ".Ok_0" in s:
            (driving_ok if not opaque_ok else collateral_ok).append(a)
        elif "->Err_0" in s or ".Err_0" in s:
            if errs_eq:
                collateral_err.append(a)
            else:
                driving_err.append(a)
        else:
            # unclassified r-reference; treat as driving conservatively
            driving_ok.append(a)

    # If discriminants differ, payload assumes become collateral relative to !equal.
    if r1_side and r2_side and r1_side != r2_side:
        collateral_ok.extend(driving_ok); driving_ok = []
        collateral_err.extend(driving_err); driving_err = []
        gap = f"r1 is {r1_side} && r2 is {r2_side} — discriminant mismatch alone forces !equal"
    else:
        parts = []
        if r1_side and r2_side and r1_side == r2_side:
            parts.append(f"both results are {r1_side}")
        if driving_ok:
            parts.append(f"{len(driving_ok)} Ok-payload difference(s)")
        if driving_err:
            parts.append(f"{len(driving_err)} Err-payload difference(s) (policy: errs_equivalent=False)")
        gap = "; ".join(parts) if parts else "gap shape unclear from committed assumes"

    return ClassifiedAssumes(
        input_narrowing=input_narrowing,
        discriminant=discriminant,
        driving_ok=driving_ok,
        driving_err=driving_err,
        collateral_ok=collateral_ok,
        collateral_err=collateral_err,
        result_assertion=result_assertion,
        gap_summary=gap,
    )


def _artifact_key(crate: str, function: str) -> str:
    return f"{crate}__{function}"


def load_witness(corpus: CorpusConfig, crate: str, function: str) -> Witness:
    """Load the latest witness for <crate>::<function> from spec-determinism outputs.

    Reads full_run.json for the committed assumes and per-artifact det_spec.json
    for symbol / equal-fn context.
    """
    full_run_path = corpus.full_run_path
    if not full_run_path.exists():
        raise FileNotFoundError(
            f"spec-determinism full_run.json not found at {full_run_path}. "
            f"Run spec-determinism-run {crate}::{function} first."
        )
    runs = json.loads(full_run_path.read_text())
    entry = None
    for e in runs:
        if e.get("crate") == crate and e.get("function") == function:
            entry = e
            break
    if entry is None:
        raise KeyError(
            f"{crate}::{function} not found in {full_run_path}. "
            f"Run spec-determinism-run {crate}::{function} first."
        )

    key = _artifact_key(crate, function)
    artifact_dir = corpus.artifacts_dir / key
    det_spec_path = artifact_dir / "det_spec.json"
    raw_det: dict[str, Any] = {}
    if det_spec_path.exists():
        raw_det = json.loads(det_spec_path.read_text())

    return Witness(
        crate=crate,
        function=function,
        det_fn=entry.get("det_fn", f"det_{function}"),
        assumes=list(entry.get("assumes", [])),
        n_rounds=int(entry.get("n_rounds", 0)),
        n_schemas=int(entry.get("n_schemas", 0)),
        status=entry.get("status", "unknown"),
        symbols=raw_det.get("symbols"),
        equal_fn_def=raw_det.get("equal_fn_def"),
        equal_fn_name=raw_det.get("equal_fn_name"),
        det_check_template=raw_det.get("det_check_template"),
        equal_policy=raw_det.get("equal_policy") or {},
        raw_full_run=entry,
        raw_det_spec=raw_det,
    )


def crate_for(corpus: CorpusConfig, crate: str) -> CrateConfig:
    if crate not in corpus.crates:
        raise KeyError(f"crate '{crate}' not in corpus config (known: {list(corpus.crates)})")
    return corpus.crates[crate]
