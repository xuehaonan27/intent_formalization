"""Verification runner.

v0: single observation — re-run `spec-determinism-run <crate::fn>` after
the patch and diff the committed assumes. spec-determinism already
invokes Verus internally, so a successful rerun implies the spec
compiles; a failed rerun surfaces both compile and determinism errors.

v0.1: also runs `spec-determinism-regen` between patch and rerun so that
post-patch det_spec.json (symbol table + equal_fn_def) reflects the
edited spec. Best-effort — if regen fails (e.g. signature change broke
extraction), the rerun proceeds with the stale template and the
post-regen snapshot is left blank for the metrics layer.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from spec_determinism.config import CorpusConfig, CrateConfig

from .gap import load_witness


@dataclass
class RegenResult:
    ok: bool
    returncode: int
    cmd: list[str] = field(default_factory=list)
    stderr_tail: str = ""


@dataclass
class RerunResult:
    ok: bool
    returncode: int
    before_assumes: list[str]
    after_assumes: list[str]
    closed: list[str]        # in before, gone in after
    added: list[str]         # new in after
    n_rounds_after: int
    stderr_tail: str
    cmd: list[str] = field(default_factory=list)


@dataclass
class VerifyReport:
    rerun: RerunResult
    regen: RegenResult | None = None
    post_det_spec: dict[str, Any] | None = None  # loaded post-regen, for score


def _tail(s: str, n: int = 4000) -> str:
    return s[-n:] if len(s) > n else s


def run_rerun(
    corpus: CorpusConfig,
    crate: str,
    function: str,
    before_assumes: list[str],
    timeout: int | None = None,
) -> RerunResult:
    cmd = ["spec-determinism-run", f"{crate}::{function}", "-c", str(corpus.path)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout or 900,
        )
    except subprocess.TimeoutExpired as e:
        return RerunResult(
            ok=False, returncode=-1,
            before_assumes=list(before_assumes), after_assumes=[],
            closed=[], added=[], n_rounds_after=0,
            stderr_tail=f"TIMEOUT after {e.timeout}s", cmd=cmd,
        )

    ok = proc.returncode == 0
    after_assumes: list[str] = []
    n_rounds_after = 0
    if ok:
        try:
            w = load_witness(corpus, crate, function)
            after_assumes = list(w.assumes)
            n_rounds_after = w.n_rounds
        except Exception as e:
            return RerunResult(
                ok=False, returncode=proc.returncode,
                before_assumes=list(before_assumes), after_assumes=[],
                closed=[], added=[], n_rounds_after=0,
                stderr_tail=_tail((proc.stdout or "") + (proc.stderr or "") +
                                  f"\n[spec-debug] failed to reload witness: {e}"),
                cmd=cmd,
            )

    before_set = set(before_assumes)
    after_set = set(after_assumes)
    return RerunResult(
        ok=ok,
        returncode=proc.returncode,
        before_assumes=list(before_assumes),
        after_assumes=after_assumes,
        closed=sorted(before_set - after_set),
        added=sorted(after_set - before_set),
        n_rounds_after=n_rounds_after,
        stderr_tail=_tail((proc.stdout or "") + (proc.stderr or "")),
        cmd=cmd,
    )


def run_regen(
    corpus: CorpusConfig,
    crate: str,
    function: str,
    timeout: int | None = None,
) -> RegenResult:
    """Best-effort regeneration of det_spec.json after a spec patch.

    Failure is non-fatal: callers may still proceed with run_rerun using
    whatever det_spec.json is on disk.
    """
    cmd = ["spec-determinism-regen", f"{crate}::{function}", "-c", str(corpus.path)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout or 600,
        )
    except subprocess.TimeoutExpired as e:
        return RegenResult(
            ok=False, returncode=-1, cmd=cmd,
            stderr_tail=f"TIMEOUT after {e.timeout}s",
        )
    return RegenResult(
        ok=(proc.returncode == 0),
        returncode=proc.returncode,
        cmd=cmd,
        stderr_tail=_tail((proc.stdout or "") + (proc.stderr or "")),
    )


def _post_det_spec(corpus: CorpusConfig, crate: str, function: str) -> dict[str, Any] | None:
    art = corpus.artifacts_dir / f"{crate}__{function}" / "det_spec.json"
    if not art.exists():
        return None
    try:
        return json.loads(art.read_text())
    except Exception:
        return None


def verify(
    corpus: CorpusConfig,
    crate_cfg: CrateConfig,
    function: str,
    before_assumes: list[str],
    *,
    do_regen: bool = True,
) -> VerifyReport:
    regen_res: RegenResult | None = None
    post_det: dict[str, Any] | None = None
    if do_regen:
        regen_res = run_regen(corpus, crate_cfg.name, function)
        # Capture post-regen det_spec snapshot regardless of regen rc:
        # even on failure it may still contain a partial update (or the
        # original, in which case symbol_table_stable will be True).
        post_det = _post_det_spec(corpus, crate_cfg.name, function)
    rerun = run_rerun(corpus, crate_cfg.name, function, before_assumes)
    if post_det is None:
        # Try once more after rerun in case regen happened lazily.
        post_det = _post_det_spec(corpus, crate_cfg.name, function)
    return VerifyReport(rerun=rerun, regen=regen_res, post_det_spec=post_det)

