"""Parser for LLM responses that contain a Verus proof block.

The prompt asks for a single ```verus fenced block followed by an
optional ```json metadata block. We accept several lenient variants
(``rust`` / ``rs`` / no language tag) so a minor LLM hiccup doesn't
force a retry.

Pattern A — helper lemmas
-------------------------
The LLM may optionally emit a second fenced block tagged
``verus_lemmas`` (or the lenient ``lemmas`` / ``helpers``). It is
expected to contain one or more ``proof fn lemma_<name>(...)``
declarations at module scope. Those declarations are *not* placed
inside the det-check body; instead the runner splices them next to
the synthesised det-check fn so the det-check can call them.

The sandbox enforces a different (more permissive) set of constructs
for the helper block — see :mod:`sandbox.scan_helper_lemmas`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


# Try in order: ```verus ... ```, ```rust ... ```, ```rs ... ```, bare ``` ... ```
_FENCE_RE = re.compile(
    r"```(?P<lang>verus|rust|rs|)\s*\n(?P<body>.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)

# Pattern A: helper lemmas fenced block. Accept the canonical tag plus a
# few synonyms the LLM tends to use.
_LEMMA_FENCE_RE = re.compile(
    r"```(?P<lang>verus_lemmas|verus-lemmas|lemmas|helpers|verus_helpers)\s*\n(?P<body>.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)

_JSON_FENCE_RE = re.compile(
    r"```json\s*\n(?P<body>.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class ParsedProof:
    """The contents of one LLM response, parsed into structured form."""

    proof_block: str            # the Verus statements to inject (may be empty)
    rationale: str = ""         # optional LLM-provided explanation
    raw_response: str = ""      # full response text (for debug logs)
    helper_lemmas: str = ""     # Pattern A: optional module-scope proof fn lemmas


class ProofParseError(ValueError):
    """The LLM response did not contain a usable proof block."""


def parse_proof_response(text: str) -> ParsedProof:
    """Extract the proof block (and optional rationale / lemmas) from an LLM reply.

    Strategy:
      * Prefer the first ```verus`` fence. Fall back to ```rust``` /
        ```rs``` / bare triple-tick.
      * Optional ```json`` metadata block may contain ``{"rationale": "..."}``.
      * Optional ``verus_lemmas`` / ``lemmas`` / ``helpers`` fenced block
        carries module-scope proof fn declarations (Pattern A).
      * If no fenced block is found at all, raise :class:`ProofParseError`.
    """
    if not text or not text.strip():
        raise ProofParseError("empty LLM response")

    # Look for helper-lemma fenced blocks BEFORE we scan generic fences, so
    # they don't get mis-claimed as a primary proof_block fallback. Multiple
    # helper-lemma blocks are concatenated with a blank line.
    helper_chunks: list[str] = []
    helper_spans: list[tuple[int, int]] = []
    for m in _LEMMA_FENCE_RE.finditer(text):
        body = m.group("body").strip()
        if body:
            helper_chunks.append(body)
            helper_spans.append((m.start(), m.end()))
    helper_lemmas = "\n\n".join(helper_chunks)

    # Mask the helper-lemma regions so the generic fence scan below
    # cannot accidentally treat them as the proof block.
    if helper_spans:
        chars = list(text)
        for a, b in helper_spans:
            for i in range(a, b):
                chars[i] = " "
        scan_text = "".join(chars)
    else:
        scan_text = text

    # First, look for a verus-tagged fence (highest priority).
    verus_match: Optional[re.Match[str]] = None
    fallback_match: Optional[re.Match[str]] = None
    for m in _FENCE_RE.finditer(scan_text):
        lang = m.group("lang").lower()
        if lang == "verus" and verus_match is None:
            verus_match = m
            break
        if lang in ("rust", "rs", "") and fallback_match is None:
            # Skip if this is actually the json fence; that block has lang=='json'
            # but our regex's lang group only matches verus/rust/rs/empty so
            # json blocks won't be picked up here.
            fallback_match = m

    chosen = verus_match or fallback_match
    if chosen is None:
        raise ProofParseError(
            "no fenced code block found in LLM response. "
            "Expected ```verus … ``` (or ```rust … ```)."
        )
    proof_block = chosen.group("body").rstrip()

    rationale = ""
    jm = _JSON_FENCE_RE.search(text)
    if jm is not None:
        try:
            meta = json.loads(jm.group("body"))
            if isinstance(meta, dict):
                r = meta.get("rationale")
                if isinstance(r, str):
                    rationale = r.strip()
        except json.JSONDecodeError:
            # Non-fatal: rationale is optional, parse failure shouldn't block.
            pass

    return ParsedProof(
        proof_block=proof_block,
        rationale=rationale,
        raw_response=text,
        helper_lemmas=helper_lemmas,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> None:
    sample = """\
