"""Tier 1.5 — round-trip a ``type_str`` to a ``TypeInfo`` through tree-sitter.

Why a dedicated parser
----------------------
The LLM patches emit textual type expressions like ``Map<AbstractKey, Seq<u8>>``
or ``Vec<CSingleMessage>``. We need these to become ``TypeInfo`` instances
that flow through gen_det exactly as if ``extract_spec`` had produced them
from real source — so we reuse the same ``_parse_type_node`` helper that
``extract_spec`` uses. That way:

* ``Vec<T>`` is automatically tagged ``kind=SEQ`` with ``spec_view=Seq<T>``
  (prelude rule baked into ``_parse_type_node``).
* ``Map<K,V>`` becomes ``kind=MAP``, ``Result<T,E>`` becomes ``kind=RESULT``
  with the correct variant scaffolding, etc.
* Primitives and unit auto-classify.

This module is intentionally tiny: it wraps the input string into a synthetic
``type X = <s>;`` declaration, parses it, walks to the type node, and hands
the node off to ``extract.extractor._parse_type_node``.

If the type_str cannot be parsed at all, ``parse_type_str`` raises
``ValueError`` — the validator (V2) treats that as patch-rejection and the
applier never sees the patch.
"""

from __future__ import annotations

from typing import Optional

import tree_sitter as ts
import tree_sitter_verus

from spec_determinism.extract import extractor as _ex
from spec_determinism.extract.types import TypeInfo, TypeKind


_LANG = ts.Language(tree_sitter_verus.language())
_PARSER = ts.Parser(_LANG)


def _walk_for_type_node(node: ts.Node) -> Optional[ts.Node]:
    """Find the first descendant node that looks like a type expression."""
    # Most direct: a type alias `type __X = T;` exposes the rhs as one of the
    # well-known type-node kinds the extractor's _parse_type_node accepts.
    type_node_kinds = {
        "primitive_type", "unit_type", "type_identifier",
        "generic_type", "scoped_type_identifier", "reference_type",
        "tuple_type", "array_type",
    }
    if node.type in type_node_kinds:
        return node
    for c in node.children:
        r = _walk_for_type_node(c)
        if r is not None:
            return r
    return None


def parse_type_str(s: str) -> TypeInfo:
    """Parse a textual type expression like ``Map<AbstractKey, Seq<u8>>`` into
    a fully-tagged :class:`TypeInfo`.

    The returned TypeInfo uses the same prelude classification as
    ``extract_spec`` would have produced from real source.

    Raises ``ValueError`` if the string cannot be parsed as a Rust type.
    """
    if not s or not isinstance(s, str):
        raise ValueError(f"parse_type_str: empty or non-str input: {s!r}")

    s = s.strip()
    # Strip leading `&` / `&mut` references — _parse_type_node handles
    # reference_type recursively, but our wrapper "type __X = &T;" is more
    # robust when the rhs is already a bare type. Both paths work; normalising
    # gives stabler output names.
    while s.startswith("&"):
        s = s[1:].lstrip()
        if s.startswith("mut "):
            s = s[4:].lstrip()

    # Wrap in `type __t15_probe = <s>;` and parse. We then locate the
    # ``type_item`` AST node anywhere in the tree, and extract only its rhs
    # (the child that follows the ``=`` token). Note the rhs is *not*
    # necessarily an immediate child of ``source_file`` — tree-sitter wraps
    # the type alias in ``declaration_with_attrs``.
    src = f"type __t15_probe = {s};".encode()
    tree = _PARSER.parse(src)

    # Reject inputs that produce parse errors — tree-sitter is forgiving and
    # will give partial trees for clearly-broken input like ``totally not a
    # type @@@``; we want to surface those as ValueError.
    def _has_error(node: ts.Node) -> bool:
        if node.has_error or node.type == "ERROR":
            return True
        for c in node.children:
            if _has_error(c):
                return True
        return False

    if _has_error(tree.root_node):
        raise ValueError(f"parse_type_str: tree-sitter parse error on {s!r}")

    def _find_type_item(node: ts.Node) -> Optional[ts.Node]:
        if node.type in ("type_alias", "type_item"):
            return node
        for c in node.children:
            r = _find_type_item(c)
            if r is not None:
                return r
        return None

    type_item = _find_type_item(tree.root_node)

    rhs_node: Optional[ts.Node] = None
    if type_item is not None:
        saw_eq = False
        for cc in type_item.children:
            if cc.type == "=":
                saw_eq = True
                continue
            if saw_eq and cc.type != ";":
                rhs_node = _walk_for_type_node(cc)
                if rhs_node is not None:
                    break

    if rhs_node is None:
        raise ValueError(
            f"parse_type_str: could not find a type node in parse of {s!r}"
        )

    ti = _ex._parse_type_node(rhs_node)
    if ti is None:
        raise ValueError(f"parse_type_str: _parse_type_node returned None for {s!r}")
    return ti


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    cases: list[tuple[str, TypeKind, Optional[str]]] = [
        # (input, expected kind, expected name hint or None)
        ("usize",           TypeKind.USIZE,    "usize"),
        ("()",              TypeKind.UNIT,     "()"),
        ("bool",            TypeKind.BOOL,     "bool"),
        ("u64",             TypeKind.U64,      "u64"),
        ("Vec<u8>",         TypeKind.SEQ,      "Vec<u8>"),
        ("Seq<u8>",         TypeKind.SEQ,      "Seq<u8>"),
        ("Map<u32, u8>",    TypeKind.MAP,      None),
        ("Set<u32>",        TypeKind.SET,      None),
        ("Option<u8>",      TypeKind.OPTION,   None),
        ("Result<u8, ()>",  TypeKind.RESULT,   None),
        ("HashMap<EndPoint, V>", TypeKind.UNKNOWN, None),  # HashMap not in prelude
        ("Foo",             TypeKind.UNKNOWN,  "Foo"),
        ("Map<AbstractKey, Seq<u8>>", TypeKind.MAP, None),
    ]
    ok = 0
    for inp, want_kind, want_name in cases:
        try:
            ti = parse_type_str(inp)
        except Exception as e:
            print(f"FAIL: parse_type_str({inp!r}) raised {e}")
            continue
        if ti.kind != want_kind:
            print(f"FAIL: parse_type_str({inp!r}).kind = {ti.kind} (want {want_kind})")
            continue
        if want_name and ti.name != want_name:
            print(f"FAIL: parse_type_str({inp!r}).name = {ti.name!r} (want {want_name!r})")
            continue
        ok += 1

    # Vec<T>.spec_view should be Seq<T>
    vec_ti = parse_type_str("Vec<u8>")
    if vec_ti.spec_view is None or vec_ti.spec_view.kind != TypeKind.SEQ:
        print(f"FAIL: Vec<u8>.spec_view should be Seq, got {vec_ti.spec_view}")
    else:
        ok += 1

    # Map<K,V>.type_args length
    map_ti = parse_type_str("Map<u32, u8>")
    if len(map_ti.type_args) != 2:
        print(f"FAIL: Map<u32, u8>.type_args length = {len(map_ti.type_args)} (want 2)")
    else:
        ok += 1

    # Error path
    try:
        parse_type_str("")
        print("FAIL: empty string should have raised ValueError")
    except ValueError:
        ok += 1

    total = len(cases) + 3
    print(f"parse self-test: {ok}/{total} passed")
    return ok == total


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
