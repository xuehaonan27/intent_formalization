"""Result classification for spec-determinism runs.

The high-level ``status`` field in a result records pipeline outcome
(``ok`` / ``verus_error`` / ``search_error`` / ...). When ``status == "ok"``
the determinism check itself ran successfully, but its semantic verdict
depends on what z3 returned at R0 (no schema narrowing applied):

  * ``r0_z3 == "unsat"`` — the spec is **complete**: it pins the
    function's behaviour to a single observable post-state. Optional
    narrowing may have committed assumes, but those are unused
    refinement attempts.

  * ``r0_z3 == "sat"`` — the spec is **incomplete**: z3 found two
    distinct post-states both satisfying the ensures. Narrowing then
    refined which fields are responsible. ``assumes`` is a *real*
    spec-incompleteness witness. May be intentional (spec uses
    ``|||`` to permit multiple posts) — see ``permitted`` flag.

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
``complete_llm`` bucket so paper claims can distinguish baseline z3
proofs from LLM-assisted proofs.

This module returns one of:

  * ``"complete"``         — spec pins a unique post (R0=unsat,
                            baseline z3 alone)
  * ``"complete_llm"``     — same, after LLM-authored proof block
  * ``"incomplete"``       — spec admits multiple posts; real
                            nondeterminism witness (R0=sat)
  * ``"ok_inconclusive"``  — undecided (R0=unknown, including legacy)
  * ``"ok_unknown_kind"``  — status==ok but r0_z3 has an unexpected
                            value

Permitted-incompleteness detection
----------------------------------
Some Verus ensures intentionally use ``|||`` to declare an OR over
post-states (e.g., IronKV's ``next_delegate_postconditions`` allows the
"normal" branch OR the "ignoring unparseable" branch). The function
:func:`ensures_uses_permissive_or` recognises this both at the
top-level ensures *and* transitively through ``closed spec fn``
predicates referenced from the ensures. Pipeline drivers set
``result["permitted"] = True`` when this detector fires; the result
still classifies as ``incomplete`` but renderers add a "permitted
by spec ``|||``" annotation so paper claims can distinguish
spec-design-intended SAT from accidental spec gaps.

Renamed 2026-05-19: old ``ok_proved``/``ok_proved_llm``/``ok_witness``
are now ``complete``/``complete_llm``/``incomplete`` respectively.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional


# Public bucket names — keep stable; tooling, summaries, slides reference them.
BUCKET_COMPLETE = "complete"
BUCKET_COMPLETE_LLM = "complete_llm"
BUCKET_INCOMPLETE = "incomplete"
BUCKET_INCONCLUSIVE = "ok_inconclusive"
BUCKET_UNKNOWN_KIND = "ok_unknown_kind"

# Backwards-compat aliases (still imported from a couple of call sites;
# emit the new strings but keep the old Python names working).
BUCKET_PROVED = BUCKET_COMPLETE
BUCKET_PROVED_LLM = BUCKET_COMPLETE_LLM
BUCKET_WITNESS = BUCKET_INCOMPLETE

OK_BUCKETS = (
    BUCKET_COMPLETE,
    BUCKET_COMPLETE_LLM,
    BUCKET_INCOMPLETE,
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
            return BUCKET_COMPLETE_LLM
        return BUCKET_COMPLETE
    if r0 == "sat":
        return BUCKET_INCOMPLETE
    if r0 == "unknown":
        return BUCKET_INCONCLUSIVE
    if r0 == "":
        # Legacy run — assumes-bearing maps to inconclusive (empirical),
        # no-assumes maps to complete.
        return BUCKET_INCONCLUSIVE if result.get("assumes") else BUCKET_COMPLETE
    return BUCKET_UNKNOWN_KIND


# --------------------------------------------------------------------------
# Permitted-incompleteness detection (spec uses ``|||``)
# --------------------------------------------------------------------------
#
# Verus syntax: ``|||`` is the "spec OR" delimiter inside an
# expression-block ensures (each branch is a top-level disjunct over the
# post-state). When the top-level ensures uses ``|||`` directly *or* it
# calls a ``[pub] [open|closed] spec fn`` whose body uses ``|||``, the
# spec semantically permits multiple post-states — z3 returning sat/
# unknown is then a known-correct property, not a spec gap.

_PERMISSIVE_OR_RE = re.compile(r"\|\|\|")

# Match an unqualified Rust identifier in call position: ``foo(``.
# We use this to harvest candidate spec-fn names from an ensures text.
_CALLEE_RE = re.compile(r"\b([A-Za-z_][A-Za-z_0-9]*)\s*\(")

# Match a spec-fn header like ``pub closed spec fn foo(...) ...``.
# Capture group 1 is the name. We then brace-match to extract the body.
_SPEC_FN_HEADER_RE = re.compile(
    r"(?:pub(?:\([^)]*\))?\s+)?"
    r"(?:open\s+|closed\s+)?"
    r"(?:uninterp\s+)?"
    r"spec\s+fn\s+"
    r"([A-Za-z_][A-Za-z_0-9]*)"
)


def _spec_fn_body(source: str, name: str) -> Optional[str]:
    """Return the body text (between the first ``{`` and matching ``}``)
    of a ``spec fn <name>`` defined in *source*, or ``None`` if the
    function isn't defined / has no body / source is unbalanced."""
    for m in _SPEC_FN_HEADER_RE.finditer(source):
        if m.group(1) != name:
            continue
        # Find the opening brace for the body (skip the parameter list and
        # any ``-> RetType`` clause).
        i = m.end()
        depth_paren = 0
        body_open = -1
        while i < len(source):
            c = source[i]
            if c == "(":
                depth_paren += 1
            elif c == ")":
                depth_paren -= 1
            elif c == "{" and depth_paren == 0:
                body_open = i
                break
            elif c == ";" and depth_paren == 0:
                # uninterp spec fn / forward decl — no body.
                break
            i += 1
        if body_open < 0:
            continue
        # Brace-match the body.
        depth = 0
        for j in range(body_open, len(source)):
            if source[j] == "{":
                depth += 1
            elif source[j] == "}":
                depth -= 1
                if depth == 0:
                    return source[body_open + 1 : j]
        # Unbalanced — give up on this match.
    return None


