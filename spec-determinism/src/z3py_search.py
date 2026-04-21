"""
Z3-Python incremental search context.

Replaces the "re-invoke Verus per binary-search round" loop with a single
Verus run that produces a `.smt2` vocabulary, then drives all subsequent
search via z3-py push/pop + assert_and_track. Per-round cost drops from
~30 s (Verus compile) to ~1 ms (Z3 incremental check).

Design rationale (see DESIGN.md / chat history 2026-04-21):

* All SMT *encoding* knowledge stays in Verus. Python only manipulates
  facts whose shape is either (a) trivially structural (e.g. `(= x y)`
  on top-level symbols) or (b) a call to a helper spec fn that Verus
  generated for us.
* unsat_core via `assert_and_track` lets callers identify the minimal
  guard set that forced determinism — no need to push/pop-shrink
  manually unless we want a true MUS (which is a constant-factor
  follow-up loop).

Usage::

    smt2 = run_verus_once(template_rs)            # one slow call
    ctx  = Z3PySearchContext.from_smt2_text(smt2)
    ctx.declare("(declare-const r1! Foo)")
    g1 = ctx.assert_fact("(= r1! r2!)", label="eq_r")
    if ctx.check() == z3.unsat:
        print("forced determinism via:", ctx.unsat_core())
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import z3

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prelude extraction
# ---------------------------------------------------------------------------

def load_verus_prelude(smt2_path: str | Path) -> str:
    """Return everything before the first `(push)` in a Verus-generated
    `.smt2` file: sort/datatype/function declarations, axioms, and
    Verus's preamble options. Everything inside push/pop blocks (the
    actual proof goals) is dropped — those are what we replace with our
    own search-driven facts.
    """
    text = Path(smt2_path).read_text() if not isinstance(smt2_path, str) \
        or Path(smt2_path).exists() else str(smt2_path)
    lines = text.splitlines()
    push_idx = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("(push"):
            push_idx = i
            break
    if push_idx is None:
        logger.debug("no (push) found in smt2; using full text as prelude")
        return text
    return "\n".join(lines[:push_idx])


# ---------------------------------------------------------------------------
# Search context
# ---------------------------------------------------------------------------

class Z3PySearchContext:
    """Wraps a Z3 Solver that has been preloaded with a Verus-generated
    SMT vocabulary (sort/datatype/spec-fn decls + axioms).

    Two solvers share a `Context`: the *main* solver is the search state
    (push/pop, asserts, checks); the *side* solver is used purely to
    parse SMT-LIB expression strings in the same context and extract
    `z3.BoolRef`s without polluting the main state. This avoids us having
    to rebuild Verus's encoded sorts/decls in the z3-py API by hand.

    Facts are stored as `(=> guard fact)` so we can disable any subset by
    omitting its guard from the assumption list at check-sat time. This
    is what makes proper MUS minimization work — `assert_and_track`
    alone adds the fact unconditionally and only labels it for unsat_core
    extraction, which would defeat MUS shrinking.
    """

    def __init__(self, prelude: str):
        # Single shared Z3 Context — required so expressions parsed by
        # `_side` are usable in `solver`.
        self._ctx = z3.Context()
        self.solver = z3.Solver(ctx=self._ctx)
        self.solver.set(unsat_core=True)
        self.solver.from_string(prelude)
        self._side = z3.Solver(ctx=self._ctx)
        self._side.from_string(prelude)
        self._guard_counter = 0
        self._declared: list[str] = []   # for diagnostics
        # Stack of "guards added at this push level". A push() opens a
        # new (empty) frame; pop() discards the top frame, removing its
        # guards from the active assumption set. The solver itself is
        # also push/popped so the underlying `(=> g fact)` Implies are
        # garbage-collected on pop.
        self._guard_stack: list[list[z3.BoolRef]] = [[]]
        self._guards_by_label: dict[str, z3.BoolRef] = {}

    # ----- factory -----
    @classmethod
    def from_smt2_path(cls, smt2_path: str | Path) -> "Z3PySearchContext":
        return cls(load_verus_prelude(smt2_path))

    # ----- declarations -----
    def declare(self, smt_text: str) -> None:
        """Add declarations (e.g. `(declare-const r1! Foo)`,
        `(declare-fun ...)`). Mirrored to both solvers so subsequent
        expression parsing sees them.
        """
        self.solver.from_string(smt_text)
        self._side.from_string(smt_text)
        self._declared.append(smt_text)

    # ----- expression parsing -----
    def parse_expr(self, smt_text: str) -> z3.BoolRef:
        """Parse a single SMT-LIB Boolean expression and return it as a
        z3-py term living in our Context.

        Implementation: temporarily wrap as `(assert ...)` in the side
        solver under push/pop, then read back the last assertion.
        """
        self._side.push()
        try:
            self._side.from_string(f"(assert {smt_text})")
            asserts = list(self._side.assertions())
            if not asserts:
                raise ValueError(f"no expression parsed from: {smt_text!r}")
            return asserts[-1]
        finally:
            self._side.pop()

    # ----- search primitives -----
    def push(self) -> None:
        self.solver.push()
        self._guard_stack.append([])

    def pop(self, n: int = 1) -> None:
        self.solver.pop(n)
        for _ in range(n):
            for g in self._guard_stack.pop():
                self._guards_by_label.pop(str(g), None)
            if not self._guard_stack:
                self._guard_stack.append([])  # always keep base frame

    def assert_fact(self, fact: str | z3.BoolRef,
                    label: str | None = None) -> z3.BoolRef:
        """Assert a fact under an automatically-managed Bool guard, then
        return that guard. If `label` is given, the guard's name is
        `<label>` (must be unique across currently-active facts);
        otherwise a fresh `_g<N>` is used.

        The fact may be a raw SMT-LIB string or a pre-parsed Z3 expression.
        Internally added as `(=> guard fact)` so it can be disabled by
        omitting `guard` from a subsequent `check()` call.
        """
        if isinstance(fact, str):
            expr = self.parse_expr(fact)
        else:
            expr = fact
        if label is None:
            label = f"_g{self._guard_counter}"
            self._guard_counter += 1
        if label in self._guards_by_label:
            raise ValueError(f"duplicate guard label: {label}")
        guard = z3.Bool(label, self._ctx)
        self.solver.add(z3.Implies(guard, expr))
        self._guard_stack[-1].append(guard)
        self._guards_by_label[label] = guard
        return guard

    @property
    def active_guards(self) -> list[z3.BoolRef]:
        """All guards that have been asserted at the current push level
        or any ancestor — i.e. the facts logically "in effect" right now.
        """
        return [g for frame in self._guard_stack for g in frame]

    def check(self, extra: Iterable[z3.BoolRef] = ()) -> z3.CheckSatResult:
        """Run check-sat with the currently-active guards plus optional
        `extra` ones. Returns z3.sat / z3.unsat / z3.unknown.

        Note: passing `extra=[]` is the common case (use everything
        currently asserted). Pass extras to do an ad-hoc "what if we also
        forced X" probe without permanently asserting it.
        """
        guards = self.active_guards + list(extra)
        return self.solver.check(*guards) if guards else self.solver.check()

    def unsat_core(self) -> list[str]:
        """After a `check()` returning unsat, return the labels of the
        guards that participated. May not be globally minimal — call
        `minimize_core()` for an MUS.
        """
        return [str(c) for c in self.solver.unsat_core()]

    def minimize_core(self, core: Iterable[str]) -> list[str]:
        """Shrink an unsat core to a minimal unsat subset (MUS) via
        deletion-based filtering. One extra check per element.
        """
        cur = list(core)
        i = 0
        while i < len(cur):
            trial = [self._guards_by_label[g] for g in cur if g != cur[i]]
            if self.solver.check(*trial) == z3.unsat:
                cur.pop(i)
            else:
                i += 1
        return cur

    def model(self) -> z3.ModelRef:
        return self.solver.model()


# ---------------------------------------------------------------------------
# Helpers for top-level symbol discovery
# ---------------------------------------------------------------------------

def find_top_level_constants(prelude: str,
                             suffix: str = "_!") -> list[tuple[str, str]]:
    """Scan a prelude for `(declare-fun NAME () SORT)` declarations
    matching a name suffix (default `_!`, which is Verus's convention
    for proof-context user variables).

    Returns `[(name, sort), ...]`. This lets callers programmatically
    discover the SMT names of `pre_self_!`, `r1!`, `post1_self_!`, etc.
    without having to mirror Verus's mangling rules.
    """
    import re
    out: list[tuple[str, str]] = []
    pat = re.compile(
        r"\(declare-(?:fun|const)\s+(\S+%s)\s*(?:\(\s*\))?\s*([^\)]+)\)" % re.escape(suffix)
    )
    for m in pat.finditer(prelude):
        out.append((m.group(1), m.group(2).strip()))
    return out
