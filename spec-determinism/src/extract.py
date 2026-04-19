"""
Module 1: extract — Spec Extraction

Uses tree-sitter-verus for structured parsing of Verus function specs.
Handles both:
  - #[verus_spec(...)] attribute-level specs
  - Inline fn_qualifier (requires/ensures) inside verus! {} blocks
"""

import logging
import re
from typing import Optional

import tree_sitter as ts
import tree_sitter_verus as tsv

from .types import (
    TypeKind, TypeInfo, FieldInfo, VariantInfo,
    Param, FunctionSpec,
)

logger = logging.getLogger(__name__)

_lang = ts.Language(tsv.language())
_parser = ts.Parser(_lang)


# ---------------------------------------------------------------------------
# Tree-sitter helpers
# ---------------------------------------------------------------------------

def _children_by_type(node: ts.Node, *types: str) -> list[ts.Node]:
    return [c for c in node.children if c.type in types]


def _child_by_type(node: ts.Node, *types: str) -> Optional[ts.Node]:
    for c in node.children:
        if c.type in types:
            return c
    return None


def _text(node: ts.Node) -> str:
    return node.text.decode()


# ---------------------------------------------------------------------------
# Type extraction from AST nodes
# ---------------------------------------------------------------------------

PRIMITIVE_MAP = {
    "usize": TypeKind.USIZE, "isize": TypeKind.ISIZE,
    "u8": TypeKind.U8, "u16": TypeKind.U16, "u32": TypeKind.U32, "u64": TypeKind.U64,
    "i8": TypeKind.I8, "i16": TypeKind.I16, "i32": TypeKind.I32, "i64": TypeKind.I64,
    "int": TypeKind.INT, "nat": TypeKind.INT,
    "bool": TypeKind.BOOL, "()": TypeKind.UNIT,
    "str": TypeKind.STR, "String": TypeKind.STR,
}

_KNOWN_GENERICS = {
    "Result": TypeKind.RESULT, "Option": TypeKind.OPTION,
    "Set": TypeKind.SET, "Seq": TypeKind.SEQ,
}


def _parse_type_node(node: ts.Node) -> TypeInfo:
    """Convert a tree-sitter type node into TypeInfo."""
    if node.type == "primitive_type":
        name = _text(node)
        return TypeInfo(kind=PRIMITIVE_MAP.get(name, TypeKind.UNKNOWN), name=name)

    if node.type == "unit_type":
        return TypeInfo(kind=TypeKind.UNIT, name="()")

    if node.type == "type_identifier":
        name = _text(node)
        return TypeInfo(kind=PRIMITIVE_MAP.get(name, TypeKind.UNKNOWN), name=name)

    if node.type == "generic_type":
        name_node = _child_by_type(node, "type_identifier")
        args_node = _child_by_type(node, "type_arguments")
        name = _text(name_node) if name_node else _text(node)
        type_args = []
        if args_node:
            for c in args_node.children:
                if c.type not in ("<", ">", ","):
                    type_args.append(_parse_type_node(c))

        kind = _KNOWN_GENERICS.get(name, TypeKind.UNKNOWN)
        info = TypeInfo(kind=kind, name=_text(node), type_args=type_args)

        if kind == TypeKind.RESULT and len(type_args) >= 2:
            info.variants = [VariantInfo("Ok", type_args[0]),
                             VariantInfo("Err", type_args[1])]
        elif kind == TypeKind.OPTION and len(type_args) >= 1:
            info.variants = [VariantInfo("Some", type_args[0]),
                             VariantInfo("None")]
        return info

    if node.type == "scoped_type_identifier":
        return TypeInfo(kind=TypeKind.UNKNOWN, name=_text(node))

    if node.type == "reference_type":
        inner = node.children[-1]
        return _parse_type_node(inner)

    # Fallback
    return TypeInfo(kind=TypeKind.UNKNOWN, name=_text(node))


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------

