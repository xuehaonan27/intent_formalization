"""
Module 4: binary_search — Type-Guided Witness Narrowing

Core data structure: AssumeTree — a tree where each node holds one assume.
Same-node refinement replaces; different nodes accumulate.

Decorator-based strategy registry. Each strategy is recursive.
LLM fallback for unknown types.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from .types import (
    TypeKind, TypeInfo, FieldInfo, Param,
    FunctionSpec, Assume, VerifyResult, Witness,
    Symbol, DetCheckSpec,
)
from .gen_det import render_template
from .verify import VerusRunner

logger = logging.getLogger(__name__)


# ===========================================================================
# AssumeTree
# ===========================================================================

@dataclass
class AssumeNode:
    """
    A node in the assume tree.
    
    Each node represents one narrowing dimension for a variable/field.
    Its `assume` is the current constraint at this level.
    Refinement (e.g. [0,8] → [3,4] → 3) replaces `assume` in-place.
    Children represent sub-structure (fields, inner types, elements).
    
    Example tree for `alloc(&mut self) -> Result<usize, Error>`:
    
      root
      ├── pre_self_ (Bitmap)
      │   └── @view (BitmapView)
      │       ├── num_bits: assume(== 8)
      │       └── set_bits: assume(== Set::empty())
      ├── r1 (Result)
      │   ├── [variant]: assume(r1 is Ok)
      │   └── Ok_0 (usize): assume(== 0)
      └── r2 (Result)
          ├── [variant]: assume(r2 is Ok)
          └── Ok_0 (usize): assume(== 1)
    """
    key: str                                    # node identifier within parent
    assume: Optional[Assume] = None             # current constraint (replaced on refinement)
    children: dict[str, "AssumeNode"] = field(default_factory=dict)

    def get_or_create(self, key: str) -> "AssumeNode":
        """Get or create a child node."""
        if key not in self.children:
            self.children[key] = AssumeNode(key=key)
        return self.children[key]

    def collect_assumes(self) -> list[Assume]:
        """DFS: collect all non-None assumes from this subtree."""
        result = []
        if self.assume is not None:
            result.append(self.assume)
        for child in self.children.values():
            result.extend(child.collect_assumes())
        return result

    def __repr__(self):
        parts = [f"AssumeNode({self.key!r}"]
        if self.assume:
            parts.append(f", assume={self.assume.expression!r}")
        if self.children:
            parts.append(f", children={list(self.children.keys())}")
        return "".join(parts) + ")"


# ===========================================================================
# Strategy registry
# ===========================================================================

_registry: dict[TypeKind, Callable] = {}


def strategy_for(*type_kinds: TypeKind):
    """Register a narrowing strategy for one or more type kinds."""
    def decorator(fn):
        for kind in type_kinds:
            _registry[kind] = fn
        return fn
    return decorator


def narrow(ty: TypeInfo, var: str, node: "AssumeNode", ctx: "SearchContext"):
    """Dispatch to the registered strategy. Each strategy gets its own tree node."""
    handler = _registry.get(ty.kind, _llm_fallback)
    handler(ty, var, node, ctx)


# ===========================================================================
# Integer range helpers
# ===========================================================================

_SMALL_UNSIGNED = (0, 17)      # [0, 16] inclusive
_SMALL_SIGNED = (-8, 9)       # [-8, 8] inclusive

_FULL_RANGE: dict[TypeKind, tuple[int, int]] = {
    TypeKind.U8:    (0, 256),
    TypeKind.U16:   (0, 65536),
    TypeKind.U32:   (0, 2**32),
    TypeKind.U64:   (0, 2**64),
    TypeKind.USIZE: (0, 2**64),
    TypeKind.I8:    (-128, 128),
    TypeKind.I16:   (-32768, 32768),
    TypeKind.I32:   (-(2**31), 2**31),
    TypeKind.I64:   (-(2**63), 2**63),
    TypeKind.ISIZE: (-(2**63), 2**63),
    TypeKind.INT:   (-(2**31), 2**31),
}


def _int_range(ty: TypeInfo) -> tuple[int, int]:
    """Small initial range (lo inclusive, hi exclusive)."""
    if ty.kind in (TypeKind.U8, TypeKind.U16, TypeKind.U32,
                   TypeKind.U64, TypeKind.USIZE):
        return _SMALL_UNSIGNED
    return _SMALL_SIGNED


def _full_int_range(ty: TypeInfo) -> tuple[int, int]:
    return _FULL_RANGE.get(ty.kind, (-256, 256))


# ===========================================================================
# Concrete strategies
# ===========================================================================

@strategy_for(TypeKind.RESULT)
def narrow_result(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow Result<T, E>: try Ok first, then Err if Ok PASS."""
    variant_node = node.get_or_create("variant")
    ok_assume = Assume(var, f"{var} is Ok", "variant: Ok")
    if ctx.test_and_set(variant_node, ok_assume):
        # FAIL → nondeterminism with this var as Ok. Narrow Ok inner.
        if ty.type_args:
            inner_node = node.get_or_create("Ok_0")
            narrow(ty.type_args[0], f"{var}->Ok_0", inner_node, ctx)
    else:
        # PASS → Ok doesn't exhibit nondeterminism here. Try Err.
        err_assume = Assume(var, f"{var} is Err", "variant: Err")
        if ctx.test_and_set(variant_node, err_assume):
            if len(ty.type_args) > 1:
                inner_node = node.get_or_create("Err_0")
                narrow(ty.type_args[1], f"{var}->Err_0", inner_node, ctx)


