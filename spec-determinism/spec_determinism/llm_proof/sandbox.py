"""Lex-level allowlist for LLM-emitted Verus proof blocks.

Sole purpose: ensure no LLM-emitted construct can make Verus accept the
``det_<f>`` postcondition without an honest proof. The forbidden
constructs are:

  ``assume(P)``       — adds P as an axiom without checking it. Verus
                        silently accepts ``assume(false)`` → trivially
                        proves any postcondition. **The reason this
                        scanner exists.**
  ``admit()``         — explicitly discharges any pending obligation.
  ``unimplemented!()``— Rust macro; Verus treats the call site as having
                        any postcondition (since it can't be reached).
  ``unreachable!()``  — same reasoning.
  ``assume_specification`` — declares an extern fn's spec without checking.
  ``#[verifier::external_body]`` / ``#[verifier(external_body)]`` —
                        Verus skips body verification. The LLM has no
                        business placing this attribute.
  New ``fn`` / ``spec fn`` / ``proof fn`` / ``exec fn`` definitions —
                        the prompt asks for *statements* to put inside an
                        existing proof body; new fn defs are out-of-scope
                        and create a vector for axiom-style declarations.
  ``impl`` / ``trait`` / ``struct`` / ``enum`` / ``type`` items —
                        same reason; items belong at module scope, not
                        inside a proof body.

The scan strips comments and string literals first so commented-out
mentions of ``assume`` don't false-positive. Returns a list of
:class:`SandboxViolation` entries with line offsets pointing into the
ORIGINAL block (so the caller can quote them back to the LLM as
feedback for the next iteration).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class SandboxViolation:
    pattern: str
    reason: str
    line: int            # 1-indexed line in the original (un-stripped) block
    col: int             # 1-indexed column
    snippet: str         # the offending substring, with ~30 chars context


# Pattern table. Each entry: (regex, human-readable reason).
#
# `\b` anchors avoid matching inside identifiers like ``assume_something``
# *except* where the rule is to forbid the whole prefix (``assume_specification``
# uses an explicit \b boundary which still matches the start of the token).
_FORBIDDEN: List[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bassume\s*\("),
        "`assume(P)` is an axiom — Verus accepts P without proof. "
        "Use `assert(P)` (which Verus must verify) or `assert P by { ... }`.",
    ),
    (
        re.compile(r"\badmit\s*\(\s*\)"),
        "`admit()` discharges any pending obligation without proof.",
    ),
    (
        re.compile(r"\bunimplemented\s*!"),
        "`unimplemented!()` lets Verus skip the post; not a real proof.",
    ),
    (
        re.compile(r"\bunreachable\s*!"),
        "`unreachable!()` lets Verus assume the site is dead code; "
        "not a real proof unless you've discharged reachability first.",
    ),
    (
        re.compile(r"\bassume_specification\b"),
        "`assume_specification` declares an unverified external spec.",
    ),
    (
        re.compile(r"external_body"),
        "`#[verifier::external_body]` skips body verification; "
        "the LLM has no business placing this attribute.",
    ),
    (
        re.compile(r"#\s*\[\s*verifier\b[^]]*\bexternal\b"),
        "`#[verifier(external)]` / `#[verifier(external_body)]` skips checks.",
    ),
    # ----- structural / item-level forbids -----
    (
        re.compile(r"\bfn\s+[A-Za-z_]"),
        "new `fn` definitions are not allowed inside the proof block — "
        "emit statements only.",
    ),
    (
        re.compile(r"\b(?:spec|proof|exec|open\s+spec|closed\s+spec)\s+fn\b"),
        "new `spec fn` / `proof fn` definitions are out of scope — "
        "emit statements only.",
    ),
    (
        re.compile(r"\bimpl\b\s*[<\w]"),
        "`impl` items are not allowed inside a proof block.",
    ),
    (
        re.compile(r"\btrait\s+[A-Za-z_]"),
        "`trait` declarations are not allowed inside a proof block.",
    ),
    (
        re.compile(r"\bstruct\s+[A-Za-z_]"),
        "`struct` definitions are not allowed inside a proof block.",
    ),
    (
        re.compile(r"\benum\s+[A-Za-z_]"),
        "`enum` definitions are not allowed inside a proof block.",
    ),
]


# ---------------------------------------------------------------------------
# Comment / string stripping.
# ---------------------------------------------------------------------------

_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
# Match: standard "...", raw r"..." / r#"..."#. Conservative: keep the
# replacement same-length so line/col offsets in the original are preserved.
_STRINGS = re.compile(
    r"""
    (?P<raw>r\#*"(?:[^"]|"(?!\#*))*?"\#*)   # raw string r"..." / r#"..."#
    |
    (?P<plain>"(?:\\.|[^"\\])*")             # plain string
    """,
    re.DOTALL | re.VERBOSE,
)


def _mask(text: str) -> str:
    """Replace comments / strings with same-length spaces (preserving \\n).

    This way line/column offsets in violations point back into the
    original text exactly.
    """
    out = list(text)

    def blank_match(m: re.Match[str]) -> None:
        for i in range(m.start(), m.end()):
            ch = out[i]
            if ch != "\n":
                out[i] = " "

    for m in _BLOCK_COMMENT.finditer(text):
        blank_match(m)
    masked = "".join(out)
    out = list(masked)
    for m in _LINE_COMMENT.finditer(masked):
        blank_match(m)
    masked = "".join(out)
    out = list(masked)
    for m in _STRINGS.finditer(masked):
        blank_match(m)
    return "".join(out)


def _line_col(text: str, pos: int) -> tuple[int, int]:
    """Convert an absolute char position into (1-indexed line, 1-indexed col)."""
    line = text.count("\n", 0, pos) + 1
    last_nl = text.rfind("\n", 0, pos)
    col = pos - last_nl if last_nl >= 0 else pos + 1
    return line, col


def _snippet(text: str, pos: int, width: int = 30) -> str:
    a = max(0, pos - width // 2)
    b = min(len(text), pos + width)
    s = text[a:b].replace("\n", " ⏎ ")
    if a > 0:
        s = "…" + s
    if b < len(text):
        s = s + "…"
    return s


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------

def scan_proof_block(block: str) -> List[SandboxViolation]:
    """Return all allowlist violations found in ``block``.

    Empty list ⇒ the block passed the sandbox and may be injected.
    """
    masked = _mask(block)
    violations: list[SandboxViolation] = []
    for pat, reason in _FORBIDDEN:
        for m in pat.finditer(masked):
            line, col = _line_col(block, m.start())
            violations.append(
                SandboxViolation(
                    pattern=pat.pattern,
                    reason=reason,
                    line=line,
                    col=col,
                    snippet=_snippet(block, m.start()),
                )
            )
    return violations


def format_violations(vs: Iterable[SandboxViolation]) -> str:
    """Render violations as a multi-line string for LLM feedback / logs."""
    out: list[str] = []
    for v in vs:
        out.append(
            f"  - line {v.line} col {v.col}: {v.reason}\n"
            f"    snippet: {v.snippet}"
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Self-test.
# ---------------------------------------------------------------------------

def _self_test() -> None:
    ok_block = """
    // safe proof: just asserts
    assert(x == y);
    assert forall|i: int| 0 <= i < n implies a[i] == b[i] by {
        // local reasoning
        assert(a[i] == b[i]);
    }
    reveal(spec_foo);
    broadcast use group_foo;
    lemma_seq_extensionality::<int>(s1, s2);
    """
    vs = scan_proof_block(ok_block)
    assert vs == [], f"safe block flagged: {vs}"

    bad_assume = "assert(x == y);\nassume(false);\n"
    vs = scan_proof_block(bad_assume)
    assert any("assume" in v.reason for v in vs), vs

    bad_attr = '#[verifier::external_body]\nproof { assert(true); }\n'
    vs = scan_proof_block(bad_attr)
    assert any("external" in v.reason for v in vs), vs

    bad_fn = "fn helper() -> int { 0 }\n"
    vs = scan_proof_block(bad_fn)
    assert any("fn" in v.pattern for v in vs), vs

    bad_admit = "admit();\n"
    vs = scan_proof_block(bad_admit)
    assert any("admit" in v.reason for v in vs), vs

    # Comments and strings must not trigger.
    commented = '// assume(false) — explanation\nassert(true);\n'
    vs = scan_proof_block(commented)
    assert vs == [], f"comment false-positive: {vs}"
    in_string = 'assert(msg == "assume(false)");\n'
    vs = scan_proof_block(in_string)
    assert vs == [], f"string literal false-positive: {vs}"

    # spec fn / proof fn forms.
    bad_spec_fn = "spec fn aux(x: int) -> int { x + 1 }\n"
    vs = scan_proof_block(bad_spec_fn)
    assert any("fn" in v.pattern for v in vs), vs

    print("sandbox self-test: PASS")


if __name__ == "__main__":
    _self_test()
