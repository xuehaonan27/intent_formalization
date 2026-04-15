"""
Step 3 (fuzz): Enumerate seed cases via Cartesian product of scenario × arg domain.

For each function template (from step2), expand all (state_scenario, arg_values,
return_path) combinations into concrete Case objects. The assume statements are
left as descriptive comments/placeholders — step4 / LLM will flesh out exact
Verus values.

Outputs: <task_dir>/seed_cases.json

Usage:
  python -m src.pipeline_fuzz.step3_enumerate --task-dir <path>
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

from src.pipeline_fuzz.schemas import Case


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_value(v) -> str:
    """Format a domain value as a Verus literal string."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return str(v)


def _build_arg_assumes(arg_domains: list[dict], arg_values: tuple) -> list[str]:
    """
    Build arg_assumes from one concrete (arg_name, value) combination.
    """
    assumes = []
    for domain_info, val in zip(arg_domains, arg_values):
        name = domain_info["name"]
        assumes.append(f"{name} == {_format_value(val)}")
    return assumes


def _build_pre_assumes(scenario: dict) -> list[str]:
    """Convert scenario pre_constraints into pre_assumes."""
    constraints = scenario.get("pre_constraints", [])
    # Strip comment-only constraints — keep real ones
    result = []
    for c in constraints:
        c = c.strip()
        if c.startswith("//"):
            # It's a hint comment; include as a commented assume for readability
            result.append(c)
        else:
            result.append(c)
    return result


def _build_result_assume(return_path: str) -> str | None:
    """Translate a return path name into a result_assume hint."""
    if return_path == "Ok":
        return "result is Ok"
    elif return_path == "Err":
        return "result is Err"
    else:
        return None  # scalar returns — no result assume needed


def enumerate_cases(template: dict, task: str) -> list[Case]:
    """
    Enumerate seed cases for one function template.
    """
    fn_name = template["fn"]
    arg_domains = template.get("arg_domains", [])
    return_paths = template.get("return_paths", ["Ok"])
    state_scenarios = template.get("state_scenarios", [{"name": "general", "pre_constraints": []}])

    # Build domain value lists — cap each domain at 4 values to limit explosion
    MAX_DOMAIN = 4
    domain_lists = [d["domain"][:MAX_DOMAIN] for d in arg_domains]

    # If no args, use a single empty combination
    if not domain_lists:
        arg_combinations = [()]
    else:
        arg_combinations = list(itertools.product(*domain_lists))

    cases: list[Case] = []
    case_counter = 0

    for scenario in state_scenarios:
        for arg_vals in arg_combinations:
            for ret_path in return_paths:
                case_id = f"{fn_name}_{case_counter}"
                case_counter += 1

                pre_assumes = _build_pre_assumes(scenario)
                arg_assumes = _build_arg_assumes(arg_domains, arg_vals)
                result_assume = _build_result_assume(ret_path)

                cases.append(Case(
                    task=task,
                    fn=fn_name,
                    case_id=case_id,
                    pre_assumes=pre_assumes,
                    arg_assumes=arg_assumes,
                    post_assumes=[],  # step4/LLM fills these in
                    result_assume=result_assume,
                ))

    return cases


def process_one(task_dir: Path) -> list[Case]:
    """
    Enumerate seed cases for all functions and write seed_cases.json.
    """
    templates_path = task_dir / "templates.json"
    if not templates_path.exists():
        raise FileNotFoundError(f"templates.json not found in {task_dir}")

    templates = json.loads(templates_path.read_text())
    task_name = task_dir.name

    all_cases: list[Case] = []
    for tmpl in templates:
        fn_cases = enumerate_cases(tmpl, task_name)
        all_cases.extend(fn_cases)

    (task_dir / "seed_cases.json").write_text(
        json.dumps([c.to_dict() for c in all_cases], indent=2)
    )
    return all_cases


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 3 (fuzz): Enumerate seed cases from templates"
    )
    parser.add_argument("--task-dir", type=str, required=True)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).resolve()
    print(f"[step3] Enumerating seed cases for {task_dir.name}")

    try:
        cases = process_one(task_dir)
    except FileNotFoundError as e:
        print(f"[step3] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    fn_counts: dict[str, int] = {}
    for c in cases:
        fn_counts[c.fn] = fn_counts.get(c.fn, 0) + 1

    for fn, cnt in fn_counts.items():
        print(f"  fn={fn:20s}  seed_cases={cnt}")

    print(f"[step3] Total seed cases: {len(cases)}")
    print(f"[step3] Wrote seed_cases.json → {task_dir / 'seed_cases.json'}")


if __name__ == "__main__":
    main()
