"""Structured predicates emitted by narrow strategies.

Before the refactor, narrow_* strategies emitted ``Assume.expression`` as
a Rust source string (``"var.contains(3)"``), and the A' backend
parsed those strings back with regex.  That made Step 2 (narrow) and
Step 1 (A' schema translation) implicitly coupled through a small,
brittle surface grammar.

Now narrow emits a structured :data:`AssumePred` object.
``Assume.pred`` carries the structured form; ``Assume.expression`` is
still populated via :meth:`to_rust`, so Verus-subprocess backends and
the witness renderer keep working verbatim.  The A' backend matches on
the pred type directly and never parses the Rust string.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class EqPred:
    """`var == value` for an integer-typed ``var``."""
    var: str
    value: int
    def to_rust(self) -> str:
        return f"{self.var} == {self.value}"


@dataclass(frozen=True)
class RangePred:
    """`var >= lo && var <= hi` for an integer-typed ``var``."""
    var: str
    lo: int
    hi: int
    def to_rust(self) -> str:
        return f"{self.var} >= {self.lo} && {self.var} <= {self.hi}"


@dataclass(frozen=True)
class VariantIsPred:
    """`var is Variant` for Result/Option/enum."""
    var: str
    variant: str
    def to_rust(self) -> str:
        return f"{self.var} is {self.variant}"


@dataclass(frozen=True)
class BoolPred:
    """`var == true` / `var == false`."""
    var: str
    value: bool
    def to_rust(self) -> str:
        return f"{self.var} == {'true' if self.value else 'false'}"


@dataclass(frozen=True)
class StrEqPred:
    """`var == "literal"` — string content narrowing."""
    var: str
    value: str
    def to_rust(self) -> str:
        return f'{self.var} == "{self.value}"'


@dataclass(frozen=True)
class SetEmptyPred:
    """`var == Set::<T>::empty()`."""
    var: str
    elem_ty_name: str
    def to_rust(self) -> str:
        return f"{self.var} == Set::<{self.elem_ty_name}>::empty()"


@dataclass(frozen=True)
class SetLenGtPred:
    """`var.len() > 0` — used to rule out infinite-set witness."""
    var: str
    def to_rust(self) -> str:
        return f"{self.var}.len() > 0"


@dataclass(frozen=True)
class LenEqPred:
    """`var.len() == n` — Set or Seq cardinality."""
    var: str
    n: int
    def to_rust(self) -> str:
        return f"{self.var}.len() == {self.n}"


@dataclass(frozen=True)
class LenRangePred:
    """`var.len() >= lo && var.len() <= hi`."""
    var: str
    lo: int
    hi: int
    def to_rust(self) -> str:
        return f"{self.var}.len() >= {self.lo} && {self.var}.len() <= {self.hi}"


@dataclass(frozen=True)
class SetContainsPred:
    """`var.contains(elem)` — probe a set for membership."""
    var: str
    elem: int
    def to_rust(self) -> str:
        return f"{self.var}.contains({self.elem})"


@dataclass(frozen=True)
class SetLiteralPred:
    """`var == Set::<T>::empty().insert(e1).insert(e2)...` — final
    confirmation after contains-probing enumerated all elements."""
    var: str
    elem_ty_name: str
    elements: tuple[int, ...]
    def to_rust(self) -> str:
        expr = f"Set::<{self.elem_ty_name}>::empty()"
        for e in self.elements:
            expr += f".insert({e})"
        return f"{self.var} == {expr}"


@dataclass(frozen=True)
class NotEqualFnPred:
    """Distinctness step: `!fn(arg1, arg2, ...)` — the final witness
    that the two output tuples are non-equivalent under the chosen
    equality relation.  Carries the pre-rendered call so we don't have
    to re-synthesise the argument list here."""
    call: str
    def to_rust(self) -> str:
        return f"!{self.call}"


@dataclass(frozen=True)
class OpaquePred:
    """Escape hatch for narrow strategies that still produce free-form
    Rust expressions (currently just the LLM fallback).  A' cannot
    translate these — it falls through to ``pass_untranslatable``."""
    var: str
    expression: str
    def to_rust(self) -> str:
        return self.expression


AssumePred = Union[
    EqPred, RangePred, VariantIsPred, BoolPred, StrEqPred,
    SetEmptyPred, SetLenGtPred, LenEqPred, LenRangePred,
    SetContainsPred, SetLiteralPred, NotEqualFnPred, OpaquePred,
]
