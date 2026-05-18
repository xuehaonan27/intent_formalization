"""Tier 1.5 — static gap detector.

Lists what is missing or incomplete in a ``FunctionSpec`` so the LLM knows
exactly which types to resolve. The detector is purely static — no LLM,
no expensive analysis. Each ``Gap`` carries a short reason code so the
prompt can phrase the ask precisely.

Trigger conditions
------------------
1. ``GENERIC_UNRESOLVED`` — ``self_type`` (or any param/return) is a name
   containing ``<…>``, and the bare-name part (before the first ``<``) is
   not in ``type_defs``. Catches ``HashMap<V>`` etc. when the worklist's
   ``_lookup`` failed to type-arg-strip the name.
2. ``UNKNOWN_KIND_REACHABLE`` — any reachable ``TypeInfo`` has
   ``kind=UNKNOWN`` and ``name`` is non-primitive, non-tuple, and not
   already in ``type_defs``. Catches type-refs that the worklist gave up on
   (e.g. macro-wrapped definitions invisible to ``enum_item``-style walks).
3. ``MACRO_WRAPPED`` — the type appears as ``pub enum X`` / ``pub struct X``
   inside a ``macro_invocation`` token tree somewhere in the parsed source,
   so the standard ``enum_item`` / ``struct_item`` AST walks miss it.
4. ``MISSING_SPEC_VIEW`` — a struct in ``type_defs`` has
   ``spec_view is None`` *and* the source contains an inherent
   ``spec fn view`` for it, but the existing ``_find_view_method_return``
   helper didn't pick it up (e.g. the impl is ``impl<T> X<T> { … }`` —
   children are ``[impl, type_parameters, generic_type, …]``).

We do NOT trigger on:

* ``spec_view`` with ``kind=UNKNOWN`` (these are abstract IronSpec types
  intentionally treated as opaque — the gen_det STRUCT branch handles them
  correctly via ``(lhs)@ == (rhs)@``).
* Primitive type names (``usize``, ``bool``, ``u64`` …).
* Bare ``Vec<…>`` / ``Seq<…>`` / ``Map<…>`` / ``Set<…>`` / ``Option<…>`` /
  ``Result<…>`` / ``Ghost<…>`` / ``Tracked<…>`` — those are prelude rules
  handled by ``_parse_type_node`` and don't need a TypeInfo in ``type_defs``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import tree_sitter as ts
import tree_sitter_verus

from spec_determinism.extract import extractor as _ex
from spec_determinism.extract.types import (
    FunctionSpec,
    TypeInfo,
    TypeKind,
)


_LANG = ts.Language(tree_sitter_verus.language())
_PARSER = ts.Parser(_LANG)


# Prelude-handled names: gen_det understands them without a TypeInfo
# in type_defs. Keep in sync with extract.extractor._KNOWN_GENERICS.
_PRELUDE_NAMES = frozenset({
    "Vec", "Seq", "Set", "Map", "Option", "Result",
    "Ghost", "Tracked", "PointsTo",
    "Box", "Rc", "Arc",   # transparent wrappers — gen_det treats inner as the real thing
})

_PRIMITIVE_NAMES = frozenset({
    "usize", "isize", "u8", "u16", "u32", "u64", "u128",
    "i8", "i16", "i32", "i64", "i128",
    "bool", "char", "str", "int", "nat",
    "()",
})


@dataclass
class Gap:
    """A missing or incomplete type the LLM should resolve."""
    name: str                    # bare type name, e.g. "HashMap"
    reason: str                  # one of REASON_* below
    where_seen: str              # human-readable context (param/field/self/...)
    hint: str = ""               # any static hint (e.g. macro head, impl line)


REASON_GENERIC_UNRESOLVED = "generic_unresolved"
REASON_UNKNOWN_KIND = "unknown_kind"
REASON_MACRO_WRAPPED = "macro_wrapped"
REASON_MISSING_SPEC_VIEW = "missing_spec_view"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bare_name(name: str) -> str:
    """``HashMap<u8>`` → ``HashMap``; ``Foo`` → ``Foo``; ``()`` → ``()``."""
    if "<" not in name:
        return name
    return name.split("<", 1)[0].strip()


def _is_skippable(name: str) -> bool:
    """True if ``name`` is a primitive or prelude container — no TypeInfo
    in ``type_defs`` is expected."""
    bare = _bare_name(name)
    if bare in _PRIMITIVE_NAMES:
        return True
    if bare in _PRELUDE_NAMES:
        return True
    # collections::HashMap and similar fully-qualified paths — skip the
    # qualification, defer to the bare-name check.
    if "::" in bare:
        bare = bare.rsplit("::", 1)[-1]
        return bare in _PRIMITIVE_NAMES or bare in _PRELUDE_NAMES
    # Generic-parameter placeholders (single uppercase letter or two-letter
    # placeholders like K / V / KT / VT). These are type-vars, not types
    # the LLM should resolve.
    if bare.isupper() and 1 <= len(bare) <= 3:
        return True
    return False


def _collect_typeinfo_names(ti: TypeInfo, out: list[tuple[str, TypeInfo]],
                            origin: str) -> None:
    """Walk a TypeInfo recursively and gather (name, the_typeinfo, origin)
    so the caller can decide which need to be in ``type_defs``."""
    if ti.name:
        out.append((ti.name, ti))
    for ta in ti.type_args:
        _collect_typeinfo_names(ta, out, origin)
    for f in ti.fields:
        _collect_typeinfo_names(f.type, out, origin)
    for v in ti.variants:
        if v.inner:
            _collect_typeinfo_names(v.inner, out, origin)
    if ti.spec_view is not None:
        _collect_typeinfo_names(ti.spec_view, out, origin)


def _find_macro_wrapped_decls(source: str) -> dict[str, str]:
    """Find ``pub enum X`` / ``pub struct X`` declarations hidden inside
    ``macro_invocation`` nodes (e.g. ``define_enum_and_derive_marshalable!``).

    Returns ``{type_name: macro_name}`` so the prompt can tell the LLM
    "look inside macro `M!{...}` for `X`".
    """
    tree = _PARSER.parse(source.encode())
    out: dict[str, str] = {}

    pat = re.compile(
        r"\bpub\s+(?:enum|struct)\s+([A-Z][A-Za-z0-9_]*)\b"
    )

    def walk(node: ts.Node) -> None:
        if node.type == "macro_invocation":
            text = source[node.start_byte:node.end_byte]
            # macro name = identifier child before the `!`
            macro_name = ""
            for c in node.children:
                if c.type == "identifier" or c.type == "scoped_identifier":
                    macro_name = source[c.start_byte:c.end_byte]
                    break
            for m in pat.finditer(text):
                tname = m.group(1)
                out.setdefault(tname, macro_name or "<unknown_macro>")
        for c in node.children:
            walk(c)

    walk(tree.root_node)
    return out


def _find_inherent_view_for(source: str, type_name: str) -> Optional[str]:
    """Best-effort: does the source contain an inherent ``spec fn view`` for
    ``type_name``? Returns the impl-header line text or ``None``. Uses
    regex (not AST) because we explicitly want to catch the generic-impl
    case where ``_find_view_method_return`` fails."""
    # match `impl[<…>] X[<…>] {`  followed eventually by `spec fn view(self)`.
    # Use a generous capture: stop at the next top-level `}` is too slow,
    # so we just look for the impl-header and a spec fn view nearby.
    pat = re.compile(
        r"impl(?:\s*<[^>]+>)?\s+"
        + re.escape(type_name)
        + r"(?:\s*<[^>]+>)?\s*\{",
    )
    for m in pat.finditer(source):
        # Look for `spec fn view(self)` in the next ~2000 chars
        window = source[m.start(): m.start() + 4000]
        if re.search(r"\bspec\s+fn\s+view\s*\(\s*(?:&\s*)?self\s*\)", window):
            # Return the impl header (first line up to `{`)
            header = source[m.start(): m.end()].splitlines()[0]
            return header.strip()
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_gaps(spec: FunctionSpec, source: str) -> list[Gap]:
    """Enumerate gaps in ``spec.type_defs`` relative to ``source``.

    ``source`` is the same source text that was passed to ``extract_spec``.
    For the verusage pipeline this is the ``injected.rs`` content; for other
    callers it can be the bare project file.
    """
    gaps: list[Gap] = []
    seen_names: set[str] = set()

    def _add(g: Gap) -> None:
        key = (g.name, g.reason)
        if key in seen_names:
            return
        seen_names.add(key)
        gaps.append(g)

    # 1) self_type unresolved
    if spec.self_type:
        bare = _bare_name(spec.self_type)
        if (not _is_skippable(spec.self_type)
                and bare not in spec.type_defs):
            _add(Gap(
                name=bare,
                reason=(REASON_GENERIC_UNRESOLVED
                        if "<" in spec.self_type
                        else REASON_UNKNOWN_KIND),
                where_seen=f"self_type {spec.self_type!r}",
            ))

    # 2) reachable UNKNOWN-kind names not in type_defs
    reachable: list[tuple[str, TypeInfo]] = []
    for p in spec.params:
        _collect_typeinfo_names(p.type, reachable,
                                f"param {p.name}: {p.type.name}")
    _collect_typeinfo_names(spec.return_type, reachable,
                            f"return: {spec.return_type.name}")
    for tn, td in list(spec.type_defs.items()):
        _collect_typeinfo_names(td, reachable, f"type_def {tn}")

    for name, ti in reachable:
        if _is_skippable(name):
            continue
        bare = _bare_name(name)
        if bare in spec.type_defs:
            continue
        if bare in _PRELUDE_NAMES or bare in _PRIMITIVE_NAMES:
            continue
        # An UNKNOWN-kind name reachable from anywhere is a candidate.
        if ti.kind == TypeKind.UNKNOWN:
            reason = (REASON_GENERIC_UNRESOLVED
                      if "<" in name
                      else REASON_UNKNOWN_KIND)
            _add(Gap(name=bare, reason=reason, where_seen=name))

    # 3) macro-wrapped: find declarations hidden inside macros, then check
    # whether they're referenced from anywhere reachable but missing.
    macro_wrapped = _find_macro_wrapped_decls(source)
    referenced_names: set[str] = set()
    for name, _ti in reachable:
        referenced_names.add(_bare_name(name))
    for tname, macro_name in macro_wrapped.items():
        if tname in referenced_names and tname not in spec.type_defs:
            _add(Gap(
                name=tname,
                reason=REASON_MACRO_WRAPPED,
                where_seen=f"macro {macro_name}!{{ pub … {tname} … }}",
                hint=f"defined inside macro `{macro_name}!`",
            ))

    # 4) missing spec_view for structs that DO have an inherent view fn
    for tname, td in list(spec.type_defs.items()):
        if td.kind != TypeKind.STRUCT:
            continue
        if td.spec_view is not None:
            continue
        header = _find_inherent_view_for(source, tname)
        if header:
            _add(Gap(
                name=tname,
                reason=REASON_MISSING_SPEC_VIEW,
                where_seen=f"struct {tname} in type_defs, no spec_view",
                hint=f"source has `{header}` with `spec fn view`",
            ))

    return gaps


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    # Build a tiny FunctionSpec by hand and synthesise a matching source
    # string with a generic struct + a macro-wrapped enum + a missing view.
    from spec_determinism.extract.types import (
        Param, TypeInfo as TI, TypeKind as TK,
    )

    src = """
