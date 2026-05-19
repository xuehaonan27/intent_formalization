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

from spec_determinism.extract.types import (
    TypeKind, TypeInfo, Param, FunctionSpec, Assume,
    Symbol, DetCheckSpec,
)
from .equal_policy import EqualPolicy, default_policy

if TYPE_CHECKING:
    from spec_determinism.view.registry import ViewRegistry

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
    from spec_determinism.extract.type_registry import TypeExpr

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

    # Trait-fn fallback: when the source fn lives inside a `trait { ... }`
    # block (no `impl` ancestor), `spec.self_type` is None but `Self`
    # still appears in params / return / ensures. Renderering it verbatim
    # at module scope triggers E0411 ("Self not allowed in a function").
    # Substitute it with a synthetic generic and inject the generic into
    # the proof-fn's type-parameter list so the synthesized fn typechecks
    # in isolation.
    needs_self_subst = (not spec.self_type) and (
        re.search(r'\bSelf\b', params_str) is not None
        or re.search(r'\bSelf\b', run1) is not None
        or re.search(r'\bSelf\b', run2) is not None
        or re.search(r'\bSelf\b', requires_str) is not None
        or re.search(r'\bSelf\b', conclusion) is not None
    )
    if needs_self_subst:
        placeholder = "__DetSelf"
        params_str = re.sub(r'\bSelf\b', placeholder, params_str)
        run1 = re.sub(r'\bSelf\b', placeholder, run1)
        run2 = re.sub(r'\bSelf\b', placeholder, run2)
        requires_str = re.sub(r'\bSelf\b', placeholder, requires_str)
        conclusion = re.sub(r'\bSelf\b', placeholder, conclusion)
        # If the source fn lives inside a `trait Foo { ... }` declaration,
        # bound `__DetSelf` by the trait so `Self::method` calls (e.g.
        # `Self::zero_spec()`) resolve. Otherwise leave it unbounded.
        placeholder_decl = (
            f"{placeholder}: {spec.trait_name}" if spec.trait_name else placeholder
        )
        # Splice `__DetSelf` into the generics list (creating one if absent).
        if pruned_generics.strip():
            inner = pruned_generics.strip().lstrip('<').rstrip('>').strip()
            pruned_generics = f"<{inner}, {placeholder_decl}>"
        else:
            pruned_generics = f"<{placeholder_decl}>"

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
    equal_fn_self_type = spec.self_type
    equal_fn_generics = spec.generics_decl
    if needs_self_subst:
        equal_fn_self_type = "__DetSelf"
        placeholder_decl = (
            f"__DetSelf: {spec.trait_name}" if spec.trait_name else "__DetSelf"
        )
        # Add the placeholder to the equal-fn's generics decl as well.
        if equal_fn_generics.strip():
            inner = equal_fn_generics.strip().lstrip('<').rstrip('>').strip()
            equal_fn_generics = f"<{inner}, {placeholder_decl}>"
        else:
            equal_fn_generics = f"<{placeholder_decl}>"
    equal_fn_def = _build_equal_fn(
        equal_fn_name, equal_params, equal_body_args, policy,
        generics_decl=equal_fn_generics,
        where_decl=spec.where_decl,
        self_type=equal_fn_self_type,
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

def _strip_unary_deref(text: str, name: str, replacement: str) -> str:
    """Replace ``*name`` (unary dereference) with ``replacement``, but
    preserve ``EXPR * name`` (binary multiplication).

    The injection pipeline rewrites ``&mut`` / ``&`` parameters from
    reference types to bare values, which means any ``*p`` in the source
    must drop the leading ``*``. A naive ``re.sub(r'\\*\\s*p\\b', …)``
    also matches multiplication contexts like ``4 * p.len`` and silently
    eats the operator, breaking the synthesized Verus output (see fix
    plan entry A2, 11 atmosphere targets pre-fix).

    Heuristic: look at the first non-whitespace character before the
    ``*``. If it is alphanumeric / ``_`` / ``)`` / ``]`` it is the tail
    of an expression, so the ``*`` is a binary operator — leave alone.
    Otherwise it is a unary prefix and we strip it.
    """
    pat = re.compile(rf'\*\s*{re.escape(name)}\b')
    out_chunks: list[str] = []
    pos = 0
    for m in pat.finditer(text):
        out_chunks.append(text[pos:m.start()])
        i = m.start() - 1
        while i >= 0 and text[i] in ' \t':
            i -= 1
        if i >= 0 and (text[i].isalnum() or text[i] == '_' or text[i] in ')]'):
            out_chunks.append(m.group(0))
        else:
            out_chunks.append(replacement)
        pos = m.end()
    out_chunks.append(text[pos:])
    return "".join(out_chunks)


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
            result = _strip_unary_deref(result, p.name, f'pre_{vn}')
            result = re.sub(rf'\b{re.escape(p.name)}\b', f'pre_{vn}', result)
        elif p.is_ref and not p.is_mut_ref:
            # Shared reference param passed by value in det-check fn:
            # strip `*p` dereferences.
            result = _strip_unary_deref(result, p.name, p.name)
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
            result = _strip_unary_deref(result, p.name, f'post{run_id}_{vn}')
            name_map[p.name] = f'post{run_id}_{vn}'
        elif p.is_self:
            vn = _var_name(p)
            result = re.sub(r'\bold\s*\(\s*self\s*,?\s*\)', vn, result)
            name_map['self'] = vn
        elif p.is_ref:
            # Shared reference: spec body may write `*p`; strip deref since the
            # det-check fn takes the param by value.
            result = _strip_unary_deref(result, p.name, p.name)

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
        prelude_decls: list[str] = []
    else:
        prelude_decls = []
        clauses = []
        for (lhs, rhs, ty) in arg_pairs:
            clauses.append(build_equal_expr(ty, lhs, rhs, policy,
                                            view_registry=view_registry,
                                            prelude_collector=prelude_decls))

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
    fn_def = (
        f"{header}\n"
        f"spec fn {fn_name}{pruned_generics}({param_decls}) -> bool{where_block} {{\n"
        f"    {body}\n"
        f"}}"
    )

    # PR-D2: prepend L4 LLM-synthesised `impl View for T { … }` decls so the
    # `.view()` calls embedded in the equal-fn resolve at compile time.
    # Dedupe while preserving first-seen order — the same prelude may be
    # collected multiple times when the type appears in several arg pairs.
    if prelude_decls:
        seen: set[str] = set()
        deduped: list[str] = []
        for d in prelude_decls:
            key = d.strip()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(d.strip())
        prelude_text = (
            "// L4-llm view declarations (generated, see "
            "view_registry cache)\n"
            + "\n\n".join(deduped)
        )
        fn_def = prelude_text + "\n\n" + fn_def
    return fn_def


def _type_annotation(ty: TypeInfo) -> str:
    """Render a TypeInfo as a Verus type annotation for a parameter."""
    return ty.name


# ---------------------------------------------------------------------------
# PR-G — A-3 nested-Err policy: detect Result hiding inside a container
# so we can lift `errs_equivalent` element-wise instead of letting raw `==`
# on Seq/Map structurally compare Err payloads.
# ---------------------------------------------------------------------------

def _contains_result(ty: TypeInfo, _seen: Optional[set[int]] = None) -> bool:
    """True iff `ty` transitively contains a `Result<_, _>`.

    Used by `build_equal_expr` to decide whether raw structural `==` on
    a Seq/Map element would over-compare under `errs_equivalent=True`.
    A `visited` guard handles self-referential TypeInfo graphs (e.g.
    a struct field whose type points back to the struct).
    """
    if _seen is None:
        _seen = set()
    tid = id(ty)
    if tid in _seen:
        return False
    _seen.add(tid)
    if ty.kind == TypeKind.RESULT:
        return True
    for arg in ty.type_args or []:
        if _contains_result(arg, _seen):
            return True
    for fld in ty.fields or []:
        if _contains_result(fld.type, _seen):
            return True
    for var in ty.variants or []:
        if var.inner is not None and _contains_result(var.inner, _seen):
            return True
    return False


def _container_needs_elementwise(ty: TypeInfo, policy: EqualPolicy) -> bool:
    """True iff a container of `ty` cannot be safely compared with raw
    structural `==` under `policy`. Currently this fires only when
    `errs_equivalent=True` and `ty` transitively contains a `Result`."""
    if not policy.errs_equivalent:
        return False
    return _contains_result(ty)


def build_equal_expr(
    ty: TypeInfo,
    lhs: str,
    rhs: str,
    policy: EqualPolicy | None = None,
    view_registry: Optional["ViewRegistry"] = None,
    prelude_collector: Optional[list[str]] = None,
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

    ``view_registry`` (Phase 2 L1+L2+L3+L4 resolver) — when provided, the
    STRUCT / UNKNOWN fallback first consults the registry for a
    view-aware-equal projection (prelude container, alias deref, discovered
    ``impl View``, or LLM-synthesised view from the on-disk cache). When
    ``None``, behaviour is unchanged.

    ``prelude_collector`` — list passed in by ``_build_equal_fn`` to gather
    L4 ``impl View for T { … }`` declarations that gen_det must emit before
    the equal-fn so the synthesized ``.view()`` calls resolve at compile
    time. Caller dedupes.
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
        TypeKind.SET,
    ):
        # NOTE: TypeKind.SET stays here — Set has no positional indexing so
        # we can't lift `errs_equivalent` element-wise without redefining
        # set equality. If `policy.errs_equivalent` and the element type
        # contains Result, raw `==` over-compares. Tracked as a known
        # limitation (PR-G follow-up); see _container_needs_elementwise.
        return f"{lhs} == {rhs}"

    # PR-G: Seq<E> where E transitively contains Result needs elementwise
    # comparison so `errs_equivalent` reaches the nested Err. Raw `==` on
    # a spec Seq is element-wise structural and would compare Err payloads.
    if k == TypeKind.SEQ:
        # PR-N: when the extractor recorded a `spec_view` on this SEQ, the
        # type is really a wrapper (e.g. exec `Vec<T>`) whose struct-eq is
        # not derivable from view equality (`Vec` is external_body in
        # Verus). Compare through the view so the obligation matches what
        # the wrapper's `ensures` actually delivers.
        if ty.spec_view is not None:
            return build_equal_expr(
                ty.spec_view, f"({lhs})@", f"({rhs})@", policy,
                view_registry=view_registry,
                prelude_collector=prelude_collector,
            )
        elem_ty = ty.type_args[0] if ty.type_args else None
        if elem_ty is not None and _container_needs_elementwise(elem_ty, policy):
            elem_eq = build_equal_expr(elem_ty, f"{lhs}[i]", f"{rhs}[i]", policy,
                                       view_registry=view_registry,
                                       prelude_collector=prelude_collector)
            return (
                f"({lhs}.len() == {rhs}.len()"
                f" && forall|i: int| 0 <= i < {lhs}.len() ==> ({elem_eq}))"
            )
        return f"{lhs} == {rhs}"

    # PR-G: Map<K, V> where V transitively contains Result also needs
    # value-wise comparison. Domain must match, then each value is
    # compared via the policy-aware equal-expr.
    if k == TypeKind.MAP:
        # PR-N: same wrapper rule as SEQ — when the extractor saw `spec_view`
        # on this MAP, the type is really an exec `HashMap<K,V>` (or
        # similar) and struct-eq is not derivable from view equality.
        if ty.spec_view is not None:
            return build_equal_expr(
                ty.spec_view, f"({lhs})@", f"({rhs})@", policy,
                view_registry=view_registry,
                prelude_collector=prelude_collector,
            )
        v_ty = ty.type_args[1] if len(ty.type_args) > 1 else None
        if v_ty is not None and _container_needs_elementwise(v_ty, policy):
            val_eq = build_equal_expr(v_ty, f"{lhs}[k]", f"{rhs}[k]", policy,
                                      view_registry=view_registry,
                                      prelude_collector=prelude_collector)
            k_ty = ty.type_args[0] if ty.type_args else TypeInfo(TypeKind.INT, "int")
            k_name = k_ty.name or "int"
            return (
                f"({lhs}.dom() == {rhs}.dom()"
                f" && forall|k: {k_name}| {lhs}.dom().contains(k)"
                f" ==> ({val_eq}))"
            )
        return f"{lhs} == {rhs}"

    if k == TypeKind.RESULT:
        ok_ty = ty.type_args[0] if len(ty.type_args) > 0 else TypeInfo(TypeKind.UNIT, "()")
        err_ty = ty.type_args[1] if len(ty.type_args) > 1 else TypeInfo(TypeKind.UNKNOWN, "unknown")
        # Ok side — opaque or recurse
        if policy.opaque_ok:
            ok_clause = f"(({lhs} is Ok) ==> true)"
        else:
            ok_eq = build_equal_expr(ok_ty, f"{lhs}->Ok_0", f"{rhs}->Ok_0", policy,
                                     view_registry=view_registry,
                                     prelude_collector=prelude_collector)
            ok_clause = f"(({lhs} is Ok) ==> ({ok_eq}))"
        # Err side — collapse all Errs or recurse
        if policy.errs_equivalent:
            # All Errs are equivalent: only discriminator match matters.
            return (
                f"(({lhs} is Ok) == ({rhs} is Ok))"
                f" && {ok_clause}"
            )
        err_eq = build_equal_expr(err_ty, f"{lhs}->Err_0", f"{rhs}->Err_0", policy,
                                  view_registry=view_registry,
                                  prelude_collector=prelude_collector)
        return (
            f"(({lhs} is Ok) == ({rhs} is Ok))"
            f" && {ok_clause}"
            f" && (({lhs} is Err) ==> ({err_eq}))"
        )

    if k == TypeKind.OPTION:
        inner_ty = ty.type_args[0] if ty.type_args else TypeInfo(TypeKind.UNKNOWN, "unknown")
        some_eq = build_equal_expr(inner_ty, f"{lhs}->Some_0", f"{rhs}->Some_0", policy,
                                   view_registry=view_registry,
                                   prelude_collector=prelude_collector)
        return (
            f"(({lhs} is Some) == ({rhs} is Some))"
            f" && (({lhs} is Some) ==> ({some_eq}))"
        )

    # PR-F: Tracked<T> / Ghost<T> — wrapper types whose spec value is the
    # inner T accessed via `@`. Compare through the projection so policy
    # rules (errs_equivalent / opaque_ok / ignore_fields) apply to the
    # inner value, not the wrapper identity.
    if k in (TypeKind.TRACKED, TypeKind.GHOST):
        if ty.type_args:
            inner_ty = ty.type_args[0]
            inner_eq = build_equal_expr(
                inner_ty, f"({lhs})@", f"({rhs})@", policy,
                view_registry=view_registry,
                prelude_collector=prelude_collector,
            )
            return inner_eq
        # No inner info — compare wrappers via `@` raw.
        return f"({lhs})@ == ({rhs})@"

    # PR-F: PointsTo<V> — the meaningful spec equality is "same init
    # state, and (if init) same inner value, at the same addr". We
    # compare each projection separately so policy can drive the inner.
    if k == TypeKind.POINTS_TO:
        parts = [
            f"(({lhs}).is_init() == ({rhs}).is_init())",
            f"(({lhs}).addr() == ({rhs}).addr())",
        ]
        if ty.type_args:
            v_ty = ty.type_args[0]
            v_eq = build_equal_expr(
                v_ty, f"({lhs}).value()", f"({rhs}).value()", policy,
                view_registry=view_registry,
                prelude_collector=prelude_collector,
            )
            parts.append(
                f"(({lhs}).is_init() ==> ({v_eq}))"
            )
        return " && ".join(parts)

    if k == TypeKind.ENUM:
        if not ty.variants:
            # No variant info — try the view registry before raw `==` so
            # macro-generated enums (e.g. `state_machine!`) can still get
            # a view-aware equal.
            vreg_eq = _try_view_registry_equal(view_registry, ty, lhs, rhs,
                                               prelude_collector)
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
        # Pre-compute the set of struct-form field names that appear in
        # more than one variant. Verus only auto-generates an ``arrow_f``
        # accessor when ``f`` is unique across all variants of the enum;
        # for ambiguous names ``lhs->f`` errors with "method `arrow_f`
        # not found". We fall back to whole-variant structural equality
        # in that case (sound: ``lhs == rhs`` is strictly stronger than
        # per-field equality given matching discriminators).
        ambiguous_struct_fields = ty.ambiguous_struct_variant_fields()
        # For each variant, require both sides to be that variant and inner
        # fields to match. The discriminators must agree first.
        parts = []
        for v in ty.variants:
            disc = f"(({lhs} is {v.name}) == ({rhs} is {v.name}))"
            parts.append(disc)
            if v.inner is not None:
                if v.struct_form and v.inner.fields:
                    # Struct-form variant ``V { f1, f2, ... }`` — Verus
                    # accesses fields directly as ``lhs->fname`` only when
                    # the name is unambiguous across all variants.
                    has_ambiguous = any(
                        fld.name in ambiguous_struct_fields
                        for fld in v.inner.fields
                    )
                    if has_ambiguous:
                        # Fall back to whole-variant structural equality.
                        # Sound: under the discriminator guard ``lhs is V``,
                        # ``lhs == rhs`` implies all per-field equalities.
                        inner_eq = f"{lhs} == {rhs}"
                    else:
                        field_clauses: list[str] = []
                        for fld in v.inner.fields:
                            field_clauses.append(build_equal_expr(
                                fld.type,
                                f"{lhs}->{fld.name}",
                                f"{rhs}->{fld.name}",
                                policy,
                                view_registry=view_registry,
                                prelude_collector=prelude_collector,
                            ))
                        inner_eq = " && ".join(f"({c})" for c in field_clauses) \
                            if field_clauses else "true"
                else:
                    # Tuple-form variant ``V(T)`` — accessed via ``lhs->V_0``.
                    inner_eq = build_equal_expr(
                        v.inner, f"{lhs}->{v.name}_0", f"{rhs}->{v.name}_0",
                        policy,
                        view_registry=view_registry,
                        prelude_collector=prelude_collector,
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
                    prelude_collector=prelude_collector,
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
        # Consult the L1+L2+L3+L4 resolver before falling back to a recursive
        # field-by-field structural comparison. The resolver's hit covers
        # alias-to-primitive (e.g. `Pcid = usize`), prelude containers
        # appearing as struct types, explicit `impl View for X`, and
        # cached LLM-synthesised `impl View` declarations.
        vreg_eq = _try_view_registry_equal(view_registry, ty, lhs, rhs,
                                           prelude_collector)
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
                    prelude_collector=prelude_collector,
                ))
            if not clauses:
                return "true"
            return " && ".join(f"({c})" for c in clauses)
        # No field info at all — fall back to `==`
        return f"{lhs} == {rhs}"

    # UNKNOWN: try the view registry before falling back to raw `==`.
    vreg_eq = _try_view_registry_equal(view_registry, ty, lhs, rhs,
                                       prelude_collector)
    if vreg_eq is not None:
        return vreg_eq
    return f"{lhs} == {rhs}"


