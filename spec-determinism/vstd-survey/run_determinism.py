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
    "cell::pcell_maybe_uninit": ["vstd::cell::MemContents"],
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


def build_harness(module: str, det_spec, schemas) -> str:
    body = det_spec.equal_fn_def + "\n\n" + render_guarded_template(
        det_spec,
        schemas,
    )
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
            return result
        if spec.return_type.name.strip().startswith("&mut "):
            result["status"] = "unsupported_mut_ref_return"
            result["error"] = (
                "current gen_det emits direct mutable-reference result "
                "projections instead of old(result)/final(result)"
            )
            return result

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
        harness = build_harness(module, det_spec, schemas)

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
                return result

        smt2_candidates = sorted(
            log_dir.rglob("*.smt2"),
            key=lambda path: path.stat().st_size,
        )
        if not smt2_candidates:
            result["status"] = "no_smt2"
            return result
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
        return result
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
        "",
        "| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |",
        "|---|---|---:|---|---|---|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            f"| `{result['module']}` | `{result['function']}` | "
            f"{result.get('source_line') or ''} | "
            f"{result.get('status', '')} | {result.get('r0_z3', '')} | "
            f"{result.get('classification', '')} | "
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
    version_data = json.loads(version_path.read_text())["verus"]
    metadata = {
        "vstd_root": str(args.vstd_root.resolve()),
        "verus_root": str(args.verus_root.resolve()),
        "verus_version": version_data["version"],
        "verus_commit": version_data["commit"],
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