def _extract_params(params_node: ts.Node) -> list[Param]:
    """Extract parameters from a `parameters` AST node."""
    result = []
    for child in params_node.children:
        if child.type == "self_parameter":
            has_mut = _child_by_type(child, "mutable_specifier") is not None
            has_ref = any(c.type == "&" for c in child.children)
            result.append(Param(
                name="self",
                type=TypeInfo(kind=TypeKind.UNKNOWN, name="Self"),
                is_mut_ref=has_ref and has_mut,
                is_ref=has_ref,
                is_self=True,
            ))
        elif child.type == "parameter":
            name_node = _child_by_type(child, "identifier")
            # Type is the child after ":"
            type_node = None
            after_colon = False
            for c in child.children:
                if c.type == ":":
                    after_colon = True
                elif after_colon and c.type not in (",",):
                    type_node = c
            # Detect &mut on the type: reference_type with mutable_specifier
            is_ref = type_node is not None and type_node.type == "reference_type"
            is_mut = is_ref and _child_by_type(type_node, "mutable_specifier") is not None
            result.append(Param(
                name=_text(name_node) if name_node else "?",
                type=_parse_type_node(type_node) if type_node else TypeInfo(kind=TypeKind.UNKNOWN, name="?"),
                is_mut_ref=is_mut,
                is_ref=is_ref,
                is_self=False,
            ))
    return result


# ---------------------------------------------------------------------------
# Return type extraction
# ---------------------------------------------------------------------------

def _extract_return_type(fn_node: ts.Node) -> tuple[TypeInfo, Optional[str]]:
    """
    Extract return type and optional result binding name.
    Returns (TypeInfo, binding_name_or_None).
    
    Handles both:
      -> Result<usize, Error>                    (no binding)
      -> (result: Result<usize, Error>)          (named return)
    """
    ret_node = _child_by_type(fn_node, "named_return_type")
    if ret_node is None:
        return TypeInfo(kind=TypeKind.UNIT, name="()"), None

    # Named return: (name: Type)
    id_node = _child_by_type(ret_node, "identifier")
    binding_name = _text(id_node) if id_node else None

    # Find the type node (generic_type, type_identifier, primitive_type, etc.)
    type_node = _child_by_type(ret_node, "generic_type", "type_identifier",
                                "primitive_type", "unit_type", "scoped_type_identifier")
    if type_node:
        return _parse_type_node(type_node), binding_name

    return TypeInfo(kind=TypeKind.UNKNOWN, name=_text(ret_node)), binding_name


# ---------------------------------------------------------------------------
# Requires/ensures clause extraction
# ---------------------------------------------------------------------------

def _extract_clauses(fn_qualifier: ts.Node) -> tuple[list[str], list[str]]:
    """Extract requires and ensures clause texts from an fn_qualifier node."""
    requires = []
    ensures = []
    for child in fn_qualifier.children:
        if child.type == "requires_clause":
            requires.extend(_clause_expressions(child))
        elif child.type == "ensures_clause":
            ensures.extend(_clause_expressions(child))
    return requires, ensures


def _clause_expressions(clause_node: ts.Node) -> list[str]:
    """Extract expression text from a requires_clause or ensures_clause node."""
    exprs = []
    for child in clause_node.children:
        if child.type in ("requires", "ensures", ",", "line_comment", "block_comment"):
            continue
        exprs.append(_text(child))
    return exprs


# ---------------------------------------------------------------------------
# Find function + spec in parsed tree
# ---------------------------------------------------------------------------