def _try_view_registry_equal(
    view_registry: Optional["ViewRegistry"],
    ty: TypeInfo,
    lhs: str,
    rhs: str,
    prelude_collector: Optional[list[str]] = None,
) -> Optional[str]:
    """Phase 2 hook: ask the resolver for a view-aware equality
    expression. Returns ``None`` when the registry isn't supplied or
    the type is uncovered — caller falls through to its existing
    structural fallback. Failures inside the resolver are swallowed
    and logged (we never want a registry bug to break codegen).

    When the resolver returns an L4 hit (LLM-synthesised view), the
    cached ``impl View for T { … }`` declaration is appended to
    ``prelude_collector`` (deduplicated by the caller). The caller
    must prepend the collector to the synthesized equal-fn so the
    ``.view()`` projection actually resolves at compile time.
    """
    if view_registry is None or not ty.name:
        return None
    try:
        type_expr = _typeinfo_to_typeexpr(ty)
        res = view_registry.resolve(type_expr)
        if not res.is_resolved:
            return None
        if res.prelude_decl and prelude_collector is not None:
            prelude_collector.append(res.prelude_decl)
        return f"({res.view_expr(lhs)} == {res.view_expr(rhs)})"
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


# ---------------------------------------------------------------------------
# Self-tests — invoked via `python -m spec_determinism.codegen.gen_det test`
# ---------------------------------------------------------------------------