pub struct CSingleDelivery {
    pub send_state: CSendState,
}

pub struct CSendState {
    pub epmap: HashMap<CAckState>,
}

pub struct CAckState {
    pub num_packets_acked: u64,
}

pub struct HashMap<V> {
    m: u8,
}

impl<V> HashMap<V> {
    pub uninterp spec fn view(self) -> Map<EndPoint, V>;
}

define_enum_and_derive_marshalable! {
    pub enum CSingleMessage {
        Message { seqno: u64 },
    }
}

pub struct Plain {
    inner: u32,
}

impl Plain {
    pub open spec fn view(self) -> u32 { 0 }
}
"""
    spec = FunctionSpec(
        name="f",
        params=[
            Param(name="self", type=TI(TK.STRUCT, "CSingleDelivery",
                  fields=[], variants=[], type_args=[]),
                  is_self=True),
            Param(name="msg", type=TI(TK.UNKNOWN, "CSingleMessage")),
            Param(name="h", type=TI(TK.UNKNOWN, "HashMap<u8>")),
            Param(name="p", type=TI(TK.STRUCT, "Plain")),
        ],
        return_type=TI(TK.UNIT, "()"),
        requires=[],
        ensures=[],
        type_defs={
            # Pretend extract_spec only found CSingleDelivery, CSendState,
            # CAckState, and Plain. HashMap + CSingleMessage missing.
            "CSingleDelivery": TI(TK.STRUCT, "CSingleDelivery"),
            "CSendState": TI(TK.STRUCT, "CSendState"),
            "CAckState": TI(TK.STRUCT, "CAckState"),
            "Plain": TI(TK.STRUCT, "Plain"),
        },
        self_type="CSingleDelivery",
    )

    gaps = detect_gaps(spec, src)
    names = sorted((g.name, g.reason) for g in gaps)
    expected = [
        ("CSingleMessage", REASON_MACRO_WRAPPED),
        ("CSingleMessage", REASON_UNKNOWN_KIND),
        ("HashMap", REASON_GENERIC_UNRESOLVED),
        ("Plain", REASON_MISSING_SPEC_VIEW),
    ]
    # We expect at least the macro_wrapped + generic_unresolved + missing_view
    # gaps. UNKNOWN_KIND for CSingleMessage *and* macro_wrapped both fire —
    # the LLM wants the macro hint, but having both is fine and de-dupes
    # at the prompt level. Keep both to surface maximum information.
    ok = True
    for want in expected:
        if want not in names:
            print(f"FAIL: missing gap {want!r}; got {names}")
            ok = False

    # Skippable: prelude / primitive names should never appear as gaps.
    for g in gaps:
        if _bare_name(g.name) in _PRELUDE_NAMES | _PRIMITIVE_NAMES:
            print(f"FAIL: prelude/primitive surfaced as gap: {g.name}")
            ok = False

    # _bare_name sanity
    if _bare_name("HashMap<u8>") != "HashMap":
        print("FAIL: _bare_name('HashMap<u8>')")
        ok = False
    if _bare_name("Foo") != "Foo":
        print("FAIL: _bare_name('Foo')")
        ok = False

    print("gaps self-test:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
