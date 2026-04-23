"""Verification runner.

v0: single observation — re-run `spec-determinism-run <crate::fn>` after
the patch and diff the committed assumes. spec-determinism already
invokes Verus internally, so a successful rerun implies the spec
compiles; a failed rerun surfaces both compile and determinism errors.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from spec_determinism.config import CorpusConfig, CrateConfig

from .gap import load_witness


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


def verify(
    corpus: CorpusConfig,
    crate_cfg: CrateConfig,
    function: str,
    before_assumes: list[str],
) -> VerifyReport:
    return VerifyReport(rerun=run_rerun(corpus, crate_cfg.name, function, before_assumes))

