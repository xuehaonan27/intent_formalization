"""
Module 2: gen_det — Determinism Check Generator

Merged with extract into Step 1 of the pipeline.
Produces a DetCheckSpec (template + symbol table) that Step 2 consumes.
"""

import logging
import re
from typing import TYPE_CHECKING, Optional

import tree_sitter as ts
import tree_sitter_verus as tsv

from .types import (
    TypeKind, TypeInfo, Param, FunctionSpec, Assume,
    Symbol, DetCheckSpec,
)
from .equal_policy import EqualPolicy, default_policy

if TYPE_CHECKING:
    from .view.registry import ViewRegistry

logger = logging.getLogger(__name__)

_lang = ts.Language(tsv.language())
_parser = ts.Parser(_lang)


# ---------------------------------------------------------------------------
# TypeInfo → TypeExpr bridge for the L1+L2+L3 view resolver
# ---------------------------------------------------------------------------

# TypeKind → TypeExpr.kind map for primitive / unit so the resolver picks
# the identity-view path. For composite kinds we hand-craft TypeExpr below.
_PRIMITIVE_KINDS = {
    TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
    TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
    TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
    TypeKind.BOOL, TypeKind.STR,
}


def _typeinfo_to_typeexpr(ty: "TypeInfo"):
    """Convert a ``TypeInfo`` (gen_det's runtime type model) into a
    ``TypeExpr`` (type_registry's symbolic tree) so the
    :class:`ViewRegistry` can resolve it.

    The conversion is lossy on the head-name side (Verus's
    ``Vec<u32>`` and ``Vec<Foo>`` collapse to head ``"Vec"`` in the
    registry's short-name index), but that's exactly what the
    resolver wants — prelude rules fire on head name regardless of
    instantiation.
    """
    from .type_registry import TypeExpr

    if ty.kind in _PRIMITIVE_KINDS:
        return TypeExpr(kind="primitive", head=ty.name or "u32",
                        raw=ty.name or "u32")
    if ty.kind == TypeKind.UNIT:
        return TypeExpr(kind="unit", raw="()")
    if ty.kind in (TypeKind.SEQ, TypeKind.SET):
        head = "Seq" if ty.kind == TypeKind.SEQ else "Set"
        args = [_typeinfo_to_typeexpr(a) for a in (ty.type_args or [])]
        return TypeExpr(kind="generic" if args else "leaf",
                        head=head, args=args, raw=ty.name or head)
    if ty.kind == TypeKind.OPTION:
        args = [_typeinfo_to_typeexpr(a) for a in (ty.type_args or [])]
        return TypeExpr(kind="generic" if args else "leaf",
                        head="Option", args=args, raw=ty.name or "Option")
    if ty.kind == TypeKind.RESULT:
        args = [_typeinfo_to_typeexpr(a) for a in (ty.type_args or [])]
        return TypeExpr(kind="generic" if args else "leaf",
                        head="Result", args=args, raw=ty.name or "Result")
    # Struct / Enum / Unknown — use whatever name we have
    head = ty.name or "?"
    args = [_typeinfo_to_typeexpr(a) for a in (ty.type_args or [])]
    return TypeExpr(kind="generic" if args else "leaf",
                    head=head, args=args, raw=ty.name or "")


class Unsupported(Exception):
    """Triggers LLM fallback for ensures substitution."""
    pass


def _var_name(param: Param, prefix: str = "") -> str:
    name = "self_" if param.is_self else param.name
    return f"{prefix}{name}" if prefix else name


# Raw-pointer detection: recognised by TypeInfo.name prefix because tree-sitter
# parses `*mut T` / `*const T` as pointer_type nodes and the extractor records
# the full source text as `name`.
_RAW_POINTER_PREFIXES = ("*mut ", "*const ", "*mut\t", "*const\t")


def _is_raw_pointer_type(ty: TypeInfo) -> bool:
    """Return True iff `ty` is a raw-pointer type (`*mut T` / `*const T`).

    Raw pointers are matched only on syntactic form because the extractor
    classifies them as TypeKind.UNKNOWN (they have no interesting spec
    structure) — all we have to key off is the original source text.
    """
    name = (ty.name or "").lstrip()
    return any(name.startswith(p) for p in _RAW_POINTER_PREFIXES)


def _type_name(param: Param) -> str:
    return param.type.name


def _is_unsized_ty(ty: str) -> bool:
    """Heuristic: does this type need to stay behind `&` to be Sized?

    Slice `[T]`, str, and `dyn Trait` are the common unsized forms in
    Verus corpora. Fixed-size arrays `[T; N]` are Sized. Anything else
    (structs, enums, raw pointers, primitives) is Sized.
    """
    t = ty.strip()
    if t == "str":
        return True
    if t.startswith("dyn "):
        return True
    if t.startswith("[") and t.endswith("]") and ";" not in t:
        return True
    return False


# ---------------------------------------------------------------------------
# Phantom-generic pruning
# ---------------------------------------------------------------------------

def _ts_find_function_item(node: ts.Node) -> Optional[ts.Node]:
    """Locate the synthesized `function_item` inside a probe-fn parse tree."""
    if node.type == "function_item":
        return node
    for c in node.children:
        out = _ts_find_function_item(c)
        if out is not None:
            return out
    return None


def _ts_child_by_type(node: ts.Node, *types: str) -> Optional[ts.Node]:
    for c in node.children:
        if c.type in types:
            return c
    return None


def _ts_collect_referenced(node: ts.Node, known: set[str]) -> set[str]:
    """Walk ``node`` collecting every leaf identifier / lifetime / type-id
    whose text intersects ``known``. Skips ``type_parameters`` subtrees so
    HRTB / nested-fn binders don't count as outer-scope references.
    """
    out: set[str] = set()

    def visit(n: ts.Node) -> None:
        # type_parameters introduces a fresh binder list (HRTB ``for<'a>`` or
        # nested-fn `fn<'a>`); names inside are local, skip the whole subtree.
        if n.type == "type_parameters":
            return
        if n.type in ("type_identifier", "lifetime", "identifier", "primitive_type"):
            t = n.text.decode()
            if t in known:
                out.add(t)
        for c in n.children:
            visit(c)

    visit(node)
    return out