def _extract_fn_chunk(source: str, fn_name: str) -> tuple[str, Optional[ts.Tree]]:
    """
    Extract a source chunk containing #[verus_spec(...)] + fn definition,
    and re-parse it in isolation for a cleaner AST.
    
    Returns (chunk_text, parsed_tree) or ("", None).
    """
    import re
    # Find `pub fn <name>` in source
    fn_pattern = re.compile(
        rf'(?:pub(?:\s*\([^)]*\))?\s+)?(?:const\s+|async\s+|unsafe\s+|extern(?:\s+"[^"]*")?\s+)*fn\s+{re.escape(fn_name)}\s*(?:<[^>]*>)?\s*\(',
    )
    m = fn_pattern.search(source)
    if not m:
        return "", None

    fn_start = m.start()

    # Walk backwards to find the verus_spec attribute (if any)
    chunk_start = fn_start
    prefix = source[:fn_start].rstrip()
    if prefix.endswith(')]'):
        # Find the matching #[verus_spec or #[cfg_attr(... verus_spec
        bracket_depth = 0
        i = len(prefix) - 1
        while i >= 0:
            if prefix[i] == ']':
                bracket_depth += 1
            elif prefix[i] == '[':
                bracket_depth -= 1
                if bracket_depth == 0:
                    # Check for # before [
                    if i > 0 and prefix[i - 1] == '#':
                        chunk_start = i - 1
                    else:
                        chunk_start = i
                    break
            i -= 1

    # Walk forward from fn_start to find the opening brace of the body
    body_open = None
    for i in range(fn_start, len(source)):
        if source[i] == '{':
            body_open = i
            break

    if body_open is None:
        return "", None

    # Walk forward to find end of body (text-level brace matching; may be
    # wrong in the presence of `proof!{}` / macros — we accept that because
    # we discard the body below).
    depth = 0
    fn_end = len(source)
    for i in range(body_open, len(source)):
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                fn_end = i + 1
                break

    chunk = source[chunk_start:fn_end]
    chunk_tree = _parser.parse(chunk.encode())

    # If the body contains constructs tree-sitter can't parse (e.g. `proof!`,
    # `cfg_attr(..., verus_spec(...))` invariants), the root can end up as
    # ERROR and no function_item is recognised. Retry with the body stubbed
    # out — we only need the signature + attribute for spec extraction.
    if chunk_tree.root_node.has_error:
        stub = source[chunk_start:body_open] + "{}"
        stub_tree = _parser.parse(stub.encode())
        if not stub_tree.root_node.has_error or \
           _find_function_items(stub_tree):
            return stub, stub_tree

    return chunk, chunk_tree

def _find_function_items(tree: ts.Tree) -> list[ts.Node]:
    """Find all function_item nodes in the tree (including inside impl blocks)."""
    results = []

    def walk(node: ts.Node):
        if node.type == "function_item":
            results.append(node)
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return results


def _find_impl_type(fn_node: ts.Node, tree: ts.Tree, source: str,
                    fn_name: Optional[str] = None) -> Optional[str]:
    """Find the impl type name for a function.
    
    Strategy:
      1. Walk up parent chain looking for impl_item
      2. Find impl_item nodes by byte range
      3. Scan top-level tokens for `impl` → `type_identifier` → `{` ... `}` pattern
         and check containment (by byte range, or by fn_name text search)
    """
    fn_start = fn_node.start_byte
    fn_end = fn_node.end_byte

    # Strategy 1: walk up parent chain
    node = fn_node.parent
    while node is not None:
        if node.type == "impl_item":
            ty = _child_by_type(node, "type_identifier")
            if ty:
                return _text(ty)
        node = node.parent

    # Strategy 2: find enclosing impl_item by byte range
    best = None
    for impl_node in _find_all_nodes(tree.root_node, "impl_item"):
        if impl_node.start_byte <= fn_start and impl_node.end_byte >= fn_end:
            if best is None or (impl_node.end_byte - impl_node.start_byte) < (best.end_byte - best.start_byte):
                best = impl_node
    if best:
        ty = _child_by_type(best, "type_identifier")
        if ty:
            return _text(ty)

    # Strategy 3: scan for flat `impl` → `type_identifier` → `{` ... `}` pattern
    root = tree.root_node
    children = root.children
    for i, child in enumerate(children):
        if child.type == "impl" and child.child_count == 0:
            if i + 2 < len(children) and children[i + 1].type == "type_identifier":
                type_name = _text(children[i + 1])
                if children[i + 2].type != "{":
                    continue
                brace_start = children[i + 2].start_byte
                # Find matching `}` by scanning forward
                depth = 0
                impl_end = len(source)
                for j in range(i + 2, len(children)):
                    if children[j].type == "{" and children[j].child_count == 0:
                        depth += 1
                    elif children[j].type == "}" and children[j].child_count == 0:
                        depth -= 1
                        if depth == 0:
                            impl_end = children[j].end_byte
                            break

                # Check containment: either by byte range (same tree)
                # or by fn_name text search in the impl span (for chunk-parsed fns)
                if brace_start <= fn_start and impl_end >= fn_end:
                    return type_name
                if fn_name:
                    impl_text = source[brace_start:impl_end]
                    import re
                    if re.search(rf'\bfn\s+{re.escape(fn_name)}\b', impl_text):
                        return type_name

    return None


