"""Result classification for spec-determinism runs.

The high-level ``status`` field in a result records pipeline outcome
(``ok`` / ``verus_error`` / ``search_error`` / ...). When ``status == "ok"``
the determinism check itself ran successfully, but its semantic verdict
depends on what z3 returned at R0 (no schema narrowing applied):

  * ``r0_z3 == "unsat"`` — the function is provably deterministic (best
    outcome). Optional narrowing may have committed assumes, but those
    are not witnesses; they are unused refinement attempts.

  * ``r0_z3 == "sat"`` — z3 produced a concrete counterexample at R0;
    narrowing then refined which fields are responsible. ``assumes`` is
    a *real* nondeterminism witness.

  * ``r0_z3 == "unknown"`` — z3 surrendered (incomplete quantifiers,
    timeout, etc). Any ``assumes`` recorded by narrowing are unreliable
    because they were built on top of an undecided baseline. Reporting
    these as witnesses is a known false-positive class.

  * ``r0_z3 == ""`` — legacy run from before this field was persisted.
    Empirically (atmosphere/ironkv/memory-allocator replays, 2026-05-14)
    100 % of ``ok`` + ``assumes`` legacy results were R0=unknown, so we
    fall back to that classification.

When the LLM proof loop (:mod:`spec_determinism.llm_proof`) closes an
``unknown`` case by re-running Verus with an LLM-authored proof block,
the driver overwrites ``r0_z3`` with ``"unsat"`` and sets the result key
``llm_assisted=True``. The classifier then yields the dedicated
``ok_proved_llm`` bucket so paper claims can distinguish baseline z3
proofs from LLM-assisted proofs.

This module returns one of:

  * ``"ok_proved"``        — deterministic (R0=unsat, baseline z3 alone)
  * ``"ok_proved_llm"``    — deterministic after LLM-authored proof block
  * ``"ok_witness"``       — real nondeterminism witness (R0=sat)
  * ``"ok_inconclusive"``  — undecided (R0=unknown, including legacy)
  * ``"ok_unknown_kind"``  — status==ok but r0_z3 has an unexpected value
"""
from __future__ import annotations


# Public bucket names — keep stable; tooling, summaries, slides reference them.
BUCKET_PROVED = "ok_proved"
BUCKET_PROVED_LLM = "ok_proved_llm"
BUCKET_WITNESS = "ok_witness"
BUCKET_INCONCLUSIVE = "ok_inconclusive"
BUCKET_UNKNOWN_KIND = "ok_unknown_kind"

OK_BUCKETS = (
    BUCKET_PROVED,
    BUCKET_PROVED_LLM,
    BUCKET_WITNESS,
    BUCKET_INCONCLUSIVE,
    BUCKET_UNKNOWN_KIND,
)


def classify_ok(result: dict) -> str:
    """Classify an ``ok`` result by its R0 z3 verdict.

    Caller is expected to first check ``result.get("status") == "ok"``.
    """
    r0 = result.get("r0_z3", "")
    if r0 == "unsat":
        if result.get("llm_assisted"):
            return BUCKET_PROVED_LLM
        return BUCKET_PROVED
    if r0 == "sat":
        return BUCKET_WITNESS
    if r0 == "unknown":
        return BUCKET_INCONCLUSIVE
    if r0 == "":
        # Legacy run — assumes-bearing maps to inconclusive (empirical),
        # no-assumes maps to proved.
        return BUCKET_INCONCLUSIVE if result.get("assumes") else BUCKET_PROVED
    return BUCKET_UNKNOWN_KIND
