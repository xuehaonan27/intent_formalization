"""Type registry — Phase 1: structural type dependency graph.

Walks a Verus source file, enumerates every top-level *type definition*
(``struct`` / ``enum`` / ``union`` / ``type`` alias) — including those nested
under ``mod`` blocks — and records:

* its kind, generics, visibility, derives, ``cfg(...)`` guards;
* whether it is marked ``#[verifier::external_body]`` /
  ``#[verifier::external_type_specification]``;
* for structs: each field's name, raw type text, and the *short* type names
  it references (e.g. ``Vec<Option<Bar>>`` → ``["Vec", "Option", "Bar"]``);
* for enums: each variant (unit / tuple / named struct), with the same
  per-field info.

The output is a per-file dependency graph (nodes = type defs, edges =
"this type's body references that type by name"). It is **deliberately
unresolved** — short names are recorded as written; we do *not* try to map
``crate::foo::Bar`` to a fully-qualified name in this phase. Resolution
(use-tracking, View impls, trait impls) is Phase 2 work.

Verusage corpus is flat single-file style — every `.rs` is self-contained.
The registry therefore operates one source file at a time. A separate
audit CLI rolls up registries across a project for cross-file statistics.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import tree_sitter as ts

from .extract import _child_by_type, _children_by_type, _parser, _text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class GenericParam:
    """A single generic parameter on a type definition."""
    kind: str            # "type" | "lifetime" | "const"
    name: str            # "T" / "'a" / "N"
    raw: str             # full source text incl. bounds / default
    # Bound names referenced in trait bounds (so they get pruned out of edges).
    bounds: list[str] = field(default_factory=list)


@dataclass
class FieldDecl:
    """A struct field or an enum-variant field."""
    name: str            # named field name; "0" / "1" / ... for tuple positions
    type_text: str       # raw type expression as written
    type_refs: list[str] # short names referenced (excludes generic params)
    is_pub: bool = False
    span: tuple[int, int] = (0, 0)


@dataclass
class VariantDecl:
    """An enum variant (unit / tuple / struct-shaped)."""
    name: str
    kind: str                                # "unit" | "tuple" | "struct"
    fields: list[FieldDecl] = field(default_factory=list)


@dataclass
class TypeDef:
    """A single type definition."""
    name: str                                # local short name
    qualified_name: str                      # mod::path::Name
    kind: str                                # "struct" | "enum" | "union" | "alias"
    generics: list[GenericParam] = field(default_factory=list)
    fields: list[FieldDecl] = field(default_factory=list)        # struct/union
    variants: list[VariantDecl] = field(default_factory=list)    # enum
    alias_target: Optional[str] = None                           # type alias RHS
    alias_target_refs: list[str] = field(default_factory=list)
    is_external_body: bool = False
    is_external_type_specification: bool = False
    derives: list[str] = field(default_factory=list)
    visibility: str = ""                     # "" / "pub" / "pub(crate)" / ...
    cfg: list[str] = field(default_factory=list)
    source_file: str = ""
    source_line: int = 0


@dataclass
class TypeRegistry:
    """Per-file type registry.

    `types` is keyed by qualified name (mod path + local name); `short_names`
    maps a local name to all qualified names that share it (handles
    cfg-gated duplicates and inner-mod shadowing). `edges` records, for
    each qualified name, the set of *short* type names referenced in its
    body.
    """
    source_file: str
    types: dict[str, TypeDef] = field(default_factory=dict)
    short_names: dict[str, list[str]] = field(default_factory=dict)
    edges: dict[str, set[str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tree-sitter helpers (local — keep extract.py untouched)
# ---------------------------------------------------------------------------


def _attr_text(attr_node: ts.Node) -> str:
    """Return the inner attribute path text — e.g. for ``#[derive(Eq, Clone)]``
    return ``derive(Eq, Clone)`` (the bytes between ``#[`` / ``#![`` and ``]``).
    """
    return _text(attr_node).strip("#![] ").strip()


def _parse_derives(attr_text: str) -> list[str]:
    m = re.match(r"derive\s*\((.*)\)\s*$", attr_text, re.DOTALL)
    if not m:
        return []
    return [t.strip() for t in m.group(1).split(",") if t.strip()]


def _is_external_body(attr_text: str) -> bool:
    return "external_body" in attr_text and "verifier" in attr_text


def _is_external_type_specification(attr_text: str) -> bool:
    return "external_type_specification" in attr_text and "verifier" in attr_text


def _extract_cfg(attr_text: str) -> Optional[str]:
    if attr_text.startswith("cfg(") or attr_text.startswith("cfg_attr("):
        return attr_text
    return None


# ---------------------------------------------------------------------------
# Type-reference extraction
# ---------------------------------------------------------------------------

# Builtin / prelude names that should never be filtered as "user-defined refs"
# but are still recorded as referenced (they participate in the graph as
# external nodes — useful for the audit).
_PRIMITIVES = {
    "u8", "u16", "u32", "u64", "u128", "usize",
    "i8", "i16", "i32", "i64", "i128", "isize",
    "bool", "char", "str", "f32", "f64",
    "int", "nat",  # Verus spec types
}


def _looks_like_const_name(name: str) -> bool:
    """True for SCREAMING_SNAKE_CASE / all-caps names that are extremely
    unlikely to be a type. We use this as a heuristic filter because the
    tree-sitter-verus grammar classifies const arguments inside
    ``Array<T, NUM_PAGES>`` as ``type_identifier`` even though
    ``NUM_PAGES`` is a const item — there is no way to distinguish them
    structurally. Rust convention requires type names to be PascalCase
    and constants to be UPPER_SNAKE, so the rule "no lowercase letter →
    likely a const" is highly reliable in practice (no false positives
    seen in the verusage corpus' ~3.8k user types).
    """
    if not any(c.isalpha() for c in name):
        return False
    return all((not c.isalpha()) or c.isupper() for c in name)


def _collect_type_refs(node: ts.Node, generics: set[str]) -> list[str]:
    """Walk a type-expression subtree collecting every ``type_identifier`` /
    ``scoped_type_identifier`` head that is *not* a generic parameter bound
    in the enclosing scope.

    The result preserves first-seen order and de-dupes. Lifetimes and
    primitive keywords are dropped (lifetimes are not types; primitives
    are intentionally kept *only* if they appear via ``type_identifier``,
    e.g. ``str`` may show up as a primitive_type node and is skipped).
    Const-looking identifiers (UPPER_SNAKE_CASE) are filtered — see
    :func:`_looks_like_const_name`.
    """
    seen: list[str] = []
    seen_set: set[str] = set()

    def add(name: str) -> None:
        if name in generics or name in seen_set:
            return
        if _looks_like_const_name(name):
            return
        seen.append(name)
        seen_set.add(name)

    def visit(n: ts.Node) -> None:
        # Plain `type_identifier` leaves are the names we want, except when
        # they're part of a `scoped_type_identifier` (in which case we
        # already recorded the head).
        if n.type == "type_identifier":
            add(_text(n))
            return
        if n.type == "scoped_type_identifier":
            # Record the *last* identifier (the actual type) and drop the
            # scope path — Phase 1 doesn't resolve scopes. Walk children
            # to also catch generic args inside.
            tids = [c for c in n.named_children if c.type == "type_identifier"]
            if tids:
                add(_text(tids[-1]))
            for c in n.named_children:
                # only descend into type_arguments — the scope path itself
                # has been collapsed
                if c.type == "type_arguments":
                    visit(c)
            return
        if n.type == "function_type":
            # tree-sitter-verus parses ``spec_fn(u8) -> bool`` (and similar
            # Rust function-pointer types) as ``function_type`` whose first
            # named child is a ``type_identifier`` carrying the constructor
            # marker (``spec_fn`` / ``fn``). That marker is not a user type
            # — skip it and recurse only into params / return type.
            seen_head = False
            for c in n.named_children:
                if not seen_head and c.type == "type_identifier":
                    seen_head = True
                    continue
                visit(c)
            return
        if n.type == "primitive_type":
            # Never recorded as user-ref; primitives are leaves.
            return
        if n.type == "lifetime":
            return
        # Generic / reference / pointer / tuple / array / slice / dyn / impl
        # all have nested type expressions — recurse into them.
        for c in n.named_children:
            visit(c)

    visit(node)
    return seen


# ---------------------------------------------------------------------------
# Per-item parsing
# ---------------------------------------------------------------------------


def _parse_generics(node: ts.Node) -> tuple[list[GenericParam], set[str]]:
    """Parse a ``type_parameters`` node. Returns the parsed params and the
    set of names that should be filtered out of any field-type ref scan
    (i.e. type+const params; lifetimes are already filtered separately).
    """
    params: list[GenericParam] = []
    bound_names: set[str] = set()
    if node is None or node.type != "type_parameters":
        return params, bound_names
    for c in node.named_children:
        raw = _text(c)
        if c.type == "lifetime_parameter":
            params.append(GenericParam(kind="lifetime", name=raw, raw=raw))
        elif c.type == "type_parameter":
            tid = _child_by_type(c, "type_identifier")
            name = _text(tid) if tid else raw
            tb = _child_by_type(c, "trait_bounds")
            bounds = _collect_type_refs(tb, set()) if tb else []
            params.append(GenericParam(kind="type", name=name, raw=raw,
                                       bounds=bounds))
            bound_names.add(name)
        elif c.type == "const_parameter":
            ids = _children_by_type(c, "identifier")
            name = _text(ids[0]) if ids else raw
            params.append(GenericParam(kind="const", name=name, raw=raw))
            bound_names.add(name)
    return params, bound_names


def _parse_field_declaration(
    fd: ts.Node, generics: set[str]
) -> Optional[FieldDecl]:
    """Parse a ``field_declaration`` (named struct field)."""
    fname = _child_by_type(fd, "field_identifier")
    if not fname:
        return None
    # The field's type is the child after ':'. Find it positionally.
    after_colon = False
    type_node: Optional[ts.Node] = None
    for cc in fd.children:
        if cc.type == ":":
            after_colon = True
            continue
        if after_colon and cc.is_named:
            type_node = cc
            break
    if not type_node:
        return None
    is_pub = _child_by_type(fd, "visibility_modifier") is not None
    return FieldDecl(
        name=_text(fname),
        type_text=_text(type_node),
        type_refs=_collect_type_refs(type_node, generics),
        is_pub=is_pub,
        span=(fd.start_byte, fd.end_byte),
    )


def _parse_ordered_fields(
    odl: ts.Node, generics: set[str]
) -> list[FieldDecl]:
    """Parse an ``ordered_field_declaration_list`` (tuple struct / variant).

    Per-field elements are sequences of [optional visibility_modifier]
    [optional attribute_item*] <type-expr>. Positional names use indices.
    """
    out: list[FieldDecl] = []
    pending_pub = False
    for c in odl.children:
        if c.type == "visibility_modifier":
            pending_pub = True
            continue
        if c.type == "attribute_item":
            continue
        if not c.is_named:
            # punctuation '(' ',' ')'
            continue
        if c.type in ("visibility_modifier", "attribute_item"):
            continue
        # type expression
        out.append(FieldDecl(
            name=str(len(out)),
            type_text=_text(c),
            type_refs=_collect_type_refs(c, generics),
            is_pub=pending_pub,
            span=(c.start_byte, c.end_byte),
        ))
        pending_pub = False
    return out


def _parse_variants(
    vl: ts.Node, generics: set[str]
) -> list[VariantDecl]:
    out: list[VariantDecl] = []
    for c in vl.named_children:
        if c.type != "enum_variant":
            continue
        name_node = _child_by_type(c, "identifier") or _child_by_type(c, "type_identifier")
        if not name_node:
            continue
        name = _text(name_node)
        # Variant body: nothing → unit; ordered_field_declaration_list → tuple;
        # field_declaration_list → struct-shaped.
        odl = _child_by_type(c, "ordered_field_declaration_list")
        fdl = _child_by_type(c, "field_declaration_list")
        if fdl is not None:
            fields: list[FieldDecl] = []
            for fc in fdl.named_children:
                if fc.type == "field_declaration":
                    fld = _parse_field_declaration(fc, generics)
                    if fld:
                        fields.append(fld)
            out.append(VariantDecl(name=name, kind="struct", fields=fields))
        elif odl is not None:
            out.append(VariantDecl(
                name=name, kind="tuple",
                fields=_parse_ordered_fields(odl, generics)))
        else:
            out.append(VariantDecl(name=name, kind="unit", fields=[]))
    return out


def _parse_struct_item(
    node: ts.Node, qpath: list[str], src_file: str
) -> TypeDef:
    """Parse a ``struct_item`` (named-fields, tuple, or unit struct)."""
    name = _text(_child_by_type(node, "type_identifier"))
    tp = _child_by_type(node, "type_parameters")
    generics, bound = _parse_generics(tp)
    fields: list[FieldDecl] = []
    fdl = _child_by_type(node, "field_declaration_list")
    odl = _child_by_type(node, "ordered_field_declaration_list")
    if fdl is not None:
        for fc in fdl.named_children:
            if fc.type == "field_declaration":
                fld = _parse_field_declaration(fc, bound)
                if fld:
                    fields.append(fld)
    elif odl is not None:
        fields = _parse_ordered_fields(odl, bound)
    vis_node = _child_by_type(node, "visibility_modifier")
    return TypeDef(
        name=name,
        qualified_name="::".join(qpath + [name]),
        kind="struct",
        generics=generics,
        fields=fields,
        visibility=_text(vis_node) if vis_node else "",
        source_file=src_file,
        source_line=node.start_point[0] + 1,
    )


def _parse_enum_item(
    node: ts.Node, qpath: list[str], src_file: str
) -> TypeDef:
    name = _text(_child_by_type(node, "type_identifier"))
    tp = _child_by_type(node, "type_parameters")
    generics, bound = _parse_generics(tp)
    variants: list[VariantDecl] = []
    vl = _child_by_type(node, "enum_variant_list")
    if vl is not None:
        variants = _parse_variants(vl, bound)
    vis_node = _child_by_type(node, "visibility_modifier")
    return TypeDef(
        name=name,
        qualified_name="::".join(qpath + [name]),
        kind="enum",
        generics=generics,
        variants=variants,
        visibility=_text(vis_node) if vis_node else "",
        source_file=src_file,
        source_line=node.start_point[0] + 1,
    )


def _parse_union_item(
    node: ts.Node, qpath: list[str], src_file: str
) -> TypeDef:
    """Parse a ``union_item``. Treated as a struct-shape with a different
    kind — same field-declaration grammar."""
    name = _text(_child_by_type(node, "type_identifier"))
    tp = _child_by_type(node, "type_parameters")
    generics, bound = _parse_generics(tp)
    fields: list[FieldDecl] = []
    fdl = _child_by_type(node, "field_declaration_list")
    if fdl is not None:
        for fc in fdl.named_children:
            if fc.type == "field_declaration":
                fld = _parse_field_declaration(fc, bound)
                if fld:
                    fields.append(fld)
    vis_node = _child_by_type(node, "visibility_modifier")
    return TypeDef(
        name=name,
        qualified_name="::".join(qpath + [name]),
        kind="union",
        generics=generics,
        fields=fields,
        visibility=_text(vis_node) if vis_node else "",
        source_file=src_file,
        source_line=node.start_point[0] + 1,
    )


def _parse_type_alias(
    node: ts.Node, qpath: list[str], src_file: str
) -> TypeDef:
    """Parse a ``type_item`` (e.g. ``pub type Foo<T> = Vec<T>;``)."""
    name = _text(_child_by_type(node, "type_identifier"))
    tp = _child_by_type(node, "type_parameters")
    generics, bound = _parse_generics(tp)
    # The RHS is the last named child (after '=' and the lhs type_identifier).
    target_node: Optional[ts.Node] = None
    seen_eq = False
    for cc in node.children:
        if cc.type == "=":
            seen_eq = True
            continue
        if seen_eq and cc.is_named and cc.type != "type_parameters":
            target_node = cc
    target_text = _text(target_node) if target_node else None
    target_refs = _collect_type_refs(target_node, bound) if target_node else []
    vis_node = _child_by_type(node, "visibility_modifier")
    return TypeDef(
        name=name,
        qualified_name="::".join(qpath + [name]),
        kind="alias",
        generics=generics,
        alias_target=target_text,
        alias_target_refs=target_refs,
        visibility=_text(vis_node) if vis_node else "",
        source_file=src_file,
        source_line=node.start_point[0] + 1,
    )


# ---------------------------------------------------------------------------
# Top-level walker
# ---------------------------------------------------------------------------


_ITEM_TYPES = {
    "struct_item", "enum_item", "union_item", "type_item",
}


def _apply_attrs(td: TypeDef, attr_nodes: list[ts.Node]) -> None:
    """Fold pending attribute nodes into the type def's metadata."""
    derives: list[str] = []
    cfgs: list[str] = []
    for a in attr_nodes:
        text = _attr_text(a)
        derives.extend(_parse_derives(text))
        if _is_external_body(text):
            td.is_external_body = True
        if _is_external_type_specification(text):
            td.is_external_type_specification = True
        c = _extract_cfg(text)
        if c is not None:
            cfgs.append(c)
    td.derives.extend(derives)
    td.cfg.extend(cfgs)


def _walk_items(
    node: ts.Node,
    qpath: list[str],
    src_file: str,
    out_types: list[TypeDef],
) -> None:
    """Walk *children of a container* (source_file / verus_block /
    declaration_list). Honours the ``declaration_with_attrs`` wrapper —
    its first children are ``attribute_item``s, the last is the actual
    item (``struct_item`` / ``mod_item`` / ...).
    """
    for child in node.named_children:
        if child.type == "verus_block":
            _walk_items(child, qpath, src_file, out_types)
        elif child.type == "declaration_with_attrs":
            attrs = [c for c in child.named_children if c.type == "attribute_item"]
            inner = next(
                (c for c in child.named_children if c.type != "attribute_item"),
                None,
            )
            if inner is None:
                continue
            _process_inner(inner, qpath, src_file, out_types, attrs)
        else:
            _process_inner(child, qpath, src_file, out_types, [])


def _process_inner(
    inner: ts.Node,
    qpath: list[str],
    src_file: str,
    out_types: list[TypeDef],
    attrs: list[ts.Node],
) -> None:
    if inner.type == "mod_item":
        # Inner mod: descend with extended path.
        name_node = _child_by_type(inner, "identifier")
        modname = _text(name_node) if name_node else "<anon>"
        body = _child_by_type(inner, "declaration_list")
        if body is not None:
            _walk_items(body, qpath + [modname], src_file, out_types)
        return
    if inner.type not in _ITEM_TYPES:
        return
    if inner.type == "struct_item":
        td = _parse_struct_item(inner, qpath, src_file)
    elif inner.type == "enum_item":
        td = _parse_enum_item(inner, qpath, src_file)
    elif inner.type == "union_item":
        td = _parse_union_item(inner, qpath, src_file)
    elif inner.type == "type_item":
        td = _parse_type_alias(inner, qpath, src_file)
    else:
        return
    _apply_attrs(td, attrs)
    out_types.append(td)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_registry(source: str, source_file: str = "<memory>") -> TypeRegistry:
    """Parse *source* and produce a :class:`TypeRegistry` for its type defs."""
    tree = _parser.parse(source.encode())
    if tree.root_node.has_error:
        logger.warning("parse errors in %s — registry may be incomplete", source_file)
    out: list[TypeDef] = []
    _walk_items(tree.root_node, qpath=[], src_file=source_file, out_types=out)

    reg = TypeRegistry(source_file=source_file)
    for td in out:
        reg.types[td.qualified_name] = td
        reg.short_names.setdefault(td.name, []).append(td.qualified_name)
        # Edge set: union of refs in every field / variant / alias target.
        edges: set[str] = set()
        for f in td.fields:
            edges.update(f.type_refs)
        for v in td.variants:
            for f in v.fields:
                edges.update(f.type_refs)
        edges.update(td.alias_target_refs)
        # Don't self-loop on the type's own name.
        edges.discard(td.name)
        reg.edges[td.qualified_name] = edges
    return reg


def build_registry_from_file(path: Path) -> TypeRegistry:
    return build_registry(path.read_text(), source_file=str(path))


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _registry_to_dict(reg: TypeRegistry) -> dict:
    return {
        "source_file": reg.source_file,
        "types": {qn: asdict(td) for qn, td in reg.types.items()},
        "short_names": reg.short_names,
        "edges": {qn: sorted(es) for qn, es in reg.edges.items()},
    }


def registry_to_json(reg: TypeRegistry) -> str:
    return json.dumps(_registry_to_dict(reg), indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Audit — roll up a directory of registries / source files
# ---------------------------------------------------------------------------


def _iter_rs_files(root: Path) -> Iterable[Path]:
    for p in sorted(root.rglob("*.rs")):
        yield p


def audit_project(root: Path, limit: Optional[int] = None) -> dict:
    """Build per-file registries for every .rs under *root* and roll up
    coverage stats for diagnostic purposes.
    """
    files: list[Path] = list(_iter_rs_files(root))
    if limit:
        files = files[:limit]

    total_types = 0
    by_kind: dict[str, int] = {}
    external_body = 0
    external_type_spec = 0
    has_derive_eq = 0
    in_degree: dict[str, int] = {}
    out_degree_sum = 0
    dangling: dict[str, int] = {}   # short name referenced but never defined here
    parse_errors: list[str] = []

    for f in files:
        try:
            reg = build_registry_from_file(f)
        except Exception as e:
            parse_errors.append(f"{f}: {e}")
            continue
        defined_names = set(reg.short_names.keys())
        for qn, td in reg.types.items():
            total_types += 1
            by_kind[td.kind] = by_kind.get(td.kind, 0) + 1
            if td.is_external_body:
                external_body += 1
            if td.is_external_type_specification:
                external_type_spec += 1
            if any(d in ("Eq", "PartialEq") for d in td.derives):
                has_derive_eq += 1
        for qn, edges in reg.edges.items():
            out_degree_sum += len(edges)
            for r in edges:
                in_degree[r] = in_degree.get(r, 0) + 1
                if r not in defined_names and r not in _PRIMITIVES:
                    dangling[r] = dangling.get(r, 0) + 1

    return {
        "files_scanned": len(files),
        "total_types": total_types,
        "by_kind": by_kind,
        "external_body": external_body,
        "external_type_specification": external_type_spec,
        "has_derive_eq_or_partialeq": has_derive_eq,
        "out_degree_sum": out_degree_sum,
        "in_degree_top20": sorted(in_degree.items(), key=lambda x: -x[1])[:20],
        "dangling_top20": sorted(dangling.items(), key=lambda x: -x[1])[:20],
        "parse_errors": parse_errors,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_build(args: argparse.Namespace) -> int:
    src = Path(args.source).expanduser().resolve()
    reg = build_registry_from_file(src)
    js = registry_to_json(reg)
    if args.out:
        Path(args.out).expanduser().write_text(js)
    else:
        sys.stdout.write(js + "\n")
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    summary = audit_project(root, limit=args.limit)
    if args.json:
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return 0
    print(f"Audit: {root}")
    print(f"  files scanned       : {summary['files_scanned']}")
    print(f"  total type defs     : {summary['total_types']}")
    print(f"  by kind             : {summary['by_kind']}")
    print(f"  external_body       : {summary['external_body']}")
    print(f"  ext_type_spec       : {summary['external_type_specification']}")
    print(f"  derive(Eq/PartialEq): {summary['has_derive_eq_or_partialeq']}")
    print(f"  out-degree sum      : {summary['out_degree_sum']}")
    print(f"  top-20 in-degree (most-referenced):")
    for n, d in summary['in_degree_top20']:
        print(f"    {d:5d}  {n}")
    print(f"  top-20 dangling refs (referenced but not defined in this corpus):")
    for n, d in summary['dangling_top20']:
        print(f"    {d:5d}  {n}")
    if summary['parse_errors']:
        print(f"  parse_errors        : {len(summary['parse_errors'])}")
        for e in summary['parse_errors'][:5]:
            print(f"    {e}")
    return 0


def _cmd_selftest(args: argparse.Namespace) -> int:
    """Inline self-check exercising every parse path. Returns 0 on success."""
    cases: list[tuple[str, str, callable]] = []

    def case(name, src, check):
        cases.append((name, src, check))

    case("named-fields struct + generics + visibility",
         "verus!{ pub struct Foo<T, const N: usize> { pub a: T, b: Vec<Bar> } }",
         lambda r: (
             r.types["Foo"].kind == "struct"
             and [g.name for g in r.types["Foo"].generics] == ["T", "N"]
             and r.types["Foo"].fields[0].name == "a"
             and r.types["Foo"].fields[0].is_pub
             and r.types["Foo"].fields[0].type_refs == []  # T filtered as generic
             and r.types["Foo"].fields[1].type_refs == ["Vec", "Bar"]
             and r.types["Foo"].visibility == "pub"
         ))

    case("tuple struct",
         "verus!{ pub struct T(pub u32, Bar, Vec<u8>); }",
         lambda r: (
             r.types["T"].kind == "struct"
             and [f.name for f in r.types["T"].fields] == ["0", "1", "2"]
             and r.types["T"].fields[0].is_pub
             and not r.types["T"].fields[1].is_pub
             and r.types["T"].fields[1].type_refs == ["Bar"]
             and r.types["T"].fields[2].type_refs == ["Vec"]
         ))

    case("unit struct",
         "verus!{ pub struct Unit; }",
         lambda r: (
             r.types["Unit"].kind == "struct"
             and r.types["Unit"].fields == []
             and r.edges["Unit"] == set()
         ))

    case("enum with all three variant shapes",
         "verus!{ pub enum E<T> { A, B(u32, Bar), C { x: T, y: Map<usize, Baz> } } }",
         lambda r: (
             r.types["E"].kind == "enum"
             and {v.name: v.kind for v in r.types["E"].variants} == {
                 "A": "unit", "B": "tuple", "C": "struct",
             }
             and r.types["E"].variants[1].fields[1].type_refs == ["Bar"]
             and r.types["E"].variants[2].fields[0].type_refs == []  # T filtered
             and r.types["E"].variants[2].fields[1].type_refs == ["Map", "Baz"]
             and r.edges["E"] == {"Bar", "Map", "Baz"}
         ))

    case("type alias with generics",
         "verus!{ pub type Alias<T> = Vec<Option<T>>; }",
         lambda r: (
             r.types["Alias"].kind == "alias"
             and r.types["Alias"].alias_target == "Vec<Option<T>>"
             and r.types["Alias"].alias_target_refs == ["Vec", "Option"]
             and r.edges["Alias"] == {"Vec", "Option"}
         ))

    case("derives + external_body + cfg",
         "verus!{ "
         "#[derive(Eq, PartialEq, Clone)] "
         "#[verifier(external_body)] "
         "#[cfg(feature = \"x\")] "
         "pub struct Op { x: u8 } "
         "}",
         lambda r: (
             r.types["Op"].is_external_body
             and "Eq" in r.types["Op"].derives
             and "PartialEq" in r.types["Op"].derives
             and "Clone" in r.types["Op"].derives
             and any("cfg" in c for c in r.types["Op"].cfg)
         ))

    case("modern external_body syntax",
         "verus!{ #[verifier::external_body] pub struct Op2 { x: u8 } }",
         lambda r: r.types["Op2"].is_external_body)

    case("external_type_specification",
         "verus!{ #[verifier::external_type_specification] pub struct Spec { x: u8 } }",
         lambda r: r.types["Spec"].is_external_type_specification)

    case("nested mod path",
         "verus!{ mod outer { pub struct Inner { x: u8 } } }",
         lambda r: (
             "outer::Inner" in r.types
             and r.types["outer::Inner"].name == "Inner"
             and r.short_names["Inner"] == ["outer::Inner"]
         ))

    case("generic params filter — bound names not edges",
         "verus!{ pub struct G<A, B: Clone, const K: usize> { x: A, y: B, z: [A; K] } }",
         lambda r: (
             # A, B, K are bound generics. None should appear in edges.
             # Clone (a trait bound) is captured under generics[1].bounds, not
             # in edges, since we don't record bounds as field type refs.
             r.edges["G"] == set()
             and r.types["G"].generics[1].bounds == ["Clone"]
         ))

    case("scoped type identifier — drop scope, keep tail",
         "verus!{ pub struct S { x: crate::a::b::Foo, y: alloc::vec::Vec<u8> } }",
         lambda r: (
             r.types["S"].fields[0].type_refs == ["Foo"]
             and r.types["S"].fields[1].type_refs == ["Vec"]
         ))

    case("UPPER_SNAKE const-name filter (parser bug workaround)",
         "verus!{ pub struct S { x: Array<Page, NUM_PAGES>, y: [u8; MAX_LEN] } }",
         lambda r: (
             "NUM_PAGES" not in r.edges["S"]
             and "MAX_LEN" not in r.edges["S"]
             and r.edges["S"] == {"Array", "Page"}
         ))

    case("self-loop in edges suppressed",
         "verus!{ pub struct LL { next: Option<Box<LL>> } }",
         lambda r: "LL" not in r.edges["LL"] and {"Option", "Box"} <= r.edges["LL"])

    case("function_type marker (spec_fn) not recorded as ref",
         "verus!{ pub struct S { f: spec_fn(u8) -> Bar, g: fn(Baz) -> u8 } }",
         lambda r: (
             "spec_fn" not in r.edges["S"]
             and "fn" not in r.edges["S"]
             and r.edges["S"] == {"Bar", "Baz"}
         ))

    case("duplicate (cfg-gated) types kept under same short name",
         "verus!{ "
         "#[cfg(a)] pub struct D { x: u8 } "
         "#[cfg(b)] pub struct D { x: u32 } "
         "}",
         lambda r: len(r.short_names["D"]) == 2)

    fails: list[tuple[str, str]] = []
    passes = 0
    for name, src, check in cases:
        try:
            reg = build_registry(src, "<self_check>")
            ok = check(reg)
        except Exception as e:
            ok = False
            err = str(e)
        else:
            err = "" if ok else "assertion failed"
        if ok:
            passes += 1
            sys.stdout.write(f"  ok    {name}\n")
        else:
            fails.append((name, err))
            sys.stdout.write(f"  FAIL  {name}: {err}\n")
    sys.stdout.write(f"\n{passes}/{len(cases)} passed\n")
    return 0 if not fails else 1


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="Build a per-file type registry.")
    p_build.add_argument("source", help="Path to a .rs source file.")
    p_build.add_argument("--out", default=None, help="Output JSON path "
                         "(stdout if omitted).")
    p_build.set_defaults(func=_cmd_build)

    p_audit = sub.add_parser("audit",
                             help="Roll up per-file registries into a "
                                  "project-wide diagnostic summary.")
    p_audit.add_argument("root", help="Project root containing .rs files.")
    p_audit.add_argument("--limit", type=int, default=None)
    p_audit.add_argument("--json", action="store_true")
    p_audit.set_defaults(func=_cmd_audit)

    p_test = sub.add_parser("test",
                            help="Run inline self-check on the parser path.")
    p_test.set_defaults(func=_cmd_selftest)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