def _find_verus_spec_for_fn(
    fn_node: ts.Node,
    tree: ts.Tree,
) -> Optional[tuple[Optional[str], ts.Node]]:
    """
    Find verus_spec attribute associated with a function.
    Returns (result_binding_name, fn_qualifier_node) or None.
    
    Strategy:
      1. Check sibling attribute_items in the same declaration_with_attrs
      2. Fallback: find nearest verus_spec_attribute by byte proximity
         (handles cases where parse errors break the parent chain)
    """
    result = _find_verus_spec_sibling(fn_node)
    if result:
        return result

    # Fallback: search all verus_spec_attribute nodes in the tree
    # and find the one immediately before this function
    all_attrs = _find_all_nodes(tree.root_node, "verus_spec_attribute")
    best = None
    for attr in all_attrs:
        if attr.end_byte <= fn_node.start_byte:
            if best is None or attr.end_byte > best.end_byte:
                best = attr
    if best is None:
        return None

    # Only accept if the gap is small (whitespace/comments only)
    gap = fn_node.start_byte - best.end_byte
    if gap > 200:
        return None

    return _extract_from_verus_spec_attr_node(best)


def _find_verus_spec_sibling(fn_node: ts.Node) -> Optional[tuple[Optional[str], ts.Node]]:
    """Try to find verus_spec as a sibling attribute in declaration_with_attrs."""
    parent = fn_node.parent
    if parent is None or parent.type != "declaration_with_attrs":
        return None

    for sibling in parent.children:
        if sibling.type != "attribute_item":
            continue
        spec_attr = _child_by_type(sibling, "verus_spec_attribute")
        if spec_attr is None:
            continue
        result = _extract_from_verus_spec_attr_node(spec_attr)
        if result:
            return result

    return None


def _extract_from_verus_spec_attr_node(
    spec_attr: ts.Node,
) -> Optional[tuple[Optional[str], ts.Node]]:
    """Extract (binding_name, fn_qualifier) from a verus_spec_attribute node."""
    # Find verus_spec_attr (could be direct or inside cfg_attr_verus_spec)
    vs_attr = _child_by_type(spec_attr, "verus_spec_attr")
    if vs_attr is None:
        cfg = _child_by_type(spec_attr, "cfg_attr_verus_spec")
        if cfg:
            vs_attr = _child_by_type(cfg, "verus_spec_attr")
    if vs_attr is None:
        return None

    binding = None
    id_node = _child_by_type(vs_attr, "identifier")
    if id_node:
        binding = _text(id_node)

    fq = _child_by_type(vs_attr, "fn_qualifier")
    if fq:
        return binding, fq

    return None


def _find_all_nodes(node: ts.Node, target_type: str) -> list[ts.Node]:
    """Find all nodes of a given type in the tree."""
    results = []
    if node.type == target_type:
        results.append(node)
    for child in node.children:
        results.extend(_find_all_nodes(child, target_type))
    return results


# ---------------------------------------------------------------------------
# Struct / enum extraction
# ---------------------------------------------------------------------------

def _find_struct(tree: ts.Tree, name: str) -> Optional[TypeInfo]:
    """Find a struct definition by name and extract its fields."""
    def walk(node: ts.Node) -> Optional[TypeInfo]:
        if node.type == "struct_item":
            name_node = _child_by_type(node, "type_identifier")
            if name_node and _text(name_node) == name:
                fields = []
                fdl = _child_by_type(node, "field_declaration_list")
                if fdl:
                    for fd in _children_by_type(fdl, "field_declaration"):
                        fname_node = _child_by_type(fd, "field_identifier")
                        ftype_node = None
                        after_colon = False
                        for c in fd.children:
                            if c.type == ":":
                                after_colon = True
                            elif after_colon:
                                ftype_node = c
                                break
                        if fname_node and ftype_node:
                            fields.append(FieldInfo(
                                name=_text(fname_node),
                                type=_parse_type_node(ftype_node),
                            ))
                is_ghost = _child_by_type(node, "data_mode") is not None
                return TypeInfo(kind=TypeKind.STRUCT, name=name, fields=fields)
        for child in node.children:
            result = walk(child)
            if result:
                return result
        return None

    return walk(tree.root_node)


