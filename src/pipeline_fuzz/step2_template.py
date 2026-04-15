"""
Step 2 (fuzz): Generate per-function symbolic scenario templates.

For each exec function in exec_functions.json, produce a template that
describes:
  - State scenarios (empty, normal, boundary, full/error) inferred from
    the function's requires/ensures clauses and the struct fields visible
    in the source.
  - Argument domains (min/zero/max/typical concrete values).
  - Return paths (Ok/Err variants found in the ensures).

Outputs: <task_dir>/templates.json

Usage:
  python -m src.pipeline_fuzz.step2_template --task-dir <path>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers for lightweight static analysis of Verus specs
# ---------------------------------------------------------------------------

def _extract_requires(declaration: str) -> str:
    """Pull the raw requires clause text from a verus_spec declaration."""
    m = re.search(r'\brequires\b(.*?)(?=\bensures\b|\)\])', declaration, re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_ensures(declaration: str) -> str:
    """Pull the raw ensures clause text from a verus_spec declaration."""
    m = re.search(r'\bensures\b(.*?)(?=\)\]|\Z)', declaration, re.DOTALL)
    return m.group(1).strip() if m else ""


def _has_self_param(declaration: str) -> bool:
    return bool(re.search(r'\bself\b', declaration.split(')')[0]))


def _is_mut_self(declaration: str) -> bool:
    return bool(re.search(r'&\s*mut\s+self', declaration))


def _detect_return_paths(ensures: str) -> list[str]:
    """Heuristically detect Ok / Err result paths from ensures text."""
    paths = []
    if re.search(r'\bOk\b', ensures):
        paths.append("Ok")
    if re.search(r'\bErr\b', ensures):
        paths.append("Err")
    if not paths:
        paths.append("scalar")  # non-Result return
    return paths


def _detect_state_scenarios(requires: str, ensures: str, fn_name: str) -> list[dict[str, Any]]:
    """
    Produce a small set of state scenario descriptors from spec text.

    Each descriptor:
      {
        "name": str,
        "description": str,
        "pre_constraints": [str],   # Verus assume() snippets (partial/hints)
      }
    """
    scenarios = []

    # Universal scenario — no extra constraints
    scenarios.append({
        "name": "general",
        "description": "No specific pre-state constraints; tests spec in an arbitrary valid state.",
        "pre_constraints": [],
    })

    # Empty / is_empty heuristics
    if re.search(r'is_empty|num_bits\s*==\s*0|usage.*==.*0|set_bits.*==.*Set::empty', ensures + requires):
        scenarios.append({
            "name": "empty",
            "description": "Pre-state where the data structure is completely empty.",
            "pre_constraints": ["// pre-state is empty"],
        })

    # Full / is_full heuristics
    if re.search(r'is_full|full|no.*free|all.*set', ensures + requires, re.IGNORECASE):
        scenarios.append({
            "name": "full",
            "description": "Pre-state where the data structure is completely full.",
            "pre_constraints": ["// pre-state is full"],
        })

    # Almost-full (one slot left) — relevant for allocation functions
    if re.search(r'\balloc\b|\bset\b', fn_name):
        scenarios.append({
            "name": "almost_full",
            "description": "Pre-state with exactly one free slot.",
            "pre_constraints": ["// pre-state has exactly one free slot"],
        })

    # Error-path / boundary heuristic
    if re.search(r'\bErr\b', ensures):
        scenarios.append({
            "name": "error_path",
            "description": "Pre-state that forces the function to return an error.",
            "pre_constraints": ["// pre-state triggers error path"],
        })

    return scenarios


def _detect_arg_domains(declaration: str) -> list[dict[str, Any]]:
    """
    Heuristically detect argument names and suggest concrete value sets.

    Returns list of {name, type_hint, domain} dicts.
    """
    # Find the parameter list between first `(` and matching `)`.
    # Strip leading &self / &mut self.
    sig_m = re.search(r'pub\s+fn\s+\w+\s*\((.*?)\)', declaration, re.DOTALL)
    if not sig_m:
        sig_m = re.search(r'fn\s+\w+\s*\((.*?)\)', declaration, re.DOTALL)
    if not sig_m:
        return []

    params_raw = sig_m.group(1)
    # Remove &self / &mut self
    params_raw = re.sub(r'&\s*(?:mut\s+)?self\s*,?\s*', '', params_raw).strip()

    args = []
    for param in re.split(r',\s*', params_raw):
        param = param.strip()
        if not param:
            continue
        # Parse  name: Type
        pm = re.match(r'(\w+)\s*:\s*(.*)', param)
        if not pm:
            continue
        name, type_hint = pm.group(1), pm.group(2).strip()

        # Suggest domain based on type
        if re.search(r'\busize\b|\bu\d+\b|\bi\d+\b|\bisize\b', type_hint):
            domain = [0, 1, 7, 8, 255, "usize::MAX"]
        elif re.search(r'\bbool\b', type_hint):
            domain = [True, False]
        elif re.search(r'\bStr\b|&str\b', type_hint):
            domain = ["\"\"", "\"a\""]
        else:
            domain = ["<concrete value>"]

        args.append({"name": name, "type_hint": type_hint, "domain": domain})

    return args


# ---------------------------------------------------------------------------
# Main template generation
# ---------------------------------------------------------------------------

def generate_template(fn_info: dict) -> dict:
    """
    Generate a symbolic template for one exec function.

    fn_info: one entry from exec_functions.json
      {"name": str, "code": str, "declaration": str}
    """
    name = fn_info["name"]
    declaration = fn_info.get("declaration", "")

    requires = _extract_requires(declaration)
    ensures = _extract_ensures(declaration)

    has_self = _has_self_param(declaration)
    is_mut = _is_mut_self(declaration)
    return_paths = _detect_return_paths(ensures)
    state_scenarios = _detect_state_scenarios(requires, ensures, name) if has_self else []
    arg_domains = _detect_arg_domains(declaration)

    return {
        "fn": name,
        "has_self": has_self,
        "is_mut_self": is_mut,
        "requires_text": requires,
        "ensures_text": ensures,
        "return_paths": return_paths,
        "state_scenarios": state_scenarios,
        "arg_domains": arg_domains,
    }


def process_one(task_dir: Path) -> list[dict]:
    """
    Generate templates for all exec functions in task_dir/exec_functions.json.

    Writes templates.json and returns the list.
    """
    exec_fns_path = task_dir / "exec_functions.json"
    if not exec_fns_path.exists():
        raise FileNotFoundError(f"exec_functions.json not found in {task_dir}")

    exec_fns = json.loads(exec_fns_path.read_text())
    templates = [generate_template(fn) for fn in exec_fns]

    (task_dir / "templates.json").write_text(json.dumps(templates, indent=2))
    return templates


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 2 (fuzz): Generate per-function scenario templates"
    )
    parser.add_argument("--task-dir", type=str, required=True)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).resolve()
    print(f"[step2] Generating templates for {task_dir.name}")

    try:
        templates = process_one(task_dir)
    except FileNotFoundError as e:
        print(f"[step2] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    for t in templates:
        n_scen = len(t["state_scenarios"])
        n_args = len(t["arg_domains"])
        print(f"  fn={t['fn']:20s}  scenarios={n_scen}  arg_domains={n_args}  return_paths={t['return_paths']}")

    print(f"[step2] Wrote templates.json → {task_dir / 'templates.json'}")


if __name__ == "__main__":
    main()
