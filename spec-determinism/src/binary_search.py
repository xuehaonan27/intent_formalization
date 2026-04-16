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
)
from .gen_det import generate_det_check
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
    """Narrow Result<T, E>: binary choice Ok vs Err, then recurse into inner."""
    variant_node = node.get_or_create("variant")
    ok_assume = Assume(var, f"{var} is Ok", "variant: Ok")
    if ctx.test_and_set(variant_node, ok_assume):
        # FAIL → nondeterminism within Ok. Narrow inner.
        if ty.type_args:
            inner_node = node.get_or_create("Ok_0")
            narrow(ty.type_args[0], f"{var}->Ok_0", inner_node, ctx)
    else:
        # PASS → cross-variant (Ok vs Err). Liveness gap.
        pass


@strategy_for(TypeKind.OPTION)
def narrow_option(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow Option<T>: binary choice Some vs None."""
    variant_node = node.get_or_create("variant")
    some_assume = Assume(var, f"{var} is Some", "variant: Some")
    if ctx.test_and_set(variant_node, some_assume):
        if ty.type_args:
            inner_node = node.get_or_create("Some_0")
            narrow(ty.type_args[0], f"{var}->Some_0", inner_node, ctx)
    else:
        pass


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
    """Narrow integer: small range first, then bisect."""
    small_lo, small_hi = _int_range(ty)
    hi_inclusive = small_hi - 1
    small_assume = Assume(var, f"{var} >= {small_lo} && {var} <= {hi_inclusive}",
                          f"small range: [{small_lo}, {hi_inclusive}]")
    if ctx.test_and_set(node, small_assume):
        # FAIL → nondeterminism within small range, bisect it
        _bisect_range(var, small_lo, hi_inclusive, node, ctx)
    else:
        # PASS → not in small range. Try full type range.
        full_lo, full_hi = _full_int_range(ty)
        full_hi_inclusive = full_hi - 1
        full_assume = Assume(var, f"{var} >= {full_lo} && {var} <= {full_hi_inclusive}",
                             f"full range: [{full_lo}, {full_hi_inclusive}]")
        if ctx.test_and_set(node, full_assume):
            # FAIL → nondeterminism in full range (but outside small range), bisect
            _bisect_range(var, full_lo, full_hi_inclusive, node, ctx)
        else:
            # PASS → truly not a nondeterminism source. Skip.
            pass


def _bisect_range(var: str, lo: int, hi: int, node: AssumeNode, ctx: "SearchContext"):
    """Recursive bisection on [lo, hi] inclusive. Refines node.assume in-place."""
    if lo == hi:
        ctx.test_and_set(node, Assume(var, f"{var} == {lo}", f"exact: {lo}"))
        return

    mid = (lo + hi) // 2
    if lo == mid:
        left = Assume(var, f"{var} == {lo}", f"exact: {lo}")
    else:
        left = Assume(var, f"{var} >= {lo} && {var} <= {mid}", f"range: [{lo}, {mid}]")

    if ctx.test_and_set(node, left):
        _bisect_range(var, lo, mid, node, ctx)
    else:
        _bisect_range(var, mid + 1, hi, node, ctx)


@strategy_for(TypeKind.BOOL)
def narrow_bool(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    assume_true = Assume(var, f"{var} == true", "bool: true")
    if not ctx.test_and_set(node, assume_true):
        ctx.test_and_set(node, Assume(var, f"{var} == false", "bool: false"))


@strategy_for(TypeKind.SET)
def narrow_set(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    elem_ty_name = ty.type_args[0].name if ty.type_args else "int"

    # Try empty
    empty = Assume(var, f"{var} == Set::<{elem_ty_name}>::empty()", "set: empty")
    if ctx.test_and_set(node, empty):
        return

    # Try sizes via bisection on length
    len_node = node.get_or_create("len")
    for size in [1, 2, 3, 4]:
        assume = Assume(var, f"{var}.len() == {size}", f"set: len={size}")
        if ctx.test_and_set(len_node, assume):
            # Narrow elements
            if ty.type_args and size <= 2:
                for i in range(size):
                    elem_node = node.get_or_create(f"elem_{i}")
                    narrow(ty.type_args[0], f"/* {var}[{i}] */", elem_node, ctx)
            return


@strategy_for(TypeKind.SEQ)
def narrow_seq(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    # Length first
    len_node = node.get_or_create("len")
    for length in [0, 1, 2, 3, 4]:
        assume = Assume(var, f"{var}.len() == {length}", f"seq: len={length}")
        if ctx.test_and_set(len_node, assume):
            # Narrow elements
            if ty.type_args:
                for i in range(length):
                    elem_node = node.get_or_create(f"elem_{i}")
                    narrow(ty.type_args[0], f"{var}[{i}]", elem_node, ctx)
            return


@strategy_for(TypeKind.UNIT)
def narrow_unit(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    pass


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
    Holds search state: the assume tree, Verus runner, trace log.
    
    All strategies call `test_and_set(node, assume)` which:
    1. Temporarily sets node.assume = assume
    2. Collects all assumes from tree
    3. Runs Verus
    4. On FAIL: keeps the assume (refinement in-place). Returns True.
    5. On PASS: reverts node.assume. Returns False.
    """

    def __init__(self, spec: FunctionSpec, runner: VerusRunner, llm_client=None):
        self.spec = spec
        self.runner = runner
        self.llm_client = llm_client
        self.tree = AssumeNode(key="root")
        self.trace: list[dict] = []
        self._round = 0

    def test_and_set(self, node: AssumeNode, assume: Assume, phase: str = "") -> bool:
        """
        The single operation for all strategies.
        
        Sets node.assume = assume, runs Verus with ALL current tree assumes.
        FAIL → keep (return True). PASS → revert (return False).
        """
        old_assume = node.assume
        node.assume = assume

        all_assumes = self.tree.collect_assumes()
        code = generate_det_check(self.spec, extra_assumes=all_assumes)
        fn_name = f"det_{self.spec.name}"
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

def binary_search(spec: FunctionSpec, runner: VerusRunner, llm_client=None) -> Witness:
    """Run full binary search: input first, then output."""
    ctx = SearchContext(spec, runner, llm_client)

    # R0: initial determinism check
    code = generate_det_check(spec)
    fn_name = f"det_{spec.name}"
    r0 = runner.check(code, fn_name)
    ctx.trace.append({
        "round": 0, "phase": "initial", "node_key": "root",
        "assumes": [], "new_assume": None,
        "result": r0.status, "description": "full determinism check",
    })

    if r0.status == "pass":
        logger.info(f"{spec.name}: spec is deterministic")
        return Witness(function=spec.name, trace=ctx.trace)

    if r0.status != "fail":
        logger.error(f"{spec.name}: initial check returned {r0.status}")
        return Witness(function=spec.name, trace=ctx.trace)

    logger.info(f"{spec.name}: nondeterminism detected, starting binary search")

    # Phase 1: Narrow inputs
    for param in spec.params:
        var = _input_var_name(param)
        param_node = ctx.tree.get_or_create(var)
        narrow(param.type, var, param_node, ctx)

    # Phase 2: Narrow outputs — simple types first (enum/primitive), then compound (struct)
    simple_outputs = []  # Result, Option, Enum, bool, integers
    compound_outputs = []  # Struct, Set, Seq
    for out_name, out_type in spec.output_vars():
        if out_type.kind in (TypeKind.RESULT, TypeKind.OPTION, TypeKind.ENUM,
                             TypeKind.BOOL, TypeKind.UNIT,
                             TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
                             TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
                             TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64):
            simple_outputs.append((out_name, out_type))
        else:
            compound_outputs.append((out_name, out_type))

    for out_name, out_type in simple_outputs:
        _narrow_output_pair(ctx, out_type, out_name)
    for out_name, out_type in compound_outputs:
        _narrow_output_pair(ctx, out_type, out_name)

    return Witness(
        function=spec.name,
        assumes=ctx.tree.collect_assumes(),
        trace=ctx.trace,
    )


def _input_var_name(param: Param) -> str:
    base = "self_" if param.is_self else param.name
    return f"pre_{base}" if param.is_mut_ref else base


def _narrow_output_pair(ctx: SearchContext, ty: TypeInfo, base_name: str):
    """Narrow output pair (r1/r2 or post1/post2)."""
    if base_name == "result":
        name1, name2 = "r1", "r2"
    elif base_name.startswith("post_"):
        suffix = base_name[5:]
        name1, name2 = f"post1_{suffix}", f"post2_{suffix}"
    else:
        name1, name2 = f"{base_name}1", f"{base_name}2"

    out1_node = ctx.tree.get_or_create(name1)
    narrow(ty, name1, out1_node, ctx)
