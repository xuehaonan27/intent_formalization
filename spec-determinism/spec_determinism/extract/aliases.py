"""Normalize ``verus!``-macro aliases (e.g. ``verus_!``) to plain ``verus!``.

tree-sitter-verus only parses the contents of a literal ``verus! { ... }``
macro invocation into a ``verus_block``; aliased invocations such as

```rust
use verus as verus_;
verus_! {
    pub fn new() -> Self { ... }
}
```

parse as an opaque ``macro_invocation`` whose token tree is invisible to the
AST. vstd uses the ``verus_`` alias in (at least) ``cell/invcell.rs``,
``cell/pcell.rs``, ``cell/pcell_maybe_uninit.rs``, ``tokens.rs``, ``map.rs``
and several ``std_specs/*.rs`` files — without normalization, every function
inside those blocks is missing from extraction, type discovery and the
inventory scanner.

The rewrite is line-preserving: only the alias identifier token is replaced
(``verus_!`` -> ``verus!``), which shortens the line by one byte per
occurrence but never adds or removes newlines, so 1-based line numbers used
for ``module:fn@line`` target selection remain valid. Byte offsets after an
occurrence shift within the same line, so callers must parse *and* slice
from the normalized text consistently (``extract_spec`` does exactly that).

The transform is idempotent and a no-op on files without aliases.
"""
from __future__ import annotations

import re

# ``use verus as verus_;`` or ``use some::path::verus as verus_;``
_ALIAS_USE_RE = re.compile(
    r"\buse\s+(?:[A-Za-z_][A-Za-z0-9_]*::)*verus\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\s*;"
)


def find_verus_aliases(source: str) -> list[str]:
    """Return the macro aliases bound to ``verus`` in *source* (e.g. ``["verus_"]``)."""
    return _ALIAS_USE_RE.findall(source)


def normalize_verus_aliases(source: str) -> str:
    """Rewrite ``<alias>!`` invocations to ``verus!`` for every bound alias.

    Only the alias identifier is replaced (lookahead keeps the ``!``), so the
    newline structure of *source* is untouched. Idempotent.
    """
    for alias in set(find_verus_aliases(source)):
        source = re.sub(
            rf"\b{re.escape(alias)}(?=\s*!)",
            "verus",
            source,
        )
    return source


if __name__ == "__main__":
    sample = (
        "use verus as verus_;\n"
        "\n"
        "verus_! {\n"
        "    pub fn new() -> Self { todo!() }\n"
        "    // verus_! mentioned in a comment stays a comment token-wise\n"
        "}\n"
        "\n"
        "verus! {\n"
        "    pub fn old() -> Self { todo!() }\n"
        "}\n"
    )
    out = normalize_verus_aliases(sample)
    assert "verus_! {" not in out, out
    assert out.count("verus! {") == 2, out
    assert "use verus as verus_;" in out
    assert len(out.splitlines()) == len(sample.splitlines())
    # idempotent
    assert normalize_verus_aliases(out) == out
    # no alias -> no-op
    plain = "verus! { fn f() {} }\n"
    assert normalize_verus_aliases(plain) == plain
    print("aliases self-test ok")
