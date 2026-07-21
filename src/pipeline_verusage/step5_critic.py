#!/usr/bin/env python3
"""
Step 4: Critic — filter verified φ into true/false positives.

Two sub-steps:
  4a: Tautology check — strip spec, re-verify with Verus. If still passes → auto-FP.
  4b: LLM critic — ghost/exec check, generality check, incompleteness check.

Reads:  workspace/<task_name>/entailment_results.json + candidates.json + original.rs
Writes: workspace/<task_name>/taut_<name>.rs  (tautology test files)
        workspace/<task_name>/tautology_results.json
        workspace/<task_name>/critic_raw.txt
        workspace/<task_name>/verdicts.json
        workspace/<task_name>/summary.md

Usage:
  python3 step4_critic.py [--limit N] [--offset N] [--model MODEL] [--workspace DIR]
"""

import argparse
import json
import sys
import time
from pathlib import Path

BASE = Path.home() / "intent_formalization"

sys.path.insert(0, str(BASE / "src" / "utils"))
from llm import LLMClient
from verus import run_verus
from pipeline_common import (
    extract_spec_portion, build_entailment_file, strip_spec,
    parse_verdicts, parse_summary,
)

VERUS_BINARY = str(Path.home() / "intent_formalization" / "verus" / "verus")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CRITIC_PROMPT = """You are a spec consistency critic for Verus.

You receive a Verus source file and verified candidate properties (φ) that the spec ENTAILS.
Each φ targets an EXECUTABLE function's spec. These φ have already passed the tautology filter
(they depend on the spec — removing the spec breaks them).

For each φ, apply these checks IN ORDER:

1. GHOST/EXEC CHECK: Does the φ target a ghost struct, spec fn, or proof fn? In Verus, ghost code
   is proof-only. A ghost invariant admitting more values is a MORE GENERAL (stronger) proof, not
   a weaker spec. Only flag issues affecting executable function behavior.

2. GENERALITY CHECK: Does the φ show the spec is "too permissive"? A spec proving ∀n≥0 is strictly
   stronger than ∀n≥4. More general = stronger, not weaker — UNLESS the generality causes the spec
   to FAIL TO EXPRESS intended behavior (missing completeness/liveness for exec functions).

3. INCOMPLETENESS CHECK: Does the φ reveal something the function body guarantees but the spec
   doesn't promise? This is the real target — spec gaps that affect what callers can rely on.

Output EXACTLY this format for each:

===VERDICT_START===
PHI: <name>
VERDICT: TRUE_POSITIVE | FALSE_POSITIVE
CONFIDENCE: high | medium | low
FILTER_APPLIED: ghost_exec | generality | incompleteness | none
REASONING: <2-3 sentences, mention which check(s) you applied>
===VERDICT_END===

Then at the end:
===SUMMARY===
<one paragraph summarizing findings>
===END_SUMMARY===
"""


# ---------------------------------------------------------------------------
# Step 4a: Tautology check
# ---------------------------------------------------------------------------

def check_tautologies(task_dir: Path, verified_phis: list, candidates: list, source_text: str) -> tuple[list, list, int]:
    """Check which verified φ are tautologies (spec-independent).

    Returns: (non_tautological, tautological, count)
    """
    try:
        stripped_source = strip_spec(source_text)
    except Exception as e:
        print(f"    [warn] strip_spec failed: {e}, skipping tautology check")
        return verified_phis, [], 0

    non_tautological = []
    tautological = []
    code_map = {c["name"]: c["code"] for c in candidates}

    for p in verified_phis:
        phi_code = code_map.get(p["name"])
        if not phi_code:
            non_tautological.append(p)
            continue

        try:
            test_code = build_entailment_file(stripped_source, phi_code)
            test_file = task_dir / f"taut_{p['name']}.rs"
            test_file.write_text(test_code)
            check = run_verus(str(test_file), verus_binary=VERUS_BINARY, timeout=120)
            p["tautology"] = check.success
            if check.success:
                print(f"    [taut] {p['name']} — TAUTOLOGY (auto-FP)")
                tautological.append(p)
            else:
                non_tautological.append(p)
        except Exception as e:
            p["tautology"] = False
            p["tautology_error"] = str(e)
            non_tautological.append(p)

    # Save tautology results
    taut_results = [{"name": p["name"], "tautology": p.get("tautology", False)} for p in verified_phis]
    (task_dir / "tautology_results.json").write_text(json.dumps(taut_results, indent=2))

    return non_tautological, tautological, len(tautological)


