#!/home/chentianyu/miniconda3/bin/python3
"""
Full pipeline run on nanvix bitmap with AST-based spec extraction.
Steps: extract declarations → reuse brainstorm_v2 → formalize (new) → entailment → critic

This script imports prompts and utilities from the pipeline modules to stay in sync.
"""
import json, os, sys, re, time, subprocess
from pathlib import Path

BASE = Path.home() / "intent_formalization"
sys.path.insert(0, str(BASE / "src" / "utils"))
sys.path.insert(0, str(BASE / "src" / "pipeline"))

from verus_parser import verus_parser
from step1_extract import strip_body, extract_fn_name
from step3_formalize import (
    FORMALIZE_PROMPT, assemble_proof_fn, _rewrite_declaration_to_proof_fn,
    formalize_batch,
)
from step5_critic import CRITIC_PROMPT
from pipeline_common import parse_phi_blocks, parse_verdicts
from llm import LLMClient

VERUS_SO = str(BASE / "verus.so")
WORKSPACE = BASE / "nanvix" / "workspace" / "bitmap"
NANVIX_ROOT = Path.home() / "nanvix"
ORIGINAL_RS = WORKSPACE / "original.rs"
TEST_RS = NANVIX_ROOT / "src" / "libs" / "bitmap" / "src" / "lib.test.rs"
TEST_RS_BAK = TEST_RS.with_suffix(".rs.bak")

# Tags for this run
TAG = "v3"

def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ============================================================
# Step 1: Extract declarations from AST
# ============================================================
def step1_extract_declarations():
    log("=== STEP 1: Extract declarations ===")
    vp = verus_parser(VERUS_SO)
    source = ORIGINAL_RS.read_text()
    tree = vp.parser.parse(bytes(source, 'utf-8')).root_node
    exec_fns = vp.extract_exec_functions(tree, skip_external=True)

    declarations = {}
    exec_info = []
    for decl in exec_fns:
        name = extract_fn_name(decl)
        if name == 'main':
            continue
        decl_text = strip_body(decl)
        declarations[name] = decl_text
        exec_info.append({
            "name": name,
            "code": decl.text.decode(),
            "declaration": decl_text,
        })
        log(f"  {name}: {len(decl_text)} chars declaration")

    (WORKSPACE / "exec_functions.json").write_text(json.dumps(exec_info, indent=2))
    log(f"  → {len(declarations)} exec functions extracted")
    return declarations

# ============================================================
# Step 2: Reuse existing brainstorm
# ============================================================
def step2_load_brainstorm():
    log("=== STEP 2: Load brainstorm (reusing v2) ===")
    brainstorm = json.loads((WORKSPACE / "brainstorm_v2.json").read_text())
    log(f"  → {len(brainstorm)} properties loaded")
    return brainstorm

# ============================================================
# Step 3: Formalize with AST-based spec extraction
# ============================================================
def step3_formalize(declarations, properties):
    log("=== STEP 3: Formalize (AST-based) ===")
    llm = LLMClient(timeout=600)
    source_path = str(ORIGINAL_RS.resolve())

    BATCH_SIZE = 5
    all_candidates = []
    all_raw = []

    for batch_start in range(0, len(properties), BATCH_SIZE):
        batch = properties[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(properties) + BATCH_SIZE - 1) // BATCH_SIZE

        log(f"  batch {batch_num}/{total_batches} ({len(batch)} properties)...")
        t0 = time.time()
        raw, candidates = formalize_batch(llm, "claude-opus-4.6", source_path, batch, declarations)
        elapsed = time.time() - t0

        # Assemble full proof fns
        for c in candidates:
            if "body" in c:
                c["code"] = assemble_proof_fn(c, declarations)

        all_raw.append(f"=== BATCH {batch_num} ===\n{raw}")
        all_candidates.extend(candidates)
        log(f"  → {len(candidates)} φ in {elapsed:.0f}s")

    (WORKSPACE / f"formalize_{TAG}_raw.txt").write_text("\n\n".join(all_raw))
    (WORKSPACE / f"candidates_{TAG}.json").write_text(json.dumps(all_candidates, indent=2))
    log(f"  → Total: {len(all_candidates)} candidates")
    return all_candidates

