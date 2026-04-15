"""
Dataclass schemas for the spec-fuzzing pipeline.

All enums use Literal types; all schemas use @dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Enum-like Literals
# ---------------------------------------------------------------------------

OracleLabel = Literal["ACCEPT", "REJECT"]
VerusOutcome = Literal["verifies", "fails", "timeout"]
Verdict = Literal["OK", "INCORRECTNESS", "INCOMPLETENESS", "UNKNOWN"]


# ---------------------------------------------------------------------------
# Core Case schema
# ---------------------------------------------------------------------------

@dataclass
class Case:
    """A single concrete (pre-state, args, post-state, return) test case."""

    task: str                    # e.g. "bitmap__bitmap"
    fn: str                      # e.g. "alloc"
    case_id: str                 # unique within task+fn, e.g. "alloc_0"

    pre_assumes: list[str]       # e.g. ["old(self)@.num_bits == 8"]
    arg_assumes: list[str]       # e.g. ["n == 3"]
    post_assumes: list[str]      # e.g. ["self@.set_bits == old(self)@.set_bits.insert(0)"]
    result_assume: str | None    # e.g. "result is Ok && result.unwrap() == 0"

    oracle: OracleLabel | None = None
    oracle_justification: str | None = None

    # Set after step7
    verus_outcome: VerusOutcome | None = None
    verus_log: str | None = None

    # Derived verdict (set in step8)
    verdict: Verdict | None = None

    # True if the case was discarded (requires-violating)
    requires_violated: bool = False

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "fn": self.fn,
            "case_id": self.case_id,
            "pre_assumes": self.pre_assumes,
            "arg_assumes": self.arg_assumes,
            "post_assumes": self.post_assumes,
            "result_assume": self.result_assume,
            "oracle": self.oracle,
            "oracle_justification": self.oracle_justification,
            "verus_outcome": self.verus_outcome,
            "verus_log": self.verus_log,
            "verdict": self.verdict,
            "requires_violated": self.requires_violated,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Case":
        return cls(
            task=d["task"],
            fn=d["fn"],
            case_id=d["case_id"],
            pre_assumes=d.get("pre_assumes", []),
            arg_assumes=d.get("arg_assumes", []),
            post_assumes=d.get("post_assumes", []),
            result_assume=d.get("result_assume"),
            oracle=d.get("oracle"),
            oracle_justification=d.get("oracle_justification"),
            verus_outcome=d.get("verus_outcome"),
            verus_log=d.get("verus_log"),
            verdict=d.get("verdict"),
            requires_violated=d.get("requires_violated", False),
        )


# ---------------------------------------------------------------------------
# Finding schema (one per INCORRECTNESS / INCOMPLETENESS case)
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A non-OK verdict case — potential spec bug."""

    task: str
    fn: str
    case_id: str
    verdict: Verdict
    oracle: OracleLabel
    verus_outcome: VerusOutcome
    oracle_justification: str | None
    pre_assumes: list[str]
    arg_assumes: list[str]
    post_assumes: list[str]
    result_assume: str | None

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "fn": self.fn,
            "case_id": self.case_id,
            "verdict": self.verdict,
            "oracle": self.oracle,
            "verus_outcome": self.verus_outcome,
            "oracle_justification": self.oracle_justification,
            "pre_assumes": self.pre_assumes,
            "arg_assumes": self.arg_assumes,
            "post_assumes": self.post_assumes,
            "result_assume": self.result_assume,
        }

    @classmethod
    def from_case(cls, case: Case) -> "Finding":
        assert case.verdict in ("INCORRECTNESS", "INCOMPLETENESS")
        assert case.oracle is not None
        assert case.verus_outcome is not None
        return cls(
            task=case.task,
            fn=case.fn,
            case_id=case.case_id,
            verdict=case.verdict,
            oracle=case.oracle,
            verus_outcome=case.verus_outcome,
            oracle_justification=case.oracle_justification,
            pre_assumes=case.pre_assumes,
            arg_assumes=case.arg_assumes,
            post_assumes=case.post_assumes,
            result_assume=case.result_assume,
        )


# ---------------------------------------------------------------------------
# Verdict matrix helper
# ---------------------------------------------------------------------------

def compute_verdict(oracle: OracleLabel, verus_outcome: VerusOutcome) -> Verdict:
    """
    Verdict matrix:
      oracle=ACCEPT  + verifies  → OK
      oracle=ACCEPT  + fails     → INCORRECTNESS
      oracle=REJECT  + verifies  → INCOMPLETENESS
      oracle=REJECT  + fails     → OK
      anything       + timeout   → UNKNOWN
    """
    if verus_outcome == "timeout":
        return "UNKNOWN"
    if oracle == "ACCEPT" and verus_outcome == "verifies":
        return "OK"
    if oracle == "ACCEPT" and verus_outcome == "fails":
        return "INCORRECTNESS"
    if oracle == "REJECT" and verus_outcome == "verifies":
        return "INCOMPLETENESS"
    if oracle == "REJECT" and verus_outcome == "fails":
        return "OK"
    return "UNKNOWN"