def ensures_uses_permissive_or(
    ensures_texts: Iterable[str],
    source: str = "",
    *,
    max_depth: int = 4,
) -> bool:
    """Heuristic: ensures uses ``|||`` (direct or via a referenced spec fn).

    Returns ``True`` iff any of:

      1. The literal text of one of *ensures_texts* contains ``|||``.
      2. A ``[open|closed] spec fn`` referenced (transitively, up to
         *max_depth* hops) from the ensures is defined in *source* and
         its body contains ``|||``.

    Conservative on missing sources: when *source* is empty or the
    referenced spec fn isn't defined in *source*, the transitive
    check skips that callee (returns ``False`` for that branch).
    """
    joined = "\n".join(ensures_texts)
    if _PERMISSIVE_OR_RE.search(joined):
        return True
    if not source:
        return False

    seen: set[str] = set()
    queue: list[tuple[str, int]] = [
        (name, 0) for name in _CALLEE_RE.findall(joined)
    ]
    while queue:
        name, depth = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        if depth >= max_depth:
            continue
        body = _spec_fn_body(source, name)
        if body is None:
            continue
        if _PERMISSIVE_OR_RE.search(body):
            return True
        for callee in _CALLEE_RE.findall(body):
            if callee not in seen:
                queue.append((callee, depth + 1))
    return False


# ----------------------------- self-tests --------------------------------

def _selftest_classify() -> None:
    cases = [
        ({"status": "ok", "r0_z3": "unsat"}, BUCKET_COMPLETE),
        ({"status": "ok", "r0_z3": "unsat", "llm_assisted": True}, BUCKET_COMPLETE_LLM),
        ({"status": "ok", "r0_z3": "sat"}, BUCKET_INCOMPLETE),
        ({"status": "ok", "r0_z3": "unknown"}, BUCKET_INCONCLUSIVE),
        ({"status": "ok", "r0_z3": "", "assumes": ["x"]}, BUCKET_INCONCLUSIVE),
        ({"status": "ok", "r0_z3": ""}, BUCKET_COMPLETE),
        ({"status": "ok", "r0_z3": "bogus"}, BUCKET_UNKNOWN_KIND),
    ]
    for r, want in cases:
        got = classify_ok(r)
        assert got == want, f"classify({r}) -> {got}, want {want}"


def _selftest_permitted_or() -> None:
    # Direct ||| in ensures.
    assert ensures_uses_permissive_or(["a ||| b"]) is True
    # No ||| anywhere.
    assert ensures_uses_permissive_or(["a && b"]) is False
    # || (boolean OR, not Verus spec-OR) does NOT trigger.
    assert ensures_uses_permissive_or(["a || b"]) is False

    # Transitive via single-hop closed spec fn.
    source = """
        pub closed spec fn p(x: T) -> bool {
            ||| a(x) ||| b(x)
        }
    """
    assert ensures_uses_permissive_or(["self.p(x)"], source) is True

    # Transitive over two hops.
    source2 = """
        pub closed spec fn p(x: T) -> bool { q(x) }
        pub open spec fn q(x: T) -> bool { ||| a(x) ||| b(x) }
    """
    assert ensures_uses_permissive_or(["self.p(x)"], source2) is True

    # uninterp spec fn — has no body, must not crash.
    source3 = "pub uninterp spec fn p(x: T) -> bool;\n"
    assert ensures_uses_permissive_or(["self.p(x)"], source3) is False

    # max_depth bound respected (no |||).
    source4 = """
        pub closed spec fn p(x: T) -> bool { q(x) }
        pub closed spec fn q(x: T) -> bool { r(x) }
        pub closed spec fn r(x: T) -> bool { s(x) }
        pub closed spec fn s(x: T) -> bool { true && false }
    """
    assert ensures_uses_permissive_or(["self.p(x)"], source4) is False

    # Conservative: missing source returns False even with callee.
    assert ensures_uses_permissive_or(["self.p(x)"], "") is False


def _selftest() -> None:
    _selftest_classify()
    _selftest_permitted_or()
    print("classify self-tests PASS")


if __name__ == "__main__":
    _selftest()
