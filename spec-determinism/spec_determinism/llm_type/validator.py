"""Tier 1.5 — validator gates V1..V3.

Each gate is a pure function returning ``(ok: bool, reason: str)``.
The runner calls them in order; on the first failure the patch is
rejected and recorded with the reason.

V1 evidence-existence
    Open ``<project_root>/<rel_path>``, read line ``<line>`` ± 3 lines,
    assert the patch's ``snippet`` substring is present (whitespace
    normalised). Catches LLM hallucinations of source locations.

V2 type-str parses
    ``parse_type_str`` round-trips every ``type_str`` field on the patch
    (fields, variant inners, spec_view). Catches malformed type
    expressions before they reach gen_det.

V3 codegen smoke
    Apply the patch to a *copy* of the spec, run gen_det in dry-run mode,
    confirm no exception. Catches structural mismatches (e.g. wrong
    arity on a generic).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from spec_determinism.extract.types import FunctionSpec

from .apply import TypePatch, _patch_to_typeinfo


@dataclass
class GateResult:
    ok: bool
    reason: str = ""


def _normalise_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def v1_evidence_exists(
    p: TypePatch,
    project_root: str,
    window: int = 3,
) -> GateResult:
    """V1: patch.source_snippet must appear within ±window lines of
    ``source_line`` in ``project_root / source_rel_path``."""
    if not p.source_rel_path or not p.source_snippet:
        return GateResult(False, "V1: missing source_evidence (rel_path or snippet)")
    abs_path = os.path.join(project_root, p.source_rel_path)
    if not os.path.isfile(abs_path):
        return GateResult(False, f"V1: file not found: {p.source_rel_path}")
    try:
        with open(abs_path, encoding="utf-8", errors="replace") as fp:
            lines = fp.readlines()
    except OSError as e:
        return GateResult(False, f"V1: read error: {e}")

    snippet = _normalise_ws(p.source_snippet)
    if not snippet:
        return GateResult(False, "V1: empty snippet after ws-normalise")

    line = max(1, min(p.source_line, len(lines)))
    lo = max(0, line - 1 - window)
    hi = min(len(lines), line - 1 + window + 1)
    blob = _normalise_ws(" ".join(lines[lo:hi]))
    if snippet not in blob:
        # Also try a wider window (full file) as a fallback before failing,
        # so a slightly-wrong line number doesn't trash an otherwise-valid
        # patch. The hard requirement is presence in source.
        full = _normalise_ws(" ".join(lines))
        if snippet not in full:
            return GateResult(
                False,
                f"V1: snippet not found in {p.source_rel_path} "
                f"(±{window} of L{p.source_line}, nor anywhere in file)",
            )
        return GateResult(
            True,
            f"V1: snippet found in file but not within ±{window} of L{p.source_line} "
            "(line number imprecise)",
        )
    return GateResult(True)


def v2_type_strs_parse(p: TypePatch) -> GateResult:
    """V2: every ``type_str`` round-trips through parse_type_str."""
    try:
        _patch_to_typeinfo(p)
    except ValueError as e:
        return GateResult(False, f"V2: type_str parse failed: {e}")
    return GateResult(True)


def v3_codegen_smoke(
    spec: FunctionSpec,
    patches: list[TypePatch],
) -> GateResult:
    """V3: applying ``patches`` to a deep-copy of ``spec`` then running
    gen_det must not raise.

    We import gen_det lazily so this module has no hard dependency on a
    fully-wired codegen subpackage during unit tests.
    """
    import copy
    spec_copy = copy.deepcopy(spec)
    from .apply import apply_patches
    apply_patches(spec_copy, patches)
    try:
        from spec_determinism.codegen import gen_det as _gen_det
    except Exception as e:  # pragma: no cover
        return GateResult(False, f"V3: cannot import gen_det: {e}")
    try:
        # gen_det.build_det_artifact / build_injected — pick whichever exists.
        # The contract is "no exception when fed the patched spec".
        for fn_name in (
            "build_det_artifact", "build_injected", "gen_det", "build",
        ):
            fn = getattr(_gen_det, fn_name, None)
            if fn is not None:
                fn(spec_copy)
                break
        else:
            return GateResult(
                False,
                "V3: gen_det module has none of build_det_artifact/"
                "build_injected/gen_det/build",
            )
    except Exception as e:
        return GateResult(False, f"V3: gen_det raised: {type(e).__name__}: {e}")
    return GateResult(True)


def run_gates(
    spec: FunctionSpec,
    patches: list[TypePatch],
    project_root: str,
    *,
    skip_v3: bool = False,
) -> tuple[list[TypePatch], list[tuple[TypePatch, GateResult]]]:
    """Filter ``patches`` to those passing all enabled gates.
    Returns ``(accepted, rejected_with_reason)``.

    V3 is run once on the accepted set as a whole (post-V1/V2), since
    individual patches may depend on each other.
    """
    accepted: list[TypePatch] = []
    rejected: list[tuple[TypePatch, GateResult]] = []

    for p in patches:
        r1 = v1_evidence_exists(p, project_root)
        if not r1.ok:
            rejected.append((p, r1))
            continue
        r2 = v2_type_strs_parse(p)
        if not r2.ok:
            rejected.append((p, r2))
            continue
        accepted.append(p)

    if not skip_v3 and accepted:
        r3 = v3_codegen_smoke(spec, accepted)
        if not r3.ok:
            # Roll back the whole batch — we cannot localise which patch
            # broke codegen without re-running per-subset.
            rejected.extend((p, r3) for p in accepted)
            accepted = []

    return accepted, rejected


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    import tempfile, textwrap
    from spec_determinism.extract.types import (
        FunctionSpec, Param, TypeInfo as TI, TypeKind as TK,
    )

    ok = True

    # Build a tiny tempdir project with one source file.
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "src")
        os.makedirs(src)
        path = os.path.join(src, "host.rs")
        with open(path, "w") as f:
            f.write(textwrap.dedent("""\
                pub struct HashMap<V> {
                    pub m: collections::HashMap<EndPoint, V>,
                }
                impl<V> HashMap<V> {
                    // line 5
                    pub uninterp spec fn view(self) -> Map<EndPoint, V>;
                }
            """))

        good = TypePatch(
            name="HashMap", kind="struct", type_params=["V"],
            fields=[("m", "u8")],
            spec_view_type_str="Map<EndPoint, V>",
            source_rel_path="src/host.rs", source_line=6,
            source_snippet="pub uninterp spec fn view(self) -> Map<EndPoint, V>;",
        )
        bad_snippet = TypePatch(
            name="HashMap", kind="struct",
            fields=[("m", "u8")],
            source_rel_path="src/host.rs", source_line=6,
            source_snippet="this string does not appear anywhere",
        )
        bad_parse = TypePatch(
            name="HashMap", kind="struct",
            fields=[("m", "totally not a type @@@ ;;; <<<")],
            source_rel_path="src/host.rs", source_line=6,
            source_snippet="pub uninterp spec fn view(self) -> Map<EndPoint, V>;",
        )
        wrong_path = TypePatch(
            name="HashMap", kind="struct", fields=[],
            source_rel_path="src/nonexistent.rs", source_line=1,
            source_snippet="anything",
        )

        # V1 good
        r = v1_evidence_exists(good, td)
        if not r.ok:
            print(f"FAIL V1 good: {r.reason}"); ok = False
        # V1 bad snippet
        r = v1_evidence_exists(bad_snippet, td)
        if r.ok:
            print("FAIL V1 bad_snippet: should have rejected"); ok = False
        # V1 wrong path
        r = v1_evidence_exists(wrong_path, td)
        if r.ok:
            print("FAIL V1 wrong_path: should have rejected"); ok = False

        # V2 good
        r = v2_type_strs_parse(good)
        if not r.ok:
            print(f"FAIL V2 good: {r.reason}"); ok = False
        # V2 bad type_str
        r = v2_type_strs_parse(bad_parse)
        if r.ok:
            print("FAIL V2 bad_parse: should have rejected"); ok = False

        # run_gates (skip V3 since gen_det may need more wired-up spec)
        spec = FunctionSpec(
            name="f",
            params=[Param(name="h", type=TI(TK.UNKNOWN, "HashMap<u8>"))],
            return_type=TI(TK.UNIT, "()"),
            requires=[], ensures=[], type_defs={},
        )
        accepted, rejected = run_gates(
            spec,
            [good, bad_snippet, bad_parse],
            td,
            skip_v3=True,
        )
        if len(accepted) != 1 or accepted[0] is not good:
            print(f"FAIL run_gates: accepted should be [good], got {accepted}")
            ok = False
        if len(rejected) != 2:
            print(f"FAIL run_gates: expected 2 rejected, got {len(rejected)}")
            ok = False

    print("validator self-test:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