Here is my proof:

```verus
assert(x == y);
assert forall|i: int| 0 <= i < n implies a[i] == b[i] by {
    assert(a[i] == b[i]);
}
```

```json
{"rationale": "case-split on bounds then pointwise."}
```
"""
    pr = parse_proof_response(sample)
    assert "assert(x == y);" in pr.proof_block
    assert "case-split" in pr.rationale, pr.rationale
    assert pr.helper_lemmas == "", pr.helper_lemmas

    bare_rust = "```rust\nreveal(spec_foo);\n```"
    pr2 = parse_proof_response(bare_rust)
    assert pr2.proof_block.strip() == "reveal(spec_foo);"
    assert pr2.rationale == ""

    try:
        parse_proof_response("no code at all here")
        assert False, "should have raised"
    except ProofParseError:
        pass

    # verus fence preferred over rust fence
    mixed = "```rust\nignored();\n```\n```verus\nreveal(foo);\n```"
    pr3 = parse_proof_response(mixed)
    assert "reveal(foo)" in pr3.proof_block, pr3.proof_block
    assert "ignored" not in pr3.proof_block, pr3.proof_block

    # Pattern A: helper-lemma fence is captured separately and DOES NOT
    # bleed into the proof_block fallback.
    with_helpers = """\
Helper first:

```verus_lemmas
proof fn lemma_sorted_unique(a: Seq<int>, i: int, j: int)
    requires sorted(a), 0 <= i < a.len(), 0 <= j < a.len(), a[i] == a[j]
    ensures i == j
{}
```

Then the body:

```verus
lemma_sorted_unique(s, 3, 7);
assert(r1 == r2);
```
"""
    pr4 = parse_proof_response(with_helpers)
    assert "lemma_sorted_unique" in pr4.helper_lemmas, pr4.helper_lemmas
    assert "proof fn lemma_sorted_unique" in pr4.helper_lemmas
    # Critically, the helper body must NOT have leaked into proof_block.
    assert "proof fn" not in pr4.proof_block, pr4.proof_block
    assert "lemma_sorted_unique(s, 3, 7);" in pr4.proof_block, pr4.proof_block

    # Synonym tags accepted, multiple blocks concatenated.
    with_two_helpers = """\
```lemmas
proof fn lemma_a() {}
```

```helpers
proof fn lemma_b() {}
```

```verus
lemma_a(); lemma_b();
```
"""
    pr5 = parse_proof_response(with_two_helpers)
    assert "lemma_a" in pr5.helper_lemmas and "lemma_b" in pr5.helper_lemmas
    assert "lemma_a(); lemma_b();" in pr5.proof_block

    # No helper block -> empty helper_lemmas, proof_block unaffected.
    no_helpers = "```verus\nassert(true);\n```"
    pr6 = parse_proof_response(no_helpers)
    assert pr6.helper_lemmas == ""
    assert "assert(true);" in pr6.proof_block

    print("parser self-test: PASS")


if __name__ == "__main__":
    _self_test()
