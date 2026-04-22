#!/usr/bin/env python3
"""
Quick integration test: run spec-determinism on bitmap::alloc.

Since the extract module may not handle the verus_spec macro perfectly,
we manually construct the FunctionSpec and test the binary search.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.types import (
    TypeKind, TypeInfo, FieldInfo, VariantInfo,
    Param, FunctionSpec, Assume,
)
from src.gen_det import generate_det_check
from src.verify import VerusRunner
from src.binary_search import binary_search

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---- Manually construct FunctionSpec for bitmap::alloc ----

# BitmapView { num_bits: int, set_bits: Set<int> }
bitmap_view = TypeInfo(
    kind=TypeKind.STRUCT, name="BitmapView",
    fields=[
        FieldInfo("num_bits", TypeInfo(kind=TypeKind.INT, name="int")),
        FieldInfo("set_bits", TypeInfo(kind=TypeKind.SET, name="Set<int>",
                                       type_args=[TypeInfo(kind=TypeKind.INT, name="int")])),
    ],
)

bitmap_type = TypeInfo(
    kind=TypeKind.STRUCT, name="Bitmap",
    spec_view=bitmap_view,
)

error_type = TypeInfo(kind=TypeKind.UNKNOWN, name="Error")

return_type = TypeInfo(
    kind=TypeKind.RESULT, name="Result<usize, Error>",
    variants=[
        VariantInfo("Ok", TypeInfo(kind=TypeKind.USIZE, name="usize")),
        VariantInfo("Err", error_type),
    ],
    type_args=[
        TypeInfo(kind=TypeKind.USIZE, name="usize"),
        error_type,
    ],
)

alloc_spec = FunctionSpec(
    name="alloc",
    params=[
        Param(name="self", type=bitmap_type, is_mut_ref=True, is_ref=True, is_self=True),
    ],
    return_type=return_type,
    requires=[
        "pre_self_.inv()",
    ],
    ensures=[
        """__POST__.inv()
        && (match __RESULT__ {
            Ok(index) => {
                &&& 0 <= index < __POST__@.num_bits
                &&& __POST__@.num_bits == __PRE__@.num_bits
                &&& !__PRE__@.is_bit_set(index as int)
                &&& __POST__@.is_bit_set(index as int)
                &&& forall|i: int| 0 <= i < __POST__@.num_bits && i != index
                    ==> __POST__@.is_bit_set(i) == __PRE__@.is_bit_set(i)
                &&& __POST__@.set_bits == __PRE__@.set_bits.insert(index as int)
                &&& __POST__@.usage() == __PRE__@.usage() + 1
            },
            Err(_) => {
                &&& __PRE__@.is_full()
                &&& __POST__@ == __PRE__@
            },
        })""",
    ],
    type_defs={"Bitmap": bitmap_type, "BitmapView": bitmap_view},
)

# ---- Step 1: Just test gen_det output ----

print("=" * 60)
print("Step 1: Generated det check code")
print("=" * 60)
code = generate_det_check(alloc_spec)
print(code)
print()

# ---- Step 2: Test with Verus ----

print("=" * 60)
print("Step 2: Running Verus...")
print("=" * 60)

runner = VerusRunner(
    crate_dir=os.path.expanduser("~/nanvix"),
    crate_name="bitmap",
    proof_file=os.path.expanduser("~/nanvix/src/libs/bitmap/src/lib.proof.rs"),
    verus_path=os.path.expanduser("~/nanvix/toolchain/verus"),
    features=["std"],
    timeout=120,
)

result = runner.check(code, "det_alloc")
print(f"Result: {result.status}")
if result.status == "error":
    print(f"Error details:\n{result.stderr[:1000]}")

if result.status == "fail":
    print("\n✅ Nondeterminism detected! Now running binary search...")
    print("=" * 60)
    print("Step 3: Binary search")
    print("=" * 60)

    witness = binary_search(alloc_spec, runner)

    print(f"\nTrace ({len(witness.trace)} rounds):")
    for step in witness.trace:
        r = step["round"]
        status = "❌ FAIL" if step["result"] == "fail" else "✅ PASS"
        assume = step.get("new_assume", "—") or "—"
        print(f"  R{r}: {status}  {assume}")

    print(f"\nFinal assumes ({len(witness.assumes)}):")
    for a in witness.assumes:
        print(f"  {a.expression}")
elif result.status == "pass":
    print("Spec is deterministic — no nondeterminism found.")
