"""Schema enumeration, guarded template rendering, and assume translation.

A "schema" is an independent narrowing step pre-declared as a
(guard: bool, k: int/...) parameter pair on the Verus proof fn. The
guard activates the assume; the k-param (if any) makes the schema
polymorphic in its concrete value so the SAME schema covers all
bisection rounds.

Phase 2 scope
-------------
Schemas are generated **recursively** through the symbol tree:

 - Top-level integer / bool / variant / equal-fn (as in v1)
 - Nested Result/Option/Enum inner types (`r1->Ok_0`, `r1->Err_0`, ...)
 - Struct fields (`r1->Err_0.code`, `r1->Err_0.reason`, `r1->Ok_0@.num_bits`)
 - String literal equality (`reason == "string 1"` etc.)

Each nested schema carries a `parent_chain`: the sequence of variant
assertions that must hold for its assume expression to be well-typed
in Verus (e.g., ``r1 is Err`` must be asserted before accessing
``r1->Err_0.code``).  The generated ``if g_NAME { ... }`` block
re-asserts the parent chain first; these assumes are idempotent, so
repeatedly doing so in the same proof fn is safe.

Still deferred (translate_assume returns None → search treats as
"pass_untranslatable"):

 - Set::contains / Set literal equality
 - Set length / Seq length
 - Custom (non-built-in) compound kinds
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..types import (
    DetCheckSpec, TypeInfo, TypeKind, VariantInfo,
)


# ---------------------------------------------------------------------------

class SchemaKind(Enum):
    SCALAR_EQ = "scalar_eq"
    SCALAR_RANGE = "scalar_range"
    VARIANT_IS = "variant_is"
    BOOL_EQ = "bool_eq"
    STR_EQ = "str_eq"
    NOT_EQUAL_FN = "not_equal_fn"


@dataclass
class SchemaBinding:
    """One guarded schema in the generated template."""
    id: str
    kind: SchemaKind
    rust_var: str                               # full dotted/arrow path
    rust_expr_tmpl: str                         # assume body with {k}/{k_lo}/{k_hi} placeholders
    guard_name: str
    k_params: list[tuple[str, str]] = field(default_factory=list)
    variant: Optional[str] = None               # VARIANT_IS
    bool_value: Optional[bool] = None           # BOOL_EQ
    str_value: Optional[str] = None             # STR_EQ (literal w/out quotes)
    # Chain of (outer_rust_var, variant_name) asserts required first so
    # the assume body is well-typed (e.g., [("r1", "Err")] for r1->Err_0.*).
    parent_chain: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

_INT_KINDS = {
    TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
    TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
    TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
}

_STR_LITERALS = ["", "string 1", "string 2"]


def _sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _emit(
    var: str,
    ty: TypeInfo,
    parent_chain: list[tuple[str, str]],
    out: list[SchemaBinding],
    seen_tags: set[str],
) -> None:
    """Emit all schemas for (var, ty), recursing through the type tree."""
    tag_base = _sanitize(var)

    def _uniq(tag: str) -> str:
        # Guarantee uniqueness across the whole template.
        base = tag
        i = 1
        while tag in seen_tags:
            i += 1
            tag = f"{base}_{i}"
        seen_tags.add(tag)
        return tag

    # --- Integers ---
    if ty.kind in _INT_KINDS:
        needs_cast = ty.kind != TypeKind.INT
        lhs = f"{var} as int" if needs_cast else var
        sid = _uniq(f"{tag_base}_eq")
        out.append(SchemaBinding(
            id=sid, kind=SchemaKind.SCALAR_EQ, rust_var=var,
            rust_expr_tmpl=f"{lhs} == {{k}}",
            guard_name=f"g_{sid}",
            k_params=[(f"k_{sid}", "int")],
            parent_chain=list(parent_chain),
        ))
        sid = _uniq(f"{tag_base}_rng")
        out.append(SchemaBinding(
            id=sid, kind=SchemaKind.SCALAR_RANGE, rust_var=var,
            rust_expr_tmpl=f"{lhs} >= {{k_lo}} && {lhs} <= {{k_hi}}",
            guard_name=f"g_{sid}",
            k_params=[(f"k_{sid}_lo", "int"), (f"k_{sid}_hi", "int")],
            parent_chain=list(parent_chain),
        ))
        return

    # --- Bool ---
    if ty.kind == TypeKind.BOOL:
        for v in (True, False):
            lit = "true" if v else "false"
            sid = _uniq(f"{tag_base}_is_{lit}")
            out.append(SchemaBinding(
                id=sid, kind=SchemaKind.BOOL_EQ, rust_var=var,
                rust_expr_tmpl=f"{var} == {lit}",
                guard_name=f"g_{sid}", bool_value=v,
                parent_chain=list(parent_chain),
            ))
        return

    # --- Str ---
    if ty.kind == TypeKind.STR:
        for s in _STR_LITERALS:
            lit_tag = "empty" if s == "" else _sanitize(s)
            sid = _uniq(f"{tag_base}_eq_{lit_tag}")
            out.append(SchemaBinding(
                id=sid, kind=SchemaKind.STR_EQ, rust_var=var,
                rust_expr_tmpl=f'{var} == "{s}"',
                guard_name=f"g_{sid}", str_value=s,
                parent_chain=list(parent_chain),
            ))
        return

    # --- Result / Option / generic Enum (sum types) ---
    if ty.kind in (TypeKind.RESULT, TypeKind.OPTION, TypeKind.ENUM):
        if ty.kind == TypeKind.RESULT:
            # variants + their inner types come from type_args, not ty.variants
            variant_items: list[tuple[str, Optional[TypeInfo]]] = [
                ("Ok", ty.type_args[0] if ty.type_args else None),
                ("Err", ty.type_args[1] if len(ty.type_args) > 1 else None),
            ]
        elif ty.kind == TypeKind.OPTION:
            variant_items = [
                ("Some", ty.type_args[0] if ty.type_args else None),
                ("None", None),
            ]
        else:  # ENUM — may have no inner
            variant_items = [(v.name, v.inner) for v in (ty.variants or [])]

        for (vname, inner_ty) in variant_items:
            sid = _uniq(f"{tag_base}_is_{vname}")
            out.append(SchemaBinding(
                id=sid, kind=SchemaKind.VARIANT_IS, rust_var=var,
                rust_expr_tmpl=f"{var} is {vname}",
                guard_name=f"g_{sid}", variant=vname,
                parent_chain=list(parent_chain),
            ))
            if inner_ty is not None:
                inner_var = f"{var}->{vname}_0"
                child_chain = parent_chain + [(var, vname)]
                _emit(inner_var, inner_ty, child_chain, out, seen_tags)
        return

    # --- Struct ---
    if ty.kind == TypeKind.STRUCT:
        view = ty.spec_view or ty
        accessor = f"{var}@" if ty.spec_view else var
        for fld in view.fields:
            _emit(f"{accessor}.{fld.name}", fld.type, parent_chain, out, seen_tags)
        return

    # Other kinds (Set/Seq/Unit/Unknown) — skipped in phase 2.
    return


def enumerate_schemas(det_spec: DetCheckSpec) -> list[SchemaBinding]:
    """Walk the symbol table and emit all schemas (recursive)."""
    schemas: list[SchemaBinding] = []
    seen_tags: set[str] = set()
    seen_vars: set[str] = set()
    for sym in det_spec.symbols:
        if sym.name in seen_vars:
            continue
        seen_vars.add(sym.name)
        _emit(sym.name, sym.type, [], schemas, seen_tags)

    schemas.append(SchemaBinding(
        id="neq_tuple",
        kind=SchemaKind.NOT_EQUAL_FN,
        rust_var="__tuple__",
        rust_expr_tmpl="!{equal_fn_call}",
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
        if "{k}" in body and s.k_params:
            body = body.replace("{k}", s.k_params[0][0])
        if "{k_lo}" in body:
            body = body.replace("{k_lo}", s.k_params[0][0])
        if "{k_hi}" in body:
            body = body.replace("{k_hi}", s.k_params[1][0])

        # Re-assert parent chain so inner arrow projections are well-typed.
        chain_asserts = "".join(
            f" assume({outer} is {vname});"
            for (outer, vname) in s.parent_chain
        )
        lines.append(f"    if {s.guard_name} {{{chain_asserts} assume({body}); }}")
    return "\n".join(lines)


def render_guarded_template(
    det_spec: DetCheckSpec,
    schemas: list[SchemaBinding],
) -> str:
    extra_params: list[str] = []
    for s in schemas:
        extra_params.append(f"{s.guard_name}: bool")
        for (pname, pty) in s.k_params:
            extra_params.append(f"{pname}: {pty}")
    extra_str = ", ".join(extra_params)

    eq_args: list[str] = []
    for pair in det_spec.equal_arg_pairs:
        eq_args.extend([pair["lhs"], pair["rhs"]])
    equal_call = f"{det_spec.equal_fn_name}({', '.join(eq_args)})"

    body = _render_body(schemas, equal_call)

    tmpl = det_spec.det_check_template
    new_tmpl = re.sub(
        r"(proof fn \w+)\(",
        lambda m: f"{m.group(1)}({extra_str}, ",
        tmpl, count=1,
    )
    return new_tmpl.replace("{ASSUMES}", body + "\n")


# ---------------------------------------------------------------------------
# Translation: Rust assume expression → schema activation
# ---------------------------------------------------------------------------

_INT_LIT = r"-?\d+"


def _match_int_eq(var: str, expr: str) -> Optional[int]:
    m = re.fullmatch(rf"\s*{re.escape(var)}\s*==\s*({_INT_LIT})\s*", expr)
    return int(m.group(1)) if m else None


def _match_int_range(var: str, expr: str) -> Optional[tuple[int, int]]:
    m = re.fullmatch(
        rf"\s*{re.escape(var)}\s*>=\s*({_INT_LIT})\s*&&\s*{re.escape(var)}\s*<=\s*({_INT_LIT})\s*",
        expr,
    )
    return (int(m.group(1)), int(m.group(2))) if m else None


def _match_variant_is(var: str, expr: str) -> Optional[str]:
    m = re.fullmatch(rf"\s*{re.escape(var)}\s+is\s+(\w+)\s*", expr)
    return m.group(1) if m else None


def _match_bool_eq(var: str, expr: str) -> Optional[bool]:
    m = re.fullmatch(rf"\s*{re.escape(var)}\s*==\s*(true|false)\s*", expr)
    return (m.group(1) == "true") if m else None


def _match_str_eq(var: str, expr: str) -> Optional[str]:
    m = re.fullmatch(rf'\s*{re.escape(var)}\s*==\s*"([^"]*)"\s*', expr)
    return m.group(1) if m else None


def translate_assume(
    rust_expr: str,
    schemas: list[SchemaBinding],
    equal_fn_name: str = "",
) -> Optional[tuple[str, dict[str, int]]]:
    """Match rust_expr to the first applicable schema, returning
    (schema_id, k_bindings). None if no schema applies."""
    expr = rust_expr.strip()

    if equal_fn_name and expr.startswith(f"!{equal_fn_name}("):
        for s in schemas:
            if s.kind == SchemaKind.NOT_EQUAL_FN:
                return (s.id, {})

    for s in schemas:
        v = s.rust_var
        if s.kind == SchemaKind.SCALAR_EQ:
            val = _match_int_eq(v, expr)
            if val is not None:
                return (s.id, {s.k_params[0][0]: val})
        elif s.kind == SchemaKind.SCALAR_RANGE:
            rng = _match_int_range(v, expr)
            if rng is not None:
                lo, hi = rng
                return (s.id, {s.k_params[0][0]: lo, s.k_params[1][0]: hi})
        elif s.kind == SchemaKind.VARIANT_IS:
            vname = _match_variant_is(v, expr)
            if vname == s.variant:
                return (s.id, {})
        elif s.kind == SchemaKind.BOOL_EQ:
            b = _match_bool_eq(v, expr)
            if b is not None and b == s.bool_value:
                return (s.id, {})
        elif s.kind == SchemaKind.STR_EQ:
            sv = _match_str_eq(v, expr)
            if sv is not None and sv == s.str_value:
                return (s.id, {})
    return None
