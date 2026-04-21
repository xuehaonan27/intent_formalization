"""Schema enumeration, guarded template rendering, and assume translation.

A "schema" is an independent narrowing step that can be predeclared
as a (guard, k-param) pair in the Verus proof fn. The guard activates
the assume; the k-param (if any) makes the assume polymorphic in its
concrete value so the SAME schema covers all bisection rounds.

Supported kinds (v1):
    - ScalarEq:    g, k:Int  ⇒  assume(expr_of_var == k)
    - ScalarRange: g, k_lo:Int, k_hi:Int  ⇒  assume(lo <= expr <= hi)
    - VariantIs:   g  ⇒  assume(var is Variant)
    - BoolEq:      g  ⇒  assume(var == {true|false})  (one schema per polarity)
    - NotEqualFn:  g  ⇒  assume(!{equal_fn}(r1, r2, ...))  (distinctness step)

Deferred (v1 returns None for translate_assume → caller treats as "pass",
search moves on):
    - Set::contains(k) / len-eq
    - Seq indexing
    - Nested variant-inner field schemas (Err_0.code is X, Err_0.reason == ""...)
    - Compound Set literal equality
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..types import (
    DetCheckSpec, Symbol, TypeInfo, TypeKind, VariantInfo,
)


# ---------------------------------------------------------------------------

class SchemaKind(Enum):
    SCALAR_EQ = "scalar_eq"
    SCALAR_RANGE = "scalar_range"
    VARIANT_IS = "variant_is"
    BOOL_EQ = "bool_eq"
    NOT_EQUAL_FN = "not_equal_fn"


@dataclass
class SchemaBinding:
    """One guarded schema in the generated template."""
    id: str                         # unique within template, used in guard name
    kind: SchemaKind
    rust_var: str                   # the variable this schema narrows ("number_of_bits", "r1", ...)
    rust_expr_tmpl: str             # body of the assume, with {k}/{k_lo}/{k_hi} placeholders
    guard_name: str                 # "g_<id>"
    k_params: list[tuple[str, str]] = field(default_factory=list)  # [(param_name, rust_type)]
    # For VariantIs:
    variant: Optional[str] = None
    # For BoolEq:
    bool_value: Optional[bool] = None


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

_INT_KINDS = {
    TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
    TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
    TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
}


def _sanitize(name: str) -> str:
    """Convert a Rust-ish var name to a valid Rust ident fragment."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _schemas_for_var(var: str, ty: TypeInfo, counter: list[int]) -> list[SchemaBinding]:
    """Emit independent top-level schemas for a single symbol.

    v1 scope: only emits schemas for the outermost level. Nested
    (inner-of-variant) field narrowing is NOT emitted here; those are
    handled by falling back to "pass" in the search driver.
    """
    out: list[SchemaBinding] = []
    tag = _sanitize(var)

    if ty.kind in _INT_KINDS:
        # ScalarEq
        sid = f"{tag}_eq"
        out.append(SchemaBinding(
            id=sid, kind=SchemaKind.SCALAR_EQ,
            rust_var=var, rust_expr_tmpl=f"{var} as int == {{k}}",
            guard_name=f"g_{sid}",
            k_params=[(f"k_{sid}", "int")],
        ))
        # ScalarRange
        sid = f"{tag}_rng"
        out.append(SchemaBinding(
            id=sid, kind=SchemaKind.SCALAR_RANGE,
            rust_var=var, rust_expr_tmpl=f"{var} as int >= {{k_lo}} && {var} as int <= {{k_hi}}",
            guard_name=f"g_{sid}",
            k_params=[(f"k_{sid}_lo", "int"), (f"k_{sid}_hi", "int")],
        ))
    elif ty.kind == TypeKind.INT:
        # 'int' doesn't need `as int`; handled above anyway
        pass

    if ty.kind == TypeKind.BOOL:
        for v in (True, False):
            lit = "true" if v else "false"
            sid = f"{tag}_is_{lit}"
            out.append(SchemaBinding(
                id=sid, kind=SchemaKind.BOOL_EQ,
                rust_var=var, rust_expr_tmpl=f"{var} == {lit}",
                guard_name=f"g_{sid}", bool_value=v,
            ))

    if ty.kind in (TypeKind.RESULT, TypeKind.OPTION, TypeKind.ENUM):
        # Variant-is schemas. Determine variant names:
        if ty.kind == TypeKind.RESULT:
            variants = ["Ok", "Err"]
        elif ty.kind == TypeKind.OPTION:
            variants = ["Some", "None"]
        else:
            variants = [v.name for v in (ty.variants or [])]
        for vname in variants:
            sid = f"{tag}_is_{vname}"
            out.append(SchemaBinding(
                id=sid, kind=SchemaKind.VARIANT_IS,
                rust_var=var, rust_expr_tmpl=f"{var} is {vname}",
                guard_name=f"g_{sid}", variant=vname,
            ))

    return out


