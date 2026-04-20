#!/usr/bin/env python3
"""
Full completeness test: run spec-determinism on all executable functions
in bitmap and slab crates.
"""

import sys, os, json, time, logging, traceback
sys.path.insert(0, os.path.dirname(__file__))

from src.types import *
from src.extract import extract_spec
from src.gen_det import build_det_check_spec, render_template
from src.equal_policy import EqualPolicy
from src.verify import VerusRunner
from src.binary_search import binary_search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

NANVIX = os.path.expanduser("~/nanvix")
VERUS_PATH = os.path.join(NANVIX, "toolchain/verus")

# ---------------------------------------------------------------------------
# Crate configs
# ---------------------------------------------------------------------------

BITMAP_CFG = {
    "crate_name": "bitmap",
    "src": os.path.join(NANVIX, "src/libs/bitmap/src/lib.rs"),
    "spec": os.path.join(NANVIX, "src/libs/bitmap/src/lib.spec.rs"),
    "proof": os.path.join(NANVIX, "src/libs/bitmap/src/lib.proof.rs"),
    "features": ["std"],
    "extra_type_sources": [
        os.path.join(NANVIX, "src/libs/error/src/lib.rs"),
    ],
    "functions": [
        "number_of_bits", "new", "from_raw_array",
        "alloc", "alloc_range", "set", "clear", "test",
    ],
    "check_name_overrides": {"alloc_range": "det_alloc_range_chk"},
    "use_llm_equal_policy": True,
}

SLAB_CFG = {
    "crate_name": "slab",
    "src": os.path.join(NANVIX, "src/libs/slab/src/lib.rs"),
    "spec": os.path.join(NANVIX, "src/libs/slab/src/lib.spec.rs"),
    "proof": os.path.join(NANVIX, "src/libs/slab/src/lib.proof.rs"),
    "features": ["std"],
    "extra_type_sources": [
        os.path.join(NANVIX, "src/libs/error/src/lib.rs"),
    ],
    "functions": ["from_raw_parts", "allocate", "deallocate"],
    # Avoid name collision with existing det_allocate in slab proof file
    "check_name_overrides": {"allocate": "det_allocate_chk"},
    "use_llm_equal_policy": True,
}

# kheap lives inside the kernel crate. Verifying the kernel needs build-std +
# the custom kernel target file (mirrors `verify-kernel` in the Makefile).
KHEAP_CFG = {
    "crate_name": "kernel",
    "src": os.path.join(NANVIX, "src/kernel/src/mm/kheap.rs"),
    "spec": os.path.join(NANVIX, "src/kernel/src/mm/kheap.spec.rs"),
    "proof": os.path.join(NANVIX, "src/kernel/src/mm/kheap.proof.rs"),
    "features": ["microvm", "error"],
    "extra_args": [
        "-Z", "build-std=core,alloc,compiler_builtins",
        "-Z", "build-std-features=compiler-builtins-mem",
        "--target", os.path.join(NANVIX, "build/targets/x86-kernel.json"),
    ],
    "functions": [
        "from_raw_parts", "allocate", "deallocate", "layout_to_allocator",
    ],
    "check_name_overrides": {},
    # Error struct / ErrorCode enum live in the error crate
    "extra_type_sources": [
        os.path.join(NANVIX, "src/libs/error/src/lib.rs"),
    ],
    # kheap.allocate / deallocate verify slow — bump timeout
    "timeout": 300,
    # Scope verify to this module (with --verify-function det_<name>)
    # to dodge proof-stability collateral on unrelated kernel functions.
    "verify_module": "mm::kheap",
    "use_llm_equal_policy": True,
}

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

results = []

