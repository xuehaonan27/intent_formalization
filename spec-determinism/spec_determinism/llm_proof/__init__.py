"""LLM-driven Verus proof annotation loop.

Triggers when the schema-search baseline returns ``r0_z3 == "unknown"``
(z3 surrendered on the determinism postcondition because of quantifier
instantiation gaps, not a real spec gap). The loop:

  1. Asks an LLM (Copilot CLI) for a Verus *proof block* — ``assert``,
     ``assert ... by``, ``reveal``, ``broadcast use``, ``lemma_*`` calls,
     plain let / if / match. The block is injected at the bottom of the
     synthetic ``det_<f>`` proof fn body, *after* the schema-assume
     scaffolding, matching the hand-written worked examples.
  2. Runs a lex-level allowlist over the LLM's output to reject any
     axiom-style construct (``assume`` / ``admit`` / ``unimplemented!``
     / ``unreachable!`` / ``assume_specification`` / ``external_body`` /
     new fn definitions). This is *mandatory*: Verus silently accepts
     ``assume(false)``, so the soundness gate cannot live downstream.
  3. Re-runs Verus on the patched file. If Verus accepts the postcondition,
     the function is proved deterministic (``complete_llm`` bucket).
     Otherwise the stderr tail is fed back into the next attempt
     (default K=3 iterations).

The package is **opt-in** — drivers pass ``use_llm_proof=True`` (or set
``SPEC_DET_LLM_PROOF=1``). Default behaviour of single-file / corpus
runners is unchanged.

Bucket convention: see :mod:`spec_determinism.classify`.

Public API:
    :func:`run_llm_proof_loop` — the entry point.
    :class:`ProofAttempt`     — record of one LLM iteration.
    :class:`ProofResult`      — aggregate over K iterations.
"""
from __future__ import annotations

from .prover import ProofAttempt, ProofResult, run_llm_proof_loop
from .sandbox import SandboxViolation, scan_proof_block

__all__ = [
    "ProofAttempt",
    "ProofResult",
    "SandboxViolation",
    "run_llm_proof_loop",
    "scan_proof_block",
]