# ---------------------------------------------------------------------------
# Step 4b: LLM Critic
# ---------------------------------------------------------------------------

def run_llm_critic(llm: LLMClient, model: str, spec_text: str, candidates: list, phis: list) -> tuple[str, list, str]:
    """Run LLM critic on non-tautological φ.

    Returns: (raw_response, verdicts, summary)
    """
    code_map = {c["name"]: c["code"] for c in candidates}

    phi_desc = ""
    for p in phis:
        phi_desc += f"\n### φ: {p['name']}"
        if p.get('target_fn'):
            phi_desc += f" (targets `{p['target_fn']}`)"
        phi_desc += f"\nType: {p.get('type', '?')} | Source: {p.get('source', 'spec_only')}\n"
        code = code_map.get(p["name"], "")
        if code:
            phi_desc += f"```verus\n{code}\n```\n"
        phi_desc += f"Reason flagged: {p.get('reason', '?')}\n"

    try:
        resp = llm.chat(
            CRITIC_PROMPT,
            f"Source file:\n```rust\n{spec_text}\n```\n\n"
            f"Verified candidate properties (passed tautology filter):\n{phi_desc}",
            model=model,
        )
        raw = resp.content
    except Exception as e:
        raw = f"ERROR: {e}"

    verdicts = parse_verdicts(raw)
    summary = parse_summary(raw)
    return raw, verdicts, summary


# ---------------------------------------------------------------------------
# Summary writer
# ---------------------------------------------------------------------------

def write_summary_md(task_dir: Path, source_path: str, all_phis: list,
                     taut_count: int, verdicts: list, llm_summary: str):
    tp = [v for v in verdicts if v.get("verdict") == "TRUE_POSITIVE"]
    fp = [v for v in verdicts if v.get("verdict") == "FALSE_POSITIVE"]
    verified = [p for p in all_phis if p.get("entailed")]

    md = f"# Spec Consistency Report\n\n"
    md += f"**Source:** `{source_path}`\n"
    md += f"**Date:** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n\n"
    md += f"## Stats\n\n"
    md += f"- Candidates generated: {len(all_phis)}\n"
    md += f"- Entailed (verified): {len(verified)}\n"
    md += f"- Tautologies filtered: {taut_count}\n"
    md += f"- True positives: {len(tp)}\n"
    md += f"- False positives: {len(fp)}\n\n"

    if llm_summary:
        md += f"## Summary\n\n{llm_summary}\n\n"

    if tp:
        md += f"## True Positives\n\n"
        for v in tp:
            md += f"### {v['phi']}\n"
            md += f"- **Confidence:** {v.get('confidence', '?')}\n"
            md += f"- **Filter:** {v.get('filter_applied', '?')}\n"
            md += f"- **Reasoning:** {v.get('reasoning', '?')}\n\n"

    md += f"## All Candidates\n\n"
    for i, p in enumerate(all_phis):
        md += f"### φ{i+1}: {p.get('name', '?')}"
        if p.get('target_fn'):
            md += f" → `{p['target_fn']}`"
        md += "\n"
        md += f"- **Type:** {p.get('type', '?')} | **Source:** {p.get('source', '?')}\n"
        md += f"- **Entailed:** {'✅' if p.get('entailed') else '❌'}\n"
        if p.get('tautology'):
            md += f"- **Tautology:** ✅ (auto-FP)\n"
        if p.get('reason'):
            md += f"- **Why flagged:** {p['reason']}\n"
        for v in verdicts:
            if v.get("phi") == p.get("name"):
                md += f"- **Verdict:** {v['verdict']} ({v.get('confidence', '?')})\n"
                break
        md += "\n"

    (task_dir / "summary.md").write_text(md)