def _find_enum(tree: ts.Tree, name: str) -> Optional[TypeInfo]:
    """Find an enum definition by name and extract its variants."""
    def walk(node: ts.Node) -> Optional[TypeInfo]:
        if node.type == "enum_item":
            name_node = _child_by_type(node, "type_identifier")
            if name_node and _text(name_node) == name:
                variants = []
                vl = _child_by_type(node, "enum_variant_list")
                if vl:
                    for v in _children_by_type(vl, "enum_variant"):
                        vname = _child_by_type(v, "identifier")
                        # Check for tuple inner type
                        inner = None
                        ofl = _child_by_type(v, "ordered_field_declaration_list")
                        if ofl:
                            for c in ofl.children:
                                if c.type not in ("(", ")", ","):
                                    inner = _parse_type_node(c)
                                    break
                        if vname:
                            variants.append(VariantInfo(
                                name=_text(vname),
                                inner=inner,
                            ))
                return TypeInfo(kind=TypeKind.ENUM, name=name, variants=variants)
        for child in node.children:
            result = walk(child)
            if result:
                return result
        return None

    return walk(tree.root_node)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class Unsupported(Exception):
    """Raised when parser cannot handle a pattern → triggers LLM fallback."""
    pass


def _resolve_self_in_type(ty: TypeInfo, impl_name: str):
    """Replace Self references in a TypeInfo with the concrete impl type name."""
    if ty.name == "Self":
        ty.name = impl_name
    ty.name = ty.name.replace("Self", impl_name)
    for ta in ty.type_args:
        _resolve_self_in_type(ta, impl_name)
    for v in ty.variants:
        if v.inner:
            _resolve_self_in_type(v.inner, impl_name)


def extract_spec(
    source: str,
    fn_name: str,
    type_sources: list[str] | None = None,
) -> FunctionSpec:
    """
    Extract function spec from source code using tree-sitter-verus.

    Args:
        source: The .rs source containing the function
        fn_name: Name of the target function
        type_sources: Additional sources to search for type definitions

    Returns:
        FunctionSpec

    Raises:
        Unsupported: when parser cannot handle the pattern
    """
    full_tree = _parser.parse(source.encode())

    # Find target function — first try tree-sitter, then re-parse a chunk
    fn_node = None
    tree = full_tree  # tree used for fn_node context (may be chunk tree)
    for fn in _find_function_items(full_tree):
        name_node = _child_by_type(fn, "identifier")
        if name_node and _text(name_node) == fn_name:
            fn_node = fn
            break

    if fn_node is None:
        # Fallback: extract the function chunk and re-parse it in isolation.
        # This handles cases where ERROR recovery in the full file swallows
        # some functions (e.g. due to proof! macros, nested cfg_attr, etc.)
        chunk, chunk_tree = _extract_fn_chunk(source, fn_name)
        if chunk_tree is not None:
            tree = chunk_tree
            for fn in _find_function_items(tree):
                name_node = _child_by_type(fn, "identifier")
                if name_node and _text(name_node) == fn_name:
                    fn_node = fn
                    break

    if fn_node is None:
        raise Unsupported(f"Cannot find function '{fn_name}' in source")

    # Extract parameters
    params_node = _child_by_type(fn_node, "parameters")
    params = _extract_params(params_node) if params_node else []

    # Extract return type
    return_type, ret_binding = _extract_return_type(fn_node)

    # Extract requires/ensures — try attribute first, then inline fn_qualifier
    requires_raw: list[str] = []
    ensures_raw: list[str] = []
    result_binding = ret_binding  # from named return type

    spec_info = _find_verus_spec_for_fn(fn_node, tree)
    if spec_info is not None:
        attr_binding, fq_node = spec_info
        if attr_binding:
            result_binding = attr_binding
        requires_raw, ensures_raw = _extract_clauses(fq_node)
    else:
        # Inline fn_qualifier on the function itself
        fq = _child_by_type(fn_node, "fn_qualifier")
        if fq:
            requires_raw, ensures_raw = _extract_clauses(fq)

    # Resolve self type from enclosing impl block (always use full_tree)
    impl_type_name = _find_impl_type(fn_node, full_tree, source, fn_name=fn_name)
    if impl_type_name:
        for p in params:
            if p.is_self:
                p.type = TypeInfo(kind=TypeKind.UNKNOWN, name=impl_type_name)
        # Also resolve Self in return type
        _resolve_self_in_type(return_type, impl_type_name)

    # Resolve type definitions from all sources
    all_sources = [source] + (type_sources or [])
    type_defs = _resolve_types(params, return_type, all_sources)

    return FunctionSpec(
        name=fn_name,
        params=params,
        return_type=return_type,
        requires=requires_raw,
        ensures=ensures_raw,
        type_defs=type_defs,
    )


