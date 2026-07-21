"""Hand-pilot: deep-sampling refinement on z3 'unknown' cases.

For each chosen artifact:
  1. Run Verus on injected.rs to regen smt2
  2. Build schema_ctx
  3. Enumerate all schemas; group by symbol + kind
  4. Generate N parallel "deep samples", each enabling K schemas at once
     with diversity heuristics (no contradictory pairs, r1 vs r2 pinned to
     different values when possible).
  5. For each sample: solver.push(); add asserts for guard=T + k=v; check;
     pop. Record result.
  6. Report sat / unsat / unknown counts; if any sat, print the model.
"""
from __future__ import annotations
import json, sys, shutil, subprocess, tempfile, time, random, itertools
from pathlib import Path
from collections import defaultdict

ROOT = Path("/home/xuehaonan/intent_formalization")
sys.path.insert(0, str(ROOT / "spec-determinism"))

from spec_determinism.extract.types import DetCheckSpec
from spec_determinism.schema_search.schemas import enumerate_schemas, SchemaKind
from spec_determinism.schema_search.search import build_schema_ctx
import z3

VERUS = Path.home() / "nanvix/toolchain/verus" / "verus"
ART_ROOT = ROOT / "spec-determinism/results-verusage/atmosphere/artifacts"


def regen_smt2(art_dir: Path) -> tuple[Path, Path]:
    """Returns (tmp_dir, smt2_path). Caller owns tmp_dir."""
    tmp = Path(tempfile.mkdtemp(prefix=f"sample_{art_dir.name[:20]}_"))
    shutil.copy(art_dir / "injected.rs", tmp / "injected.rs")
    log_dir = tmp / "log"
    log_dir.mkdir()
    subprocess.run(
        [str(VERUS), str(tmp / "injected.rs"),
         "--log-all", "--log-dir", str(log_dir)],
        capture_output=True, timeout=180,
    )
    smt2s = sorted(log_dir.rglob("*.smt2"),
                   key=lambda p: (p.name == "root.smt2", p.stat().st_size))
    return tmp, smt2s[-1]


def k_value_for_schema(s, alt: int = 0) -> dict[str, int]:
    """Return concrete k assignments for a schema; alt picks among
    {0, 1, small, large} alternatives so we can pin r1/r2 to *different*
    values."""
    out = {}
    for (name, _ty) in s.k_params:
        # use alt to pick distinct values
        v = [0, 1, 2, 5, 7, 16, 64][alt % 7]
        out[name] = v
    return out


def group_schemas_by_symbol(schemas):
    """Group schemas by top-level symbol (first dotted/arrow component of
    rust_var). Returns dict: symbol -> list[SchemaBinding]."""
    out = defaultdict(list)
    for s in schemas:
        v = s.rust_var
        # crude: split on . or -> or [ or @
        head = v.split(".")[0].split("->")[0].split("@")[0].split("[")[0]
        head = head.strip().strip("(")
        out[head].append(s)
    return out


def is_r1_r2_pair(name1: str, name2: str) -> bool:
    """Check whether two rust_var strings refer to corresponding components
    of r1 and r2 (so pinning them to different k yields a witness)."""
    if not (name1.startswith("r1") and name2.startswith("r2")): return False
    return name1[2:] == name2[2:]


