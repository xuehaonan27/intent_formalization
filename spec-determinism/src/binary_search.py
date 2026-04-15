"""
Module 4: binary_search — Type-Guided Witness Narrowing

Decorator-based strategy registry + search driver.
Each type kind has its own narrowing function.
LLM fallback for unknown types.
"""

import logging
from typing import Callable, Generator, Optional

from .types import (
    TypeKind, TypeInfo, FieldInfo, Param,
    FunctionSpec, Assume, VerifyResult, Witness,
)
from .gen_det import generate_det_check
from .verify import VerusRunner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strategy registry (decorator-based)
# ---------------------------------------------------------------------------

_registry: dict[TypeKind, Callable] = {}


def strategy_for(*type_kinds: TypeKind):
    """Register a narrowing strategy for one or more type kinds."""
    def decorator(fn):
        for kind in type_kinds:
            _registry[kind] = fn
        return fn
    return decorator


def narrow(ty: TypeInfo, var: str, ctx: "SearchContext") -> Generator[Assume, None, None]:
    """Dispatch to the registered strategy for this type, or LLM fallback."""
    handler = _registry.get(ty.kind, _llm_fallback)
    yield from handler(ty, var, ctx)


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------

@strategy_for(TypeKind.RESULT)
def narrow_result(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow Result<T, E>: try Ok vs Err variants."""
    yield Assume(var, f"{var} is Ok", "variant: Ok")
    yield Assume(var, f"{var} is Err", "variant: Err")
    # If Ok, narrow inner value
    if ty.type_args:
        ok_ty = ty.type_args[0]
        yield from narrow(ok_ty, f"{var}->Ok_0", ctx)


@strategy_for(TypeKind.OPTION)
def narrow_option(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow Option<T>: try Some vs None."""
    yield Assume(var, f"{var} is Some", "variant: Some")
    yield Assume(var, f"{var} is None", "variant: None")
    if ty.type_args:
        inner_ty = ty.type_args[0]
        yield from narrow(inner_ty, f"{var}->Some_0", ctx)


@strategy_for(TypeKind.ENUM)
def narrow_enum(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow a general enum by trying each variant."""
    for variant in ty.variants:
        yield Assume(var, f"{var} is {variant.name}", f"variant: {variant.name}")
        if variant.inner:
            yield from narrow(variant.inner, f"{var}->{variant.name}_0", ctx)


@strategy_for(TypeKind.STRUCT)
def narrow_struct(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow a struct by iterating over fields."""
    # If type has a spec view (@), use that for field access
    view = ty.spec_view or ty
    accessor = f"{var}@" if ty.spec_view else var

    for field in view.fields:
        yield from narrow(field.type, f"{accessor}.{field.name}", ctx)


@strategy_for(
    TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
    TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
    TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
)
def narrow_integer(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow integer: range bisection then exact values."""
    # Common ranges to try
    ranges = [100, 10, 5]
    for bound in ranges:
        yield Assume(var, f"{var} < {bound}", f"range: [0, {bound})")

    # Common exact values
    for val in [0, 1, 8, 16, 32]:
        yield Assume(var, f"{var} == {val}", f"exact: {val}")


@strategy_for(TypeKind.BOOL)
def narrow_bool(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow bool: try true, then false."""
    yield Assume(var, f"{var} == true", "bool: true")
    yield Assume(var, f"{var} == false", "bool: false")


@strategy_for(TypeKind.SET)
def narrow_set(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow Set<T>: length first, then elements."""
    elem_ty_name = ty.type_args[0].name if ty.type_args else "int"
    yield Assume(var, f"{var} == Set::<{elem_ty_name}>::empty()", "set: empty")
    yield Assume(var, f"{var}.len() == 1", "set: len=1")
    yield Assume(var, f"{var}.len() == 2", "set: len=2")
    # If we know element type, try narrowing elements
    if ty.type_args:
        yield from narrow(ty.type_args[0], f"/* element of {var} */", ctx)


@strategy_for(TypeKind.SEQ)
def narrow_seq(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow Seq<T>: length first, then elements."""
    yield Assume(var, f"{var}.len() == 0", "seq: empty")
    yield Assume(var, f"{var}.len() == 1", "seq: len=1")
    yield Assume(var, f"{var}.len() == 2", "seq: len=2")
    if ty.type_args:
        yield Assume(var, f"{var}[0]", "seq: first element")
        yield from narrow(ty.type_args[0], f"{var}[0]", ctx)


@strategy_for(TypeKind.UNIT)
def narrow_unit(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Unit type: nothing to narrow."""
    return
    yield  # make it a generator


def _llm_fallback(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """LLM fallback for unknown types."""
    logger.warning(f"No strategy for {ty.kind}:{ty.name} — using LLM fallback")
    if ctx.llm_client:
        prompt = (
            f"Given a Verus type `{ty.name}` and variable `{var}`, "
            f"suggest one `assume()` constraint to narrow its value to a concrete instance. "
            f"Current constraints: {[a.expression for a in ctx.active_assumes]}. "
            f"Return ONLY the Verus expression for the assume."
        )
        response = ctx.llm_client.chat(
            system_prompt="You are a Verus verification expert.",
            user_prompt=prompt,
        )
        expr = response.content.strip().strip("`")
        yield Assume(var, expr, f"LLM-suggested for {ty.name}")
    else:
        logger.error(f"No LLM client and no strategy for type {ty.name}")
        return
        yield


# ---------------------------------------------------------------------------
# Search context and driver
# ---------------------------------------------------------------------------

class SearchContext:
    """Holds state during binary search."""

    def __init__(
        self,
        spec: FunctionSpec,
        runner: VerusRunner,
        llm_client=None,
    ):
        self.spec = spec
        self.runner = runner
        self.llm_client = llm_client
        self.active_assumes: list[Assume] = []
        self.trace: list[dict] = []
        self._round = 0

    def _record(self, phase: str, assume: Assume | None, result: VerifyResult):
        self._round += 1
        self.trace.append({
            "round": self._round,
            "phase": phase,
            "assumes": [a.expression for a in self.active_assumes],
            "new_assume": assume.expression if assume else None,
            "result": result.status,
            "description": assume.description if assume else "",
        })

    def try_assume(self, assume: Assume, phase: str) -> bool:
        """
        Add assume and check if nondeterminism persists.

        Returns True if FAIL (keep the assume), False if PASS (backtrack).
        """
        test_assumes = self.active_assumes + [assume]
        code = generate_det_check(self.spec, extra_assumes=test_assumes)
        fn_name = f"det_{self.spec.name}"
        result = self.runner.check(code, fn_name)

        self._record(phase, assume, result)
        logger.info(
            f"R{self._round} [{phase}] {assume.expression} → {result.status}"
        )

        if result.status == "fail":
            self.active_assumes.append(assume)
            return True   # nondeterminism persists, keep this assume
        elif result.status == "pass":
            return False  # this constraint eliminated nondeterminism, backtrack
        elif result.status == "timeout":
            logger.warning(f"Timeout on {assume.expression} — treating as inconclusive")
            return False
        else:  # error
            logger.error(f"Error on {assume.expression}: {result.stderr[:200]}")
            return False


def binary_search(
    spec: FunctionSpec,
    runner: VerusRunner,
    llm_client=None,
) -> Witness:
    """
    Run the full binary search: input first, then output.

    Returns a Witness with all accumulated assumes and trace.
    """
    ctx = SearchContext(spec, runner, llm_client)

    # R0: Initial determinism check (no assumes)
    code = generate_det_check(spec)
    fn_name = f"det_{spec.name}"
    r0 = runner.check(code, fn_name)
    ctx.trace.append({
        "round": 0, "phase": "initial", "assumes": [],
        "new_assume": None, "result": r0.status,
    })

    if r0.status == "pass":
        logger.info(f"{spec.name}: spec is deterministic")
        return Witness(function=spec.name, trace=ctx.trace)

    logger.info(f"{spec.name}: nondeterminism detected, starting binary search")

    # Phase 1: Narrow inputs
    for param in spec.params:
        _narrow_var(ctx, param.type, _input_var_name(param), "P1:input")

    # Phase 2: Narrow outputs
    for out_name, out_type in spec.output_vars():
        # Narrow output1 vs output2 — need special handling
        _narrow_output_pair(ctx, out_type, out_name, "P2:output")

    return Witness(
        function=spec.name,
        assumes=list(ctx.active_assumes),
        trace=ctx.trace,
    )


def _input_var_name(param: Param) -> str:
    """Get the input variable name for a param."""
    base = "self_" if param.is_self else param.name
    if param.is_mut_ref:
        return f"pre_{base}"
    return base


def _narrow_var(ctx: SearchContext, ty: TypeInfo, var: str, phase: str):
    """Narrow a single variable using its type's strategy."""
    for assume in narrow(ty, var, ctx):
        hit = ctx.try_assume(assume, phase)
        if hit:
            # If this was a compound type (struct/enum), the strategy
            # generator already yielded child constraints — they'll be
            # tried in subsequent iterations
            pass
        # Continue trying other constraints at same level


def _narrow_output_pair(ctx: SearchContext, ty: TypeInfo, base_name: str, phase: str):
    """
    Narrow an output variable pair (out1 vs out2).
    
    For result: r1 vs r2
    For post-state: post1_self_ vs post2_self_
    """
    name1 = base_name.replace("post_", "post1_").replace("result", "r1")
    name2 = base_name.replace("post_", "post2_").replace("result", "r2")

    if name1 == base_name and "post_" not in base_name:
        name1 = "r1"
        name2 = "r2"

    for assume in narrow(ty, name1, ctx):
        # Try constraining output1
        hit = ctx.try_assume(assume, phase)
        if hit:
            # Also try a different value for output2
            for assume2 in narrow(ty, name2, ctx):
                if assume2.expression != assume.expression:
                    ctx.try_assume(assume2, phase)
                    break
