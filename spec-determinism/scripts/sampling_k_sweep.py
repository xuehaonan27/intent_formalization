"""K-sweep on the big 127-schema case to see if bigger samples close it."""
import json, sys, shutil, subprocess, tempfile, time, random
from pathlib import Path
ROOT = Path("/home/xuehaonan/intent_formalization")
sys.path.insert(0, str(ROOT / "spec-determinism"))
from spec_determinism.extract.types import DetCheckSpec
from spec_determinism.schema_search.schemas import enumerate_schemas, SchemaKind
from spec_determinism.schema_search.search import build_schema_ctx
import z3

VERUS = Path.home() / "nanvix/toolchain/verus" / "verus"
ART_ROOT = ROOT / "spec-determinism/results-verusage/atmosphere/artifacts"

sys.path.insert(0, str(ROOT / "spec-determinism/scripts"))
from sampling_pilot import regen_smt2, make_samples, assert_sample, group_schemas_by_symbol

KEY = "atmosphere__verified__kernel__kernel__syscall_send_empty_try_schedule__impl0__syscall_send_empty_try_schedule__syscall_send_empty_try_schedule"
KEY_SMALL = "atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k__add_io_mapping_4k"

def run(art_key, k_list=(10, 20, 40, 80), n=50):
    art_dir = ART_ROOT / art_key
    spec = DetCheckSpec.from_dict(json.loads((art_dir / "det_spec.json").read_text()))
    tmp, smt2 = regen_smt2(art_dir)
    try:
        schemas = enumerate_schemas(spec)
        ctx = build_schema_ctx(smt2, spec.check_fn_name, schemas, "injected")
        by_sym = group_schemas_by_symbol(schemas)
        print(f"\n=== {art_key[-60:]} ===")
        print(f"  n_schemas={len(schemas)}  symbols={len(by_sym)}  kind_breakdown:")
        from collections import Counter
        kc = Counter(s.kind.name for s in schemas)
        for k,v in kc.most_common(): print(f"     {k:20s} {v}")
        neq = next((ctx.guard_consts.get(s.guard_name) for s in schemas
                    if s.kind == SchemaKind.NOT_EQUAL_FN), None)
        # baseline
        t0=time.monotonic(); r0=ctx.solver.check(); t=(time.monotonic()-t0)*1000
        print(f"  R0 → {r0}  ({t:.0f} ms)")
        for K in k_list:
            counters = {"sat":0,"unsat":0,"unknown":0}
            t0=time.monotonic()
            for sample in make_samples(schemas, ctx, n_samples=n, k_per_sample=K, seed=42):
                a = assert_sample(ctx, sample, neq)
                ctx.solver.push()
                r = ctx.solver.check(*a)
                counters[str(r)] = counters.get(str(r),0)+1
                ctx.solver.pop()
            dt=time.monotonic()-t0
            print(f"  K={K:3d} n={n}: sat={counters['sat']} unsat={counters['unsat']} unknown={counters['unknown']}  ({dt:.1f}s)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__=="__main__":
    # Big case
    run(KEY, k_list=(10, 30, 60, 100), n=30)
    # And the n_schemas=1 case — let's see why
    run(KEY_SMALL, k_list=(5,10), n=20)