# ============================================================
# Step 4: Entailment — inject φ into source and run Verus
# ============================================================
def step4_entailment(candidates):
    log("=== STEP 4: Entailment ===")

    # Read original test file
    original_test = TEST_RS_BAK.read_text() if TEST_RS_BAK.exists() else TEST_RS.read_text()

    # Find insertion point (before closing `}` of verus!{} block)
    insert_marker = "\n} // verus!"
    idx = original_test.index(insert_marker)
    base = original_test[:idx]
    suffix = original_test[idx:]

    # Build φ block
    phi_code = f"\n\n// ===== GENERATED PHI TESTS ({TAG} — AST-based) =====\n\n"
    written = 0
    for c in candidates:
        code = c.get("code", "")
        if code and "proof fn" in code:
            phi_code += f"{code}\n\n"
            written += 1

    full_test = base + phi_code + suffix
    TEST_RS.write_text(full_test)
    log(f"  Written {len(full_test)} chars, {written} proof fns")

    # Run Verus
    log("  Running Verus verification...")
    t0 = time.time()
    result = subprocess.run(
        ["bash", "scripts/verify-bitmap.sh"],
        capture_output=True, text=True, timeout=600,
        cwd=str(NANVIX_ROOT)
    )
    elapsed = time.time() - t0
    log(f"  Verus completed in {elapsed:.0f}s")

    stderr = result.stderr
    (WORKSPACE / f"verus_{TAG}_stderr.txt").write_text(stderr)

    # Parse: extract fn names that appear in error context
    failed_fns = set()
    for m in re.finditer(r'proof fn (phi_\S+)\(', stderr):
        failed_fns.add(m.group(1))

    # Parse verification summary
    summary_m = re.search(r'(\d+) verified, (\d+) errors', stderr)
    if summary_m:
        log(f"  Results: {summary_m.group(1)} verified, {summary_m.group(2)} errors")

    # Map candidates to results
    for c in candidates:
        code = c.get("code", "")
        fn_m = re.search(r'proof fn (\S+)\(', code)
        if fn_m:
            code_fn = fn_m.group(1)
            c["code_fn"] = code_fn
            c["entailed"] = code_fn not in failed_fns
            c["verified"] = code_fn not in failed_fns
        else:
            c["code_fn"] = ""
            c["entailed"] = False
            c["verified"] = False

    verified = [c for c in candidates if c.get("entailed")]
    failed = [c for c in candidates if not c.get("entailed")]
    log(f"  → {len(verified)} verified (incomplete), {len(failed)} failed (complete)")

    (WORKSPACE / f"entailment_{TAG}.json").write_text(json.dumps(candidates, indent=2))

    return candidates

# ============================================================
# Step 5: Critic (uses prompt from step5_critic.py)
# ============================================================
def step5_critic(candidates):
    log("=== STEP 5: Critic ===")
    verified = [c for c in candidates if c.get("entailed")]
    if not verified:
        log("  No verified φ to critique")
        return

    log(f"  {len(verified)} verified φ to critique")

    phi_text = ""
    for i, r in enumerate(verified):
        phi_text += f"\n### φ{i+1}: {r.get('code_fn', r.get('name', '?'))}\n"
        phi_text += f"- Target: `{r.get('target_fn', '?')}`\n"
        phi_text += f"- Property: {r.get('property', '?')}\n"
        phi_text += f"- Code:\n```rust\n{r.get('code', '')}\n```\n"

    user_prompt = (
        f"Read the Verus source file at: {ORIGINAL_RS.resolve()}\n\n"
        f"## Verified (entailed) φ candidates:\n{phi_text}\n\n"
        f"Evaluate each φ and output verdicts."
    )

    llm = LLMClient(timeout=300)
    t0 = time.time()
    resp = llm.chat(CRITIC_PROMPT, user_prompt, model="claude-opus-4.6")
    raw = resp.content
    elapsed = time.time() - t0

    (WORKSPACE / f"critic_{TAG}_raw.txt").write_text(raw)

    tp = raw.lower().count('true_positive')
    fp = raw.lower().count('false_positive')
    log(f"  → {tp} TP, {fp} FP in {elapsed:.0f}s")

    verdicts = parse_verdicts(raw)
    (WORKSPACE / f"verdicts_{TAG}.json").write_text(json.dumps(verdicts, indent=2))

    return verdicts

# ============================================================
# Main
# ============================================================
def main():
    log(f"Pipeline {TAG} — Full run on nanvix bitmap")
    log(f"Workspace: {WORKSPACE}")

    # Step 1
    declarations = step1_extract_declarations()

    # Step 2
    properties = step2_load_brainstorm()

    # Step 3
    candidates = step3_formalize(declarations, properties)

    if not candidates:
        log("ERROR: no candidates generated")
        return

    # Step 4
    candidates = step4_entailment(candidates)

    # Step 5
    verdicts = step5_critic(candidates)

    # Summary
    verified = sum(1 for c in candidates if c.get("entailed"))
    failed = sum(1 for c in candidates if not c.get("entailed"))
    log(f"\n{'='*60}")
    log(f"PIPELINE {TAG} COMPLETE")
    log(f"  Candidates: {len(candidates)}")
    log(f"  Entailment: {verified} verified / {failed} failed")
    if verdicts:
        tp = sum(1 for v in verdicts if v.get("verdict", "").upper() == "TRUE_POSITIVE")
        fp = sum(1 for v in verdicts if v.get("verdict", "").upper() == "FALSE_POSITIVE")
        log(f"  Critic: {tp} TP / {fp} FP")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