# ---------------------------------------------------------------------------
# Task processing
# ---------------------------------------------------------------------------

def process_one(task_dir: Path, llm: LLMClient, model: str) -> dict:
    ent_file = task_dir / "entailment_results.json"
    orig_file = task_dir / "original.rs"
    cand_file = task_dir / "candidates.json"

    if not ent_file.exists():
        return {"task": task_dir.name, "status": "no_entailment"}

    all_phis = json.loads(ent_file.read_text())
    verified = [p for p in all_phis if p.get("entailed")]

    if not verified:
        write_summary_md(task_dir, str(orig_file), all_phis, 0, [], "")
        return {"task": task_dir.name, "status": "no_verified", "verified": 0}

    source_text = orig_file.read_text()
    candidates = json.loads(cand_file.read_text()) if cand_file.exists() else []
    spec_text = extract_spec_portion(source_text)

    # Step 4a: Tautology check
    print(f"  [4a] {task_dir.name} — tautology check on {len(verified)} verified φ")
    non_taut, _, taut_count = check_tautologies(task_dir, verified, candidates, source_text)

    if not non_taut:
        write_summary_md(task_dir, str(orig_file), all_phis, taut_count, [],
                         "All verified φ were tautological (spec-independent).")
        return {
            "task": task_dir.name, "status": "all_tautological",
            "verified": len(verified), "tautologies": taut_count,
            "true_positives": 0, "false_positives": 0,
        }

    # Step 4b: LLM Critic
    print(f"  [4b] {task_dir.name} — LLM critic on {len(non_taut)} non-tautological")
    raw, verdicts, llm_summary = run_llm_critic(llm, model, spec_text, candidates, non_taut)
    (task_dir / "critic_raw.txt").write_text(raw)
    (task_dir / "verdicts.json").write_text(json.dumps(verdicts, indent=2))

    tp = [v for v in verdicts if v.get("verdict") == "TRUE_POSITIVE"]
    write_summary_md(task_dir, str(orig_file), all_phis, taut_count, verdicts, llm_summary)

    print(f"  [done] {task_dir.name} — {len(tp)} TP / {len(non_taut)} non-taut / {len(verified)} verified")
    return {
        "task": task_dir.name,
        "status": "complete",
        "verified": len(verified),
        "tautologies": taut_count,
        "true_positives": len(tp),
        "false_positives": len(verdicts) - len(tp),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Step 4: Tautology filter + LLM critic")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--model", type=str, default="claude-opus-4.6")
    parser.add_argument("--workspace", type=str, default=str(BASE / "verusage" / "workspace_v4"))
    args = parser.parse_args()

    workspace = Path(args.workspace)
    task_dirs = sorted([
        d for d in workspace.iterdir()
        if d.is_dir()
        and (d / "entailment_results.json").exists()
        and not (d / "verdicts.json").exists()
    ])

    task_dirs = task_dirs[args.offset:]
    if args.limit:
        task_dirs = task_dirs[:args.limit]

    print(f"Step 4: Critic for {len(task_dirs)} tasks (model={args.model})")

    llm = LLMClient(timeout=600)
    total_tp = 0
    total_taut = 0

    for i, td in enumerate(task_dirs):
        print(f"\n[{i+1}/{len(task_dirs)}]")
        try:
            r = process_one(td, llm, args.model)
            total_tp += r.get("true_positives", 0)
            total_taut += r.get("tautologies", 0)
        except Exception as e:
            print(f"  [error] {td.name}: {e}")

    print(f"\n=== Done: {total_tp} TPs, {total_taut} tautologies filtered ===")


if __name__ == "__main__":
    main()