def _resolve_types(
    params: list[Param],
    return_type: TypeInfo,
    sources: list[str],
) -> dict[str, TypeInfo]:
    """Resolve unknown types by searching source files for struct/enum definitions.

    Does a transitive resolution: if `Error` is resolved to a struct with
    field `code: ErrorCode`, `ErrorCode` is resolved too. Also propagates
    resolved types into any TypeInfo slot (params, return type_args, struct
    field types, enum variant inners) that still has kind=UNKNOWN with the
    matching name.
    """
    type_defs: dict[str, TypeInfo] = {}
    # tree-sitter-rust trips on inner attributes (`#![...]`) at the top of
    # some files (e.g. nanvix's error crate has `#![cfg_attr(...)]`), which
    # produces an ERROR node that prevents finding enum/struct definitions.
    # Strip them out for type-resolution parsing.
    cleaned_sources = [re.sub(r'#!\[[^\]]*\]', '', s) for s in sources]
    trees = [_parser.parse(src.encode()) for src in cleaned_sources]

    def _lookup(name: str) -> Optional[TypeInfo]:
        if name in type_defs:
            return type_defs[name]
        if name in PRIMITIVE_MAP:
            return None
        for t in trees:
            resolved = _find_struct(t, name) or _find_enum(t, name)
            if resolved:
                type_defs[name] = resolved
                return resolved
        return None

    def _collect_unknown(ti: TypeInfo, out: set[str]) -> None:
        if ti.kind == TypeKind.UNKNOWN and ti.name and ti.name not in PRIMITIVE_MAP:
            out.add(ti.name)
        for ta in ti.type_args:
            _collect_unknown(ta, out)
        for f in ti.fields:
            _collect_unknown(f.type, out)
        for v in ti.variants:
            if v.inner:
                _collect_unknown(v.inner, out)

    def _substitute(ti: TypeInfo) -> TypeInfo:
        if ti.kind == TypeKind.UNKNOWN and ti.name in type_defs:
            return type_defs[ti.name]
        # Recurse into nested slots (mutate in place for consistency)
        ti.type_args = [_substitute(ta) for ta in ti.type_args]
        for f in ti.fields:
            f.type = _substitute(f.type)
        for v in ti.variants:
            if v.inner:
                v.inner = _substitute(v.inner)
        return ti

    # Seed worklist from params and return type_args
    worklist: set[str] = set()
    for p in params:
        _collect_unknown(p.type, worklist)
    _collect_unknown(return_type, worklist)

    # Transitive resolution: resolve each name, then harvest any new names
    # referenced by the resolved definition.
    seen: set[str] = set()
    while worklist:
        name = worklist.pop()
        if name in seen:
            continue
        seen.add(name)
        resolved = _lookup(name)
        if resolved is None:
            continue
        # New names referenced by the resolved def
        refs: set[str] = set()
        _collect_unknown(resolved, refs)
        worklist.update(refs - seen)

    # Propagate resolved types into all TypeInfo slots
    for p in params:
        p.type = _substitute(p.type)
    _substitute(return_type)
    for td in list(type_defs.values()):
        _substitute(td)

    # Look for spec view types (e.g. BitmapView for Bitmap)
    for name in list(type_defs.keys()):
        view_name = name + "View"
        for t in trees:
            view_type = _find_struct(t, view_name)
            if view_type:
                type_defs[view_name] = view_type
                type_defs[name].spec_view = view_type
                break

    return type_defs
