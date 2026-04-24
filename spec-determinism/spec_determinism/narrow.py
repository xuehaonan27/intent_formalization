"""
Module 4: narrow — Type-Guided Witness Narrowing

Core data structure: AssumeTree — a tree where each node holds one assume.
Same-node refinement replaces; different nodes accumulate.

Decorator-based strategy registry. Each strategy is recursive.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from .types import (
    TypeKind, TypeInfo, FieldInfo, Param,
    FunctionSpec, Assume, VerifyResult, Witness,
    Symbol, DetCheckSpec,
)
from .predicates import (
    EqPred, RangePred, VariantIsPred, BoolPred, StrEqPred,
    SetEmptyPred, SetLenGtPred, LenEqPred, LenRangePred,
    SetContainsPred, SetLiteralPred, NotEqualFnPred,
)
logger = logging.getLogger(__name__)


# ===========================================================================
# SearchCtx — structural interface consumed by the narrow_* strategies
# ===========================================================================
#
# The narrow_* functions below don't care which concrete search driver
# is orchestrating them; they only need an object with `.tree`,
# `.det_spec`, and a `.test_and_set(node, assume, phase="")` method
# that returns True iff the new assume was kept. Today there is exactly
# one implementation: `schema_search.SchemaSearchContext`.
class SearchContext(Protocol):
    tree: "AssumeNode"
    det_spec: DetCheckSpec
    trace: list[dict]

    def test_and_set(self, node: "AssumeNode", assume: Assume, phase: str = "") -> bool: ...


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


def _no_strategy(ty: TypeInfo, var: str, node: "AssumeNode", ctx: "SearchContext"):
    logger.warning(
        f"No narrow strategy for {ty.kind}:{ty.name} (var={var}); "
        f"witness will be partial for this dimension."
    )


def narrow(ty: TypeInfo, var: str, node: "AssumeNode", ctx: "SearchContext"):
    """Dispatch to the registered strategy. Each strategy gets its own tree node."""
    handler = _registry.get(ty.kind, _no_strategy)
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


_INT_RANGE_KINDS = frozenset({
    TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
    TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
    TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
})


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
    ok_assume = Assume.from_pred(var, VariantIsPred(var, "Ok"), "variant: Ok")
    if ctx.test_and_set(variant_node, ok_assume):
        # FAIL → nondeterminism with this var as Ok. Narrow Ok inner.
        if ty.type_args:
            inner_node = node.get_or_create("Ok_0")
            narrow(ty.type_args[0], f"{var}->Ok_0", inner_node, ctx)
    else:
        # PASS → Ok doesn't exhibit nondeterminism here. Try Err.
        err_assume = Assume.from_pred(var, VariantIsPred(var, "Err"), "variant: Err")
        if ctx.test_and_set(variant_node, err_assume):
            if len(ty.type_args) > 1:
                inner_node = node.get_or_create("Err_0")
                narrow(ty.type_args[1], f"{var}->Err_0", inner_node, ctx)


@strategy_for(TypeKind.OPTION)
def narrow_option(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow Option<T>: try Some first, then None if Some PASS."""
    variant_node = node.get_or_create("variant")
    some_assume = Assume.from_pred(var, VariantIsPred(var, "Some"), "variant: Some")
    if ctx.test_and_set(variant_node, some_assume):
        if ty.type_args:
            inner_node = node.get_or_create("Some_0")
            narrow(ty.type_args[0], f"{var}->Some_0", inner_node, ctx)
    else:
        # PASS → Some doesn't exhibit nondeterminism. Try None.
        none_assume = Assume.from_pred(var, VariantIsPred(var, "None"), "variant: None")
        ctx.test_and_set(variant_node, none_assume)


