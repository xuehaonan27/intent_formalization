"""
Module 1: extract — Spec Extraction

Parser path: regex-based extraction of Verus function specs.
LLM fallback: when regex fails on unknown patterns.
"""

import re
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .types import (
    TypeKind, TypeInfo, FieldInfo, VariantInfo,
    Param, FunctionSpec,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type resolution
# ---------------------------------------------------------------------------

PRIMITIVE_MAP = {
    "usize": TypeKind.USIZE, "isize": TypeKind.ISIZE,
    "u8": TypeKind.U8, "u16": TypeKind.U16, "u32": TypeKind.U32, "u64": TypeKind.U64,
    "i8": TypeKind.I8, "i16": TypeKind.I16, "i32": TypeKind.I32, "i64": TypeKind.I64,
    "int": TypeKind.INT, "bool": TypeKind.BOOL, "()": TypeKind.UNIT,
}


def parse_type(raw: str) -> TypeInfo:
    """Parse a Verus type string into TypeInfo (best-effort)."""
    raw = raw.strip()

    # Primitives
    if raw in PRIMITIVE_MAP:
        return TypeInfo(kind=PRIMITIVE_MAP[raw], name=raw)

    # Result<T, E>
    m = re.match(r"^Result\s*<(.+),\s*(.+)>$", raw)
    if m:
        ok_ty = parse_type(m.group(1).strip())
        err_ty = parse_type(m.group(2).strip())
        return TypeInfo(
            kind=TypeKind.RESULT, name=raw,
            variants=[VariantInfo("Ok", ok_ty), VariantInfo("Err", err_ty)],
            type_args=[ok_ty, err_ty],
        )

    # Option<T>
    m = re.match(r"^Option\s*<(.+)>$", raw)
    if m:
        inner = parse_type(m.group(1).strip())
        return TypeInfo(
            kind=TypeKind.OPTION, name=raw,
            variants=[VariantInfo("Some", inner), VariantInfo("None")],
            type_args=[inner],
        )

    # Set<T>
    m = re.match(r"^Set\s*<(.+)>$", raw)
    if m:
        inner = parse_type(m.group(1).strip())
        return TypeInfo(kind=TypeKind.SET, name=raw, type_args=[inner])

    # Seq<T>
    m = re.match(r"^Seq\s*<(.+)>$", raw)
    if m:
        inner = parse_type(m.group(1).strip())
        return TypeInfo(kind=TypeKind.SEQ, name=raw, type_args=[inner])

    # Unknown / user-defined struct (will be resolved later)
    return TypeInfo(kind=TypeKind.UNKNOWN, name=raw)


# ---------------------------------------------------------------------------
# Spec block extraction
# ---------------------------------------------------------------------------

def _extract_clause_block(source: str, keyword: str, start_pos: int) -> tuple[list[str], int]:
    """
    Extract a requires/ensures block starting from `keyword` at start_pos.
    Returns (list of clause strings, end position).
    """
    # Find the keyword
    idx = source.find(keyword, start_pos)
    if idx == -1:
        return [], start_pos

    # After keyword, find the clause body
    pos = idx + len(keyword)

    # Collect clauses until we hit another keyword or '{'
    clauses = []
    current = ""
    depth = 0
    while pos < len(source):
        ch = source[pos]
        if ch in "({[":
            depth += 1
            current += ch
        elif ch in ")}]":
            depth -= 1
            if depth < 0:
                break
            current += ch
        elif ch == "," and depth == 0:
            clause = current.strip()
            if clause:
                clauses.append(clause)
            current = ""
        elif source[pos:].startswith("ensures") and depth == 0 and not current.strip():
            break
        elif source[pos:].startswith("decreases") and depth == 0 and not current.strip():
            break
        elif ch == "{" and depth == 0:
            break
        else:
            current += ch
        pos += 1

    clause = current.strip()
    if clause:
        clauses.append(clause)

    return clauses, pos


def _balance_depth(text: str) -> int:
    """Count net bracket depth."""
    depth = 0
    for ch in text:
        if ch in "({[<":
            depth += 1
        elif ch in ")}]>":
            depth -= 1
    return depth


# ---------------------------------------------------------------------------
# Function signature parsing
# ---------------------------------------------------------------------------

_FN_PATTERN = re.compile(
    r"(?:pub\s+)?(?:(?:exec|proof|spec)\s+)?fn\s+(\w+)\s*"
    r"(?:<[^>]*>)?\s*"   # optional generic params
    r"\(([^)]*(?:\([^)]*\))*[^)]*)\)"  # params (handles nested parens)
    r"(?:\s*->\s*(.+?))?"             # optional return type
    r"\s*(?:requires|ensures|decreases|\{)",
    re.DOTALL,
)

_PARAM_PATTERN = re.compile(
    r"(&\s*mut\s+self|&\s*self|self|"
    r"(?:&\s*mut\s+)?(\w+)\s*:\s*(.+?))\s*(?:,|$)",
    re.DOTALL,
)


def parse_function_header(source: str, fn_name: str) -> Optional[dict]:
    """
    Parse function signature for a specific function.
    Returns dict with name, params, return_type, requires_raw, ensures_raw.
    """
    # Find the function
    pattern = re.compile(
        rf"(?:pub\s+)?(?:(?:exec|proof|spec)\s+)?fn\s+{re.escape(fn_name)}\s*"
        r"(?:<[^>]*>)?\s*"
        r"\(([^)]*(?:\([^)]*\))*[^)]*)\)"
        r"(?:\s*->\s*(.+?))?"
        r"\s*(requires|ensures|decreases|\{)",
        re.DOTALL,
    )
    m = pattern.search(source)
    if not m:
        return None

    params_raw = m.group(1)
    return_raw = m.group(2) or "()"
    after_sig = m.start(3)

    # Parse params
    params = []
    for pm in re.finditer(
        r"(&\s*mut\s+self|&\s*self|self)|"
        r"(&\s*mut\s+)?(\w+)\s*:\s*([^,]+)",
        params_raw,
    ):
        if pm.group(1):
            # self variant
            self_str = pm.group(1).replace(" ", "")
            is_mut = "mut" in self_str
            params.append(Param(
                name="self",
                type=TypeInfo(kind=TypeKind.UNKNOWN, name="Self"),
                is_mut_ref=is_mut,
                is_ref="&" in self_str,
                is_self=True,
            ))
        else:
            is_mut = pm.group(2) is not None
            name = pm.group(3)
            ty_raw = pm.group(4).strip()
            params.append(Param(
                name=name,
                type=parse_type(ty_raw),
                is_mut_ref=is_mut,
                is_ref=False,
                is_self=False,
            ))

    return_type = parse_type(return_raw.strip())

    # Extract requires and ensures blocks
    # Find from after_sig onward
    rest = source[after_sig:]

    requires_clauses = []
    ensures_clauses = []

    # Simple extraction: find `requires` and `ensures` blocks
    req_match = re.search(r"\brequires\b", rest)
    ens_match = re.search(r"\bensures\b", rest)
    body_match = re.search(r"\{", rest)

    if req_match:
        # Extract from requires to ensures or body
        req_start = req_match.end()
        if ens_match:
            req_text = rest[req_start:ens_match.start()]
        elif body_match:
            req_text = rest[req_start:body_match.start()]
        else:
            req_text = rest[req_start:]
        requires_clauses = [c.strip() for c in _split_clauses(req_text) if c.strip()]

    if ens_match:
        ens_start = ens_match.end()
        if body_match and body_match.start() > ens_match.start():
            ens_text = rest[ens_start:body_match.start()]
        else:
            ens_text = rest[ens_start:]
        ensures_clauses = [c.strip() for c in _split_clauses(ens_text) if c.strip()]

    return {
        "name": fn_name,
        "params": params,
        "return_type": return_type,
        "requires_raw": requires_clauses,
        "ensures_raw": ensures_clauses,
    }


def _split_clauses(text: str) -> list[str]:
    """
    Split ensures/requires text into individual clauses.
    Respects bracket depth and Verus &&& syntax.
    """
    text = text.strip().rstrip(",")
    # If there's a single top-level expression, return it whole
    # For now, just return the whole block as one clause
    return [text] if text else []


# ---------------------------------------------------------------------------
# Struct/enum definition extraction
# ---------------------------------------------------------------------------

def extract_struct_fields(source: str, struct_name: str) -> Optional[TypeInfo]:
    """Extract fields from a pub struct definition."""
    pattern = re.compile(
        rf"pub\s+(?:ghost\s+)?struct\s+{re.escape(struct_name)}\s*\{{([^}}]*)\}}",
        re.DOTALL,
    )
    m = pattern.search(source)
    if not m:
        return None

    fields = []
    body = m.group(1)
    for fm in re.finditer(r"pub\s+(\w+)\s*:\s*([^,\n]+)", body):
        fname = fm.group(1)
        ftype = parse_type(fm.group(2).strip().rstrip(","))
        fields.append(FieldInfo(name=fname, type=ftype))

    return TypeInfo(
        kind=TypeKind.STRUCT, name=struct_name,
        fields=fields,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class Unsupported(Exception):
    """Raised when parser cannot handle a pattern → triggers LLM fallback."""
    pass


def extract_spec(
    source: str,
    fn_name: str,
    type_sources: list[str] | None = None,
) -> FunctionSpec:
    """
    Extract function spec from source code.

    Args:
        source: The .rs source containing the function
        fn_name: Name of the target function
        type_sources: Additional sources to search for type definitions

    Returns:
        FunctionSpec

    Raises:
        Unsupported: when parser cannot handle the pattern
    """
    parsed = parse_function_header(source, fn_name)
    if parsed is None:
        raise Unsupported(f"Cannot parse function '{fn_name}' from source")

    # Resolve self type — find the impl block
    self_type_name = None
    impl_match = re.search(
        rf"impl\s+(\w+)\s*\{{[^}}]*fn\s+{re.escape(fn_name)}",
        source, re.DOTALL,
    )
    if impl_match:
        self_type_name = impl_match.group(1)

    # Update self params with resolved type
    for p in parsed["params"]:
        if p.is_self and self_type_name:
            p.type = TypeInfo(kind=TypeKind.UNKNOWN, name=self_type_name)

    # Resolve type definitions
    all_sources = [source] + (type_sources or [])
    type_defs = {}
    type_names_to_resolve = set()

    for p in parsed["params"]:
        if p.type.kind == TypeKind.UNKNOWN and p.type.name not in PRIMITIVE_MAP:
            type_names_to_resolve.add(p.type.name)
    if parsed["return_type"].kind in (TypeKind.RESULT, TypeKind.OPTION):
        for ta in parsed["return_type"].type_args:
            if ta.kind == TypeKind.UNKNOWN:
                type_names_to_resolve.add(ta.name)

    for type_name in type_names_to_resolve:
        for src in all_sources:
            resolved = extract_struct_fields(src, type_name)
            if resolved:
                type_defs[type_name] = resolved
                # Also update param types
                for p in parsed["params"]:
                    if p.type.name == type_name:
                        p.type = resolved
                break

    # Also look for spec view types (e.g. BitmapView for Bitmap)
    for type_name in list(type_defs.keys()):
        view_name = type_name + "View"
        for src in all_sources:
            view_type = extract_struct_fields(src, view_name)
            if view_type:
                type_defs[view_name] = view_type
                type_defs[type_name].spec_view = view_type
                break

    return FunctionSpec(
        name=parsed["name"],
        params=parsed["params"],
        return_type=parsed["return_type"],
        requires=parsed["requires_raw"],
        ensures=parsed["ensures_raw"],
        type_defs=type_defs,
    )