def enumerate_schemas(det_spec: DetCheckSpec) -> list[SchemaBinding]:
    """Walk the symbol table and emit independent top-level schemas."""
    counter = [0]
    schemas: list[SchemaBinding] = []
    seen_vars: set[str] = set()
    for sym in det_spec.symbols:
        if sym.name in seen_vars:
            continue
        seen_vars.add(sym.name)
        schemas.extend(_schemas_for_var(sym.name, sym.type, counter))

    # Distinctness schema (applies to final step of binary_search)
    schemas.append(SchemaBinding(
        id="neq_tuple",
        kind=SchemaKind.NOT_EQUAL_FN,
        rust_var="__tuple__",
        rust_expr_tmpl="!{equal_fn_call}",  # filled at render time
        guard_name="g_neq_tuple",
    ))
    return schemas


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _render_body(schemas: list[SchemaBinding], equal_fn_call: str) -> str:
    lines: list[str] = []
    for s in schemas:
        body = s.rust_expr_tmpl
        if s.kind == SchemaKind.NOT_EQUAL_FN:
            body = body.replace("{equal_fn_call}", equal_fn_call)
        # Replace k-placeholders with param names (mapping by order).
        if "{k}" in body and s.k_params:
            body = body.replace("{k}", s.k_params[0][0])
        if "{k_lo}" in body and len(s.k_params) >= 1:
            body = body.replace("{k_lo}", s.k_params[0][0])
        if "{k_hi}" in body and len(s.k_params) >= 2:
            body = body.replace("{k_hi}", s.k_params[1][0])
        lines.append(f"    if {s.guard_name} {{ assume({body}); }}")
    return "\n".join(lines)


def render_guarded_template(
    det_spec: DetCheckSpec,
    schemas: list[SchemaBinding],
) -> str:
    """Return full Rust source: equal_fn_def + guarded proof fn.

    Injects schema guard/k params into the proof fn signature before
    the real arguments, and replaces the template's {ASSUMES} marker
    with guarded assume bodies.
    """
    # Build extra params for schemas.
    extra_params: list[str] = []
    for s in schemas:
        extra_params.append(f"{s.guard_name}: bool")
        for (pname, pty) in s.k_params:
            extra_params.append(f"{pname}: {pty}")
    extra_str = ", ".join(extra_params)

    # Build equal-fn invocation for distinctness schema.
    eq_args: list[str] = []
    for pair in det_spec.equal_arg_pairs:
        eq_args.extend([pair["lhs"], pair["rhs"]])
    equal_call = f"{det_spec.equal_fn_name}({', '.join(eq_args)})"

    body = _render_body(schemas, equal_call)

    # Inject extra params into the template's proof fn signature.
    tmpl = det_spec.det_check_template
    # The template has: `proof fn det_X(real_args)\n    ensures ...`
    # Prepend extras to the paren list.
    new_tmpl = re.sub(
        r"(proof fn \w+)\(",
        lambda m: f"{m.group(1)}({extra_str}, ",
        tmpl, count=1,
    )
    # Substitute ASSUMES.
    return new_tmpl.replace("{ASSUMES}", body + "\n")


# ---------------------------------------------------------------------------
# Translation: Rust assume expression → schema activation
# ---------------------------------------------------------------------------

# Precompiled parse helpers.
_INT_LIT = r"-?\d+"

def _match_int_eq(var: str, expr: str) -> Optional[int]:
    # "<var> == <int>"
    m = re.fullmatch(rf"\s*{re.escape(var)}\s*==\s*({_INT_LIT})\s*", expr)
    return int(m.group(1)) if m else None


def _match_int_range(var: str, expr: str) -> Optional[tuple[int, int]]:
    # "<var> >= <lo> && <var> <= <hi>"
    m = re.fullmatch(
        rf"\s*{re.escape(var)}\s*>=\s*({_INT_LIT})\s*&&\s*{re.escape(var)}\s*<=\s*({_INT_LIT})\s*",
        expr,
    )
    return (int(m.group(1)), int(m.group(2))) if m else None


def _match_variant_is(var: str, expr: str) -> Optional[str]:
    # "<var> is <Name>"
    m = re.fullmatch(rf"\s*{re.escape(var)}\s+is\s+(\w+)\s*", expr)
    return m.group(1) if m else None


def _match_bool_eq(var: str, expr: str) -> Optional[bool]:
    m = re.fullmatch(rf"\s*{re.escape(var)}\s*==\s*(true|false)\s*", expr)
    return (m.group(1) == "true") if m else None


def translate_assume(
    rust_expr: str,
    schemas: list[SchemaBinding],
    equal_fn_name: str = "",
) -> Optional[tuple[str, dict[str, int]]]:
    """Return (schema_id, k_bindings) if rust_expr matches a schema.

    k_bindings maps k-param-name → concrete int. None means no schema
    handles this expression (caller should treat as "pass" and move on).
    """
    # Distinctness first (text match on "!{equal_fn_name}(...)").
    if equal_fn_name and rust_expr.strip().startswith(f"!{equal_fn_name}("):
        for s in schemas:
            if s.kind == SchemaKind.NOT_EQUAL_FN:
                return (s.id, {})

    for s in schemas:
        v = s.rust_var
        if s.kind == SchemaKind.SCALAR_EQ:
            val = _match_int_eq(v, rust_expr)
            if val is not None:
                return (s.id, {s.k_params[0][0]: val})
        elif s.kind == SchemaKind.SCALAR_RANGE:
            rng = _match_int_range(v, rust_expr)
            if rng is not None:
                lo, hi = rng
                return (s.id, {s.k_params[0][0]: lo, s.k_params[1][0]: hi})
        elif s.kind == SchemaKind.VARIANT_IS:
            vname = _match_variant_is(v, rust_expr)
            if vname == s.variant:
                return (s.id, {})
        elif s.kind == SchemaKind.BOOL_EQ:
            b = _match_bool_eq(v, rust_expr)
            if b is not None and b == s.bool_value:
                return (s.id, {})
    return None
