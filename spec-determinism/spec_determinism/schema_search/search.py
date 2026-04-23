"""Schema-driven search driver — replaces Verus-per-round with z3-py push/pop.

This duck-types the SearchContext interface consumed by the existing
narrow() strategies in narrow.py, so we get full reuse.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import z3

from ..types import Assume, DetCheckSpec, Witness
from ..narrow import AssumeNode, narrow, _add_distinctness_witnesses
from .schemas import SchemaBinding, SchemaKind, translate_assume

logger = logging.getLogger(__name__)


@dataclass
class SchemaCtx:
    """Holds the loaded Z3 solver + schema SMT-name map.

    Built once per (det_spec, guarded-smt2) — shared across all search
    rounds, all operations push/pop below.
    """
    z3_ctx: z3.Context
    solver: z3.Solver
    schemas: list[SchemaBinding]
    # Rust guard name → z3.BoolRef (top-level declared constants from smt2)
    guard_consts: dict[str, z3.BoolRef]
    # Rust k-param name → z3.IntRef / similar
    k_consts: dict[str, z3.ExprRef]


def build_schema_ctx(
    smt2_path: Path,
    fn_name: str,
    schemas: list[SchemaBinding],
    crate_name: str,
) -> SchemaCtx:
    """Parse smt2, load prelude + det_<fn> body into a fresh solver,
    locate the guard/k constants that Verus emitted for each schema."""
    text = Path(smt2_path).read_text()

    first_push = text.find("(push)")
    prelude = text[:first_push]

    # Locate the specific Function-Def block for fn_name. The marker may
    # include module prefix when --verify-only-module is used, e.g.
    #   ;; Function-Def kernel::mm::kheap::det_allocate
    # Search by suffix "::{fn_name}\n" which is unique enough.
    import re as _re
    m = _re.search(rf";; Function-Def\s+\S*::{_re.escape(fn_name)}\b", text)
    if not m:
        # Fallback to plain substring.
        mi = text.find(f"Function-Def {crate_name}::{fn_name}")
        if mi < 0:
            raise RuntimeError(f"No Function-Def for {fn_name} in {smt2_path}")
    else:
        mi = m.start()
    push_idx = text.find("(push)", mi)
    cs_idx = text.find("(check-sat)", push_idx)
    body = text[push_idx + len("(push)"):cs_idx]

    # Strip nested solver-control lines from body.
    kept: list[str] = []
    for ln in body.splitlines():
        s = ln.strip()
        if s.startswith(("(push)", "(pop)", "(check-sat)", "(get-info",
                          "(get-model)", "(set-option", ";")):
            continue
        kept.append(ln)
    body_clean = "\n".join(kept)

    # Build solver.
    z3_ctx = z3.Context()
    solver = z3.Solver(ctx=z3_ctx)
    solver.from_string(prelude)
    solver.from_string(body_clean)
    logger.info(f"Schema solver loaded: {len(solver.assertions())} assertions")

    # (guard_consts and k_consts are also unused above; we need to delete
    # the empty dict init that preceded batching.)

    # Batched constant resolution: instead of re-parsing prelude+body per
    # name (O(N²) in smt2 size), build ONE big assertion that references
    # every guard/k constant, parse once, then split the And(...) children.
    guard_consts: dict[str, z3.BoolRef] = {}
    k_consts: dict[str, z3.ExprRef] = {}

    guard_names = [s.guard_name + "!" for s in schemas]
    k_names: list[tuple[str, str]] = []  # (pname, smt_name)
    for s in schemas:
        for (pname, _pty) in s.k_params:
            k_names.append((pname, pname + "!"))

    probe_bool = " ".join(f"(= {n} {n})" for n in guard_names) or "true"
    probe_int = " ".join(f"(= {n} {n})" for n in (smt for _, smt in k_names)) or "true"
    probe_smt = f"(assert (and {probe_bool} {probe_int}))"
    try:
        tmp = z3.Solver(ctx=z3_ctx)
        tmp.from_string(prelude + "\n" + body_clean + "\n" + probe_smt)
        big_and = tmp.assertions()[-1]
        # big_and = And(eq_g_0, eq_g_1, ..., eq_k_0, ...).  Each child is
        # (= c c); .children()[0] is the constant.
        children = list(big_and.children())
        pos = 0
        for s in schemas:
            eq = children[pos]; pos += 1
            guard_consts[s.guard_name] = eq.children()[0]
        for (pname, _smt) in k_names:
            eq = children[pos]; pos += 1
            k_consts[pname] = eq.children()[0]
    except z3.Z3Exception as e:
        logger.warning(f"Batched const resolution failed ({e}); falling back per-name")
        for s in schemas:
            try:
                tmp = z3.Solver(ctx=z3_ctx)
                tmp.from_string(prelude + "\n" + body_clean
                                + f"\n(assert (= {s.guard_name}! {s.guard_name}!))")
                guard_consts[s.guard_name] = tmp.assertions()[-1].children()[0]
            except z3.Z3Exception:
                logger.warning(f"Missing guard const for schema {s.id}")
            for (pname, _pty) in s.k_params:
                try:
                    tmp = z3.Solver(ctx=z3_ctx)
                    tmp.from_string(prelude + "\n" + body_clean
                                    + f"\n(assert (= {pname}! {pname}!))")
                    k_consts[pname] = tmp.assertions()[-1].children()[0]
                except z3.Z3Exception:
                    logger.warning(f"Missing k const for schema {s.id}: {pname}")

    logger.info(f"Schema resolved: {len(guard_consts)} guards, {len(k_consts)} k-params")
    return SchemaCtx(
        z3_ctx=z3_ctx,
        solver=solver,
        schemas=schemas,
        guard_consts=guard_consts,
        k_consts=k_consts,
    )


# ---------------------------------------------------------------------------
# SearchContext duck-type
# ---------------------------------------------------------------------------

class SchemaSearchContext:
    """Duck-typed SearchContext that routes test_and_set to z3-py."""

    def __init__(
        self,
        det_spec: DetCheckSpec,
        schema_ctx: SchemaCtx,
    ):
        self.det_spec = det_spec
        self.a = schema_ctx
        self.tree = AssumeNode(key="root")
        self.trace: list[dict] = []
        self._round = 0
        self._schema_by_id = {s.id: s for s in schema_ctx.schemas}
        # Per-round timing
        self.check_time_ms = 0.0

    def _assumes_to_z3(self, assumes: list[Assume]) -> Optional[list[z3.BoolRef]]:
        """Translate a list of Rust assumes to z3 Bool constraints.

        Returns None if any assume can't be translated (caller should
        treat as "can't verify" → pass).
        """
        out: list[z3.BoolRef] = []
        for a in assumes:
            tr = translate_assume(a, self.a.schemas,
                                  self.det_spec.equal_fn_name)
            if tr is None:
                return None
            schema_id, k_bindings = tr
            s = self._schema_by_id[schema_id]
            g = self.a.guard_consts.get(s.guard_name)
            if g is None:
                return None
            out.append(g)
            for k_name, k_val in k_bindings.items():
                k_const = self.a.k_consts.get(k_name)
                if k_const is None:
                    return None
                out.append(k_const == k_val)
        return out

    def test_and_set(self, node, assume: Assume, phase: str = "") -> bool:
        """Mimic SearchContext.test_and_set but via z3-py."""
        old_assume = node.assume
        node.assume = assume

        all_assumes = self.tree.collect_assumes()
        bools = self._assumes_to_z3(all_assumes)

        self._round += 1
        p = phase or "search"

        if bools is None:
            # Unknown schema for at least one assume → treat as "pass"
            # (can't prove determinism; move on without keeping this assume).
            node.assume = old_assume
            self.trace.append({
                "round": self._round, "phase": p, "node_key": node.key,
                "assumes": [a.expression for a in all_assumes],
                "new_assume": assume.expression,
                "result": "pass_untranslatable",
                "description": assume.description,
            })
            logger.info(f"R{self._round} [{p}] {node.key}: {assume.expression} → pass (untranslatable)")
            return False

        # z3-py check via assumption list: solver.check(*bools) uses them
        # as unit assumptions, letting z3 keep learned clauses between
        # rounds (push/pop discards clauses from that scope).
        t0 = time.monotonic()
        r = self.a.solver.check(*bools)
        dt_ms = (time.monotonic() - t0) * 1000
        self.check_time_ms += dt_ms

        # Interpretation:
        #   unsat  → goal (not det_equal) with these assumes is UNSAT
        #            → determinism forced → assume was strong enough → "pass"
        #   sat/unknown → still a counterexample possible (or quantifier
        #            undecided) → "fail" (keep narrowing)
        if r == z3.unsat:
            status = "pass"
        else:
            status = "fail"

        self.trace.append({
            "round": self._round, "phase": p, "node_key": node.key,
            "assumes": [a.expression for a in all_assumes],
            "new_assume": assume.expression,
            "result": status,
            "description": assume.description,
            "z3_raw": str(r),
            "z3_ms": round(dt_ms, 2),
        })
        logger.info(f"R{self._round} [{p}] {node.key}: {assume.expression} → {status} ({dt_ms:.1f}ms)")

        if status == "fail":
            return True
        else:
            node.assume = old_assume
            return False


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run_schema_search(
    det_spec: DetCheckSpec,
    schema_ctx: SchemaCtx,
) -> Witness:
    """Run schema-driven search. Drives narrow() on an AssumeNode tree."""
    ctx = SchemaSearchContext(det_spec, schema_ctx)

    # R0: check baseline (no assumes)
    t0 = time.monotonic()
    r0 = schema_ctx.solver.check()
    r0_ms = (time.monotonic() - t0) * 1000
    ctx.trace.append({
        "round": 0, "phase": "initial", "node_key": "root",
        "assumes": [], "new_assume": None,
        "result": "pass" if r0 == z3.unsat else "fail",
        "description": "full determinism check (schema-driven z3-py)",
        "z3_raw": str(r0), "z3_ms": round(r0_ms, 2),
    })
    ctx._round = 0  # initial doesn't count as a search round

    if r0 == z3.unsat:
        logger.info(f"{det_spec.function}: deterministic (R0 unsat)")
        return Witness(function=det_spec.function, trace=ctx.trace)

    logger.info(f"{det_spec.function}: nondeterministic (R0 = {r0}), starting schema search")

    # Narrow each symbol.
    for sym in det_spec.symbols:
        sym_node = ctx.tree.get_or_create(sym.name)
        narrow(sym.type, sym.name, sym_node, ctx)

    # Distinctness.
    try:
        _add_distinctness_witnesses(ctx, det_spec)
    except Exception as e:
        logger.warning(f"distinctness step skipped: {e}")

    return Witness(
        function=det_spec.function,
        assumes=ctx.tree.collect_assumes(),
        trace=ctx.trace,
    )
