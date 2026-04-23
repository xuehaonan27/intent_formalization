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
    raw_full_run: dict[str, Any] = field(default_factory=dict)
    raw_det_spec: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        return f"{self.crate}::{self.function}"

    def has_gap(self) -> bool:
        return bool(self.assumes)


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
        raw_full_run=entry,
        raw_det_spec=raw_det,
    )


def crate_for(corpus: CorpusConfig, crate: str) -> CrateConfig:
    if crate not in corpus.crates:
        raise KeyError(f"crate '{crate}' not in corpus config (known: {list(corpus.crates)})")
    return corpus.crates[crate]