def _prune_generics(
    generics_decl: str,
    where_decl: str,
    sig_params_text: str,
    return_type_text: str = "",
) -> tuple[str, str]:
    """Drop generic parameters not referenced by the synthesized fn signature,
    and drop any where-predicate that refers only to dropped generics.

    Both inputs may be empty strings. Renders back to ``<...>`` / ``where ...``
    text. Conservative on parse failures: returns inputs unchanged.

    Closure rule: if a where-predicate references one kept generic and one
    pruned generic, the predicate is kept *and* the pruned generic is pulled
    back in (otherwise we'd reference an undeclared name).
    """
    if not generics_decl.strip():
        return generics_decl, where_decl

    # Build a probe fn so tree-sitter parses generics + where in proper context.
    params = sig_params_text.strip()
    if params.startswith("(") and params.endswith(")"):
        params = params[1:-1]
    rt = return_type_text.strip() or "()"
    where_part = f" {where_decl.strip()}" if where_decl.strip() else ""
    probe_src = f"fn __probe{generics_decl}({params}) -> {rt}{where_part} {{}}"

    tree = _parser.parse(probe_src.encode())
    fn_node = _ts_find_function_item(tree.root_node)
    if fn_node is None:
        return generics_decl, where_decl

    tp_node = _ts_child_by_type(fn_node, "type_parameters")
    if tp_node is None:
        return "", where_decl  # nothing declared, drop where if any

    # 1. Enumerate generic params: (kind, name, raw)
    entries: list[tuple[str, str, str]] = []
    known: set[str] = set()
    for child in tp_node.children:
        if child.type == "lifetime_parameter":
            # Node text is e.g. "'a" or "'a: 'static"
            name = child.text.decode().split(":", 1)[0].strip()
            entries.append(("lifetime", name, child.text.decode()))
            known.add(name)
        elif child.type == "type_parameter":
            ti = _ts_child_by_type(child, "type_identifier")
            if ti is None:
                # Unparseable; keep verbatim with a sentinel name.
                entries.append(("unknown", "", child.text.decode()))
                continue
            name = ti.text.decode()
            entries.append(("type", name, child.text.decode()))
            known.add(name)
        elif child.type == "const_parameter":
            ident = None
            for c in child.children:
                if c.type == "identifier":
                    ident = c
                    break
            if ident is None:
                entries.append(("unknown", "", child.text.decode()))
                continue
            name = ident.text.decode()
            entries.append(("const", name, child.text.decode()))
            known.add(name)
        # Ignore punctuation children (`<`, `>`, `,`).

    # 2. Names referenced in the synthesized signature.
    used: set[str] = set()
    params_node = _ts_child_by_type(fn_node, "parameters")
    if params_node is not None:
        used |= _ts_collect_referenced(params_node, known)
    # Return type — tree-sitter-verus uses `named_return_type` (verus form)
    # or a plain type node after `->`. Check both.
    rt_node = _ts_child_by_type(fn_node, "named_return_type")
    if rt_node is None:
        # Fall back: any sibling between `->` and the block that is a type-ish.
        seen_arrow = False
        for c in fn_node.children:
            if c.type == "->":
                seen_arrow = True
                continue
            if seen_arrow and c.type not in ("block", "where_clause"):
                used |= _ts_collect_referenced(c, known)
                break
    else:
        used |= _ts_collect_referenced(rt_node, known)

    # 3. Where predicates: parse each, pre-compute referenced name sets.
    wc_node = _ts_child_by_type(fn_node, "where_clause")
    wp_list: list[tuple[str, set[str]]] = []
    if wc_node is not None:
        for c in wc_node.children:
            if c.type == "where_predicate":
                refs = _ts_collect_referenced(c, known)
                wp_list.append((c.text.decode(), refs))

    # 4. Closure: predicate that overlaps kept ⇒ keep predicate AND pull in
    #    its other referenced names so we don't end up referencing an
    #    undeclared generic.
    kept = set(used)
    changed = True
    while changed:
        changed = False
        for raw, refs in wp_list:
            if refs & kept and not refs.issubset(kept):
                kept |= refs
                changed = True

    # 5. Filter and render.
    kept_entries = [(k, n, r) for (k, n, r) in entries
                    if k == "unknown" or n in kept]
    new_generics = (
        "<" + ", ".join(r for (_, _, r) in kept_entries) + ">"
        if kept_entries else ""
    )

    kept_preds_raw: list[str] = []
    for raw, refs in wp_list:
        # Predicates that mention no known generic are anomalous (e.g., bound
        # on an associated type binding); keep verbatim.
        if not refs:
            kept_preds_raw.append(raw)
        elif refs & kept:
            kept_preds_raw.append(raw)
    new_where = ("where " + ", ".join(kept_preds_raw)) if kept_preds_raw else ""

    return new_generics, new_where


# ---------------------------------------------------------------------------
# Symbol table construction
# ---------------------------------------------------------------------------

def _classify_phase(ty: TypeInfo) -> str:
    """Classify a type as simple or compound for output ordering."""
    if ty.kind in (TypeKind.RESULT, TypeKind.OPTION, TypeKind.ENUM,
                   TypeKind.BOOL, TypeKind.UNIT,
                   TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
                   TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
                   TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64):
        return "output_simple"
    return "output_compound"


def _build_symbols(spec: FunctionSpec) -> list[Symbol]:
    """Build the symbol table: variables to narrow, in order."""
    symbols = []

    # Phase 1: Input variables
    for p in spec.params:
        if p.is_mut_ref:
            base = _var_name(p)
            symbols.append(Symbol(
                name=f"pre_{base}",
                type=p.type,
                phase="input",
            ))
        elif p.is_ref:
            symbols.append(Symbol(
                name=_var_name(p),
                type=p.type,
                phase="input",
            ))
        else:
            symbols.append(Symbol(
                name=_var_name(p),
                type=p.type,
                phase="input",
            ))

    # Phase 2: Output variables — simple first, then compound
    simple_outputs = []
    compound_outputs = []

    # Return value (r1, r2)
    ret_phase = _classify_phase(spec.return_type)
    if ret_phase == "output_simple":
        simple_outputs.append(("r1", spec.return_type))
        simple_outputs.append(("r2", spec.return_type))
    else:
        compound_outputs.append(("r1", spec.return_type))
        compound_outputs.append(("r2", spec.return_type))

    # Post-state of &mut params (post1_*, post2_*)
    for p in spec.params:
        if p.is_mut_ref:
            base = _var_name(p)
            phase = _classify_phase(p.type)
            pair = [
                (f"post1_{base}", p.type),
                (f"post2_{base}", p.type),
            ]
            if phase == "output_simple":
                simple_outputs.extend(pair)
            else:
                compound_outputs.extend(pair)

    for name, ty in simple_outputs:
        symbols.append(Symbol(name=name, type=ty, phase="output_simple"))
    for name, ty in compound_outputs:
        symbols.append(Symbol(name=name, type=ty, phase="output_compound"))

    return symbols