@strategy_for(TypeKind.OPTION)
def narrow_option(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow Option<T>: try Some first, then None if Some PASS."""
    variant_node = node.get_or_create("variant")
    some_assume = Assume(var, f"{var} is Some", "variant: Some")
    if ctx.test_and_set(variant_node, some_assume):
        if ty.type_args:
            inner_node = node.get_or_create("Some_0")
            narrow(ty.type_args[0], f"{var}->Some_0", inner_node, ctx)
    else:
        # PASS → Some doesn't exhibit nondeterminism. Try None.
        none_assume = Assume(var, f"{var} is None", "variant: None")
        ctx.test_and_set(variant_node, none_assume)


@strategy_for(TypeKind.ENUM)
def narrow_enum(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow a general enum: try each variant."""
    variant_node = node.get_or_create("variant")
    for variant in ty.variants:
        assume = Assume(var, f"{var} is {variant.name}", f"variant: {variant.name}")
        if ctx.test_and_set(variant_node, assume):
            if variant.inner:
                inner_node = node.get_or_create(f"{variant.name}_0")
                narrow(variant.inner, f"{var}->{variant.name}_0", inner_node, ctx)
            return


@strategy_for(TypeKind.STRUCT)
def narrow_struct(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow a struct: recurse into each field."""
    view = ty.spec_view or ty
    accessor = f"{var}@" if ty.spec_view else var

    for fld in view.fields:
        field_node = node.get_or_create(fld.name)
        narrow(fld.type, f"{accessor}.{fld.name}", field_node, ctx)


@strategy_for(
    TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
    TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
    TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
)
def narrow_integer(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow integer: small range first, then full type range, then bisect."""
    small_lo, small_hi = _int_range(ty)
    hi_inclusive = small_hi - 1
    small_assume = Assume(var, f"{var} >= {small_lo} && {var} <= {hi_inclusive}",
                          f"small range: [{small_lo}, {hi_inclusive}]")
    if ctx.test_and_set(node, small_assume):
        _bisect_range(var, small_lo, hi_inclusive, node, ctx)
        return

    # Small range PASS — rare case, just bisect full type range directly
    full_lo, full_hi = _full_int_range(ty)
    full_hi_inclusive = full_hi - 1
    full_assume = Assume(var, f"{var} >= {full_lo} && {var} <= {full_hi_inclusive}",
                         f"full range: [{full_lo}, {full_hi_inclusive}]")
    if ctx.test_and_set(node, full_assume):
        _bisect_range(var, full_lo, full_hi_inclusive, node, ctx)


def _bisect_range(var: str, lo: int, hi: int, node: AssumeNode, ctx: "SearchContext") -> int | None:
    """Recursive bisection on [lo, hi] inclusive. Returns the exact value found, or None."""
    if lo == hi:
        ctx.test_and_set(node, Assume(var, f"{var} == {lo}", f"exact: {lo}"))
        return lo

    mid = (lo + hi) // 2
    if lo == mid:
        left = Assume(var, f"{var} == {lo}", f"exact: {lo}")
    else:
        left = Assume(var, f"{var} >= {lo} && {var} <= {mid}", f"range: [{lo}, {mid}]")

    if ctx.test_and_set(node, left):
        if lo == mid:
            return lo  # exact value already confirmed, skip redundant recursion
        return _bisect_range(var, lo, mid, node, ctx)
    else:
        return _bisect_range(var, mid + 1, hi, node, ctx)


def _narrow_length(var_len_expr: str, node: AssumeNode, ctx: "SearchContext",
                   max_bound: int = 2 ** 20) -> int | None:
    """
    Narrow collection length: exact probes for small values [0..4],
    then bisect the full range if needed.

    Returns the exact length found, or None.
    """
    # Phase 1: exact probes for common small values
    EXACT_LIMIT = 4
    for n in range(EXACT_LIMIT + 1):
        assume = Assume(var_len_expr, f"{var_len_expr} == {n}", f"len: {n}")
        if ctx.test_and_set(node, assume):
            return n

    # Phase 2: not in [0..4], bisect the full range
    lo = EXACT_LIMIT + 1
    full_assume = Assume(var_len_expr,
                         f"{var_len_expr} >= {lo} && {var_len_expr} <= {max_bound}",
                         f"len range: [{lo}, {max_bound}]")
    if ctx.test_and_set(node, full_assume):
        return _bisect_range(var_len_expr, lo, max_bound, node, ctx)

    return None


@strategy_for(TypeKind.BOOL)
def narrow_bool(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    assume_true = Assume(var, f"{var} == true", "bool: true")
    if not ctx.test_and_set(node, assume_true):
        ctx.test_and_set(node, Assume(var, f"{var} == false", "bool: false"))


@strategy_for(TypeKind.SET)
def narrow_set(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    elem_ty = ty.type_args[0] if ty.type_args else TypeInfo(kind=TypeKind.INT, name="int")
    elem_ty_name = elem_ty.name
    empty_expr = f"Set::<{elem_ty_name}>::empty()"

    # Verus `Set::<T>::len()` returns 0 for BOTH empty and infinite sets, so
    # len-first probing is ambiguous. Instead, split into two disjoint finite
    # cases — `s == empty` or `s.len() > 0` — and skip the "infinite set"
    # witness (Verus admits it, but it carries no useful signal for the
    # developer and cannot be printed concretely).

    # Case 1: empty set
    empty = Assume(var, f"{var} == {empty_expr}", "set: empty")
    if ctx.test_and_set(node, empty):
        return

    # Case 2: finite non-empty. Establish len > 0 as a precondition; once that
    # sticks, len() is the true cardinality and we can enumerate elements.
    pos_len = Assume(var, f"{var}.len() > 0", "set: non-empty (finite)")
    if not ctx.test_and_set(node, pos_len):
        # Spec admits neither empty nor any finite non-empty witness — the
        # only remaining nondeterminism is via infinite sets, which we don't
        # try to pin down concretely.
        return

    # Now narrow length. _narrow_length probes from small upward; its results
    # are meaningful because we've already committed to len() > 0.
    len_node = node.get_or_create("len")
    length = _narrow_length(f"{var}.len()", len_node, ctx)
    if length is None or length == 0:
        return

    # Find elements via contains() probing, skipping already-found values
    elements: list[int] = []
    for i in range(length):
        val = _bisect_set_element(var, elem_ty, node, i, ctx,
                                  skip_vals=frozenset(elements))
        if val is not None:
            elements.append(val)
        else:
            break

    # One final confirmation with full set expression; clears intermediate
    # children only if the confirmation sticks.
    if elements:
        set_expr = _build_set_expr(elem_ty_name, sorted(elements))
        desc = ", ".join(str(e) for e in sorted(elements))
        if ctx.test_and_set(node, Assume(var, f"{var} == {set_expr}", f"set: {{{desc}}}")):
            node.children.clear()  # len + elem children subsumed by full set expr


def _build_set_expr(elem_ty_name: str, elements: list[int]) -> str:
    """Build a Verus Set literal from a list of concrete elements."""
    expr = f"Set::<{elem_ty_name}>::empty()"
    for e in elements:
        expr += f".insert({e})"
    return expr


def _bisect_set_element(
    var: str,
    elem_ty: TypeInfo,
    parent_node: AssumeNode,
    elem_idx: int,
    ctx: "SearchContext",
    skip_vals: frozenset[int] = frozenset(),
) -> int | None:
    """Find the next element of a set via contains() probing, skipping known elements."""
    elem_node = parent_node.get_or_create(f"elem_{elem_idx}")

    small_lo, small_hi = _int_range(elem_ty)
    found_val = _bisect_contains(var, small_lo, small_hi - 1, elem_node, ctx, skip_vals)

    if found_val is None:
        full_lo, full_hi = _full_int_range(elem_ty)
        found_val = _bisect_contains(var, full_lo, full_hi - 1, elem_node, ctx, skip_vals)

    return found_val


def _bisect_contains(var: str, lo: int, hi: int, node: AssumeNode, ctx: "SearchContext",
                     skip: frozenset[int] = frozenset()) -> int | None:
    """Find a value that the set contains via linear probing, skipping known elements."""
    for val in range(lo, min(lo + 17, hi + 1)):
        if val in skip:
            continue
        assume = Assume(var, f"{var}.contains({val})", f"contains {val}")
        if ctx.test_and_set(node, assume):
            return val
    return None


@strategy_for(TypeKind.SEQ)
def narrow_seq(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow Seq<T>: length first, then elements."""
    len_node = node.get_or_create("len")
    length = _narrow_length(f"{var}.len()", len_node, ctx)

    if length is None:
        return

    if ty.type_args and length > 0:
        for i in range(length):
            elem_node = node.get_or_create(f"elem_{i}")
            narrow(ty.type_args[0], f"{var}[{i}]", elem_node, ctx)


@strategy_for(TypeKind.UNIT)
def narrow_unit(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    pass


_STR_CANDIDATES = ('""', '"string 1"', '"string 2"')


@strategy_for(TypeKind.STR)
def narrow_str(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow a string: try the three allowed literal values.

    To keep the search space tiny, we assume every string in the spec can
    only take one of `""`, `"string 1"`, `"string 2"`. This is intentionally
    coarse — strings are typically either ignored entirely (via custom
    equality) or distinguished by identity, not by content.
    """
    for lit in _STR_CANDIDATES:
        assume = Assume(var, f'{var} == {lit}', f'str: {lit}')
        if ctx.test_and_set(node, assume):
            return


def _llm_fallback(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """LLM fallback for unknown types."""
    logger.warning(f"No strategy for {ty.kind}:{ty.name} — using LLM fallback")
    if ctx.llm_client:
        prompt = (
            f"Given a Verus type `{ty.name}` and variable `{var}`, "
            f"suggest one assume() constraint to narrow its value. "
            f"Current constraints: {[a.expression for a in ctx.tree.collect_assumes()]}. "
            f"Return ONLY the Verus expression."
        )
        response = ctx.llm_client.chat(
            system_prompt="You are a Verus verification expert.",
            user_prompt=prompt,
        )
        expr = response.content.strip().strip("`")
        ctx.test_and_set(node, Assume(var, expr, f"LLM-suggested for {ty.name}"))
    else:
        logger.error(f"No LLM client and no strategy for type {ty.name}")


# ===========================================================================
# SearchContext
# ===========================================================================

class SearchContext:
    """
    Holds search state. Operates on DetCheckSpec (template + symbols).
    """

    def __init__(self, det_spec: DetCheckSpec, runner: VerusRunner, llm_client=None):
        self.det_spec = det_spec
        self.runner = runner
        self.llm_client = llm_client
        self.tree = AssumeNode(key="root")
        self.trace: list[dict] = []
        self._round = 0

    def test_and_set(self, node: AssumeNode, assume: Assume, phase: str = "") -> bool:
        """
        Sets node.assume = assume, renders template with ALL tree assumes,
        runs Verus. FAIL → keep. PASS → revert.
        """
        old_assume = node.assume
        node.assume = assume

        all_assumes = self.tree.collect_assumes()
        code = render_template(self.det_spec, all_assumes)
        fn_name = self.det_spec.check_fn_name or f"det_{self.det_spec.function}"
        result = self.runner.check(code, fn_name)

        self._round += 1
        p = phase or "search"
        self.trace.append({
            "round": self._round,
            "phase": p,
            "node_key": node.key,
            "assumes": [a.expression for a in all_assumes],
            "new_assume": assume.expression,
            "result": result.status,
            "description": assume.description,
        })
        logger.info(f"R{self._round} [{p}] {node.key}: {assume.expression} → {result.status}")

        if result.status == "fail":
            # Keep: node.assume already set
            return True
        else:
            # Revert
            node.assume = old_assume
            if result.status == "pass":
                return False
            elif result.status == "timeout":
                logger.warning(f"Timeout on {assume.expression}")
                return False
            else:
                logger.error(f"Error: {result.stderr[:200]}")
                return False


# ===========================================================================
# Driver
# ===========================================================================

def binary_search(det_spec: DetCheckSpec, runner: VerusRunner, llm_client=None) -> Witness:
    """Run full binary search using a DetCheckSpec (template + symbol table)."""
    ctx = SearchContext(det_spec, runner, llm_client)

    # R0: initial determinism check (no assumes)
    code = render_template(det_spec, [])
    fn_name = det_spec.check_fn_name or f"det_{det_spec.function}"
    r0 = runner.check(code, fn_name)
    ctx.trace.append({
        "round": 0, "phase": "initial", "node_key": "root",
        "assumes": [], "new_assume": None,
        "result": r0.status, "description": "full determinism check",
    })

    if r0.status == "pass":
        logger.info(f"{det_spec.function}: spec is deterministic")
        return Witness(function=det_spec.function, trace=ctx.trace)

    if r0.status != "fail":
        # Smoke-test failure: the template itself didn't even parse/typecheck.
        # Surface the stderr prominently — this is almost always a gen_det bug,
        # not a real spec issue.
        logger.error(
            f"{det_spec.function}: SMOKE TEST FAILED — initial check returned "
            f"{r0.status!r}. This usually means the generated det-check template "
            f"is malformed (syntax/type error), not that the spec is indeterminate.\n"
            f"Verus stderr:\n{r0.stderr[:4000]}"
        )
        ctx.trace[-1]["smoke_test_error"] = r0.stderr[:4000]
        return Witness(function=det_spec.function, trace=ctx.trace)

    logger.info(f"{det_spec.function}: nondeterminism detected, starting binary search")

    # Narrow symbols in order (already sorted: input → output_simple → output_compound)
    for sym in det_spec.symbols:
        sym_node = ctx.tree.get_or_create(sym.name)
        narrow(sym.type, sym.name, sym_node, ctx)

    # Final step: for each pair of output variables (r1/r2, post1_X/post2_X),
    # try to add an explicit `!=` / `@ != @` assume. If this FAILs, we have a
    # strong witness: the two outputs are provably distinct under current
    # assumes. If it PASSes, the two outputs must be equal — narrowing below
    # has already pinned them down, so we leave it alone.
    _add_distinctness_witnesses(ctx, det_spec)

    return Witness(
        function=det_spec.function,
        assumes=ctx.tree.collect_assumes(),
        trace=ctx.trace,
    )


def _add_distinctness_witnesses(ctx: "SearchContext", det_spec: DetCheckSpec):
    """Final witness step: try to assume `!{fn_name}_equal(...)`. If FAIL, the
    spec provably admits two non-equivalent output tuples, i.e. the generated
    witness is a strong demonstration of nondeterminism.

    This is a single-shot check against the same user-replaceable equal fn
    used by the conclusion, so changing the equality policy only requires
    editing `{fn_name}_equal`.
    """
    if not det_spec.equal_fn_name:
        return
    call_args = []
    for pair in det_spec.equal_arg_pairs:
        call_args.append(pair["lhs"])
        call_args.append(pair["rhs"])
    call = f"{det_spec.equal_fn_name}({', '.join(call_args)})"
    node = ctx.tree.get_or_create("tuple_not_equal")
    assume = Assume(
        "tuple",
        f"!{call}",
        f"distinctness: output tuple not equal under {det_spec.equal_fn_name}",
    )
    ctx.test_and_set(node, assume, phase="distinct")
