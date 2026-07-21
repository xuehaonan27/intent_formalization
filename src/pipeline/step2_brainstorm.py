#!/usr/bin/env python3
"""
Step 2: Brainstorm negative properties in natural language.

Given exec functions and their specs (+ optionally body), generate a list of
"things this function should NOT do" in plain English.

Two sub-steps:
  2a: Spec-only — what the spec should exclude but might not
  2b: Body-aware — what the body guarantees but the spec doesn't promise

Reads:  workspace/<task_name>/original.rs + exec_functions.json
Writes: workspace/<task_name>/brainstorm_2a.json
        workspace/<task_name>/brainstorm_2b.json
        workspace/<task_name>/brainstorm.json  (merged)

Usage:
  python3 step2_brainstorm.py [--limit N] [--offset N] [--model MODEL] [--workspace DIR]
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

BASE = Path.home() / "intent_formalization"

sys.path.insert(0, str(BASE / "src" / "utils"))
from llm import LLMClient
from pipeline_common import extract_spec_portion


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SPEC_ONLY_BRAINSTORM = """You are analyzing a Verus (Rust verification) function's specification.

Given a function's signature, requires/ensures clauses, and related type definitions,
brainstorm properties that this function should NOT satisfy — behaviors that would be
undesirable or indicate a spec gap.

Think about:
- **Behavioral**: Could the spec accidentally allow degenerate behavior? (always return default, ignore input)
- **Boundary**: Does the spec handle edge cases? (empty input, zero, max values)
- **Logical**: Are there logical consequences the spec doesn't exclude? (contradictions, vacuous truth)

Output a JSON array of objects:
```json
[
  {
    "id": "neg_1",
    "target_fn": "function_name",
    "category": "behavioral|boundary|logical",
    "property": "Natural language description of the undesirable property",
    "reasoning": "Why this would be bad if the spec allows it"
  }
]
```

Generate AT LEAST 5 negative properties. Be specific — reference actual parameter names,
types, and spec clauses. Do NOT generate Verus code — only natural language.

## State refinement

For each negative property, also consider whether it applies universally or only under
specific object states. Derive state scenarios from the spec's own predicates and conditions
(e.g., if the spec mentions `is_full()`, consider full vs non-full states; if the spec has
a size parameter with bounds, consider boundary values).

For each property, include a `state_scenarios` field — a list of meaningful state conditions
under which the bad behavior might or might not be possible. Example:
```json
{
  "id": "neg_1",
  "target_fn": "alloc",
  "category": "behavioral",
  "property": "alloc always returns index 0",
  "reasoning": "...",
  "state_scenarios": [
    "no constraints (universal)",
    "when usage == 0 (empty)",
    "when usage == num_bits - 1 (almost full)"
  ]
}
```

Derive scenarios from the spec's predicates and parameters — do NOT hardcode domain-specific
states. The scenarios should be meaningful boundaries of the spec's own conditions.
"""

BODY_AWARE_BRAINSTORM = """You are analyzing a Verus (Rust verification) function for spec incompleteness.

Given a function's full code (body + spec), identify properties that the body guarantees
but the specification does NOT promise. These represent spec gaps — callers can't rely on
behavior the function actually provides.

Strategy:
- Read the function body carefully. What does it actually compute/guarantee?
- Compare with the ensures clause. What's missing?
- Look for: forward progress, completeness, ordering, relationships between outputs
- Check if comments mention TODO/FIXME near specs

Output a JSON array of objects:
```json
[
  {
    "id": "gap_1",
    "target_fn": "function_name",
    "category": "behavioral|boundary|logical",
    "property": "Natural language description of what the body does but spec doesn't say",
    "body_evidence": "Which part of the body guarantees this",
    "reasoning": "Why the spec should express this"
  }
]
```

Generate AT LEAST 5 properties. Be specific — reference actual code lines.
Do NOT generate Verus code — only natural language.

## State refinement

For each property, also consider whether the gap manifests universally or only under
specific object states. Derive state scenarios from the spec's own predicates and conditions
(e.g., if the spec uses `is_full()`, consider full vs non-full; if the spec has range
conditions, consider their boundaries).

For each property, include a `state_scenarios` field — a list of meaningful state conditions.
Example:
```json
{
  "id": "gap_1",
  "target_fn": "alloc",
  "category": "behavioral",
  "property": "body uses next-fit but spec doesn't capture allocation cursor",
  "body_evidence": "...",
  "reasoning": "...",
  "state_scenarios": [
    "no constraints (universal)",
    "when multiple free ranges exist"
  ]
}
```