# ---------------------------------------------------------------------------
# Template generation
# ---------------------------------------------------------------------------

def _build_template(
    spec: FunctionSpec,
    check_name: str | None = None,
    policy: EqualPolicy | None = None,
    view_registry: Optional["ViewRegistry"] = None,
) -> str:
    """
    Generate the det check proof fn with {ASSUMES} placeholder.
    
    The template has a single {ASSUMES} marker where binary search
    will insert accumulated assume expressions.
    """
    fn_name = check_name or f"det_{spec.name}"

    # Build parameter list
    input_params = []
    output1_params = []
    output2_params = []

    for p in spec.params:
        ty = _type_name(p)
        if p.is_mut_ref:
            pre_name = f"pre_{_var_name(p)}"
            post1_name = f"post1_{_var_name(p)}"
            post2_name = f"post2_{_var_name(p)}"
            input_params.append((pre_name, ty))
            output1_params.append((post1_name, ty))
            output2_params.append((post2_name, ty))
        elif p.is_ref:
            # For shared refs, proof-fn params are ghost values (no
            # ownership concerns), so we typically drop the `&` — ensures
            # clauses reference the param by name as if it were the
            # pointee. That only fails for unsized pointees (slices,
            # str, dyn Trait), which must keep the `&` to be Sized.
            if _is_unsized_ty(ty):
                input_params.append((_var_name(p), f"&{ty}"))
            else:
                input_params.append((_var_name(p), ty))
        else:
            input_params.append((_var_name(p), ty))

    ret_ty = spec.return_type.name
    output1_params.append(("r1", ret_ty))
    output2_params.append(("r2", ret_ty))

    all_params = input_params + output1_params + output2_params
    params_str = ", ".join(f"{name}: {ty}" for name, ty in all_params)

    # Requires
    requires_str = ""
    if spec.requires:
        # Wrap each clause in `(...)` so constructs like `a ==> b` don't merge
        # with the next clause when joined, and join with commas.
        req_clauses = [f"({_substitute_input(c.strip(), spec)})"
                       for c in spec.requires if c.strip()]
        if req_clauses:
            requires_str = "\n    requires " + ", ".join(req_clauses) + ","

    # Ensures: join individual clauses with &&& (Verus short-circuit conjunction),
    # wrapping each clause in parens so constructs like `matches ==>` are never
    # exposed on the RHS of a binary operator.
    def _join_clauses(clauses: list[str]) -> str:
        parts = [f"({c.strip()})" for c in clauses if c.strip()]
        return "\n            &&& ".join(parts)

    ensures_joined = _join_clauses(spec.ensures)
    run1 = _substitute_run(ensures_joined, spec, run_id=1)
    run2 = _substitute_run(ensures_joined, spec, run_id=2)

    # Equality conclusion: call a generated spec fn `{fn_name}_equal(...)`.
    # This fn is a structural-equality relation generated from TypeInfo, which
    # avoids quirks of Verus's default `==` on types whose inner types lack
    # PartialEq (e.g. Result<(), Error> where Error has no Eq impl).
    equal_fn_name = f"{fn_name}_equal"
    equal_body_args = []  # list of (lhs, rhs, ty) used inside equal fn body
    equal_call_args = []  # callsite expressions (wraps `@` for view types)
    equal_params = []     # list of param decls in the spec fn signature
    # r1/r2 always go first
    equal_body_args.append(("r1", "r2", spec.return_type))
    equal_call_args.append(("r1", "r2"))
    equal_params.append(("r1", spec.return_type))
    equal_params.append(("r2", spec.return_type))
    # then each &mut param's post1/post2, using spec_view when available
    for p in spec.params:
        if not p.is_mut_ref:
            continue
        vn = _var_name(p)
        ty = p.type
        if ty.spec_view is not None:
            # callsite passes post1_X@ / post2_X@ (convert to view);
            # equal fn parameter is typed as the View; body accesses fields
            # directly on the bare param name (no `@`).
            view_ty = ty.spec_view
            equal_body_args.append((f"post1_{vn}", f"post2_{vn}", view_ty))
            equal_call_args.append((f"post1_{vn}@", f"post2_{vn}@"))
            equal_params.append((f"post1_{vn}", view_ty))
            equal_params.append((f"post2_{vn}", view_ty))
        else:
            equal_body_args.append((f"post1_{vn}", f"post2_{vn}", ty))
            equal_call_args.append((f"post1_{vn}", f"post2_{vn}"))
            equal_params.append((f"post1_{vn}", ty))
            equal_params.append((f"post2_{vn}", ty))

    call_args_flat = []
    for (a1, a2) in equal_call_args:
        call_args_flat.append(a1)
        call_args_flat.append(a2)
    conclusion = f"{equal_fn_name}({', '.join(call_args_flat)})"

    # Ensures: `({&&& run1 &&& run2}) ==> conclusion`. No assumes here — they
    # go into the body as `assume(...)` statements, which is cleaner and keeps
    # the postcondition stable across search rounds.
    # Lift impl/fn generics onto the proof fn signature, but only the subset
    # actually referenced by params/return — phantom generics trigger
    # E0284/E0283 type-annotations-needed at the call site of the equal-fn.
    sig_for_prune = params_str
    if spec.self_type:
        sig_for_prune = re.sub(r'\bSelf\b', spec.self_type, sig_for_prune)
    pruned_generics, pruned_where = _prune_generics(
        spec.generics_decl, spec.where_decl, sig_for_prune)
    where_block = f"\n    {pruned_where}" if pruned_where else ""
    code = f"""proof fn {fn_name}{pruned_generics}({params_str}){where_block}{requires_str}
    ensures
        ({{
            &&& {run1}
            &&& {run2}
        }}) ==> {conclusion},
{{
{{ASSUMES}}}}"""

    # Substitute `Self` (word-boundary) with the impl target text so the
    # generated proof fn — which lives at module scope — typechecks even
    # when ensures/requires referenced `Self` directly.
    if spec.self_type:
        code = re.sub(r'\bSelf\b', spec.self_type, code)

    # Build the default equal spec fn body uses bare names (no `@`).
    equal_fn_def = _build_equal_fn(
        equal_fn_name, equal_params, equal_body_args, policy,
        generics_decl=spec.generics_decl,
        where_decl=spec.where_decl,
        self_type=spec.self_type,
        view_registry=view_registry,
    )

    return code, equal_fn_def, equal_fn_name, equal_call_args


