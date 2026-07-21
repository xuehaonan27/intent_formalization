#!/usr/bin/env python3
"""
Step 3: Formalize natural-language negative properties into Verus proof functions.

Takes brainstormed properties (natural language) and generates corresponding
Verus proof fn code for entailment checking.

Reads:  workspace/<task_name>/brainstorm.json + original.rs
Writes: workspace/<task_name>/candidates.json

Usage:
  python3 step3_formalize.py [--limit N] [--offset N] [--model MODEL] [--workspace DIR]
"""

import argparse
import json
import sys
import time
from pathlib import Path

BASE = Path.home() / "intent_formalization"

sys.path.insert(0, str(BASE / "src" / "utils"))
from llm import LLMClient
from pipeline_common import extract_spec_portion, parse_phi_blocks


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

FORMALIZE_PROMPT = """You are a Verus (Rust verification) code generator.

You are given:
1. A Verus source file with type definitions, spec functions, and executable functions
2. A list of negative properties described in natural language

Your job: for EACH property, write a Verus `proof fn` that formalizes it.
If the spec entails this proof fn (Verus verifies it), it means the spec ALLOWS this
undesirable behavior — a spec consistency issue.

For EACH property, output in this EXACT format:

===PHI_START===
NAME: <short_snake_case_name>
TARGET_FN: <name of the exec function being tested>
TYPE: behavioral | boundary | logical
SOURCE: <source from the property: spec_only or body_aware>
PROPERTY: <the natural language property being formalized>
CODE:
```verus
proof fn phi_<n>_<snake_name>(<params>)
    requires
        <preconditions from the spec>,
    ensures
        <the undesirable property formalized>,
{
}
```
REASON: <one line why this would be undesirable if entailed>
===PHI_END===

RULES:
- Generate ONE proof fn per input property (match them 1:1)
- Each proof fn will be appended inside the existing verus!{} block
- Use types/functions/traits from the source file
- Do NOT add new `use`/`mod` statements or wrap in verus!{}
- Keep proof bodies SHORT — rely on Verus's SMT solver
- If a property is too vague to formalize, do your best and note it in REASON
"""


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def formalize_batch(llm: LLMClient, model: str, spec_text: str, properties: list) -> tuple[str, list]:
    """Formalize a batch of natural-language properties into Verus code."""
    prop_text = ""
    for i, p in enumerate(properties):
        prop_text += f"\n### Property {i+1}: {p.get('id', f'prop_{i+1}')}\n"
        prop_text += f"- **Target:** `{p.get('target_fn', '?')}`\n"
        prop_text += f"- **Category:** {p.get('category', '?')}\n"
        prop_text += f"- **Source:** {p.get('source', '?')}\n"
        prop_text += f"- **Property:** {p.get('property', '?')}\n"
        if p.get('body_evidence'):
            prop_text += f"- **Body evidence:** {p['body_evidence']}\n"
        prop_text += f"- **Reasoning:** {p.get('reasoning', '?')}\n"

    user_prompt = (
        f"Source file (spec-relevant portions):\n\n```rust\n{spec_text}\n```\n"
        f"\n## Properties to formalize:\n{prop_text}\n"
        f"\nFormalize each property into a Verus proof fn."
    )

    try:
        resp = llm.chat(FORMALIZE_PROMPT, user_prompt, model=model)
        raw = resp.content
    except Exception as e:
        raw = f"ERROR: {e}"

    candidates = parse_phi_blocks(raw)
    return raw, candidates


def process_one(task_dir: Path, llm: LLMClient, model: str) -> dict:
    """Formalize brainstormed properties for one task."""
    brainstorm_file = task_dir / "brainstorm.json"
    original_file = task_dir / "original.rs"

    if not brainstorm_file.exists() or not original_file.exists():
        return {"task": task_dir.name, "status": "missing_files"}

    properties = json.loads(brainstorm_file.read_text())
    if not properties:
        return {"task": task_dir.name, "status": "no_properties", "candidates": 0}

    source_text = original_file.read_text()
    spec_text = extract_spec_portion(source_text)

    # Batch properties in groups of 5 to avoid timeout on large files
    BATCH_SIZE = 5
    all_candidates = []
    all_raw = []

    for batch_start in range(0, len(properties), BATCH_SIZE):
        batch = properties[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(properties) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  [form] {task_dir.name} — batch {batch_num}/{total_batches} ({len(batch)} properties)")

        raw, candidates = formalize_batch(llm, model, spec_text, batch)
        all_raw.append(f"=== BATCH {batch_num} ===\n{raw}")
        all_candidates.extend(candidates)

    (task_dir / "formalize_raw.txt").write_text("\n\n".join(all_raw))
    (task_dir / "candidates.json").write_text(json.dumps(all_candidates, indent=2))

    return {
        "task": task_dir.name,
        "properties": len(properties),
        "candidates": len(candidates),
        "status": "ok" if candidates else "no_candidates",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Step 3: Formalize properties into Verus code")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--model", type=str, default="claude-opus-4.6")
    parser.add_argument("--workspace", type=str, default=str(BASE / "verusage" / "workspace_v4"))
    args = parser.parse_args()

    workspace = Path(args.workspace)
    task_dirs = sorted([
        d for d in workspace.iterdir()
        if d.is_dir()
        and (d / "brainstorm.json").exists()
        and not (d / "candidates.json").exists()
    ])

    task_dirs = task_dirs[args.offset:]
    if args.limit:
        task_dirs = task_dirs[:args.limit]

    print(f"Step 3: Formalizing for {len(task_dirs)} tasks (model={args.model})")
    llm = LLMClient(timeout=600)

    total_candidates = 0
    for i, td in enumerate(task_dirs):
        print(f"\n[{i+1}/{len(task_dirs)}]")
        try:
            r = process_one(td, llm, args.model)
            total_candidates += r.get("candidates", 0)
            print(f"  → {r['status']} ({r.get('candidates', 0)} candidates)")
        except Exception as e:
            print(f"  [error] {td.name}: {e}")

    print(f"\n=== Done: {total_candidates} candidates formalized ===")


if __name__ == "__main__":
    main()
