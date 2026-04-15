"""
Step 6 (fuzz): Assemble Case objects into proof-fn Verus source files.

Each case is rendered as a proof fn whose body consists of the case's
assume statements, using assemble_proof_fn from pipeline/step3_formalize
to attach the function's requires/ensures.

Note: The upstream step3_formalize.py depends on LLMClient via a legacy
sys.path import. All calls to assemble_proof_fn are done lazily inside
functions so that importing this module alone does not crash.

Outputs:
  <task_dir>/verus/<case_id>.rs        — one file per case
  <task_dir>/assembled_cases.json      — updated case list with source paths

Usage:
  python -m src.pipeline_fuzz.step6_assemble --task-dir <path>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from src.utils.pipeline_common import build_entailment_file, extract_spec_portion
from src.pipeline_fuzz.schemas import Case


def _ensure_path() -> None:
    """Ensure src and src/utils are on sys.path for legacy imports."""
    src_root = Path(__file__).resolve().parents[2]
    for p in [str(src_root / "src" / "utils"), str(src_root / "src")]:
        if p not in sys.path:
            sys.path.insert(0, p)


def _get_assemble_proof_fn():
    """Lazy import of assemble_proof_fn to avoid sys.path issues at module load."""
    _ensure_path()
    from src.pipeline.step3_formalize import assemble_proof_fn
    return assemble_proof_fn


# ---------------------------------------------------------------------------
# Case → proof-fn body
# ---------------------------------------------------------------------------

def _case_to_body(case: Case) -> str:
    """Convert Case assume lists into a Verus proof fn body string."""
    lines: list[str] = []

    if case.pre_assumes:
        lines.append("// --- Pre-state ---")
        for a in case.pre_assumes:
            if a.startswith("//"):
                lines.append(a)
            else:
                lines.append(f"assume({a});")

    if case.arg_assumes:
        lines.append("// --- Arguments ---")
        for a in case.arg_assumes:
            lines.append(f"assume({a});")

    if case.result_assume:
        lines.append("// --- Return value ---")
        lines.append(f"assume({case.result_assume});")

    if case.post_assumes:
        lines.append("// --- Post-state ---")
        for a in case.post_assumes:
            lines.append(f"assume({a});")

    return "\n    ".join(lines)


def assemble_case(case: Case, fn_info: dict, source_text: str) -> str:
    """
    Assemble a full Verus source file for one case.

    Embeds the proof fn into the source file using build_entailment_file.
    """
    assemble_proof_fn = _get_assemble_proof_fn()

    declaration = fn_info.get("declaration", fn_info.get("code", ""))
    fn_name = case.fn

    body = _case_to_body(case)

    # Build the candidate dict expected by assemble_proof_fn
    candidate = {
        "name": case.case_id,
        "target_fn": fn_name,
        "body": body,
        "params": "",  # assemble_proof_fn infers params from declaration
    }
    declarations = {fn_name: declaration}

    proof_fn_code = assemble_proof_fn(candidate, declarations)

    # Embed into the full source file
    spec_source = extract_spec_portion(source_text, max_lines=500)
    try:
        full_source = build_entailment_file(spec_source, proof_fn_code)
    except ValueError:
        # Fall back: wrap in a minimal verus! block
        full_source = (
            f"// Auto-generated entailment check for case {case.case_id}\n"
            f"use vstd::prelude::*;\n\n"
            f"verus! {{\n\n{proof_fn_code}\n\n}}\n"
        )

    return full_source


def process_one(task_dir: Path) -> list[Case]:
    """
    Assemble proof-fn source files for all labeled cases.

    Reads: cases_labeled.json, exec_functions.json, original.rs
    Writes: verus/<case_id>.rs per case, assembled_cases.json
    Returns: cases (list)
    """
    labeled_path = task_dir / "cases_labeled.json"
    if not labeled_path.exists():
        raise FileNotFoundError(f"cases_labeled.json not found in {task_dir}")

    cases = [Case.from_dict(d) for d in json.loads(labeled_path.read_text())]

    exec_fns_path = task_dir / "exec_functions.json"
    exec_fns = json.loads(exec_fns_path.read_text()) if exec_fns_path.exists() else []
    fn_map = {f["name"]: f for f in exec_fns}

    orig_path = task_dir / "original.rs"
    source_text = orig_path.read_text() if orig_path.exists() else ""

    verus_dir = task_dir / "verus"
    verus_dir.mkdir(exist_ok=True)

    assembled: list[dict] = []
    for case in cases:
        fn_info = fn_map.get(case.fn, {})
        try:
            source = assemble_case(case, fn_info, source_text)
        except Exception as e:
            source = f"// ERROR assembling case {case.case_id}: {e}\n"

        rs_path = verus_dir / f"{case.case_id}.rs"
        rs_path.write_text(source)

        d = case.to_dict()
        d["verus_source"] = str(rs_path)
        assembled.append(d)

    (task_dir / "assembled_cases.json").write_text(json.dumps(assembled, indent=2))
    return cases


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 6 (fuzz): Assemble Case objects into proof-fn source files"
    )
    parser.add_argument("--task-dir", type=str, required=True)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).resolve()
    print(f"[step6] Assembling proof fns for {task_dir.name}")

    try:
        cases = process_one(task_dir)
    except FileNotFoundError as e:
        print(f"[step6] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[step6] Assembled {len(cases)} proof fns")
    print(f"[step6] Source files → {task_dir / 'verus'}/")
    print(f"[step6] Wrote assembled_cases.json → {task_dir / 'assembled_cases.json'}")


if __name__ == "__main__":
    main()