# ---------------------------------------------------------------------------
# Public API: produce DetCheckSpec
# ---------------------------------------------------------------------------

def build_det_check_spec(
    spec: FunctionSpec,
    check_name: str | None = None,
    verus_config: dict | None = None,
    equal_policy: EqualPolicy | None = None,
    view_registry: Optional["ViewRegistry"] = None,
) -> DetCheckSpec:
    """
    Build a DetCheckSpec from a FunctionSpec.

    This is the output of Step 1 (extract + gen_det).

    ``equal_policy`` controls how the generated ``det_<fn>_equal`` spec fn
    coarsens structural equality. Defaults to ``default_policy()`` — all
    ``Err`` values equivalent; everything else strict.

    ``view_registry`` (Phase 2) is the L1+L2+L3 view-aware-equal resolver.
    When supplied, struct types lacking an inline ``TypeInfo.spec_view``
    will be looked up by short name in the project's prelude / alias /
    impl-View tables, and a ``.view()`` / ``@`` projection will be
    emitted instead of recursive structural comparison. Pass ``None`` for
    the legacy (pre-Phase-2) behaviour.
    """
    if equal_policy is None:
        equal_policy = default_policy()
    template, equal_fn_def, equal_fn_name, equal_call_args = _build_template(
        spec, check_name, equal_policy, view_registry=view_registry,
    )
    symbols = _build_symbols(spec)
    check_fn_name = check_name or f"det_{spec.name}"

    return DetCheckSpec(
        function=spec.name,
        det_check_template=template,
        symbols=symbols,
        verus_config=verus_config or {},
        equal_fn_def=equal_fn_def,
        equal_fn_name=equal_fn_name,
        check_fn_name=check_fn_name,
        equal_policy=equal_policy.to_dict(),
        # callsite form: includes `@` for view-wrapped compound outputs.
        # Used by distinctness phase to call `!{equal_fn_name}(lhs, rhs, ...)`.
        equal_arg_pairs=[
            {"lhs": a1, "rhs": a2} for (a1, a2) in equal_call_args
        ],
        generics_decl=spec.generics_decl,
        where_decl=spec.where_decl,
        self_type=spec.self_type,
    )


def render_template(
    template_or_spec,
    assumes: list[Assume],
) -> str:
    """Render a det check template with concrete assumes.

    Accepts either a raw template string (legacy) or a DetCheckSpec
    (preferred). When a DetCheckSpec is passed, the generated
    `spec fn {equal_fn_name}(...) -> bool` is prepended to the rendered
    code so the conclusion call `{equal_fn_name}(...)` resolves.
    Replaces `{ASSUMES}` in the template with `assume(...)` statements.
    """
    if isinstance(template_or_spec, DetCheckSpec):
        template = template_or_spec.det_check_template
        equal_fn_def = template_or_spec.equal_fn_def or ""
    else:
        template = template_or_spec
        equal_fn_def = ""

    if assumes:
        assume_parts = [f"    assume({a.expression.strip()});" for a in assumes]
        assume_str = "\n".join(assume_parts) + "\n"
    else:
        assume_str = ""

    body = template.replace("{ASSUMES}", assume_str)
    if equal_fn_def:
        return equal_fn_def + "\n\n" + body
    return body


# ---------------------------------------------------------------------------
# Substitution helpers (unchanged)
# ---------------------------------------------------------------------------

def _substitute_input(requires_raw: str, spec: FunctionSpec) -> str:
    result = requires_raw
    for p in spec.params:
        if p.is_self:
            vn = _var_name(p)
            if p.is_mut_ref:
                target = f'pre_{vn}'
            else:
                target = vn
            result = re.sub(r'\bold\s*\(\s*self\s*,?\s*\)', target, result)
            result = re.sub(r'\bself\b', target, result)
        elif p.is_mut_ref:
            # Non-self `&mut T` param: in requires, `old(p)` refers to
            # the pre-state value, which in the det-check fn is the
            # synthesised `pre_<p>` parameter.
            vn = _var_name(p)
            result = re.sub(
                rf'\*\s*old\s*\(\s*{re.escape(p.name)}\s*,?\s*\)',
                f'pre_{vn}', result,
            )
            result = re.sub(
                rf'\bold\s*\(\s*{re.escape(p.name)}\s*,?\s*\)',
                f'pre_{vn}', result,
            )
            # A bare `p` in requires (rarely seen, since requires
            # typically talk about the pre-state) also maps to pre_.
            result = re.sub(rf'\*\s*{re.escape(p.name)}\b', f'pre_{vn}', result)
            result = re.sub(rf'\b{re.escape(p.name)}\b', f'pre_{vn}', result)
        elif p.is_ref and not p.is_mut_ref:
            # Shared reference param passed by value in det-check fn:
            # strip `*p` dereferences.
            result = re.sub(rf'\*\s*{re.escape(p.name)}\b', p.name, result)
    return result


