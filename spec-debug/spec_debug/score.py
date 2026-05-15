"""Metric computation for a single repair candidate.

Implements the metrics designed in METRICS.md (revisions of REPAIR-CRITERIA.md
criteria 1-4 plus this round's additions). Criterion 5 (MDL) is delegated to
`spec_debug.mdl` (separate module, not yet implemented).

Phases landed here:
  P1  outcome metrics       — driving_closed_ratio, new_witness_driving, …
  P2  bypass detection      — no_new_admissions_in_impl, symbol_table_stable,
                              equal_fn_def_stable
  P4  observation flags     — structural_fit, literal_bleed

Phases NOT landed yet (handled elsewhere or deferred):
  P3  workspace_verus_passes — separate cargo verus build (deferred)
  P5  policy_verdict        — counterfactual policy run (deferred)
  P6  MDL                   — soft ranker, see spec_debug.mdl (deferred)
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .gap import ClassifiedAssumes, Witness, classify_assumes


# ---------------------------------------------------------------------------
# Metric dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GapClosureMetrics:
    """Axis A — outcome metrics from before/after assume sets."""
    driving_before: int
    driving_closed: int                 # |driving_before ∩ closed|
    driving_closed_ratio: float         # driving_closed / driving_before (0.0 if no driving)
    collateral_before: int
    collateral_closed: int
    closed_count: int                   # raw |before \ after| (legacy signal)
    added_count: int                    # raw |after \ before|
    new_witness_driving: bool           # rerun produced a fresh witness, and it has driving
    new_witness_driving_count: int      # number of driving assumes in fresh witness
    n_rounds_before: int
    n_rounds_after: int
    n_rounds_delta: int


@dataclass
class BypassMetrics:
    """Axis C — checker bypass detection."""
    no_new_admissions_in_impl: bool
    new_admissions: list[str] = field(default_factory=list)   # offending lines
    symbol_table_stable: bool | None = None     # None if post-regen snapshot unavailable
    equal_fn_def_stable: bool | None = None
    # Detail strings for debug:
    symbol_table_diff: str | None = None
    equal_fn_def_diff: str | None = None


@dataclass
class StructuralFitMetrics:
    """Axis B (observation only) — surface-form features of the patch."""
    ensures_clauses_after: int
    ensures_clauses_delta: int
    quantifiers_added: int
    helper_spec_fns_added: int
    helper_spec_fns_added_names: list[str] = field(default_factory=list)


@dataclass
class LiteralBleedMetrics:
    """Axis D (observation only) — witness constants leaking into the repair."""
    witness_literals: list[str]
    added_literals: list[str]
    bleed_literals: list[str]            # literals in patch that came from witness
    bleed_count: int


@dataclass
class HardGates:
    """Aggregate hard-gate verdict.

    The rest of the metrics are still recorded even when gates fail; this
    just summarises whether a candidate is eligible for MDL ranking.
    """
    impl_still_verifies: bool
    no_new_admissions_in_impl: bool
    symbol_table_stable: bool        # treat None as True (unknown ≢ fail)
    equal_fn_def_stable: bool        # same
    passed: bool
    reject_reasons: list[str] = field(default_factory=list)


@dataclass
class Metrics:
    gap_closure: GapClosureMetrics
    bypass: BypassMetrics
    structural_fit: StructuralFitMetrics
    literal_bleed: LiteralBleedMetrics
    hard_gates: HardGates

    def as_dict(self) -> dict[str, Any]:
        return {
            "gap_closure": asdict(self.gap_closure),
            "bypass": asdict(self.bypass),
            "structural_fit": asdict(self.structural_fit),
            "literal_bleed": asdict(self.literal_bleed),
            "hard_gates": asdict(self.hard_gates),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _driving(c: ClassifiedAssumes) -> list[str]:
    return list(c.discriminant) + list(c.driving_ok) + list(c.driving_err)


def _collateral(c: ClassifiedAssumes) -> list[str]:
    return list(c.collateral_ok) + list(c.collateral_err)


# Strict regex for `admit()` and `assume(false)` *introductions*. We only
# flag patterns that appear in lines newly added by the patch; lines that
# existed before are out of scope.
_ADMISSION_PATTERNS = [
    re.compile(r"\badmit\s*\(\s*\)"),
    re.compile(r"\bassume\s*\(\s*false\s*\)"),
    # `unreachable!()` inside a spec/proof block is also a soft admission
    # (proves the impossible). We flag it but leave the boolean gate based
    # on the strict patterns above.
]
_SOFT_ADMISSION_PATTERN = re.compile(r"\bunreachable\s*!\s*\(\s*\)")


def _diff_added_lines(before_text: str, after_text: str) -> list[str]:
    """Lines present in `after_text` but not in `before_text` (multiset).

    Cheap line-level diff. Does not align — `assume(true)` lines moved
    around won't show as added/removed. Good enough for admission scanning.
    """
    before = list(before_text.splitlines())
    after = list(after_text.splitlines())
    before_counts: dict[str, int] = {}
    for l in before:
        before_counts[l] = before_counts.get(l, 0) + 1
    added: list[str] = []
    for l in after:
        if before_counts.get(l, 0) > 0:
            before_counts[l] -= 1
        else:
            added.append(l)
    return added


def _scan_admissions(added_lines: list[str]) -> tuple[bool, list[str]]:
    """Return (no_new_admissions, offending_lines).

    Soft `unreachable!()` matches are reported but do NOT flip the bool.
    """
    offenders: list[str] = []
    has_strict = False
    for l in added_lines:
        # strip line comments to avoid flagging commented-out admit
        s = l.split("//", 1)[0]
        for pat in _ADMISSION_PATTERNS:
            if pat.search(s):
                offenders.append(l.strip())
                has_strict = True
                break
        else:
            if _SOFT_ADMISSION_PATTERN.search(s):
                offenders.append(f"[soft] {l.strip()}")
    return (not has_strict), offenders


# Literal-bleed support. A "literal" here is anything that looks like a
# numeric constant or a quoted string inside the repair clause text.
_NUM_RE = re.compile(r"\b(?:0[xX][0-9a-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|\d[\d_]*)(?:[uif][0-9]*)?\b")
_STR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _extract_literals(text: str) -> list[str]:
    out: list[str] = []
    out.extend(_NUM_RE.findall(text))
    out.extend(_STR_RE.findall(text))
    # normalise: strip type suffixes, underscores
    norm: list[str] = []
    for s in out:
        if isinstance(s, str):
            t = s.replace("_", "")
            t = re.sub(r"(usize|isize|u8|u16|u32|u64|i8|i16|i32|i64|f32|f64)$", "", t)
            norm.append(t)
    return norm


def _extract_witness_literals(witness: Witness) -> list[str]:
    """Pull literal-shaped tokens out of the witness's committed assumes."""
    blob = "\n".join(witness.assumes or [])
    return _extract_literals(blob)