def run_crate(cfg):
    crate = cfg["crate_name"]
    with open(cfg["src"]) as f:
        src = f.read()

    type_sources = []
    if os.path.exists(cfg["spec"]):
        with open(cfg["spec"]) as f:
            type_sources.append(f.read())
    for extra in cfg.get("extra_type_sources", []):
        if os.path.exists(extra):
            with open(extra) as f:
                type_sources.append(f.read())

    runner = VerusRunner(
        crate_dir=NANVIX,
        crate_name=crate,
        proof_file=cfg["proof"],
        verus_path=VERUS_PATH,
        features=cfg.get("features"),
        timeout=cfg.get("timeout", 120),
        extra_args=cfg.get("extra_args"),
        verify_module=cfg.get("verify_module"),
    )

    for fn_name in cfg["functions"]:
        print(f"\n{'='*70}")
        print(f"  {crate}::{fn_name}")
        print(f"{'='*70}")
        t0 = time.time()
        entry = {"crate": crate, "function": fn_name}

        # --- Step 1: Extract ---
        try:
            spec = extract_spec(src, fn_name, type_sources=type_sources)
        except Exception as e:
            elapsed = time.time() - t0
            entry.update(status="extract_fail", error=str(e), elapsed=elapsed)
            results.append(entry)
            print(f"  ⚠️  Extract failed: {e}")
            continue

        # --- Step 2: Gen det check ---
        try:
            check_name = cfg.get("check_name_overrides", {}).get(fn_name)
            # Per-function equal-fn policy. Precedence:
            #   1. explicit equal_policy_overrides[fn_name]
            #   2. LLM suggestion (if use_llm_equal_policy enabled + client)
            #   3. default (errs_equivalent=True).
            manual_overrides = cfg.get("equal_policy_overrides", {})
            if fn_name in manual_overrides:
                policy = EqualPolicy.from_dict(manual_overrides[fn_name])
                print(f"  Policy: manual override → {policy.to_dict()}")
            elif cfg.get("use_llm_equal_policy"):
                from src.equal_llm import suggest_equal_policy
                llm_policy = suggest_equal_policy(
                    spec, workspace=NANVIX,
                    cache_dir=cfg.get("policy_cache_dir", "results/refine_cache"),
                )
                policy = llm_policy if llm_policy is not None else EqualPolicy()
                origin = "LLM" if llm_policy is not None else "default (LLM kept)"
                print(f"  Policy: {origin} → {policy.to_dict()}")
            else:
                policy = EqualPolicy()
            det_spec = build_det_check_spec(
                spec, check_name=check_name, equal_policy=policy
            )
        except Exception as e:
            elapsed = time.time() - t0
            entry.update(status="gen_fail", error=str(e), elapsed=elapsed)
            results.append(entry)
            print(f"  ⚠️  Gen failed: {e}")
            continue

        print(f"  Symbols ({len(det_spec.symbols)}):")
        for sym in det_spec.symbols:
            print(f"    [{sym.phase}] {sym.name}: {sym.type.kind.value}")

        # --- Dump intermediate artefacts for review ---
        # results/artifacts/<crate>__<fn>/{det_spec.json,template.rs}
        art_dir = os.path.join("results", "artifacts", f"{crate}__{fn_name}")
        os.makedirs(art_dir, exist_ok=True)
        with open(os.path.join(art_dir, "det_spec.json"), "w") as f:
            f.write(det_spec.to_json())
        with open(os.path.join(art_dir, "template.rs"), "w") as f:
            f.write(render_template(det_spec, []))
        entry["artifact_dir"] = art_dir

        # --- Step 3: Binary search ---
        try:
            witness = binary_search(det_spec, runner)
        except Exception as e:
            elapsed = time.time() - t0
            entry.update(status="search_fail", error=str(e),
                         error_trace=traceback.format_exc(), elapsed=elapsed)
            results.append(entry)
            print(f"  ⚠️  Search failed: {e}")
            continue

        elapsed = time.time() - t0
        rounds = len(witness.trace)

        # Classify result
        if not witness.trace:
            status = "unknown"
        else:
            r0 = witness.trace[0].get("result")
            smoke_err = witness.trace[0].get("smoke_test_error")
            if r0 == "pass":
                status = "deterministic"
            elif smoke_err:
                status = "verify_error"
            elif witness.assumes:
                status = "nondeterministic"
            else:
                status = "nondeterministic_no_witness"

        entry.update(
            status=status,
            rounds=rounds,
            verus_calls=runner.call_count,
            elapsed=round(elapsed, 1),
            assumes=[a.expression for a in witness.assumes] if witness.assumes else [],
        )
        if status == "verify_error" and witness.trace:
            entry["error"] = witness.trace[0].get("smoke_test_error", "")[:500]
        results.append(entry)

        # Print trace
        print(f"\n  Trace ({rounds} rounds):")
        for step in witness.trace[:5]:
            r = step["round"]
            s = "❌ FAIL" if step["result"] == "fail" else "✅ PASS" if step["result"] == "pass" else f"⚠️  {step['result']}"
            assume = step.get("new_assume", "—") or "—"
            print(f"    R{r}: {s}  {assume}")
        if rounds > 5:
            print(f"    ... ({rounds - 5} more rounds)")

        if status == "deterministic":
            print(f"\n  ✅ Deterministic  ({elapsed:.1f}s)")
        elif status == "nondeterministic":
            print(f"\n  ❌ Nondeterministic  ({rounds} rounds, {elapsed:.1f}s)")
            print(f"  Final assumes ({len(witness.assumes)}):")
            for a in witness.assumes:
                print(f"    {a.expression}")
        elif status == "verify_error":
            print(f"\n  ⚠️  Verify error  ({elapsed:.1f}s)")
        else:
            print(f"\n  ❓ {status}  ({elapsed:.1f}s)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

print("=" * 70)
print("  spec-determinism: full completeness test")
print("  bitmap (8 fns) + slab (3 fns) + kheap (4 fns)")
print("=" * 70)

run_crate(BITMAP_CFG)
run_crate(SLAB_CFG)
run_crate(KHEAP_CFG)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n\n{'='*70}")
print(f"  SUMMARY")
print(f"{'='*70}")
print(f"\n{'Function':<30} {'Status':<25} {'Rounds':>6} {'Time':>8}")
print("-" * 70)
for r in results:
    name = f"{r['crate']}::{r['function']}"
    status = r["status"]
    rounds = str(r.get("rounds", "—"))
    elapsed = f"{r.get('elapsed', 0):.0f}s"
    icon = {
        "deterministic": "✅",
        "nondeterministic": "❌",
        "verify_error": "⚠️ ",
        "extract_fail": "⚠️ ",
        "gen_fail": "⚠️ ",
        "search_fail": "⚠️ ",
    }.get(status, "❓")
    print(f"  {icon} {name:<28} {status:<23} {rounds:>6} {elapsed:>8}")

# Save results
os.makedirs("results", exist_ok=True)
with open("results/full_test_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to results/full_test_results.json")