def _rename_idents_in_expr(text: str, name_map: dict) -> str:
    """AST-aware identifier rename in a Verus expression.

    Wraps ``text`` in a probe ``proof fn __probe() ensures EXPR, {}`` and
    walks the parse tree. For every ``identifier`` (or ``self``) leaf whose
    text matches a key in ``name_map``, splice in the mapped value.

    Skips:
      - ``field_identifier`` nodes (different node type — naturally skipped)
      - identifier children of ``scoped_identifier`` (path components like
        ``Foo::next`` — neither side is a local variable)

    Falls back to a conservative regex with ``(?<![.:])`` lookbehind on
    parse failure (e.g. malformed ensures fragments).
    """
    if not name_map or not text.strip():
        return text

    wrapped_prefix = "verus!{ proof fn __probe() ensures "
    wrapped = f"{wrapped_prefix}{text}, {{}} }}"
    expr_start = len(wrapped_prefix)

    tree = _parser.parse(wrapped.encode())

    def has_error(n):
        if n.type == 'ERROR' or n.is_missing:
            return True
        return any(has_error(c) for c in n.children)

    if has_error(tree.root_node):
        out = text
        for old_name, new_name in name_map.items():
            out = re.sub(
                rf'(?<![.:])\b{re.escape(old_name)}\b',
                new_name,
                out,
            )
        return out

    edits: list[tuple[int, int, str]] = []
    expr_end = expr_start + len(text)
    wrapped_bytes = wrapped.encode()

    def visit(node):
        if node.type == 'scoped_identifier':
            return  # path components are namespace-resolved, skip subtree
        if node.type in ('identifier', 'self'):
            if node.start_byte < expr_start or node.end_byte > expr_end:
                return
            name = wrapped_bytes[node.start_byte:node.end_byte].decode()
            if name in name_map:
                s = node.start_byte - expr_start
                e = node.end_byte - expr_start
                edits.append((s, e, name_map[name]))
            return
        for c in node.children:
            visit(c)

    visit(tree.root_node)

    edits.sort(key=lambda x: -x[0])
    out_bytes = text.encode()
    for s, e, repl in edits:
        out_bytes = out_bytes[:s] + repl.encode() + out_bytes[e:]
    return out_bytes.decode()


def _substitute_run(ensures_raw: str, spec: FunctionSpec, run_id: int) -> str:
    # Rename match-arm bindings first while text is still valid Verus,
    # so tree-sitter can parse it correctly for scoped renaming.
    result = _rename_match_bindings(ensures_raw, run_id)

    # Pre-pass: handle multi-token transforms (deref strip, old(...) wrappers)
    # via regex — these are not name-vs-field-name ambiguities. We also collect
    # the single-identifier renames into ``name_map`` and apply them in one
    # AST-aware pass at the end so e.g. ``self.arr.next`` is not corrupted
    # when the result binding happens to be ``next``.
    name_map: dict[str, str] = {}
    for p in spec.params:
        if p.is_mut_ref and p.is_self:
            vn = _var_name(p)
            result = result.replace('__PRE__', f'pre_{vn}')
            result = result.replace('__POST__', f'post{run_id}_{vn}')
            result = result.replace('__RESULT__', f'r{run_id}')
            result = re.sub(r'\*\s*old\s*\(\s*self\s*,?\s*\)', f'pre_{vn}', result)
            result = re.sub(r'\bold\s*\(\s*self\s*,?\s*\)', f'pre_{vn}', result)
            result = re.sub(r'\*\s*self\b', f'post{run_id}_{vn}', result)
            name_map['self'] = f'post{run_id}_{vn}'
        elif p.is_mut_ref:
            vn = _var_name(p)
            result = re.sub(rf'\*\s*old\s*\(\s*{re.escape(p.name)}\s*,?\s*\)', f'pre_{vn}', result)
            result = re.sub(rf'\bold\s*\(\s*{re.escape(p.name)}\s*,?\s*\)', f'pre_{vn}', result)
            result = re.sub(rf'\*\s*{re.escape(p.name)}\b', f'post{run_id}_{vn}', result)
            name_map[p.name] = f'post{run_id}_{vn}'
        elif p.is_self:
            vn = _var_name(p)
            result = re.sub(r'\bold\s*\(\s*self\s*,?\s*\)', vn, result)
            name_map['self'] = vn
        elif p.is_ref:
            # Shared reference: spec body may write `*p`; strip deref since the
            # det-check fn takes the param by value.
            result = re.sub(rf'\*\s*{re.escape(p.name)}\b', p.name, result)

    # Honour the function's actual return-value binding (from `(name: T)`
    # in the signature or `#[verus_spec(name => ...)]`).
    if spec.result_binding and spec.result_binding != f"r{run_id}":
        name_map[spec.result_binding] = f'r{run_id}'

    if name_map:
        result = _rename_idents_in_expr(result, name_map)

    result = result.replace('__RESULT__', f'r{run_id}')

    return result


# ---------------------------------------------------------------------------
# AST-based match-arm binding rename
# ---------------------------------------------------------------------------

def _extract_pattern_bindings(pattern_node: ts.Node) -> list[ts.Node]:
    """Extract binding identifier nodes from a pattern AST node.

    For ``tuple_struct_pattern`` like ``Ok(x)``, returns ``[x_node]``.
    Handles nested ``tuple_pattern`` / ``tuple_struct_pattern`` recursively.

    Skips bare identifiers (could be constants) and struct-pattern shorthand
    (renaming ``Foo { a }`` to ``Foo { a_1 }`` would change the field name).
    """
    bindings: list[ts.Node] = []

    if pattern_node.type == 'tuple_struct_pattern':
        after_paren = False
        for child in pattern_node.children:
            if child.type == '(':
                after_paren = True
                continue
            if child.type == ')':
                break
            if not after_paren or child.type == ',':
                continue
            if child.type == 'identifier':
                bindings.append(child)
            elif child.type == 'mut_pattern':
                for sub in child.children:
                    if sub.type == 'identifier':
                        bindings.append(sub)
            elif child.type == '_':
                continue
            else:
                bindings.extend(_extract_pattern_bindings(child))

    elif pattern_node.type == 'tuple_pattern':
        for child in pattern_node.children:
            if child.type in ('(', ')', ','):
                continue
            if child.type == 'identifier':
                bindings.append(child)
            elif child.type == '_':
                continue
            else:
                bindings.extend(_extract_pattern_bindings(child))

    return bindings


_SHADOW_INTRODUCING_TYPES = frozenset({
    'quantifier_expression',
    'let_declaration',
    'closure_expression',
})


def _shadows_name(node: ts.Node, name: str) -> bool:
    """Check if *node* introduces a binding that shadows *name*."""
    if node.type == 'quantifier_expression':
        for child in node.children:
            if child.type == 'closure_parameters':
                for param in child.children:
                    if param.type == 'parameter':
                        for sub in param.children:
                            if sub.type == 'identifier' and sub.text.decode() == name:
                                return True
                    elif param.type == 'identifier' and param.text.decode() == name:
                        return True
    elif node.type == 'let_declaration':
        pat = node.child_by_field_name('pattern')
        if pat is None:
            # Fallback: first identifier child is the binding
            for child in node.children:
                if child.type == 'identifier':
                    pat = child
                    break
        if pat and pat.type == 'identifier' and pat.text.decode() == name:
            return True
    elif node.type == 'closure_expression':
        for child in node.children:
            if child.type == 'closure_parameters':
                for param in child.children:
                    if param.type == 'identifier' and param.text.decode() == name:
                        return True
    return False