def _count_quantifiers(text: str) -> int:
    return len(re.findall(r"\b(forall|exists)\b", text))


def _count_ensures_clauses(text: str) -> int:
    """Count top-level `ensures` clauses by looking at `ensures` keywords.

    This counts the *blocks*, not the individual conjuncts inside them.
    Approximate but cheap.
    """
    return len(re.findall(r"\bensures\b", text))


def _extract_helper_spec_fn_names(text: str) -> set[str]:
    """Names of `spec fn`s defined in the text. Heuristic.

    Matches `spec fn name(` and `pub spec fn name(`, skipping `proof fn`.
    """
    out: set[str] = set()
    for m in re.finditer(r"\bspec\s+fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        out.add(m.group(1))
    return out


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


@dataclass
class ScoreInputs:
    witness_before: Witness
    after_assumes: list[str]
    rerun_ok: bool                  # spec-determinism-run returncode == 0
    impl_still_verifies: bool       # current proxy: rerun_ok (P3 will replace)
    n_rounds_after: int
    original_spec_text: str
    new_spec_text: str
    # Optional post-regen artifact for symbol/equal_fn diffing. None if
    # regen wasn't run (e.g. because verify failed before regen).
    post_det_spec: dict[str, Any] | None = None


def compute_metrics(inputs: ScoreInputs) -> Metrics:
    w = inputs.witness_before
    policy = w.equal_policy or {}

    before_classified = classify_assumes(w.assumes, policy)
    after_classified = classify_assumes(inputs.after_assumes, policy)

    before_set = set(w.assumes or [])
    after_set = set(inputs.after_assumes or [])
    closed = before_set - after_set
    added = after_set - before_set

    driving_before = set(_driving(before_classified))
    collateral_before = set(_collateral(before_classified))
    driving_closed = driving_before & closed
    collateral_closed = collateral_before & closed

    driving_ratio = (
        (len(driving_closed) / len(driving_before)) if driving_before else 1.0
    )

    new_driving = _driving(after_classified)
    new_witness_driving = inputs.rerun_ok and bool(after_set) and bool(new_driving)

    gap_closure = GapClosureMetrics(
        driving_before=len(driving_before),
        driving_closed=len(driving_closed),
        driving_closed_ratio=round(driving_ratio, 4),
        collateral_before=len(collateral_before),
        collateral_closed=len(collateral_closed),
        closed_count=len(closed),
        added_count=len(added),
        new_witness_driving=new_witness_driving,
        new_witness_driving_count=len(new_driving),
        n_rounds_before=w.n_rounds,
        n_rounds_after=inputs.n_rounds_after,
        n_rounds_delta=inputs.n_rounds_after - w.n_rounds,
    )

    # P2 — bypass detection
    added_lines = _diff_added_lines(inputs.original_spec_text, inputs.new_spec_text)
    no_new_admissions, admission_lines = _scan_admissions(added_lines)

    pre_det = w.raw_det_spec or {}
    post_det = inputs.post_det_spec or {}
    if post_det:
        sym_stable = (pre_det.get("symbols") == post_det.get("symbols"))
        eq_stable = (pre_det.get("equal_fn_def") == post_det.get("equal_fn_def"))
        sym_diff = None if sym_stable else "symbols changed (see pre/post det_spec.json)"
        eq_diff = None if eq_stable else "equal_fn_def changed"
    else:
        sym_stable = None
        eq_stable = None
        sym_diff = "post-regen det_spec.json unavailable"
        eq_diff = "post-regen det_spec.json unavailable"

    bypass = BypassMetrics(
        no_new_admissions_in_impl=no_new_admissions,
        new_admissions=admission_lines,
        symbol_table_stable=sym_stable,
        equal_fn_def_stable=eq_stable,
        symbol_table_diff=sym_diff,
        equal_fn_def_diff=eq_diff,
    )

    # P4 — structural fit (observation only)
    ensures_after = _count_ensures_clauses(inputs.new_spec_text)
    ensures_before = _count_ensures_clauses(inputs.original_spec_text)
    quants_added = _count_quantifiers(inputs.new_spec_text) - _count_quantifiers(
        inputs.original_spec_text
    )
    helpers_before = _extract_helper_spec_fn_names(inputs.original_spec_text)
    helpers_after = _extract_helper_spec_fn_names(inputs.new_spec_text)
    helpers_new = sorted(helpers_after - helpers_before)
    structural_fit = StructuralFitMetrics(
        ensures_clauses_after=ensures_after,
        ensures_clauses_delta=ensures_after - ensures_before,
        quantifiers_added=max(0, quants_added),
        helper_spec_fns_added=len(helpers_new),
        helper_spec_fns_added_names=helpers_new,
    )

    # P4 — literal bleed (observation only)
    witness_lits = _extract_witness_literals(w)
    added_text = "\n".join(added_lines)
    added_lits = _extract_literals(added_text)
    bleed = sorted(set(added_lits) & set(witness_lits))
    literal_bleed = LiteralBleedMetrics(
        witness_literals=sorted(set(witness_lits)),
        added_literals=sorted(set(added_lits)),
        bleed_literals=bleed,
        bleed_count=len(bleed),
    )

    # Hard-gate aggregate. None for sym/eq stability is treated as PASS
    # (we don't know — don't reject on unknown). The score consumer can
    # downgrade-to-fail explicitly if it wants stricter behaviour.
    sym_pass = True if sym_stable is None else sym_stable
    eq_pass = True if eq_stable is None else eq_stable
    reasons: list[str] = []
    if not inputs.impl_still_verifies:
        reasons.append("impl_still_verifies=false (verus rerun failed)")
    if not no_new_admissions:
        reasons.append(f"no_new_admissions_in_impl=false ({len(admission_lines)} offending line(s))")
    if not sym_pass:
        reasons.append("symbol_table_stable=false")
    if not eq_pass:
        reasons.append("equal_fn_def_stable=false")
    passed = (
        inputs.impl_still_verifies
        and no_new_admissions
        and sym_pass
        and eq_pass
    )
    hard_gates = HardGates(
        impl_still_verifies=inputs.impl_still_verifies,
        no_new_admissions_in_impl=no_new_admissions,
        symbol_table_stable=sym_pass,
        equal_fn_def_stable=eq_pass,
        passed=passed,
        reject_reasons=reasons,
    )

    return Metrics(
        gap_closure=gap_closure,
        bypass=bypass,
        structural_fit=structural_fit,
        literal_bleed=literal_bleed,
        hard_gates=hard_gates,
    )
