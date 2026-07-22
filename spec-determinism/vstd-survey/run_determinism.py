#!/usr/bin/env python3
"""Run spec-determinism on vstd exec functions with explicit postconditions."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import re
import shutil
import sys
import time
import traceback
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR))

from spec_determinism.classify import classify_ok
from spec_determinism.codegen.equal_policy import EqualPolicy
from spec_determinism.codegen.gen_det import build_det_check_spec
from spec_determinism.extract.extractor import extract_spec
from spec_determinism.schema_search import (
    enumerate_schemas,
    render_guarded_template,
)
from spec_determinism.schema_search.search import (
    build_schema_ctx,
    run_schema_search,
)
from spec_determinism.verus.single_file import run_verus_file
from spec_determinism.view.registry import ViewRegistry


PILOT_TARGETS = [
    "array:array_index_get",
    "array:array_as_slice",
    "array:array_fill_for_copy_types",
    "array:ref_mut_array_unsizing_coercion",
    "bytes:u16_from_le_bytes",
    "bytes:u16_to_le_bytes",
    "bytes:u32_from_le_bytes",
    "bytes:u32_to_le_bytes",
    "bytes:u64_from_le_bytes",
    "bytes:u64_to_le_bytes",
    "bytes:u128_from_le_bytes",
    "bytes:u128_to_le_bytes",
]

EXTRA_IMPORTS = {
    "raw_ptr": ["vstd::layout::*"],
    "hash_map": ["std::hash::Hash", "vstd::std_specs::hash::*"],
    "hash_set": ["std::hash::Hash", "vstd::std_specs::hash::*"],
    "cell::invcell": ["vstd::predicate::*"],
    "std_specs::vec": ["alloc::alloc::Allocator"],
}

# Unstable library features required by some modules' signatures.
MODULE_FEATURES = {
    "std_specs::vec": ["allocator_api"],
}

# May-2026 vstd snapshot compat (version gate, see HANDOFF §6): the schema
# layer emits ``PointsTo::addr()`` — the current-vstd API. May's
# ``cell::PointsTo`` and ``raw_ptr::PointsTo`` have no ``addr``; the address
# lives at ``.ptr().addr()`` there. simple_pptr is NOT listed: its May
# ``PointsTo`` already exposes ``addr()`` (simple_pptr.rs:226).
# The new-style cell modules (invcell/pcell/pcell_maybe_uninit) are listed
# too: their ``PointsTo`` only exposes ``id()`` — no ``addr`` either — so
# the same ``.ptr().addr()`` -> ``.id()`` downgrade applies (and the
# resulting unusable scalar guards are dropped, same as deprecated ``cell``).
_MAY_PTR_ADDR_MODULES = frozenset(
    {"cell", "cell::invcell", "cell::pcell", "cell::pcell_maybe_uninit", "raw_ptr"}
)

# ---------------------------------------------------------------------------
# Audited A-case automation (HANDOFF §13 P2): per-target equal-fn overrides
# and proof hints, implementing exactly the repairs that
# experiments/UNKNOWN-AUDIT-2026-07-15.md validated manually.
#
# EQUAL_FN_OVERRIDES keys are (module, function, source_line); the wildcard
# line "*" matches any source line (for functions unique in their module
# whose line drifts between snapshots). PROOF_HINTS renders a proof block at
# the end of the det proof body (render_guarded_template proof_prelude).
# ---------------------------------------------------------------------------

EQUAL_FN_OVERRIDES = {
    # macro-generated PermissionPtr is invisible to source-level type/view
    # discovery, so the default equality compared raw identity. The ensures
    # pin every observable view() field (patomic id, addr, provenance,
    # metadata), so view equality verifies.
    ("atomic", "fetch_and", "*"): (
        "spec fn det_fetch_and_equal<T>(r1: *mut T, r2: *mut T, "
        "post1_perm: PermissionPtr<T>, post2_perm: PermissionPtr<T>) -> bool {\n"
        "    (true /* raw pointer: opaque by default */)\n"
        "    && (post1_perm.view() == post2_perm.view())\n"
        "}\n"
    ),
    ("atomic", "fetch_xor", "*"): (
        "spec fn det_fetch_xor_equal<T>(r1: *mut T, r2: *mut T, "
        "post1_perm: PermissionPtr<T>, post2_perm: PermissionPtr<T>) -> bool {\n"
        "    (true /* raw pointer: opaque by default */)\n"
        "    && (post1_perm.view() == post2_perm.view())\n"
        "}\n"
    ),
    ("atomic", "fetch_or", "*"): (
        "spec fn det_fetch_or_equal<T>(r1: *mut T, r2: *mut T, "
        "post1_perm: PermissionPtr<T>, post2_perm: PermissionPtr<T>) -> bool {\n"
        "    (true /* raw pointer: opaque by default */)\n"
        "    && (post1_perm.view() == post2_perm.view())\n"
        "}\n"
    ),
    # SharedReference intentionally gets a fresh provenance/tag; the public
    # contract fixes value(), address and metadata — compare exactly those.
    ("raw_ptr", "ptr_ref2", "*"): (
        "spec fn det_ptr_ref2_equal<'a, T>(r1: SharedReference<'a, T>, "
        "r2: SharedReference<'a, T>) -> bool {\n"
        "    (r1.value() == r2.value())\n"
        "    && (r1.ptr()@.addr == r2.ptr()@.addr)\n"
        "    && (r1.ptr()@.metadata == r2.ptr()@.metadata)\n"
        "}\n"
    ),
    # ReadHandle identity is opaque; the observable content is the value
    # snapshot. lemma_readers_match (see PROOF_HINTS) proves the views of
    # two simultaneous read handles on the same lock agree.
    ("rwlock", "acquire_read", "*"): (
        "spec fn det_acquire_read_equal<V, Pred: RwLockPredicate<V>>("
        "r1: ReadHandle<'_, V, Pred>, r2: ReadHandle<'_, V, Pred>) -> bool {\n"
        "    (r1.view() == r2.view())\n"
        "}\n"
    ),
    # Deprecated InvCell::new: both results expose the same
    # `inv(v) <==> f(v)` predicate; raw cell identity is irrelevant.
    ("cell", "new", 344): (
        "spec fn det_new_equal<T>(r1: InvCell<T>, r2: InvCell<T>) -> bool {\n"
        "    forall|v: T| r1.inv(v) == r2.inv(v)\n"
        "}\n"
    ),
    # cell::invcell::InvCell::new: ensures pin predicate() == pred and
    # `inv` is an open spec fn delegating to predicate(), so extensional
    # predicate equality follows.
    ("cell::invcell", "new", "*"): (
        "spec fn det_new_equal<T, Pred: Predicate<T>>(r1: InvCell<T, Pred>, "
        "r2: InvCell<T, Pred>) -> bool {\n"
        "    forall|v: T| r1.inv(v) == r2.inv(v)\n"
        "}\n"
    ),
    # --- P3: content/predicate quotients for fresh-identity constructors ---
    # These constructors intentionally pick a fresh identity (CellId,
    # allocator address, lock instance). Under the recorded quotient (see
    # PERMITTED_RULES) that ignores identity and observes content/predicate,
    # the result IS uniquely determined. Each override drops only the
    # identity conjuncts of the default equality.
    ("cell", "empty", 168): (
        "spec fn det_empty_equal<V>(r1: (PCell<V>, Tracked<PointsTo<V>>), "
        "r2: (PCell<V>, Tracked<PointsTo<V>>)) -> bool {\n"
        "    (((r1.1)@).is_init() == ((r2.1)@).is_init())\n"
        "    && (((r1.1)@).is_init() ==> (((r1.1)@).value() == ((r2.1)@).value()))\n"
        "}\n"
    ),
    ("cell", "new", 178): (
        "spec fn det_new_equal<V>(r1: (PCell<V>, Tracked<PointsTo<V>>), "
        "r2: (PCell<V>, Tracked<PointsTo<V>>)) -> bool {\n"
        "    (((r1.1)@).is_init() == ((r2.1)@).is_init())\n"
        "    && (((r1.1)@).is_init() ==> (((r1.1)@).value() == ((r2.1)@).value()))\n"
        "}\n"
    ),
    ("cell::pcell", "new", 132): (
        "spec fn det_new_equal<T: ?Sized>(r1: (PCell<T>, Tracked<PointsTo<T>>), "
        "r2: (PCell<T>, Tracked<PointsTo<T>>)) -> bool\n"
        "    where T: Sized {\n"
        "    ((r1.1)@).value() == ((r2.1)@).value()\n"
        "}\n"
    ),
    ("cell::pcell_maybe_uninit", "empty", 107): (
        "spec fn det_empty_equal<V>(r1: (PCell<V>, Tracked<PointsTo<V>>), "
        "r2: (PCell<V>, Tracked<PointsTo<V>>)) -> bool {\n"
        "    (((r1.1)@).is_init() == ((r2.1)@).is_init())\n"
        "    && (((r1.1)@).is_init() ==> (((r1.1)@).value() == ((r2.1)@).value()))\n"
        "}\n"
    ),
    ("cell::pcell_maybe_uninit", "new", 117): (
        "spec fn det_new_equal<V>(r1: (PCell<V>, Tracked<PointsTo<V>>), "
        "r2: (PCell<V>, Tracked<PointsTo<V>>)) -> bool {\n"
        "    (((r1.1)@).is_init() == ((r2.1)@).is_init())\n"
        "    && (((r1.1)@).is_init() ==> (((r1.1)@).value() == ((r2.1)@).value()))\n"
        "}\n"
    ),
    ("simple_pptr", "empty", 347): (
        "spec fn det_empty_equal<V>(r1: (PPtr<V>, Tracked<PointsTo<V>>), "
        "r2: (PPtr<V>, Tracked<PointsTo<V>>)) -> bool {\n"
        "    (((r1.1)@).is_init() == ((r2.1)@).is_init())\n"
        "    && (((r1.1)@).is_init() ==> (((r1.1)@).value() == ((r2.1)@).value()))\n"
        "}\n"
    ),
    ("simple_pptr", "new", "*"): (
        "spec fn det_new_equal<V>(r1: (PPtr<V>, Tracked<PointsTo<V>>), "
        "r2: (PPtr<V>, Tracked<PointsTo<V>>)) -> bool {\n"
        "    (((r1.1)@).is_init() == ((r2.1)@).is_init())\n"
        "    && (((r1.1)@).is_init() ==> (((r1.1)@).value() == ((r2.1)@).value()))\n"
        "}\n"
    ),
    ("rwlock", "new", 502): (
        "spec fn det_new_equal<V, Pred: RwLockPredicate<V>>(r1: RwLock<V, Pred>, "
        "r2: RwLock<V, Pred>) -> bool {\n"
        "    r1.pred() == r2.pred()\n"
        "}\n"
    ),
}

PROOF_HINTS = {
    # IsThread::agrees is the trusted same-thread equality axiom: two tokens
    # on the current thread have equal views, and the ensures already pin
    # token-view == ThreadId. r1/r2 must be `tracked` params of the det fn
    # (proof-fn params default to spec mode, which cannot call
    # Tracked::borrow). (Bare statements — the det fn is already a proof fn,
    # so no `proof { }` wrapper.)
    ("thread", "thread_id", "*"): {
        "tracked_params": ("r1", "r2"),
        "hint": (
            "let tracked __det_t1 = r1.1.borrow();\n"
            "    let tracked __det_t2 = r2.1.borrow();\n"
            "    __det_t1.agrees(*__det_t2);\n"
        ),
    },
    # vstd documents lemma_readers_match to prove simultaneous read handles
    # on the same lock observe the same value. The lemma takes tracked
    # references, so r1/r2 must be tracked params. Its precondition
    # (same rwlock) lives in the det fn's ensures-antecedent, which is not
    # in scope mid-body — assume the spec facts explicitly (the standard
    # "assume both runs satisfy the spec, show outputs agree" shape; the
    # det fn's contract is unchanged).
    ("rwlock", "acquire_read", "*"): {
        "tracked_params": ("r1", "r2"),
        "hint": (
            "assume(r1.rwlock() == *self_);\n"
            "    assume(r2.rwlock() == *self_);\n"
            "    ReadHandle::lemma_readers_match(&r1, &r2);\n"
        ),
    },
}

# ---------------------------------------------------------------------------
# P3 — permitted nondeterminism records (HANDOFF §13 P3).
#
# Every B-class target gets an explicit record instead of a blanket
# `equal == true`. Two flavours:
#   * quotient constructors: an EQUAL_FN_OVERRIDES entry above drops the
#     identity conjuncts; `quotient` names the quotient, and the target is
#     expected to verify (complete) under it;
#   * relation cases: no quotient makes the result unique; classification
#     becomes `incomplete_permitted` with the recorded reason.
# ---------------------------------------------------------------------------

_CELL_QUOTIENT = (
    "content quotient: fresh `CellId` ignored; compares `is_init()`/`value()`"
)

PERMITTED_RULES = {
    ("cell", "empty", 168): {
        "quotient": _CELL_QUOTIENT,
        "reason": "intentional fresh-cell identity; deterministic under the recorded content quotient",
    },
    ("cell", "new", 178): {
        "quotient": _CELL_QUOTIENT,
        "reason": "intentional fresh-cell identity; deterministic under the recorded content quotient",
    },
    ("cell::pcell", "new", 132): {
        "quotient": "content quotient: fresh `CellId` ignored; compares `value()`",
        "reason": "intentional fresh-cell identity; deterministic under the recorded content quotient",
    },
    ("cell::pcell_maybe_uninit", "empty", 107): {
        "quotient": _CELL_QUOTIENT,
        "reason": "intentional fresh-cell identity; deterministic under the recorded content quotient",
    },
    ("cell::pcell_maybe_uninit", "new", 117): {
        "quotient": _CELL_QUOTIENT,
        "reason": "intentional fresh-cell identity; deterministic under the recorded content quotient",
    },
    ("simple_pptr", "empty", 347): {
        "quotient": "content quotient: fresh allocator address ignored; compares `is_init()`/`value()`",
        "reason": "intentional fresh-address identity; deterministic under the recorded content quotient",
    },
    ("simple_pptr", "new", "*"): {
        "quotient": "content quotient: fresh allocator address ignored; compares `is_init()`/`value()`",
        "reason": "intentional fresh-address identity; deterministic under the recorded content quotient",
    },
    ("rwlock", "new", 502): {
        "quotient": "predicate quotient: fresh lock/cell instance ignored; compares `pred()`",
        "reason": "intentional fresh-instance identity; deterministic under the recorded predicate quotient",
    },
    ("float", "float_cast", 127): {
        "reason": "intentional nondeterminism: Rust float-cast relation documented as possibly non-deterministic; modeled by an uninterpreted relation",
    },
    ("raw_ptr", "allocate", 908): {
        "reason": "intentional nondeterminism: allocator may choose any address/provenance for identical size/alignment requests",
    },
    ("thread", "spawn", 107): {
        "reason": "intentional nondeterminism: fresh thread-handle identity and one-way predicate constraint on the closure result",
    },
    ("thread", "join", 27): {
        "reason": "intentional nondeterminism: successful value constrained only by the handle predicate; thread identity and runtime state intentionally hidden",
    },
}


def _lookup_rule(mapping: dict, module: str, function: str, source_line):
    """Exact (module, function, line) first, then the '*' line wildcard."""
    return mapping.get((module, function, source_line)) or mapping.get(
        (module, function, "*")
    )


# ---------------------------------------------------------------------------
# P5 — structured audit annotations (HANDOFF §13 P5).
#
# The A/B/C labels from experiments/UNKNOWN-AUDIT-2026-07-15.md and
# ALIAS-NEW-REVIEW-2026-07-21.md as machine-readable metadata. Buckets:
#   complete / complete_tool_gap / incomplete_permitted / incomplete /
#   unsupported / unknown
# ---------------------------------------------------------------------------

# C-class: genuine semantic underconstraint, established by MANUAL audit —
# the contract constrains the result only through a non-functional invariant
# predicate (`inv(result)`), so two distinct values can satisfy it. There is
# no machine sat witness; the label is audit-established.
_AUDIT_C_NOTE_CELL = (
    "audit-established genuine underconstraint: `self.inv(ret)` is a "
    "non-functional possible-value predicate (no machine sat witness)"
)

AUDIT_C = {
    ("cell", "replace", 359): {"note": _AUDIT_C_NOTE_CELL},
    ("cell", "get", 378): {"note": _AUDIT_C_NOTE_CELL},
    ("rwlock", "acquire_write", 530): {
        "note": "audit-established genuine underconstraint: returned value "
                "constrained only by the arbitrary lock invariant (no "
                "machine sat witness)",
    },
    ("rwlock", "into_inner", 702): {
        "note": "audit-established genuine underconstraint: returned value "
                "constrained only by the arbitrary lock invariant (no "
                "machine sat witness)",
    },
    ("cell::invcell", "replace", "*"): {"note": _AUDIT_C_NOTE_CELL},
    ("cell::invcell", "get", "*"): {"note": _AUDIT_C_NOTE_CELL},
    ("cell::invcell", "into_inner", "*"): {"note": _AUDIT_C_NOTE_CELL},
}

# A-class: previously unknown because of a tooling/equality/proof gap, now
# closed by the P2 overrides/hints. Reported as `complete_tool_gap` when the
# target verifies.
AUDIT_TOOL_GAP = {
    ("atomic", "fetch_and", "*"): {"mechanism": "PermissionPtr::view() equality (equal-fn override)"},
    ("atomic", "fetch_xor", "*"): {"mechanism": "PermissionPtr::view() equality (equal-fn override)"},
    ("atomic", "fetch_or", "*"): {"mechanism": "PermissionPtr::view() equality (equal-fn override)"},
    ("raw_ptr", "ptr_ref2", "*"): {"mechanism": "SharedReference projection equality (equal-fn override)"},
    ("thread", "thread_id", "*"): {"mechanism": "IsThread::agrees proof hint"},
    ("rwlock", "acquire_read", "*"): {"mechanism": "view equality + ReadHandle::lemma_readers_match proof hint"},
    ("cell", "new", 344): {"mechanism": "invariant-predicate equality (equal-fn override)"},
    ("cell::invcell", "new", "*"): {"mechanism": "invariant-predicate equality (equal-fn override)"},
}

# Free-form audit notes attached to any target (does not change the label).
AUDIT_NOTES = {
    ("std_specs::iter", "next", 287): (
        "suspected A (prophecy axiom `obeys_prophetic_iter_laws` not "
        "instantiated); the for-loop wrapper was removed upstream in cf3b5c3"
    ),
    ("std_specs::core", "index_set", "*"): (
        "`T: ?Sized` generic-bound gap in the synthesized det fn "
        "(pipeline limitation, not a spec verdict)"
    ),
}


def _audit_label(result: dict, module: str, function: str, source_line) -> str:
    """P5 bucket for aggregators (see HANDOFF §13 P5)."""
    if result.get("status") != "ok":
        # unsupported_mut_ref_return / verus_error / no_ensures / ...
        return str(result.get("status"))
    cls = result.get("classification")
    if cls in ("incomplete_permitted", "incomplete"):
        return cls
    if cls == "complete":
        if _lookup_rule(AUDIT_TOOL_GAP, module, function, source_line):
            return "complete_tool_gap"
        return "complete"
    return "unknown"


def module_file(vstd_root: Path, module: str) -> Path:
    relative = Path(*module.split("::"))
    direct = vstd_root / relative.with_suffix(".rs")
    if direct.is_file():
        return direct
    nested = vstd_root / relative / "mod.rs"
    if nested.is_file():
        return nested
    raise FileNotFoundError(f"cannot resolve vstd module {module!r}")


def safe_name(
    module: str,
    function: str,
    source_line: int | None = None,
) -> str:
    suffix = f"__L{source_line}" if source_line is not None else ""
    return f"{module.replace('::', '__')}__{function}{suffix}"


def parse_target(target: str) -> tuple[str, str, int | None]:
    if ":" not in target:
        raise ValueError(f"invalid target {target!r}; expected module:function")
    module, function_part = target.rsplit(":", 1)
    source_line = None
    if "@" in function_part:
        function, line_text = function_part.rsplit("@", 1)
        source_line = int(line_text)
    else:
        function = function_part
    return module, function, source_line


def build_harness(
    module: str,
    det_spec,
    schemas,
    *,
    snapshot: str = "may2026",
    function: str | None = None,
    source_line: int | None = None,
) -> str:
    # Audited A-case overrides (see EQUAL_FN_OVERRIDES / PROOF_HINTS above).
    override = EQUAL_FN_OVERRIDES.get(
        (module, function, source_line)
    ) or EQUAL_FN_OVERRIDES.get((module, function, "*"))
    equal_fn_def = override if override is not None else det_spec.equal_fn_def
    proof_hint = PROOF_HINTS.get(
        (module, function, source_line)
    ) or PROOF_HINTS.get((module, function, "*"))
    body = equal_fn_def + "\n\n" + render_guarded_template(
        det_spec,
        schemas,
        proof_prelude=(proof_hint or {}).get("hint"),
    )
    tracked_params = (proof_hint or {}).get("tracked_params") or ()
    if tracked_params:
        # Make the listed result params `tracked` in the det PROOF fn only
        # (never in the spec equal-fn, which cannot take tracked params).
        idx = body.find("proof fn det_")
        if idx >= 0:
            head, tail = body[:idx], body[idx:]
            for pname in tracked_params:
                tail = re.sub(
                    rf"\b{re.escape(pname)}: ",
                    f"tracked {pname}: ",
                    tail,
                    count=1,
                )
            body = head + tail
    for spec_name in det_spec.opened_closed_specs:
        body = re.sub(
            rf"^[ \t]*reveal\((?:[A-Za-z_][A-Za-z0-9_]*::)*"
            rf"{re.escape(spec_name)}\);[ \t]*\n?",
            "",
            body,
            flags=re.MULTILINE,
        )
    if module == "simple_pptr":
        body = body.replace(".ptr().addr()", ".pptr().addr()")
    elif module in {"cell", "cell::invcell", "cell::pcell", "cell::pcell_maybe_uninit"}:
        body = body.replace(".ptr().addr()", ".id()")
        body = "\n".join(
            line
            for line in body.splitlines()
            if not (
                line.lstrip().startswith("if g_")
                and ".id() as int" in line
            )
        )
        body += "\n"
    if module == "cell::pcell":
        # May `cell::pcell::PointsTo` is always initialized: it has
        # `id()`/`value()` but no `is_init()`. The POINTS_TO equal-fn and
        # schema projections assume the maybe-uninit shape, so constant-fold
        # every `.is_init()` call to `true` for this module. The pattern only
        # matches balanced single-level receivers (`(x).is_init()` and
        # `((x)@).is_init()`) so it cannot eat a parenthesis.
        body = re.sub(
            r"\((?:\([A-Za-z_][\w.]*\)@|[A-Za-z_][\w.]*)\)\.is_init\(\)",
            "(true)",
            body,
        )
    imports = "".join(
        f"use {path};\n"
        for path in EXTRA_IMPORTS.get(module, [])
    )
    if module == "cell::pcell_maybe_uninit":
        # MemContents moved from vstd::cell (May 2026 snapshot) to
        # vstd::raw_ptr (cf3b5c3, July 2026).
        imports += (
            "use vstd::cell::MemContents;\n"
            if snapshot == "may2026"
            else "use vstd::raw_ptr::MemContents;\n"
        )
    # Unstable library features required by some modules' signatures
    # (std_specs::vec's `A: Allocator` needs allocator_api).
    features = "".join(
        f"#![feature({feature})]\n"
        for feature in MODULE_FEATURES.get(module, [])
    )
    return (
        "#![allow(unused_imports)]\n"
        f"{features}"
        "extern crate alloc;\n"
        "use vstd::prelude::*;\n"
        f"use vstd::{module}::*;\n\n"
        f"{imports}\n"
        "verus! {\n"
        f"{body}\n"
        "}\n\n"
        "fn main() {}\n"
    )


def equal_fn_is_trivial(equal_fn_def: str) -> bool:
    match = re.search(
        r"->\s*bool\s*\{(?P<body>.*)\}\s*$",
        equal_fn_def,
        flags=re.DOTALL,
    )
    if not match:
        return False
    body = re.sub(r"/\*.*?\*/", "", match.group("body"), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    body = re.sub(r"[\s()]", "", body)
    return body == "true"


def normalized_text_output(text: str) -> str:
    stripped = text.rstrip()
    return stripped + "\n" if stripped else ""


def run_target(
    *,
    module: str,
    function: str,
    source_line: int | None,
    vstd_root: Path,
    verus_root: Path,
    out_dir: Path,
    timeout: int,
    rlimit: float,
    compare_raw_pointers: bool,
    view_registry: ViewRegistry | None,
    vstd_snapshot: str = "may2026",
) -> dict:
    artifact_dir = out_dir / "artifacts" / safe_name(
        module,
        function,
        source_line,
    )
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True)

    source_path = module_file(vstd_root, module)
    source = source_path.read_text(errors="replace")
    result = {
        "module": module,
        "function": function,
        "source_line": source_line,
        "source": str(source_path),
        "artifact_dir": str(artifact_dir),
        "status": "runner_crash",
    }
    started = time.monotonic()

    def _finalize(res: dict) -> dict:
        # P5 audit annotation on every exit path (including early non-ok
        # returns): attach notes, relabel audit-established C-cases, and
        # derive the bucket label.
        c_rule = _lookup_rule(AUDIT_C, module, function, source_line)
        if c_rule is not None:
            res.setdefault("audit_note", c_rule["note"])
            if res.get("classification") == "ok_inconclusive":
                res["classification"] = "incomplete"
        note = _lookup_rule(AUDIT_NOTES, module, function, source_line)
        if note is not None:
            res["audit_note"] = note
        res["audit_label"] = _audit_label(
            res, module, function, source_line
        )
        return res

    try:
        spec = extract_spec(
            source,
            function,
            type_sources=[source],
            source_line=source_line,
        )
        result["requires"] = list(spec.requires)
        result["ensures"] = list(spec.ensures)
        if not spec.ensures:
            result["status"] = "no_ensures"
            return _finalize(result)
        if spec.return_type.name.strip().startswith("&mut "):
            result["status"] = "unsupported_mut_ref_return"
            result["error"] = (
                "current gen_det emits direct mutable-reference result "
                "projections instead of old(result)/final(result)"
            )
            return _finalize(result)

        equal_policy = EqualPolicy(
            compare_raw_pointers=compare_raw_pointers,
            source="manual" if compare_raw_pointers else "default",
            rationale=(
                "vstd strict raw-pointer experiment"
                if compare_raw_pointers
                else None
            ),
        )
        det_spec = build_det_check_spec(
            spec,
            source=source,
            equal_policy=equal_policy,
            view_registry=view_registry,
        )
        schemas = enumerate_schemas(
            det_spec,
            points_to_addr=(
                "ptr().addr()" if module in _MAY_PTR_ADDR_MODULES else "addr()"
            ),
        )
        harness = build_harness(
            module,
            det_spec,
            schemas,
            snapshot=vstd_snapshot,
            function=function,
            source_line=source_line,
        )

        (artifact_dir / "det_spec.json").write_text(det_spec.to_json())
        (artifact_dir / "harness.rs").write_text(harness)
        result["det_function"] = det_spec.check_fn_name
        result["equal_fn_trivial"] = equal_fn_is_trivial(
            det_spec.equal_fn_def
        )
        result["suppressed_closed_reveals"] = list(
            det_spec.opened_closed_specs
        )
        result["n_schemas"] = len(schemas)
        result["n_params"] = sum(1 + len(schema.k_params) for schema in schemas)

        log_dir = artifact_dir / "verus_log"
        log_dir.mkdir()
        raw = run_verus_file(
            artifact_dir / "harness.rs",
            str(verus_root),
            log_dir,
            timeout=timeout,
            verify_function=det_spec.check_fn_name,
            rlimit=rlimit,
        )
        result["verus_returncode"] = raw["returncode"]
        result["verus_ms"] = raw["duration_ms"]
        (artifact_dir / "verus_stdout.txt").write_text(
            normalized_text_output(raw["stdout"])
        )
        (artifact_dir / "verus_stderr.txt").write_text(
            normalized_text_output(raw["stderr"])
        )

        if raw["returncode"] != 0:
            stderr = raw["stderr"]
            expected_failure = (
                "postcondition not satisfied" in stderr
                or "assertion failed" in stderr.lower()
            )
            if not expected_failure and "error:" in stderr:
                result["status"] = "verus_error"
                result["stderr_tail"] = stderr[-3000:]
                return _finalize(result)

        smt2_candidates = sorted(
            log_dir.rglob("*.smt2"),
            key=lambda path: path.stat().st_size,
        )
        if not smt2_candidates:
            result["status"] = "no_smt2"
            return _finalize(result)
        smt2 = smt2_candidates[-1]
        result["smt2"] = str(smt2)
        result["smt2_bytes"] = smt2.stat().st_size

        ctx_started = time.monotonic()
        schema_ctx = build_schema_ctx(
            smt2,
            det_spec.check_fn_name,
            schemas,
            safe_name(module, function, source_line),
        )
        result["ctx_ms"] = int((time.monotonic() - ctx_started) * 1000)

        search_started = time.monotonic()
        witness = run_schema_search(det_spec, schema_ctx)
        result["search_ms"] = int(
            (time.monotonic() - search_started) * 1000
        )
        result["r0_z3"] = witness.r0_z3
        result["n_rounds"] = len(witness.trace or [])
        result["assumes"] = [
            assume.expression for assume in (witness.assumes or [])
        ]
        result["status"] = "ok"
        result["permitted"] = False
        raw_classification = classify_ok(result)
        if result["equal_fn_trivial"]:
            result["raw_classification"] = raw_classification
            result["classification"] = "invalid_equal_fn_trivial"
        else:
            result["classification"] = raw_classification
        # P3: attach the explicit permitted record (quotient or reason).
        # Relation cases (no quotient) become `incomplete_permitted`;
        # quotient constructors keep their verdict plus the quotient name.
        rule = _lookup_rule(PERMITTED_RULES, module, function, source_line)
        if rule is not None:
            result["permitted"] = True
            result["permitted_reason"] = rule["reason"]
            if rule.get("quotient"):
                result["quotient"] = rule["quotient"]
            elif result["classification"] == "ok_inconclusive":
                result["classification"] = "incomplete_permitted"
        # P5 audit annotation happens in _finalize on every exit path.
        return _finalize(result)
    except Exception as exc:
        result["status"] = "runner_crash"
        result["error"] = (
            f"{type(exc).__name__}: {exc}\n"
            f"{traceback.format_exc()[-3000:]}"
        )
        return result
    finally:
        result["wall_ms"] = int((time.monotonic() - started) * 1000)
        (artifact_dir / "result.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )


def write_summary(out_dir: Path, metadata: dict, results: list[dict]) -> None:
    payload = {
        "metadata": metadata,
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")

    status_counts = Counter(result.get("status", "") for result in results)
    class_counts = Counter(
        result.get("classification", "")
        for result in results
        if result.get("classification")
    )
    audit_counts = Counter(
        result.get("audit_label", "")
        for result in results
        if result.get("audit_label")
    )
    lines = [
        "# vstd determinism pilot",
        "",
        f"- vstd root: `{metadata['vstd_root']}`",
        f"- Verus root: `{metadata['verus_root']}`",
        f"- Verus version: `{metadata['verus_version']}`",
        f"- Verus commit: `{metadata['verus_commit']}`",
        f"- Compare raw pointers: `{metadata['compare_raw_pointers']}`",
        f"- View registry: `{metadata['view_registry']}`",
        f"- Targets: {len(results)}",
        f"- Status counts: `{dict(status_counts)}`",
        f"- Classification counts: `{dict(class_counts)}`",
        f"- Audit label counts: `{dict(audit_counts)}`",
        "",
        "| Module | Function | Line | Status | R0 Z3 | Classification | Audit | Schemas | Rounds | Wall ms |",
        "|---|---|---:|---|---|---|---|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            f"| `{result['module']}` | `{result['function']}` | "
            f"{result.get('source_line') or ''} | "
            f"{result.get('status', '')} | {result.get('r0_z3', '')} | "
            f"{result.get('classification', '')} | "
            f"{result.get('audit_label', '')} | "
            f"{result.get('n_schemas', '')} | "
            f"{result.get('n_rounds', '')} | "
            f"{result.get('wall_ms', '')} |"
        )
    lines.extend(
        [
            "",
            "## Errors",
            "",
        ]
    )
    errors = [
        result
        for result in results
        if result.get("status") not in {"ok"}
    ]
    if not errors:
        lines.append("None.")
    else:
        for result in errors:
            lines.extend(
                [
                    f"### `{result['module']}::{result['function']}`",
                    "",
                    "```text",
                    result.get(
                        "stderr_tail",
                        result.get("error", result.get("status", "")),
                    ),
                    "```",
                    "",
                ]
            )
    (out_dir / "SUMMARY.md").write_text(
        "\n".join(lines).rstrip() + "\n"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vstd-root", type=Path, required=True)
    parser.add_argument("--verus-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="module:function; repeat for multiple targets",
    )
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument(
        "--targets-csv",
        type=Path,
        help="exec_functions.csv produced by scan_vstd.py",
    )
    parser.add_argument(
        "--public-free-post",
        action="store_true",
        help="select public free definitions with explicit postconditions",
    )
    parser.add_argument(
        "--public-impl-post",
        action="store_true",
        help="select public impl definitions with explicit postconditions",
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--rlimit", type=float, default=60)
    parser.add_argument("--compare-raw-pointers", action="store_true")
    parser.add_argument("--no-view-registry", action="store_true")
    parser.add_argument(
        "--vstd-snapshot",
        choices=["may2026", "jul2026"],
        default="may2026",
        help=(
            "vstd snapshot profile for compat handling; may2026 keeps the "
            "documented behaviour, jul2026 selects the cf3b5c3 source-built "
            "toolchain profile (e.g. MemContents moved to vstd::raw_ptr)"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = list(args.target)
    if args.pilot:
        targets.extend(PILOT_TARGETS)
    if args.targets_csv:
        with args.targets_csv.open() as handle:
            rows = list(csv.DictReader(handle))
        if args.public_free_post or args.public_impl_post:
            rows = [
                row
                for row in rows
                if row["node_kind"] == "definition"
                and row["visibility"] == "public"
                and row["contract_status"] == "post"
                and (
                    (args.public_free_post and row["context"] == "free")
                    or (
                        args.public_impl_post
                        and row["context"] != "free"
                    )
                )
            ]
        targets.extend(
            f"{row['module']}:{row['name']}@{row['line']}"
            for row in rows
        )
    targets = list(dict.fromkeys(targets))
    if not targets:
        raise SystemExit("provide --pilot or at least one --target module:function")

    args.out.mkdir(parents=True, exist_ok=True)
    version_path = args.verus_root / "version.json"
    if version_path.is_file():
        version_data = json.loads(version_path.read_text())["verus"]
        verus_version = version_data["version"]
        verus_commit = version_data["commit"]
    else:
        # Source-built layout (target-verus/release) ships only version.txt.
        version_txt = args.verus_root / "version.txt"
        verus_version = (
            version_txt.read_text().splitlines()[0].strip()
            if version_txt.is_file()
            else "unknown"
        )
        verus_commit = "unknown"
    metadata = {
        "vstd_root": str(args.vstd_root.resolve()),
        "verus_root": str(args.verus_root.resolve()),
        "verus_version": verus_version,
        "verus_commit": verus_commit,
        "vstd_snapshot": args.vstd_snapshot,
        "targets": targets,
        "compare_raw_pointers": args.compare_raw_pointers,
        "view_registry": not args.no_view_registry,
    }
    view_registry = (
        None
        if args.no_view_registry
        else ViewRegistry.from_project(args.vstd_root)
    )

    results = []
    for target in targets:
        try:
            module, function, source_line = parse_target(target)
        except (ValueError, TypeError) as exc:
            raise SystemExit(str(exc)) from exc
        result = run_target(
            module=module,
            function=function,
            source_line=source_line,
            vstd_root=args.vstd_root,
            verus_root=args.verus_root,
            out_dir=args.out,
            timeout=args.timeout,
            rlimit=args.rlimit,
            compare_raw_pointers=args.compare_raw_pointers,
            view_registry=view_registry,
            vstd_snapshot=args.vstd_snapshot,
        )
        results.append(result)
        print(
            f"{module}::{function}"
            f"{f'@{source_line}' if source_line is not None else ''}: "
            f"{result.get('status')} "
            f"r0={result.get('r0_z3', '-')} "
            f"class={result.get('classification', '-')}"
        )
        write_summary(args.out, metadata, results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