def _find_scoped_refs(node: ts.Node, name: str) -> list[ts.Node]:
    """Find ``identifier`` nodes matching *name* in subtree, skipping shadowed scopes."""
    refs: list[ts.Node] = []
    if node.type == 'identifier' and node.text.decode() == name:
        refs.append(node)
        return refs
    for child in node.children:
        if child.type in _SHADOW_INTRODUCING_TYPES and _shadows_name(child, name):
            continue
        refs.extend(_find_scoped_refs(child, name))
    return refs


def _rename_match_bindings(text: str, run_id: int) -> str:
    """Rename match-arm bindings using tree-sitter AST analysis.

    Wraps the ensures text in a minimal parseable context, walks the AST
    to find ``expr matches Pattern ==> body`` constructs, extracts binding
    identifiers from *Pattern*, then renames them (and their scoped
    references in *body*) to ``{name}_{run_id}`` via byte-level replacement.
    """
    prefix = 'spec fn _w() -> bool {\n'
    suffix = '\n}'
    wrapper = prefix + text + suffix
    tree = _parser.parse(wrapper.encode())

    prefix_bytes = len(prefix.encode())
    text_byte_len = len(text.encode())

    # Abort if parse produced errors in the text region.
    def _has_error(node: ts.Node) -> bool:
        if node.type == 'ERROR':
            if node.start_byte < prefix_bytes + text_byte_len and node.end_byte > prefix_bytes:
                return True
        return any(_has_error(c) for c in node.children)

    if _has_error(tree.root_node):
        logger.warning("_rename_match_bindings: parse errors in ensures text, skipping rename")
        return text

    replacements: list[tuple[int, int, str]] = []

    def _collect(node: ts.Node) -> None:
        if node.type == 'binary_expression':
            lhs = node.child_by_field_name('left')
            op = node.child_by_field_name('operator')
            rhs = node.child_by_field_name('right')

            if (lhs is not None and op is not None and rhs is not None
                    and lhs.type == 'matches_expression'
                    and op.type == '==>'):
                pattern = lhs.child_by_field_name('pattern')
                if pattern is not None:
                    for bnode in _extract_pattern_bindings(pattern):
                        bname = bnode.text.decode()
                        if bname == '_':
                            continue
                        # Binding definition in pattern
                        s = bnode.start_byte - prefix_bytes
                        e = bnode.end_byte - prefix_bytes
                        if 0 <= s < text_byte_len:
                            replacements.append((s, e, bname))
                        # Scoped references in body
                        for ref in _find_scoped_refs(rhs, bname):
                            s = ref.start_byte - prefix_bytes
                            e = ref.end_byte - prefix_bytes
                            if 0 <= s < text_byte_len:
                                replacements.append((s, e, bname))

        for child in node.children:
            _collect(child)

    _collect(tree.root_node)

    if not replacements:
        return text

    # Deduplicate by start position, sort reverse for safe byte-level editing
    seen: set[int] = set()
    unique: list[tuple[int, int, str]] = []
    for r in replacements:
        if r[0] not in seen:
            seen.add(r[0])
            unique.append(r)
    unique.sort(key=lambda x: x[0], reverse=True)

    result = bytearray(text.encode())
    for start, end, name in unique:
        result[start:end] = f"{name}_{run_id}".encode()

    return result.decode()


# ---------------------------------------------------------------------------
# Equal fn generation (structural-equality spec fn built from TypeInfo)
# ---------------------------------------------------------------------------

def _build_equal_fn(
    fn_name: str,
    params: list[tuple[str, TypeInfo]],
    arg_pairs: list[tuple[str, str, TypeInfo]],
    policy: EqualPolicy | None = None,
    generics_decl: str = "",
    where_decl: str = "",
    self_type: str | None = None,
    view_registry: Optional["ViewRegistry"] = None,
) -> str:
    """Emit a Verus spec fn that structurally compares each (lhs, rhs) pair.

    The function is `&&`-joined over all pairs. Each individual equality is
    built recursively by `build_equal_expr` based on TypeInfo + policy, which
    means enums/Results are `match`-split so we never rely on a derived `==`
    that might be missing for nested types (e.g. `Error` without `PartialEq`).

    If ``policy.custom_body`` is set, it is used verbatim as the function
    body (the caller — typically a human reviewer or an LLM hook — takes
    full responsibility for correctness).

    ``generics_decl`` / ``where_decl`` / ``self_type`` propagate the
    enclosing impl's generic context onto the synthesized spec fn.
    """
    if policy is None:
        policy = default_policy()

    param_decls = ", ".join(f"{n}: {_type_annotation(t)}" for (n, t) in params)
    if self_type:
        param_decls = re.sub(r'\bSelf\b', self_type, param_decls)

    if policy.custom_body is not None and policy.custom_body.strip():
        body = policy.custom_body.strip()
    else:
        clauses = []
        for (lhs, rhs, ty) in arg_pairs:
            clauses.append(build_equal_expr(ty, lhs, rhs, policy,
                                            view_registry=view_registry))

        if not clauses:
            body = "true"
        else:
            body = "\n    && ".join(f"({c})" for c in clauses)

    # Header comment makes it explicit to reviewers that this body is
    # generated from a declarative policy and summarises the active rules.
    header = (
        f"// Generated equal-fn for determinism check.\n"
        f"// Policy: errs_equivalent={policy.errs_equivalent}, "
        f"opaque_ok={policy.opaque_ok}"
    )
    if policy.ignore_fields:
        header += f", ignore_fields={sorted(policy.ignore_fields)}"
    if policy.opaque_types:
        header += f", opaque_types={sorted(policy.opaque_types)}"
    if policy.custom_body:
        header += " [custom_body in use]"

    # Drop unused generics (phantom-generic ⇒ E0284 at the call site). Use
    # the post-Self-substitution `param_decls` as the reference signature;
    # the equal-fn return type is `bool`, so generics never appear there.
    pruned_generics, pruned_where = _prune_generics(
        generics_decl, where_decl, param_decls)

    where_block = f"\n    {pruned_where}" if pruned_where else ""
    return (
        f"{header}\n"
        f"spec fn {fn_name}{pruned_generics}({param_decls}) -> bool{where_block} {{\n"
        f"    {body}\n"
        f"}}"
    )