@strategy_for(TypeKind.ENUM)
def narrow_enum(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow a general enum: try each variant."""
    variant_node = node.get_or_create("variant")
    for variant in ty.variants:
        assume = Assume.from_pred(var, VariantIsPred(var, variant.name),
                                  f"variant: {variant.name}")
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
    small_assume = Assume.from_pred(
        var, RangePred(var, small_lo, hi_inclusive),
        f"small range: [{small_lo}, {hi_inclusive}]",
    )
    if ctx.test_and_set(node, small_assume):
        _bisect_range(var, small_lo, hi_inclusive, node, ctx)
        return

    # Small range PASS — rare case, just bisect full type range directly
    full_lo, full_hi = _full_int_range(ty)
    full_hi_inclusive = full_hi - 1
    full_assume = Assume.from_pred(
        var, RangePred(var, full_lo, full_hi_inclusive),
        f"full range: [{full_lo}, {full_hi_inclusive}]",
    )
    if ctx.test_and_set(node, full_assume):
        _bisect_range(var, full_lo, full_hi_inclusive, node, ctx)


def _bisect_range(var: str, lo: int, hi: int, node: AssumeNode, ctx: "SearchContext") -> int | None:
    """Recursive bisection on an integer variable in [lo, hi]. Returns
    the exact value found, or None.
    """
    if lo == hi:
        ctx.test_and_set(node, Assume.from_pred(var, EqPred(var, lo), f"exact: {lo}"))
        return lo

    mid = (lo + hi) // 2
    if lo == mid:
        left = Assume.from_pred(var, EqPred(var, lo), f"exact: {lo}")
    else:
        left = Assume.from_pred(var, RangePred(var, lo, mid), f"range: [{lo}, {mid}]")

    if ctx.test_and_set(node, left):
        if lo == mid:
            return lo  # exact value already confirmed, skip redundant recursion
        return _bisect_range(var, lo, mid, node, ctx)
    else:
        return _bisect_range(var, mid + 1, hi, node, ctx)


def _bisect_len_range(base: str, lo: int, hi: int, node: AssumeNode,
                      ctx: "SearchContext") -> int | None:
    """Same shape as :func:`_bisect_range`, but emits LenEq/LenRange
    preds — used for Set/Seq length narrowing where ``base`` is the
    collection variable (not the ``.len()`` expression).
    """
    var_len_expr = f"{base}.len()"

    if lo == hi:
        ctx.test_and_set(node, Assume.from_pred(
            var_len_expr, LenEqPred(base, lo), f"len: {lo}"))
        return lo

    mid = (lo + hi) // 2
    if lo == mid:
        left = Assume.from_pred(var_len_expr, LenEqPred(base, lo), f"len: {lo}")
    else:
        left = Assume.from_pred(
            var_len_expr, LenRangePred(base, lo, mid),
            f"len range: [{lo}, {mid}]")

    if ctx.test_and_set(node, left):
        if lo == mid:
            return lo
        return _bisect_len_range(base, lo, mid, node, ctx)
    else:
        return _bisect_len_range(base, mid + 1, hi, node, ctx)


def _narrow_length(base: str, node: AssumeNode, ctx: "SearchContext",
                   max_bound: int = 2 ** 20) -> int | None:
    """Narrow collection length: exact probes for [0..4], then bisect.

    ``base`` is the collection variable (NOT a ``.len()`` expression).
    Returns the exact length found, or None.
    """
    var_len_expr = f"{base}.len()"

    # Phase 1: exact probes for common small values
    EXACT_LIMIT = 4
    for n in range(EXACT_LIMIT + 1):
        assume = Assume.from_pred(var_len_expr, LenEqPred(base, n), f"len: {n}")
        if ctx.test_and_set(node, assume):
            return n

    # Phase 2: not in [0..4], bisect the full range
    lo = EXACT_LIMIT + 1
    full_assume = Assume.from_pred(
        var_len_expr, LenRangePred(base, lo, max_bound),
        f"len range: [{lo}, {max_bound}]",
    )
    if ctx.test_and_set(node, full_assume):
        return _bisect_len_range(base, lo, max_bound, node, ctx)

    return None


@strategy_for(TypeKind.BOOL)
def narrow_bool(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    assume_true = Assume.from_pred(var, BoolPred(var, True), "bool: true")
    if not ctx.test_and_set(node, assume_true):
        ctx.test_and_set(node, Assume.from_pred(var, BoolPred(var, False), "bool: false"))


@strategy_for(TypeKind.SET)
def narrow_set(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    elem_ty = ty.type_args[0] if ty.type_args else TypeInfo(kind=TypeKind.INT, name="int")
    elem_ty_name = elem_ty.name

    # Verus `Set::<T>::len()` returns 0 for BOTH empty and infinite sets, so
    # len-first probing is ambiguous. Instead, split into two disjoint finite
    # cases — `s == empty` or `s.len() > 0` — and skip the "infinite set"
    # witness (Verus admits it, but it carries no useful signal for the
    # developer and cannot be printed concretely).

    # Case 1: empty set
    empty = Assume.from_pred(var, SetEmptyPred(var, elem_ty_name), "set: empty")
    if ctx.test_and_set(node, empty):
        return

    # Case 2: finite non-empty. Establish len > 0 as a precondition; once that
    # sticks, len() is the true cardinality and we can enumerate elements.
    pos_len = Assume.from_pred(var, SetLenGtPred(var), "set: non-empty (finite)")
    if not ctx.test_and_set(node, pos_len):
        # Spec admits neither empty nor any finite non-empty witness — the
        # only remaining nondeterminism is via infinite sets, which we don't
        # try to pin down concretely.
        return

    # Now narrow length. _narrow_length probes from small upward; its results
    # are meaningful because we've already committed to len() > 0.
    len_node = node.get_or_create("len")
    length = _narrow_length(var, len_node, ctx)
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
        sorted_elems = tuple(sorted(elements))
        desc = ", ".join(str(e) for e in sorted_elems)
        lit_assume = Assume.from_pred(
            var, SetLiteralPred(var, elem_ty_name, sorted_elems),
            f"set: {{{desc}}}",
        )
        if ctx.test_and_set(node, lit_assume):
            node.children.clear()  # len + elem children subsumed by full set expr


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
        assume = Assume.from_pred(var, SetContainsPred(var, val), f"contains {val}")
        if ctx.test_and_set(node, assume):
            return val
    return None


@strategy_for(TypeKind.SEQ)
def narrow_seq(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow Seq<T>: length first, then elements."""
    len_node = node.get_or_create("len")
    length = _narrow_length(var, len_node, ctx)

    if length is None:
        return

    if ty.type_args and length > 0:
        for i in range(length):
            elem_node = node.get_or_create(f"elem_{i}")
            narrow(ty.type_args[0], f"{var}[{i}]", elem_node, ctx)


@strategy_for(TypeKind.MAP)
def narrow_map(ty: TypeInfo, var: str, node: AssumeNode, ctx: "SearchContext"):
    """Narrow Map<K, V>.

    Dimension-separated (NOT <k,v> paired), finite by default (no infinite
    case split — per user decision):
      1. Empty: `m.dom() == Set::<K>::empty()` (implies m is empty).
      2. Domain length: probe `m.dom().len() == n`.
      3. Keys: probe `m.dom().contains(k)` for n keys via Set-element bisect.
      4. Values: for each found key k, recurse narrow on V with var `m[k]`.
         `m.dom().contains(k)` stays in the global assume set, so the value
         narrow runs under that precondition automatically.

    Reuses `SetEmptyPred`/`LenEqPred`/`SetContainsPred` on the virtual
    `{var}.dom()` — no Map-specific predicates needed.
    """
    k_ty = ty.type_args[0] if ty.type_args else TypeInfo(kind=TypeKind.INT, name="int")
    v_ty = ty.type_args[1] if len(ty.type_args) > 1 else TypeInfo(kind=TypeKind.INT, name="int")
    k_ty_name = k_ty.name or "int"

    dom_var = f"{var}.dom()"
    dom_node = node.get_or_create("dom")

    # --- Step 1: empty dom (⇔ empty map) ---
    empty = Assume.from_pred(
        dom_var, SetEmptyPred(dom_var, k_ty_name), "map: empty (dom)")
    if ctx.test_and_set(dom_node, empty):
        return

    # --- Step 2: length probe ---
    # Map is assumed finite by default; skip the SetLenGt case split and go
    # straight to length narrowing.
    len_node = dom_node.get_or_create("len")
    length = _narrow_length(dom_var, len_node, ctx)
    if length is None or length == 0:
        return

    # --- Step 3: key probing (reuse Set element bisect) ---
    if k_ty.kind not in _INT_RANGE_KINDS:
        # Non-integer key types: can still assert dom() length but can't
        # bisect concrete keys. Graceful degradation.
        return

    keys: list[int] = []
    for i in range(length):
        k = _bisect_set_element(dom_var, k_ty, dom_node, i, ctx,
                                skip_vals=frozenset(keys))
        if k is None:
            break
        keys.append(k)

    # --- Step 4: value at each found key ---
    # `m.dom().contains(k)` is already in the global assume conjunction from
    # step 3, so narrow(v_ty, f"{var}[{k}]", ...) emits value assumes under
    # that precondition without us having to thread a prefix.
    for k in keys:
        val_node = node.get_or_create(f"val_{k}")
        narrow(v_ty, f"{var}[{k}]", val_node, ctx)


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
        # Strip the surrounding quotes to get the raw string value.
        value = lit[1:-1]
        assume = Assume.from_pred(var, StrEqPred(var, value), f'str: {lit}')
        if ctx.test_and_set(node, assume):
            return


def _add_distinctness_witnesses(ctx, det_spec: DetCheckSpec):
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
    assume = Assume.from_pred(
        "tuple",
        NotEqualFnPred(call=call),
        f"distinctness: output tuple not equal under {det_spec.equal_fn_name}",
    )
    ctx.test_and_set(node, assume, phase="distinct")
