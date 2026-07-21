#!/usr/bin/env python3
"""
Step 1: Extract executable functions from all baseline-valid VeruSage files.

Outputs: <workspace>/exec_functions.json

Usage:
  python3 step1_extract.py [--workspace DIR]
"""

import argparse
import json
import sys
from pathlib import Path

BASE = Path.home() / "intent_formalization"
VERUS_SO = str(BASE / "verus.so")
VERUSAGE = BASE / "verusage" / "source-projects"

sys.path.insert(0, str(BASE / "src" / "utils"))
from verus_parser import verus_parser


def task_name_for(source_path: Path) -> str:
    rel = source_path.relative_to(VERUSAGE)
    project = rel.parts[0]
    return f"{project}__{source_path.stem}"


def extract_fn_name(decl_node) -> str:
    for child in decl_node.children:
        if child.type == 'function_item':
            name = child.child_by_field_name('name')
            return name.text.decode() if name else 'unknown'
    return 'unknown'


def extract_from_file(fpath: Path) -> dict | None:
    """Extract exec function info from a single source file. Returns entry dict or None."""
    vp = verus_parser(VERUS_SO)
    source_text = fpath.read_text()
    tree = vp.parser.parse(bytes(source_text, 'utf-8')).root_node
    exec_fns = vp.extract_exec_functions(tree, skip_external=True)

    exec_info = []
    for decl in exec_fns:
        name = extract_fn_name(decl)
        if name == 'main':
            continue
        exec_info.append({"name": name, "code": decl.text.decode()})

    if not exec_info:
        return None

    return {
        "file_path": str(fpath),
        "task_name": fpath.stem,
        "exec_functions": exec_info,
    }


def main():
    parser = argparse.ArgumentParser(description="Step 1: Extract exec functions")
    parser.add_argument("--workspace", type=str, default=str(BASE / "verusage" / "workspace_v4"))
    args = parser.parse_args()

    workspace = Path(args.workspace)
    vp = verus_parser(VERUS_SO)

    valid_file = workspace / "baseline_valid.json"
    if not valid_file.exists():
        # Fall back to v3's baseline
        valid_file = BASE / "verusage" / "workspace_v3" / "baseline_valid.json"
    files = [Path(f) for f in json.loads(valid_file.read_text())]
    print(f"Scanning {len(files)} baseline-valid files...")

    results = []
    skipped = 0

    for i, fpath in enumerate(files):
        source_text = fpath.read_text()
        tree = vp.parser.parse(bytes(source_text, 'utf-8')).root_node

        # Extract all function categories
        exec_fns = vp.extract_exec_functions(tree, skip_external=True)
        all_fns = vp.extract_functions(tree)
        spec_nodes = vp.extract_specifications(tree)
        proof_nodes = vp.extract_proofs(tree)

        # Filter out 'main'
        exec_info = []
        for decl in exec_fns:
            name = extract_fn_name(decl)
            if name == 'main':
                continue
            exec_info.append({
                "name": name,
                "code": decl.text.decode(),
            })

        if not exec_info:
            skipped += 1
            continue

        task_name = task_name_for(fpath)
        results.append({
            "file_path": str(fpath),
            "task_name": task_name,
            "exec_functions": exec_info,
            "stats": {
                "total_fns": len(all_fns),
                "exec_fns": len(exec_info),
                "spec_nodes": len(spec_nodes),
                "proof_nodes": len(proof_nodes),
            }
        })

        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(files)}] {len(results)} with exec, {skipped} skipped")

    # Save
    workspace.mkdir(parents=True, exist_ok=True)
    out_path = workspace / "exec_functions.json"
    out_path.write_text(json.dumps(results, indent=2))

    print(f"\nDone: {len(results)} files with exec functions, {skipped} skipped")
    print(f"Output: {out_path}")

    # Quick stats
    total_exec = sum(len(r["exec_functions"]) for r in results)
    print(f"Total exec functions: {total_exec}")


if __name__ == "__main__":
    main()