Derive scenarios from the spec's predicates and parameters — do NOT hardcode domain-specific
states.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_json_from_response(text: str) -> list:
    """Extract JSON array from LLM response."""
    # Try to find ```json ... ``` block
    m = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try raw parse
    m = re.search(r'\[.*\]', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return []


# ---------------------------------------------------------------------------
# Sub-steps
# ---------------------------------------------------------------------------

def brainstorm_spec_only(llm: LLMClient, model: str, spec_text: str, exec_section: str) -> tuple[str, list]:
    """Step 2a: Brainstorm negative properties from spec alone."""
    user_prompt = (
        f"Source file (spec-relevant portions):\n\n```rust\n{spec_text}\n```\n"
        f"{exec_section}\n"
        f"Brainstorm at least 5 negative properties (things these functions should NOT do)."
    )
    try:
        resp = llm.chat(SPEC_ONLY_BRAINSTORM, user_prompt, model=model)
        raw = resp.content
    except Exception as e:
        raw = f"ERROR: {e}"
    props = parse_json_from_response(raw)
    for p in props:
        p["source"] = "spec_only"
    return raw, props


def brainstorm_body_aware(llm: LLMClient, model: str, spec_text: str, exec_section: str) -> tuple[str, list]:
    """Step 2b: Brainstorm spec gaps by comparing body vs spec."""
    user_prompt = (
        f"Source file (spec-relevant portions):\n\n```rust\n{spec_text}\n```\n"
        f"{exec_section}\n"
        f"Identify at least 5 properties the body guarantees but the spec doesn't express."
    )
    try:
        resp = llm.chat(BODY_AWARE_BRAINSTORM, user_prompt, model=model)
        raw = resp.content
    except Exception as e:
        raw = f"ERROR: {e}"
    props = parse_json_from_response(raw)
    for p in props:
        p["source"] = "body_aware"
    return raw, props


# ---------------------------------------------------------------------------
# Task processing
# ---------------------------------------------------------------------------

def process_one(entry: dict, llm: LLMClient, model: str, workspace: Path) -> dict:
    """Brainstorm negative properties for one file."""
    task_name = entry["task_name"]
    task_dir = workspace / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    source_text = Path(entry["file_path"]).read_text()
    spec_text = extract_spec_portion(source_text)
    exec_section = "\n\n## Executable Functions to Test:\n\n"
    for fn in entry["exec_functions"]:
        exec_section += f"### `{fn['name']}`\n```verus\n{fn['code']}\n```\n\n"

    # Step 2a: Spec-only
    print(f"  [2a] {task_name} — spec-only brainstorm")
    raw_2a, props_2a = brainstorm_spec_only(llm, model, spec_text, exec_section)
    (task_dir / "brainstorm_2a_raw.txt").write_text(raw_2a)
    (task_dir / "brainstorm_2a.json").write_text(json.dumps(props_2a, indent=2))

    # Step 2b: Body-aware
    print(f"  [2b] {task_name} — body-aware brainstorm")
    raw_2b, props_2b = brainstorm_body_aware(llm, model, spec_text, exec_section)
    (task_dir / "brainstorm_2b_raw.txt").write_text(raw_2b)
    (task_dir / "brainstorm_2b.json").write_text(json.dumps(props_2b, indent=2))

    # Merge
    all_props = props_2a + props_2b
    (task_dir / "brainstorm.json").write_text(json.dumps(all_props, indent=2))

    return {
        "task_name": task_name,
        "props_2a": len(props_2a),
        "props_2b": len(props_2b),
        "total": len(all_props),
        "status": "ok" if all_props else "no_properties",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Step 2: Brainstorm negative properties (natural language)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--model", type=str, default="claude-opus-4.6")
    parser.add_argument("--workspace", type=str, default=str(BASE / "verusage" / "workspace_v4"))
    args = parser.parse_args()

    workspace = Path(args.workspace)
    entries = json.loads((workspace / "exec_functions.json").read_text())
    entries = entries[args.offset:]
    if args.limit:
        entries = entries[:args.limit]

    print(f"Step 2: Brainstorming for {len(entries)} files (model={args.model})")
    llm = LLMClient(timeout=600)
    results = []

    for i, entry in enumerate(entries):
        print(f"\n[{i+1}/{len(entries)}]")
        try:
            r = process_one(entry, llm, args.model, workspace)
            results.append(r)
        except Exception as e:
            print(f"  [error] {entry['task_name']}: {e}")
            results.append({"task_name": entry["task_name"], "status": "error", "error": str(e)})

    total = sum(r.get("total", 0) for r in results)
    print(f"\n=== Done: {total} properties brainstormed across {len(results)} tasks ===")

    progress_file = workspace / "step2_progress.json"
    existing = json.loads(progress_file.read_text()) if progress_file.exists() else []
    existing.extend(results)
    progress_file.write_text(json.dumps(existing, indent=2))


if __name__ == "__main__":
    main()