def _type_annotation(ty: TypeInfo) -> str:
    """Render a TypeInfo as a Verus type annotation for a parameter."""
    return ty.name


def build_equal_expr(
    ty: TypeInfo,
    lhs: str,
    rhs: str,
    policy: EqualPolicy | None = None,
    view_registry: Optional["ViewRegistry"] = None,
) -> str:
    """Recursively emit a Verus boolean expression that structurally compares
    two values of the given type. The output is always inside `spec` mode.

    For primitive / Set / Seq, uses `==` directly (Verus has structural
    equality on these). For Result / Option / generic Enum, emits a
    conjunction of `is`-discriminator equality + per-variant implication
    comparing inner fields. For Struct, emits a conjunction over field
    comparisons; uses `@` if the struct has a spec view.

    ``policy`` (default: ``default_policy()``) controls coarsening rules —
    e.g. ``errs_equivalent`` collapses all ``Err`` to one equivalence class,
    ``opaque_ok`` does the same for ``Ok``, ``opaque_types`` treats whole
    named types as equivalent, and ``ignore_fields`` omits struct fields.

    ``view_registry`` (Phase 2 L1+L2+L3 resolver) — when provided, the
    STRUCT / UNKNOWN fallback first consults the registry for a
    view-aware-equal projection (prelude container, alias deref, or
    discovered ``impl View``). When ``None``, behaviour is unchanged.
    """
    if policy is None:
        policy = default_policy()

    k = ty.kind

    # Whole-type opacity (policy override)
    if ty.name and ty.name in policy.opaque_types:
        return "true"

    # Raw-pointer opacity (mechanical default).
    # `*mut T` / `*const T` addresses are allocator-nondeterministic at the
    # Verus/Z3 level — structural `==` compares abstract heap addresses and
    # always admits spurious "different pointer" witnesses (see observations).
    # Gated by `compare_raw_pointers` for the rare case a spec genuinely
    # pins pointer identity through ghost state.
    if _is_raw_pointer_type(ty) and not policy.compare_raw_pointers:
        return "true /* raw pointer: opaque by default */"

    # Primitive / value types where structural `==` is safe
    if k in (
        TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
        TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
        TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
        TypeKind.BOOL, TypeKind.UNIT, TypeKind.STR,
        TypeKind.SET, TypeKind.SEQ,
    ):
        return f"{lhs} == {rhs}"

    if k == TypeKind.RESULT:
        ok_ty = ty.type_args[0] if len(ty.type_args) > 0 else TypeInfo(TypeKind.UNIT, "()")
        err_ty = ty.type_args[1] if len(ty.type_args) > 1 else TypeInfo(TypeKind.UNKNOWN, "unknown")
        # Ok side — opaque or recurse
        if policy.opaque_ok:
            ok_clause = f"(({lhs} is Ok) ==> true)"
        else:
            ok_eq = build_equal_expr(ok_ty, f"{lhs}->Ok_0", f"{rhs}->Ok_0", policy,
                                     view_registry=view_registry)
            ok_clause = f"(({lhs} is Ok) ==> ({ok_eq}))"
        # Err side — collapse all Errs or recurse
        if policy.errs_equivalent:
            # All Errs are equivalent: only discriminator match matters.
            return (
                f"(({lhs} is Ok) == ({rhs} is Ok))"
                f" && {ok_clause}"
            )
        err_eq = build_equal_expr(err_ty, f"{lhs}->Err_0", f"{rhs}->Err_0", policy,
                                  view_registry=view_registry)
        return (
            f"(({lhs} is Ok) == ({rhs} is Ok))"
            f" && {ok_clause}"
            f" && (({lhs} is Err) ==> ({err_eq}))"
        )

    if k == TypeKind.OPTION:
        inner_ty = ty.type_args[0] if ty.type_args else TypeInfo(TypeKind.UNKNOWN, "unknown")
        some_eq = build_equal_expr(inner_ty, f"{lhs}->Some_0", f"{rhs}->Some_0", policy,
                                   view_registry=view_registry)
        return (
            f"(({lhs} is Some) == ({rhs} is Some))"
            f" && (({lhs} is Some) ==> ({some_eq}))"
        )

    if k == TypeKind.ENUM:
        if not ty.variants:
            # No variant info — try the view registry before raw `==` so
            # macro-generated enums (e.g. `state_machine!`) can still get
            # a view-aware equal.
            vreg_eq = _try_view_registry_equal(view_registry, ty, lhs, rhs)
            if vreg_eq is not None:
                return vreg_eq
            return f"{lhs} == {rhs}"
        # C-like enums (unit variants with integer discriminants) collapse
        # to a single integer comparison. This matches how the spec
        # typically talks about them (`x as usize == N`), avoids
        # enumerating every variant, and keeps the equal-fn valid even
        # when some variants are cfg-gated out of the active build.
        if ty.is_c_like_enum():
            return f"({lhs} as int) == ({rhs} as int)"
        # For each variant, require both sides to be that variant and inner
        # fields to match. The discriminators must agree first.
        parts = []
        for v in ty.variants:
            disc = f"(({lhs} is {v.name}) == ({rhs} is {v.name}))"
            parts.append(disc)
            if v.inner is not None:
                # Single-field variant (e.g. Foo(T)). Compare ->{name}_0
                inner_eq = build_equal_expr(
                    v.inner, f"{lhs}->{v.name}_0", f"{rhs}->{v.name}_0", policy,
                    view_registry=view_registry,
                )
                parts.append(f"(({lhs} is {v.name}) ==> ({inner_eq}))")
        return " && ".join(parts)

    if k == TypeKind.STRUCT:
        view = ty.spec_view
        lhs_is_viewed = lhs.endswith("@")
        rhs_is_viewed = rhs.endswith("@")
        if view is not None and view.fields and lhs_is_viewed and rhs_is_viewed:
            clauses = []
            for fld in view.fields:
                if fld.name in policy.ignore_fields:
                    continue
                clauses.append(build_equal_expr(
                    fld.type, f"{lhs}.{fld.name}", f"{rhs}.{fld.name}", policy,
                    view_registry=view_registry,
                ))
            if not clauses:
                return "true"
            return " && ".join(f"({c})" for c in clauses)
        if view is not None and not (lhs_is_viewed and rhs_is_viewed):
            # Nested struct-with-view (e.g. Result<Kheap, _> where caller
            # passed `r1->Ok_0`). Compare through the view at spec level.
            # Note: ignore_fields/errs_equivalent cannot be threaded through
            # a raw `@ == @` comparison — if the caller needs that, they
            # should supply a custom_body for this function.
            return f"({lhs})@ == ({rhs})@"
        # Phase-2 hook: no inline `TypeInfo.spec_view` was discovered.
        # Consult the L1+L2+L3 resolver before falling back to a recursive
        # field-by-field structural comparison. The resolver's hit covers
        # alias-to-primitive (e.g. `Pcid = usize`), prelude containers
        # appearing as struct types, and explicit `impl View for X`.
        vreg_eq = _try_view_registry_equal(view_registry, ty, lhs, rhs)
        if vreg_eq is not None:
            return vreg_eq
        if ty.fields:
            clauses = []
            for fld in ty.fields:
                if fld.name in policy.ignore_fields:
                    continue
                clauses.append(build_equal_expr(
                    fld.type, f"{lhs}.{fld.name}", f"{rhs}.{fld.name}", policy,
                    view_registry=view_registry,
                ))
            if not clauses:
                return "true"
            return " && ".join(f"({c})" for c in clauses)
        # No field info at all — fall back to `==`
        return f"{lhs} == {rhs}"

    # UNKNOWN: try the view registry before falling back to raw `==`.
    vreg_eq = _try_view_registry_equal(view_registry, ty, lhs, rhs)
    if vreg_eq is not None:
        return vreg_eq
    return f"{lhs} == {rhs}"