def _run_self_tests() -> int:
    """Lightweight in-process tests for build_equal_expr + PR-G nested-Err."""
    from spec_determinism.extract.types import VariantInfo, FieldInfo

    failures: list[str] = []

    def check(label: str, got: str, expected_substrs: list[str],
              forbidden_substrs: Optional[list[str]] = None):
        for s in expected_substrs:
            if s not in got:
                failures.append(f"{label}: expected substring {s!r} in:\n  {got}")
        for s in (forbidden_substrs or []):
            if s in got:
                failures.append(f"{label}: forbidden substring {s!r} present in:\n  {got}")

    # --- PR-G fixtures: nested Result inside containers ---
    int_ty = TypeInfo(TypeKind.INT, "int")
    u32_ty = TypeInfo(TypeKind.U32, "u32")
    u8_ty = TypeInfo(TypeKind.U8, "u8")
    err_ty = TypeInfo(TypeKind.STRUCT, "MyErr")  # opaque error struct
    result_u32_err = TypeInfo(
        TypeKind.RESULT, "Result<u32, MyErr>",
        type_args=[u32_ty, err_ty],
        variants=[VariantInfo("Ok", u32_ty), VariantInfo("Err", err_ty)],
    )

    # Top-level Result — both policies covered.
    expr_top = build_equal_expr(result_u32_err, "r1", "r2", default_policy())
    check("top-level Result with errs_equivalent",
          expr_top,
          ["(r1 is Ok) == (r2 is Ok)", "r1->Ok_0", "r2->Ok_0"],
          forbidden_substrs=["Err_0"])  # err side collapsed

    expr_top_strict = build_equal_expr(
        result_u32_err, "r1", "r2",
        EqualPolicy(errs_equivalent=False))
    check("top-level Result strict",
          expr_top_strict,
          ["r1->Ok_0", "r1->Err_0", "r2->Err_0"])

    # Seq<Result<u32, MyErr>> — was buggy pre-PR-G (raw `==`).
    seq_of_result = TypeInfo(TypeKind.SEQ, "Seq<Result<u32, MyErr>>",
                             type_args=[result_u32_err])
    expr_seq = build_equal_expr(seq_of_result, "s1", "s2", default_policy())
    check("Seq<Result<…>> with errs_equivalent uses forall element-wise",
          expr_seq,
          ["s1.len() == s2.len()", "forall|i: int|", "0 <= i < s1.len()",
           "s1[i]", "s2[i]", "is Ok"],
          forbidden_substrs=["s1[i]->Err_0", "s2[i]->Err_0"])

    # Same Seq under strict policy — element-wise raw `==` is fine since
    # errs_equivalent=False means we don't want to collapse anything.
    expr_seq_strict = build_equal_expr(
        seq_of_result, "s1", "s2", EqualPolicy(errs_equivalent=False))
    check("Seq<Result<…>> strict policy keeps raw ==",
          expr_seq_strict, ["s1 == s2"])

    # Seq<u32> — should still be raw == under any policy.
    seq_u32 = TypeInfo(TypeKind.SEQ, "Seq<u32>", type_args=[u32_ty])
    expr_seq_u32 = build_equal_expr(seq_u32, "s1", "s2", default_policy())
    check("Seq<u32> stays raw ==", expr_seq_u32, ["s1 == s2"],
          forbidden_substrs=["forall"])

    # PR-N: Vec<u8> wrapper (kind=SEQ, spec_view=Seq<u8>) — Vec is
    # external_body so struct-eq is not derivable. Must compare via @.
    vec_u8_view = TypeInfo(TypeKind.SEQ, "Seq<u8>", type_args=[u8_ty])
    vec_u8 = TypeInfo(TypeKind.SEQ, "Vec<u8>", type_args=[u8_ty],
                      spec_view=vec_u8_view)
    expr_vec_u8 = build_equal_expr(vec_u8, "v1", "v2", default_policy())
    check("Vec<u8> (SEQ + spec_view) compares via @",
          expr_vec_u8, ["(v1)@ == (v2)@"],
          forbidden_substrs=["v1 == v2"])

    # PR-N: Struct{ id: Vec<u8> } — STRUCT recurses into the Vec field,
    # which must in turn compare via @ (the Case-1 ironkv shape).
    from spec_determinism.extract.types import FieldInfo as _FI
    end_point = TypeInfo(
        TypeKind.STRUCT, "EndPoint",
        fields=[_FI("id", vec_u8)],
    )
    expr_end_point = build_equal_expr(end_point, "r1", "r2", default_policy())
    check("Struct{id: Vec<u8>} drops to view-eq on the Vec field",
          expr_end_point, ["(r1.id)@ == (r2.id)@"],
          forbidden_substrs=["r1.id == r2.id"])

    # PR-N: HashMap<K,V> wrapper (kind=MAP, spec_view=Map<K,V>) — symmetric
    # to the Vec case. struct-eq is not derivable; compare via @.
    map_view = TypeInfo(TypeKind.MAP, "Map<int, u32>",
                        type_args=[int_ty, u32_ty])
    hashmap = TypeInfo(TypeKind.MAP, "HashMap<int, u32>",
                       type_args=[int_ty, u32_ty], spec_view=map_view)
    expr_hashmap = build_equal_expr(hashmap, "h1", "h2", default_policy())
    check("HashMap<K,V> (MAP + spec_view) compares via @",
          expr_hashmap, ["(h1)@ == (h2)@"],
          forbidden_substrs=["h1 == h2"])

    # Map<int, Result<u32, MyErr>> — was buggy pre-PR-G.
    map_of_result = TypeInfo(TypeKind.MAP, "Map<int, Result<u32, MyErr>>",
                             type_args=[int_ty, result_u32_err])
    expr_map = build_equal_expr(map_of_result, "m1", "m2", default_policy())
    check("Map<_, Result<…>> with errs_equivalent uses dom+forall",
          expr_map,
          ["m1.dom() == m2.dom()", "forall|k: int|",
           "m1.dom().contains(k)", "m1[k]", "m2[k]"],
          forbidden_substrs=["m1[k]->Err_0", "m2[k]->Err_0"])

    # Map<int, u32> — should stay raw ==.
    map_int_u32 = TypeInfo(TypeKind.MAP, "Map<int, u32>",
                           type_args=[int_ty, u32_ty])
    expr_map_iu = build_equal_expr(map_int_u32, "m1", "m2", default_policy())
    check("Map<int, u32> stays raw ==", expr_map_iu, ["m1 == m2"],
          forbidden_substrs=["forall"])

    # Result<Seq<Result<u32, MyErr>>, MyErr> — outer Err collapsed AND
    # inner Seq elementwise lift.
    outer = TypeInfo(
        TypeKind.RESULT,
        "Result<Seq<Result<u32, MyErr>>, MyErr>",
        type_args=[seq_of_result, err_ty],
        variants=[VariantInfo("Ok", seq_of_result),
                  VariantInfo("Err", err_ty)],
    )
    expr_outer = build_equal_expr(outer, "r1", "r2", default_policy())
    check("Result<Seq<Result<…>>, _> with errs_equivalent",
          expr_outer,
          ["(r1 is Ok) == (r2 is Ok)",
           "r1->Ok_0.len() == r2->Ok_0.len()",
           "forall|i: int|"],
          forbidden_substrs=["r1->Err_0", "r1->Ok_0[i]->Err_0"])

    # Struct with field of type Result — STRUCT branch recurses field-by-field.
    from spec_determinism.extract.types import FieldInfo
    struct_with_result = TypeInfo(
        TypeKind.STRUCT, "Holder",
        fields=[FieldInfo("payload", result_u32_err)],
    )
    expr_struct = build_equal_expr(struct_with_result, "h1", "h2",
                                   default_policy())
    check("Struct with Result field collapses Err",
          expr_struct,
          ["h1.payload", "h2.payload", "is Ok"],
          forbidden_substrs=["h1.payload->Err_0"])

    # _contains_result helper sanity
    assert _contains_result(result_u32_err) is True, "Result detected"
    assert _contains_result(seq_of_result) is True, "Seq<Result> detected"
    assert _contains_result(map_of_result) is True, "Map<_, Result> detected"
    assert _contains_result(int_ty) is False, "int has no Result"
    assert _contains_result(seq_u32) is False, "Seq<u32> has no Result"
    assert _contains_result(struct_with_result) is True, "Struct with field"

    # _container_needs_elementwise gated by policy.
    assert _container_needs_elementwise(result_u32_err, default_policy()) is True
    assert _container_needs_elementwise(
        result_u32_err, EqualPolicy(errs_equivalent=False)) is False

    # Self-referential type — must not infinite-loop in _contains_result.
    self_ref = TypeInfo(TypeKind.STRUCT, "Self")
    self_ref.fields = [FieldInfo("next", self_ref)]
    assert _contains_result(self_ref) is False, "self-ref returns False"

    # --- PR-F fixtures: Tracked<T> / Ghost<T> / PointsTo<V> equality ---
    bool_ty = TypeInfo(TypeKind.BOOL, "bool")
    usize_ty = TypeInfo(TypeKind.USIZE, "usize")

    tracked_u32 = TypeInfo(TypeKind.TRACKED, "Tracked<u32>",
                           type_args=[u32_ty])
    ghost_seq_u32 = TypeInfo(TypeKind.GHOST, "Ghost<Seq<u32>>",
                             type_args=[seq_u32])
    points_to_u32 = TypeInfo(TypeKind.POINTS_TO, "PointsTo<u32>",
                             type_args=[u32_ty])

    expr_tracked = build_equal_expr(tracked_u32, "t1", "t2", default_policy())
    check("Tracked<u32> compares through @",
          expr_tracked, ["(t1)@", "(t2)@"])

    expr_ghost = build_equal_expr(ghost_seq_u32, "g1", "g2", default_policy())
    check("Ghost<Seq<u32>> compares through @ then raw == on Seq",
          expr_ghost, ["(g1)@", "(g2)@"])

    expr_pt = build_equal_expr(points_to_u32, "p1", "p2", default_policy())
    check("PointsTo<u32> emits is_init/addr/value clauses",
          expr_pt,
          ["(p1).is_init() == (p2).is_init()",
           "(p1).addr() == (p2).addr()",
           "(p1).is_init() ==> (",
           "(p1).value()", "(p2).value()"])

    # Ghost<Result<u32, MyErr>> — PR-F + PR-G interaction: policy must
    # still collapse the Err side through the wrapper.
    ghost_result = TypeInfo(TypeKind.GHOST, "Ghost<Result<u32, MyErr>>",
                            type_args=[result_u32_err])
    expr_gr = build_equal_expr(ghost_result, "g1", "g2", default_policy())
    check("Ghost<Result<…>> with errs_equivalent collapses Err inside",
          expr_gr,
          ["(g1)@ is Ok) == ((g2)@ is Ok)", "Ok_0"],
          forbidden_substrs=["Err_0"])  # err collapsed

    # PR-F + PR-G: Tracked<Seq<Result<u32, MyErr>>> should yield forall lift.
    tracked_seq_result = TypeInfo(
        TypeKind.TRACKED, "Tracked<Seq<Result<u32, MyErr>>>",
        type_args=[seq_of_result])
    expr_tsr = build_equal_expr(tracked_seq_result, "t1", "t2",
                                default_policy())
    check("Tracked<Seq<Result<…>>> projects + elementwise lift",
          expr_tsr,
          ["(t1)@", "(t2)@", "forall|i: int|", "is Ok"],
          forbidden_substrs=["Err_0"])

    # --- Bug A: struct-form enum with field name shared across variants.
    # Verus refuses to auto-generate ``arrow_v`` when ``v`` is not unique
    # across all variants. The struct-form branch must detect this and
    # fall back to whole-variant structural equality for variants that
    # contain any ambiguous field.
    payload_ty = TypeInfo(TypeKind.SEQ, "Seq<u8>", type_args=[u8_ty])
    sr_inner = TypeInfo(TypeKind.STRUCT, "CMessage::SetRequest",
                        fields=[FieldInfo("v", payload_ty),
                                FieldInfo("k", u32_ty)])
    rep_inner = TypeInfo(TypeKind.STRUCT, "CMessage::Reply",
                         fields=[FieldInfo("v", payload_ty),
                                 FieldInfo("rk", u32_ty)])
    del_inner = TypeInfo(TypeKind.STRUCT, "CMessage::Delegate",
                         fields=[FieldInfo("h", u32_ty)])
    cmessage_ty = TypeInfo(
        TypeKind.ENUM, "CMessage",
        variants=[
            VariantInfo("SetRequest", sr_inner, struct_form=True),
            VariantInfo("Reply", rep_inner, struct_form=True),
            VariantInfo("Delegate", del_inner, struct_form=True),
        ],
    )
    assert cmessage_ty.ambiguous_struct_variant_fields() == {"v"}
    expr_cmsg = build_equal_expr(cmessage_ty, "lhs", "rhs", default_policy())
    # ambiguous-field variants must NOT emit ``->v`` accessors anywhere
    check("CMessage ambiguous `v` falls back to whole-variant equality",
          expr_cmsg,
          ["(lhs is SetRequest) ==> (lhs == rhs)",
           "(lhs is Reply) ==> (lhs == rhs)",
           # Delegate has only ``h`` (unambiguous) — keeps per-field form
           "(lhs is Delegate) ==> ((lhs->h == rhs->h))"],
          forbidden_substrs=["lhs->v", "rhs->v"])

    # An enum whose struct-form fields are all unique keeps per-field form.
    a_inner = TypeInfo(TypeKind.STRUCT, "Msg::A",
                       fields=[FieldInfo("a", u32_ty)])
    b_inner = TypeInfo(TypeKind.STRUCT, "Msg::B",
                       fields=[FieldInfo("b", u32_ty)])
    msg_ty = TypeInfo(
        TypeKind.ENUM, "Msg",
        variants=[
            VariantInfo("A", a_inner, struct_form=True),
            VariantInfo("B", b_inner, struct_form=True),
        ],
    )
    assert msg_ty.ambiguous_struct_variant_fields() == set()
    expr_msg = build_equal_expr(msg_ty, "lhs", "rhs", default_policy())
    check("Msg unambiguous struct-form keeps per-field accessors",
          expr_msg,
          ["lhs->a == rhs->a", "lhs->b == rhs->b"],
          forbidden_substrs=["(lhs is A) ==> (lhs == rhs)"])

    # A2 regression — _strip_unary_deref must preserve binary `*` (multiplication)
    # while still rewriting genuine `*p` derefs. Pre-fix, gen_det stripped `*`
    # from `4 * va_range.len`, producing the unparseable `4 va_range.len`.
    got = _strip_unary_deref("4 * va_range.len", "va_range", "va_range")
    if got != "4 * va_range.len":
        failures.append(
            f"A2: _strip_unary_deref must preserve binary `*` in '4 * va_range.len'; "
            f"got {got!r}"
        )
    got = _strip_unary_deref("(*va_range).len", "va_range", "va_range")
    if got != "(va_range).len":
        failures.append(
            f"A2: _strip_unary_deref must strip unary `*` at expression start "
            f"in '(*va_range).len'; got {got!r}"
        )
    got = _strip_unary_deref("foo(*va_range)", "va_range", "va_range")
    if got != "foo(va_range)":
        failures.append(
            f"A2: _strip_unary_deref must strip unary `*` after `(`; "
            f"got {got!r}"
        )
    got = _strip_unary_deref("x + *va_range", "va_range", "va_range")
    if got != "x + va_range":
        failures.append(
            f"A2: _strip_unary_deref must strip unary `*` after binary `+`; "
            f"got {got!r}"
        )
    got = _strip_unary_deref("len * 4 + va_range", "va_range", "va_range")
    if got != "len * 4 + va_range":
        failures.append(
            f"A2: _strip_unary_deref must not corrupt unrelated `*` operators; "
            f"got {got!r}"
        )

    # A3 regression — `Self` in a trait-fn ensures must be replaced by the
    # synthetic `__DetSelf` generic, and `__DetSelf` must be bounded by the
    # trait name (so `Self::method` calls resolve under verus).
    src_trait = (
        "verus! {\n"
        "pub trait KeyTrait: Sized {\n"
        "    spec fn zero_spec() -> Self;\n"
        "    fn zero() -> (z: Self)\n"
        "        ensures z == Self::zero_spec()\n"
        "    { Self::zero_spec() }\n"
        "}\n"
        "}\n"
    )
    from spec_determinism.extract.extractor import extract_spec
    spec_trait = extract_spec(src_trait, "zero", type_sources=[])
    ds_trait = build_det_check_spec(spec_trait)
    tpl = ds_trait.det_check_template
    if re.search(r'\bSelf\b', tpl):
        failures.append(
            f"A3: rendered template must not contain bare 'Self' after substitution; "
            f"template head:\n{tpl[:400]}"
        )
    if "__DetSelf: KeyTrait" not in tpl:
        failures.append(
            f"A3: synthesized fn must bound __DetSelf by trait name 'KeyTrait'; "
            f"template head:\n{tpl[:400]}"
        )

    if failures:
        print(f"\n{len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All gen_det self-tests passed.")
    return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        raise SystemExit(_run_self_tests())
    print("usage: python -m spec_determinism.codegen.gen_det test")
    raise SystemExit(2)