def make_samples(schemas, ctx, n_samples=200, k_per_sample=10, seed=0):
    """Yield n_samples deep samples; each is a list[(SchemaBinding, k_alt)].

    Strategy: pick ≤1 per (symbol, kind), prefer r1/r2 PAIRS pinned to
    DIFFERENT k values so witness has fighting chance.
    """
    rng = random.Random(seed)
    by_sym = group_schemas_by_symbol(schemas)
    # find r1/r2 paired schemas
    r1s = {s.rust_var: s for s in schemas if s.rust_var.startswith("r1")}
    r2s = {s.rust_var: s for s in schemas if s.rust_var.startswith("r2")}
    pairs = []
    for v1, s1 in r1s.items():
        v2 = "r2" + v1[2:]
        if v2 in r2s and r2s[v2].kind == s1.kind:
            pairs.append((s1, r2s[v2]))

    for i in range(n_samples):
        chosen = []
        # pick up to k_per_sample r1/r2 pairs with different k values
        if pairs:
            picked = rng.sample(pairs, min(len(pairs), k_per_sample // 2 + 1))
            for (s1, s2) in picked:
                # if VARIANT_IS / BOOL_EQ have no k, both must same variant — skip those
                if s1.kind in (SchemaKind.VARIANT_IS, SchemaKind.BOOL_EQ, SchemaKind.SET_EMPTY, SchemaKind.SET_LEN_GT):
                    # pin both to same (will give unsat unless variant differs)
                    chosen.append((s1, 0)); chosen.append((s2, 1))  # asymmetric anyway via guard
                else:
                    # different k values to maximize witness chance
                    chosen.append((s1, i % 7)); chosen.append((s2, (i + 1) % 7))
        # fill remainder with random non-r1/r2 schemas (state, pre_self_, etc.)
        rest = [s for s in schemas if not s.rust_var.startswith(("r1", "r2"))]
        if rest:
            for s in rng.sample(rest, min(len(rest), max(0, k_per_sample - len(chosen)))):
                chosen.append((s, i % 7))
        yield chosen


def assert_sample(ctx, sample, neq_guard):
    """Push asserts for one sample: enable each chosen guard + assign its k.
    Always also enable g_neq_tuple (the !equal_T(r1,r2) witness guard).
    Returns the asserted boolean assumptions list."""
    assumptions = []
    seen_guards = set()
    for (s, alt) in sample:
        g = ctx.guard_consts.get(s.guard_name)
        if g is None: continue
        if s.guard_name in seen_guards: continue
        seen_guards.add(s.guard_name)
        assumptions.append(g)
        for (kname, _ty) in s.k_params:
            kvar = ctx.k_consts.get(kname)
            if kvar is None: continue
            v = k_value_for_schema(s, alt)[kname]
            assumptions.append(kvar == v)
    # Always include the witness guard
    if neq_guard is not None:
        assumptions.append(neq_guard)
    return assumptions


def pilot(art_key: str, n_samples=200, k_per_sample=10):
    print(f"\n========= {art_key} =========")
    art_dir = ART_ROOT / art_key
    spec = DetCheckSpec.from_dict(json.loads((art_dir / "det_spec.json").read_text()))

    tmp, smt2 = regen_smt2(art_dir)
    try:
        schemas = enumerate_schemas(spec)
        ctx = build_schema_ctx(smt2, spec.check_fn_name, schemas, "injected")
        print(f"  n_schemas={len(schemas)}  smt2_bytes={smt2.stat().st_size}")

        # 1) Baseline R0
        t0 = time.monotonic()
        r0 = ctx.solver.check()
        print(f"  R0  → {r0}  ({(time.monotonic()-t0)*1000:.0f} ms)")
        if str(r0) != "unknown":
            return

        # 2) Deep sampling
        neq_guard = next((ctx.guard_consts.get(s.guard_name)
                          for s in schemas if s.kind == SchemaKind.NOT_EQUAL_FN),
                         None)
        counters = {"sat": 0, "unsat": 0, "unknown": 0}
        first_sat = None
        t1 = time.monotonic()
        for i, sample in enumerate(make_samples(schemas, ctx,
                                               n_samples=n_samples,
                                               k_per_sample=k_per_sample,
                                               seed=42)):
            assumptions = assert_sample(ctx, sample, neq_guard)
            ctx.solver.push()
            r = ctx.solver.check(*assumptions)
            counters[str(r)] = counters.get(str(r), 0) + 1
            if str(r) == "sat" and first_sat is None:
                first_sat = (i, ctx.solver.model())
                ctx.solver.pop()
                break
            ctx.solver.pop()
        dt = (time.monotonic() - t1)
        print(f"  sampled {sum(counters.values())} in {dt:.1f}s")
        print(f"    sat   : {counters['sat']}")
        print(f"    unsat : {counters['unsat']}")
        print(f"    unknown: {counters['unknown']}")
        if first_sat:
            i, m = first_sat
            print(f"  >>> first sat at sample #{i} — z3 produced a concrete model")
            # show a tiny excerpt
            decls = list(m.decls())[:8]
            for d in decls:
                print(f"      {d.name()}() = {m[d]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    # 5 picked spread + 1 nested-Option
    targets = [
        # n_schemas=1 — minimal, fast
        "atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__alloc_and_map_2m__pop",
        # n_schemas=3
        "atmosphere__verified__slinkedlist__slinkedlist__spec_impl_u__impl2__push__set_value",
        # nested Option, opt-heavy
        "atmosphere__verified__kernel__kernel__create_and_map_pages__impl0__check_address_space_va_range_free__resolve_pagetable_mapping",
        # Set-heavy mid
        "atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k__add_io_mapping_4k",
        # Set-heavy large
        "atmosphere__verified__kernel__kernel__syscall_send_empty_try_schedule__impl0__syscall_send_empty_try_schedule__syscall_send_empty_try_schedule",
    ]
    if len(sys.argv) > 1:
        targets = [sys.argv[1]]
    for t in targets:
        try:
            pilot(t, n_samples=200, k_per_sample=10)
        except Exception as e:
            import traceback
            print(f"  ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
