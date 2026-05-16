"""Parser for LLM responses that contain a Verus proof block.

The prompt asks for a single ```verus fenced block followed by an
optional ```json metadata block. We accept several lenient variants
(``rust`` / ``rs`` / no language tag) so a minor LLM hiccup doesn't
force a retry.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional


# Try in order: ```verus ... ```, ```rust ... ```, ```rs ... ```, bare ``` ... ```
_FENCE_RE = re.compile(
    r"```(?P<lang>verus|rust|rs|)\s*\n(?P<body>.*?)\n```",
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


class ProofParseError(ValueError):
    """The LLM response did not contain a usable proof block."""


def parse_proof_response(text: str) -> ParsedProof:
    """Extract the proof block (and optional rationale) from an LLM reply.

    Strategy:
      * Prefer the first ```verus`` fence. Fall back to ```rust``` /
        ```rs``` / bare triple-tick.
      * Optional ```json`` metadata block may contain ``{"rationale": "..."}``.
      * If no fenced block is found at all, raise :class:`ProofParseError`.
    """
    if not text or not text.strip():
        raise ProofParseError("empty LLM response")

    # First, look for a verus-tagged fence (highest priority).
    verus_match: Optional[re.Match[str]] = None
    fallback_match: Optional[re.Match[str]] = None
    for m in _FENCE_RE.finditer(text):
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

    print("parser self-test: PASS")


if __name__ == "__main__":
    _self_test()
