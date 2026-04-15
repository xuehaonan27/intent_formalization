"""
Module 4: binary_search — Type-Guided Witness Narrowing

Decorator-based strategy registry.
Each strategy is a recursive function that calls ctx.try_assume()
and branches based on FAIL/PASS results. NOT generators.

LLM fallback for unknown types.
"""

import logging
from typing import Callable, Optional

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


def narrow(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Dispatch to the registered strategy for this type, or LLM fallback."""
    handler = _registry.get(ty.kind, _llm_fallback)
    handler(ty, var, ctx)


# ---------------------------------------------------------------------------
# Integer range helper
# ---------------------------------------------------------------------------

# Small default ranges for initial search. If nondeterminism is not found
# within these, fall back to full type range.
_SMALL_UNSIGNED = (0, 9)      # [0, 8] inclusive → [0, 9) exclusive
_SMALL_SIGNED = (-4, 5)       # [-4, 4] inclusive → [-4, 5) exclusive

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
    """Return (lo_inclusive, hi_exclusive) for small initial search."""
    if ty.kind in (TypeKind.U8, TypeKind.U16, TypeKind.U32,
                   TypeKind.U64, TypeKind.USIZE):
        return _SMALL_UNSIGNED
    elif ty.kind in (TypeKind.I8, TypeKind.I16, TypeKind.I32,
                     TypeKind.I64, TypeKind.ISIZE, TypeKind.INT):
        return _SMALL_SIGNED
    else:
        return _SMALL_SIGNED


def _full_int_range(ty: TypeInfo) -> tuple[int, int]:
    """Return full type range as fallback."""
    return _FULL_RANGE.get(ty.kind, (-256, 256))


# ---------------------------------------------------------------------------
# Concrete strategies (recursive, NOT generators)
# ---------------------------------------------------------------------------

@strategy_for(TypeKind.RESULT)
def narrow_result(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """
    Narrow Result<T, E>: binary choice between Ok and Err.
    Try constraining to Ok — if nondeterminism persists, it's within Ok branch.
    If Ok eliminates nondeterminism, the gap is cross-variant (Ok vs Err).
    """
    ok_assume = Assume(var, f"{var} is Ok", "variant: Ok")
    if ctx.try_assume(ok_assume):
        # FAIL → nondeterminism within Ok branch. Narrow the Ok inner value.
        if ty.type_args:
            narrow(ty.type_args[0], f"{var}->Ok_0", ctx)
    else:
        # PASS → nondeterminism is cross-variant (one run Ok, other Err)
        # This is typically a liveness gap. No further narrowing on this var.
        pass


@strategy_for(TypeKind.OPTION)
def narrow_option(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """
    Narrow Option<T>: binary choice between Some and None.
    """
    some_assume = Assume(var, f"{var} is Some", "variant: Some")
    if ctx.try_assume(some_assume):
        # FAIL → nondeterminism within Some. Narrow inner.
        if ty.type_args:
            narrow(ty.type_args[0], f"{var}->Some_0", ctx)
    else:
        # PASS → cross-variant nondeterminism (Some vs None)
        pass


@strategy_for(TypeKind.ENUM)
def narrow_enum(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """
    Narrow a general enum: try each variant until we find the one that preserves nondeterminism.
    """
    for variant in ty.variants:
        assume = Assume(var, f"{var} is {variant.name}", f"variant: {variant.name}")
        if ctx.try_assume(assume):
            # FAIL → nondeterminism within this variant
            if variant.inner:
                narrow(variant.inner, f"{var}->{variant.name}_0", ctx)
            return
    # If no variant preserves nondeterminism → cross-variant gap


@strategy_for(TypeKind.STRUCT)
def narrow_struct(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """
    Narrow a struct: iterate over fields, narrow each.
    Uses spec view (@) if available.
    """
    view = ty.spec_view or ty
    accessor = f"{var}@" if ty.spec_view else var

    for fld in view.fields:
        narrow(fld.type, f"{accessor}.{fld.name}", ctx)


@strategy_for(
    TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
    TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
    TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
)
def narrow_integer(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """
    Narrow integer via recursive bisection.
    Try small range first [0,8] / [-4,3]. If nondeterminism is not
    found within, fall back to full type range.
    """
    small_lo, small_hi = _int_range(ty)
    # Try small range: assume(var >= lo && var <= hi-1)
    small_inclusive_hi = small_hi - 1
    small_assume = Assume(
        var,
        f"{var} >= {small_lo} && {var} <= {small_inclusive_hi}",
        f"small range: [{small_lo}, {small_inclusive_hi}]",
    )
    if ctx.try_assume_replace(small_assume):
        # FAIL → nondeterminism within small range, bisect it
        _bisect_range(var, small_lo, small_inclusive_hi, ctx)
    else:
        # PASS → nondeterminism outside small range, try full range
        full_lo, full_hi = _full_int_range(ty)
        _bisect_range(var, full_lo, full_hi - 1, ctx)


def _bisect_range(var: str, lo: int, hi: int, ctx: "SearchContext"):
    """Recursive bisection on [lo, hi] inclusive. Uses replace mode."""
    if lo == hi:
        ctx.try_assume_replace(Assume(var, f"{var} == {lo}", f"exact: {lo}"))
        return

    mid = (lo + hi) // 2
    # Test left half: [lo, mid]
    if lo == mid:
        left_assume = Assume(var, f"{var} == {lo}", f"exact: {lo}")
    else:
        left_assume = Assume(
            var,
            f"{var} >= {lo} && {var} <= {mid}",
            f"range: [{lo}, {mid}]",
        )

    if ctx.try_assume_replace(left_assume):
        # FAIL → nondeterminism in [lo, mid], recurse
        _bisect_range(var, lo, mid, ctx)
    else:
        # PASS → nondeterminism in [mid+1, hi], recurse
        _bisect_range(var, mid + 1, hi, ctx)


@strategy_for(TypeKind.BOOL)
def narrow_bool(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow bool: try true. If FAIL, it's true. If PASS, it's false."""
    assume = Assume(var, f"{var} == true", "bool: true")
    if not ctx.try_assume(assume):
        # PASS → nondeterminism only when var is false
        ctx.try_assume(Assume(var, f"{var} == false", "bool: false"))


@strategy_for(TypeKind.SET)
def narrow_set(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """
    Narrow Set<T>: try empty first, then increasing sizes.
    """
    elem_ty_name = ty.type_args[0].name if ty.type_args else "int"

    # Try empty
    empty_assume = Assume(var, f"{var} == Set::<{elem_ty_name}>::empty()", "set: empty")
    if ctx.try_assume(empty_assume):
        return  # nondeterminism with empty set, done

    # Try size 1
    size1 = Assume(var, f"{var}.len() == 1", "set: len=1")
    if ctx.try_assume(size1):
        # Narrow the single element
        if ty.type_args:
            # For a single-element set, we can try: exists |e| var == set![e]
            narrow(ty.type_args[0], f"/* elem of {var} */", ctx)
        return

    # Try size 2, etc.
    for size in [2, 3, 4]:
        assume = Assume(var, f"{var}.len() == {size}", f"set: len={size}")
        if ctx.try_assume(assume):
            return


@strategy_for(TypeKind.SEQ)
def narrow_seq(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Narrow Seq<T>: length first, then elements."""
    # Try empty
    empty_assume = Assume(var, f"{var}.len() == 0", "seq: empty")
    if ctx.try_assume(empty_assume):
        return

    # Try length 1
    len1 = Assume(var, f"{var}.len() == 1", "seq: len=1")
    if ctx.try_assume(len1):
        if ty.type_args:
            narrow(ty.type_args[0], f"{var}[0]", ctx)
        return

    # Increasing lengths
    for length in [2, 3, 4]:
        assume = Assume(var, f"{var}.len() == {length}", f"seq: len={length}")
        if ctx.try_assume(assume):
            # Narrow individual elements
            if ty.type_args:
                for i in range(length):
                    narrow(ty.type_args[0], f"{var}[{i}]", ctx)
            return


@strategy_for(TypeKind.UNIT)
def narrow_unit(ty: TypeInfo, var: str, ctx: "SearchContext"):
    """Unit type: nothing to narrow."""
    pass


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
        ctx.try_assume(Assume(var, expr, f"LLM-suggested for {ty.name}"))
    else:
        logger.error(f"No LLM client and no strategy for type {ty.name}")


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

    def _record(self, phase: str, assume: Assume, result: VerifyResult):
        self._round += 1
        self.trace.append({
            "round": self._round,
            "phase": phase,
            "assumes": [a.expression for a in self.active_assumes] + [assume.expression],
            "new_assume": assume.expression,
            "result": result.status,
            "description": assume.description,
        })

    def try_assume(self, assume: Assume, phase: str = "") -> bool:
        """
        Test an assume constraint (append mode).
        Use for constraints on NEW variables (e.g. r1 is Ok, pre@.num_bits).

        - FAIL → nondeterminism persists. Add to active.
        - PASS → eliminated nondeterminism. Do NOT add.

        Returns True if FAIL, False if PASS.
        """
        test_assumes = self.active_assumes + [assume]
        code = generate_det_check(self.spec, extra_assumes=test_assumes)
        fn_name = f"det_{self.spec.name}"
        result = self.runner.check(code, fn_name)

        p = phase or ("P1:input" if not self.active_assumes else "search")
        self._record(p, assume, result)
        logger.info(
            f"R{self._round} [{p}] +{assume.expression} → {result.status}"
        )

        if result.status == "fail":
            self.active_assumes.append(assume)
            return True
        elif result.status == "pass":
            return False
        elif result.status == "timeout":
            logger.warning(f"Timeout on {assume.expression} — treating as inconclusive, skipping")
            return False
        else:  # error (e.g. compile error)
            logger.error(f"Error on {assume.expression}: {result.stderr[:200]}")
            return False

    def try_assume_replace(self, assume: Assume, phase: str = "") -> bool:
        """
        Test an assume constraint (replace mode).
        Use when refining the SAME variable (e.g. bisecting [0,8] → [0,4] → [3,4] → 3).
        On FAIL, replaces any existing assume with the same var_name.

        Returns True if FAIL, False if PASS.
        """
        # Build test set: existing assumes with same var_name replaced
        filtered = [a for a in self.active_assumes if a.var_name != assume.var_name]
        test_assumes = filtered + [assume]
        code = generate_det_check(self.spec, extra_assumes=test_assumes)
        fn_name = f"det_{self.spec.name}"
        result = self.runner.check(code, fn_name)

        p = phase or "refine"
        self._record(p, assume, result)
        logger.info(
            f"R{self._round} [{p}] ~{assume.expression} → {result.status}"
        )

        if result.status == "fail":
            # Replace: remove old assume for this var, add new one
            self.active_assumes = filtered + [assume]
            return True
        elif result.status == "pass":
            return False
        elif result.status == "timeout":
            logger.warning(f"Timeout on {assume.expression} — treating as inconclusive, skipping")
            return False
        else:
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
        "description": "full determinism check",
    })

    if r0.status == "pass":
        logger.info(f"{spec.name}: spec is deterministic")
        return Witness(function=spec.name, trace=ctx.trace)

    if r0.status != "fail":
        logger.error(f"{spec.name}: initial check returned {r0.status}, aborting")
        return Witness(function=spec.name, trace=ctx.trace)

    logger.info(f"{spec.name}: nondeterminism detected, starting binary search")

    # Phase 1: Narrow inputs
    for param in spec.params:
        var = _input_var_name(param)
        narrow(param.type, var, ctx)

    # Phase 2: Narrow outputs
    for out_name, out_type in spec.output_vars():
        _narrow_output_pair(ctx, out_type, out_name)

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


def _narrow_output_pair(ctx: SearchContext, ty: TypeInfo, base_name: str):
    """
    Narrow an output variable pair.

    Output vars come in pairs: (post1_X, post2_X) or (r1, r2).
    We narrow by fixing one output's value and letting SMT find
    the other that differs.
    """
    # Determine the pair names
    if base_name == "result":
        name1, name2 = "r1", "r2"
    elif base_name.startswith("post_"):
        suffix = base_name[5:]  # after "post_"
        name1 = f"post1_{suffix}"
        name2 = f"post2_{suffix}"
    else:
        name1 = base_name + "1"
        name2 = base_name + "2"

    # Narrow output1 — this constrains y1. SMT will find y2 that differs.
    narrow(ty, name1, ctx)
