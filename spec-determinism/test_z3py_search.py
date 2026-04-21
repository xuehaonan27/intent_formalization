"""Smoke tests for src/z3py_search.

Validates:
 1. Prelude loads without errors.
 2. assert_fact + check returns expected sat/unsat.
 3. unsat_core returns the right labels.
 4. push/pop correctly restores state.
 5. Per-round overhead is in the milliseconds (not seconds).

Run with:  python -m pytest spec-determinism/test_z3py_search.py -v
or:        python spec-determinism/test_z3py_search.py
"""

import time
import sys
from pathlib import Path

import z3

sys.path.insert(0, str(Path(__file__).parent))
from src.z3py_search import (
    Z3PySearchContext, load_verus_prelude, find_top_level_constants,
)


SMT2_PATH = "/tmp/det-exp/log/root.smt2"   # produced by the earlier exp


def test_prelude_loads():
    prelude = load_verus_prelude(SMT2_PATH)
    assert "test!is_slab_variant.?" in prelude
    assert "(push)" not in prelude
    print(f"  prelude: {len(prelude)} bytes, no (push) inside — ok")


def test_basic_contradiction_and_core():
    ctx = Z3PySearchContext.from_smt2_path(SMT2_PATH)
    ctx.declare("(declare-const r1! test!Result.)")

    # Single-step contradiction via Verus spec fns.
    ctx.assert_fact("(test!is_slab_variant.? (Poly%test!Result. r1!))",
                    label="g_var")
    ctx.assert_fact("(= (test!slab_len.? (Poly%test!Result. r1!)) 3)",
                    label="g_len3")
    ctx.assert_fact("(= (test!slab_len.? (Poly%test!Result. r1!)) 5)",
                    label="g_len5")
    r = ctx.check()
    assert r == z3.unsat, f"expected unsat, got {r}"
    core = ctx.unsat_core()
    assert "g_len3" in core and "g_len5" in core, f"unexpected core: {core}"
    print(f"  unsat_core = {core} — ok")


def test_minimize_core_removes_redundant():
    ctx = Z3PySearchContext.from_smt2_path(SMT2_PATH)
    ctx.declare("(declare-const r1! test!Result.)")
    # variant assume is irrelevant for the len contradiction
    ctx.assert_fact("(test!is_slab_variant.? (Poly%test!Result. r1!))",
                    label="g_var")
    ctx.assert_fact("(= (test!slab_len.? (Poly%test!Result. r1!)) 3)",
                    label="g_len3")
    ctx.assert_fact("(= (test!slab_len.? (Poly%test!Result. r1!)) 5)",
                    label="g_len5")
    assert ctx.check() == z3.unsat
    raw = ctx.unsat_core()
    mus = ctx.minimize_core(raw)
    assert set(mus) == {"g_len3", "g_len5"}, f"MUS not minimal: {mus} from {raw}"
    print(f"  raw_core={raw}  →  MUS={mus} — ok")


def test_push_pop_restores_sat():
    ctx = Z3PySearchContext.from_smt2_path(SMT2_PATH)
    ctx.declare("(declare-const r1! test!Result.)")
    ctx.assert_fact("(test!is_slab_variant.? (Poly%test!Result. r1!))",
                    label="g_var")
    base = ctx.check()
    assert base in (z3.sat, z3.unknown), f"baseline: {base}"

    ctx.push()
    ctx.assert_fact("(= (test!slab_len.? (Poly%test!Result. r1!)) 3)",
                    label="g_len3_push")
    ctx.push()
    ctx.assert_fact("(= (test!slab_len.? (Poly%test!Result. r1!)) 5)",
                    label="g_len5_push")
    assert ctx.check() == z3.unsat
    ctx.pop()
    after = ctx.check()
    assert after in (z3.sat, z3.unknown), f"after pop: {after}"
    ctx.pop()
    print(f"  state correctly restored after pop — ok ({base} → unsat → {after})")


def test_per_round_speed():
    ctx = Z3PySearchContext.from_smt2_path(SMT2_PATH)
    ctx.declare("(declare-const r1! test!Result.)")
    ctx.assert_fact("(test!is_slab_variant.? (Poly%test!Result. r1!))",
                    label="g_var_speed")

    n = 200
    t0 = time.time()
    for i in range(n):
        ctx.push()
        ctx.assert_fact(
            f"(= (test!slab_len.? (Poly%test!Result. r1!)) {i})",
            label=f"g_speed_{i}")
        ctx.check()
        ctx.pop()
    elapsed_ms = (time.time() - t0) * 1000
    per_round = elapsed_ms / n
    print(f"  {n} push/check/pop rounds: {elapsed_ms:.1f} ms total, "
          f"{per_round:.2f} ms/round")
    # Sanity bound: must be at least 1000× faster than a Verus round (~30 s).
    assert per_round < 30.0, f"per-round {per_round} ms is too slow"


def test_find_top_level_constants():
    """Smoke: at least the spec fn `(declare-fun ... () SORT)` form is
    discoverable. (Our exp file doesn't have user-suffixed `_!` constants
    at top level — those live inside push blocks — so we exercise a
    different suffix.)"""
    prelude = load_verus_prelude(SMT2_PATH)
    # Verus generates `(declare-const fuel%test!is_slab_variant. FuelId)`
    # — these are 0-ary constants, so let's pick those up by suffix `.`.
    cs = find_top_level_constants(prelude, suffix=".")
    names = [n for n, _ in cs]
    assert any("fuel%test!is_slab_variant" in n for n in names), \
        f"didn't find fuel%test!is_slab_variant. in {names[:10]}"
    print(f"  found {len(cs)} top-level constants ending in `.` — ok")


if __name__ == "__main__":
    if not Path(SMT2_PATH).exists():
        print(f"  ⚠️  {SMT2_PATH} not found — re-run the experiment first")
        print("     (see chat log: experiment A in /tmp/det-exp)")
        sys.exit(1)
    tests = [
        test_prelude_loads,
        test_basic_contradiction_and_core,
        test_minimize_core_removes_redundant,
        test_push_pop_restores_sat,
        test_per_round_speed,
        test_find_top_level_constants,
    ]
    for t in tests:
        print(f"--- {t.__name__} ---")
        t()
    print("\nall smoke tests passed.")