def _try_view_registry_equal(
    view_registry: Optional["ViewRegistry"],
    ty: TypeInfo,
    lhs: str,
    rhs: str,
) -> Optional[str]:
    """Phase 2 hook: ask the resolver for a view-aware equality
    expression. Returns ``None`` when the registry isn't supplied or
    the type is uncovered — caller falls through to its existing
    structural fallback. Failures inside the resolver are swallowed
    and logged (we never want a registry bug to break codegen).
    """
    if view_registry is None or not ty.name:
        return None
    try:
        type_expr = _typeinfo_to_typeexpr(ty)
        return view_registry.equal_expr(lhs, rhs, type_expr)
    except Exception as e:  # pragma: no cover — safety net
        logger.warning("ViewRegistry.equal_expr failed for %s: %s",
                       ty.name, e)
        return None


# ---------------------------------------------------------------------------
# rebuild_equal_fn — regenerate equal fn after llm_refine (types may have
# become more informative, e.g. UNKNOWN -> struct).
# ---------------------------------------------------------------------------

def rebuild_equal_fn(det_spec: DetCheckSpec,
                     view_registry: Optional["ViewRegistry"] = None,
                     ) -> DetCheckSpec:
    """Regenerate ``equal_fn_def`` / ``equal_fn_name`` / ``equal_arg_pairs`` from
    the (possibly refined) ``det_spec.symbols`` and return the updated spec.

    Strategy: find the output symbols by phase (output_simple / output_compound),
    group into pairs (r1/r2, post1_X/post2_X), then replay ``_build_equal_fn``.

    ``view_registry`` — optional Phase-2 L1+L2+L3 view resolver, propagated
    to ``build_equal_expr``. ``None`` preserves legacy behaviour.
    """
    base = det_spec.check_fn_name or f"det_{det_spec.function}"
    equal_fn_name = f"{base}_equal"

    # Collect output symbols. Symbols are created by _build_symbols with
    # names r1/r2 (output_simple) and post1_X/post2_X (output_compound).
    sym_by_name: dict[str, Symbol] = {s.name: s for s in det_spec.symbols}

    params: list[tuple[str, TypeInfo]] = []
    body_pairs: list[tuple[str, str, TypeInfo]] = []   # used inside equal fn
    callsite_pairs: list[tuple[str, str]] = []         # used at call site
    declared: set[str] = set()

    # r1 / r2 first
    if "r1" in sym_by_name and "r2" in sym_by_name:
        r1 = sym_by_name["r1"]
        r2 = sym_by_name["r2"]
        params.append(("r1", r1.type))
        params.append(("r2", r2.type))
        body_pairs.append(("r1", "r2", r1.type))
        callsite_pairs.append(("r1", "r2"))
        declared.add("r1")
        declared.add("r2")

    # then post1_X / post2_X — for compound outputs with a spec view, the
    # equal fn parameter is typed as the view (e.g. BitmapView), and the
    # callsite passes `post1_X@`. Inside the fn body the local name is
    # already the view, so we access fields directly (no `@`).
    for name in sorted(sym_by_name.keys()):
        if not name.startswith("post1_"):
            continue
        partner = "post2_" + name[len("post1_"):]
        if partner not in sym_by_name:
            continue
        if name in declared or partner in declared:
            continue
        sym = sym_by_name[name]
        ty = sym.type
        if sym.phase == "output_compound" and ty.spec_view is not None:
            view_ty = ty.spec_view
            params.append((name, view_ty))
            params.append((partner, view_ty))
            body_pairs.append((name, partner, view_ty))
            callsite_pairs.append((f"{name}@", f"{partner}@"))
        else:
            params.append((name, ty))
            params.append((partner, ty))
            body_pairs.append((name, partner, ty))
            callsite_pairs.append((name, partner))
        declared.add(name)
        declared.add(partner)

    equal_fn_def = _build_equal_fn(
        equal_fn_name, params, body_pairs,
        EqualPolicy.from_dict(det_spec.equal_policy),
        generics_decl=det_spec.generics_decl,
        where_decl=det_spec.where_decl,
        self_type=det_spec.self_type,
        view_registry=view_registry,
    )
    det_spec.equal_fn_def = equal_fn_def
    det_spec.equal_fn_name = equal_fn_name
    det_spec.equal_arg_pairs = [{"lhs": a1, "rhs": a2} for (a1, a2) in callsite_pairs]

    # Also rewrite the template's conclusion call so it uses the updated
    # callsite forms (may differ from pre-refine if spec_view became known).
    call_args_flat = []
    for (a1, a2) in callsite_pairs:
        call_args_flat.append(a1)
        call_args_flat.append(a2)
    new_call = f"{equal_fn_name}({', '.join(call_args_flat)})"
    import re as _re
    det_spec.det_check_template = _re.sub(
        rf"{_re.escape(equal_fn_name)}\([^)]*\)",
        new_call,
        det_spec.det_check_template,
        count=1,
    )
    return det_spec
