#!/home/chentianyu/miniconda3/bin/python3
"""
Full pipeline run on nanvix slab with AST-based spec extraction.
Adapts run_pipeline_v3.py (bitmap) for the slab module.
"""
import json, os, sys, re, time, subprocess
from pathlib import Path

BASE = Path.home() / "intent_formalization"
sys.path.insert(0, str(BASE / "src" / "utils"))
sys.path.insert(0, str(BASE / "src" / "pipeline"))

from verus_parser import verus_parser
from step1_extract import strip_body, extract_fn_name
from step3_formalize import (
    FORMALIZE_PROMPT, assemble_proof_fn, formalize_batch,
)
from step2_brainstorm import SPEC_ONLY_BRAINSTORM, BODY_AWARE_BRAINSTORM
from step5_critic import CRITIC_PROMPT
from pipeline_common import parse_phi_blocks, parse_verdicts
from llm import LLMClient

VERUS_SO = str(BASE / "verus.so")
WORKSPACE = BASE / "nanvix" / "workspace" / "slab"
NANVIX_ROOT = Path.home() / "nanvix"
ORIGINAL_RS = WORKSPACE / "original.rs"
SLAB_TEST_RS = NANVIX_ROOT / "src" / "libs" / "slab" / "src" / "test.rs"
SLAB_TEST_RS_BAK = SLAB_TEST_RS.with_suffix(".rs.bak")

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
    return declarations, exec_info

# ============================================================
# Step 2: Brainstorm negative properties
# ============================================================
def step2_brainstorm(exec_info):
    log("=== STEP 2: Brainstorm ===")
    llm = LLMClient(timeout=300)
    source_path = str(ORIGINAL_RS.resolve())

    # Build exec function summary for prompt
    fn_summary = ""
    for fn in exec_info:
        fn_summary += f"\n### `{fn['name']}`\n```rust\n{fn['declaration']}\n```\n"

    # 2a: Spec-only brainstorm
    user_2a = (
        f"Read the Verus source file at: {source_path}\n\n"
        f"## Executable functions:\n{fn_summary}\n\n"
        f"Generate negative properties (things the spec should exclude but might not)."
    )
    log("  Running spec-only brainstorm...")
    t0 = time.time()
    resp_2a = llm.chat(SPEC_ONLY_BRAINSTORM, user_2a, model="claude-opus-4.6")
    raw_2a = resp_2a.content
    log(f"  Spec-only done in {time.time()-t0:.0f}s")
    (WORKSPACE / "brainstorm_2a_raw.txt").write_text(raw_2a)

    # 2b: Body-aware brainstorm
    user_2b = (
        f"Read the Verus source file at: {source_path}\n\n"
        f"## Executable functions:\n{fn_summary}\n\n"
        f"Generate body-aware negative properties (things the body guarantees but the spec doesn't)."
    )
    log("  Running body-aware brainstorm...")
    t0 = time.time()
    resp_2b = llm.chat(BODY_AWARE_BRAINSTORM, user_2b, model="claude-opus-4.6")
    raw_2b = resp_2b.content
    log(f"  Body-aware done in {time.time()-t0:.0f}s")
    (WORKSPACE / "brainstorm_2b_raw.txt").write_text(raw_2b)

    # Parse and merge
    properties = _parse_brainstorm(raw_2a, "spec_only") + _parse_brainstorm(raw_2b, "body_aware")
    (WORKSPACE / "brainstorm.json").write_text(json.dumps(properties, indent=2))
    log(f"  → {len(properties)} total properties")
    return properties


def _parse_brainstorm(raw, source):
    """Parse brainstorm output into property dicts (JSON format)."""
    # Try ```json ... ``` code fence first
    m = re.search(r'```json\s*\n(.*?)\n```', raw, re.DOTALL)
    if m:
        try:
            items = json.loads(m.group(1))
            for item in items:
                item["source"] = source
            return items
        except json.JSONDecodeError:
            pass
    # Try raw JSON array
    m = re.search(r'\[.*\]', raw, re.DOTALL)
    if m:
        try:
            items = json.loads(m.group(0))
            for item in items:
                item["source"] = source
            return items
        except json.JSONDecodeError:
            pass
    return []

# ============================================================
# Step 3: Formalize
# ============================================================
def step3_formalize(declarations, properties):
    log("=== STEP 3: Formalize (AST-based) ===")
    llm = LLMClient(timeout=1200)
    source_path = str(ORIGINAL_RS.resolve())

    MAX_RETRIES = 3
    BATCH_SIZE = 5
    all_candidates = []
    all_raw = []

    for batch_start in range(0, len(properties), BATCH_SIZE):
        batch = properties[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(properties) + BATCH_SIZE - 1) // BATCH_SIZE

        raw = ""
        candidates = []
        for attempt in range(1, MAX_RETRIES + 1):
            log(f"  batch {batch_num}/{total_batches} ({len(batch)} props) attempt {attempt}/{MAX_RETRIES}...")
            t0 = time.time()
            raw, candidates = formalize_batch(llm, "claude-opus-4.6", source_path, batch, declarations)
            elapsed = time.time() - t0

            if candidates or "ERROR" not in raw:
                break
            log(f"  ⚠ batch {batch_num} attempt {attempt} failed ({elapsed:.0f}s): {raw[:100]}")
            if attempt < MAX_RETRIES:
                log(f"  retrying in 10s...")
                time.sleep(10)

        for c in candidates:
            if "body" in c:
                c["code"] = assemble_proof_fn(c, declarations)

        all_raw.append(f"=== BATCH {batch_num} (attempt {attempt}) ===\n{raw}")
        all_candidates.extend(candidates)
        log(f"  → {len(candidates)} φ in {elapsed:.0f}s")

    (WORKSPACE / f"formalize_{TAG}_raw.txt").write_text("\n\n".join(all_raw))
    (WORKSPACE / f"candidates_{TAG}.json").write_text(json.dumps(all_candidates, indent=2))
    log(f"  → Total: {len(all_candidates)} candidates")
    return all_candidates

# ============================================================
# Step 4: Entailment
# ============================================================
def step4_entailment(candidates):
    log("=== STEP 4: Entailment ===")

    # Backup test file
    if not SLAB_TEST_RS_BAK.exists():
        if SLAB_TEST_RS.exists():
            import shutil
            shutil.copy2(SLAB_TEST_RS, SLAB_TEST_RS_BAK)
        else:
            # Create empty test file
            SLAB_TEST_RS_BAK.write_text("verus! {\n\n} // verus!\n")

    original_test = SLAB_TEST_RS_BAK.read_text()

    # Find insertion point
    insert_marker = "\n} // verus!"
    if insert_marker not in original_test:
        # Try to find closing brace of verus! block
        if "verus!" in original_test:
            # Insert before last }
            idx = original_test.rstrip().rfind("}")
            base = original_test[:idx]
            suffix = original_test[idx:]
        else:
            # No verus block, wrap in one
            base = "verus! {\n" + original_test
            suffix = "\n} // verus!\n"
    else:
        idx = original_test.index(insert_marker)
        base = original_test[:idx]
        suffix = original_test[idx:]

    phi_code = f"\n\n// ===== GENERATED PHI TESTS (slab {TAG} — AST-based) =====\n\n"
    written = 0
    for c in candidates:
        code = c.get("code", "")
        if code and "proof fn" in code:
            phi_code += f"{code}\n\n"
            written += 1

    full_test = base + phi_code + suffix
    SLAB_TEST_RS.write_text(full_test)
    log(f"  Written {len(full_test)} chars, {written} proof fns")

    # Run Verus
    log("  Running Verus verification...")
    t0 = time.time()
    result = subprocess.run(
        ["bash", "scripts/verify-slab.sh"],
        capture_output=True, text=True, timeout=600,
        cwd=str(NANVIX_ROOT)
    )
    elapsed = time.time() - t0
    log(f"  Verus completed in {elapsed:.0f}s")

    stderr = result.stderr
    (WORKSPACE / f"verus_{TAG}_stderr.txt").write_text(stderr)

    # Parse failed fns
    failed_fns = set()
    for m in re.finditer(r'proof fn (phi_\S+)\(', stderr):
        failed_fns.add(m.group(1))

    summary_m = re.search(r'(\d+) verified, (\d+) errors', stderr)
    if summary_m:
        log(f"  Results: {summary_m.group(1)} verified, {summary_m.group(2)} errors")

    for c in candidates:
        code = c.get("code", "")
        fn_m = re.search(r'proof fn (\S+)\(', code)
        if fn_m:
            c["code_fn"] = fn_m.group(1)
            c["entailed"] = c["code_fn"] not in failed_fns
        else:
            c["code_fn"] = ""
            c["entailed"] = False

    verified = [c for c in candidates if c.get("entailed")]
    failed = [c for c in candidates if not c.get("entailed")]
    log(f"  → {len(verified)} verified (incomplete), {len(failed)} failed (complete)")

    (WORKSPACE / f"entailment_{TAG}.json").write_text(json.dumps(candidates, indent=2))
    return candidates

# ============================================================
# Step 5: Critic
# ============================================================
def step5_critic(candidates):
    log("=== STEP 5: Critic ===")
    verified = [c for c in candidates if c.get("entailed")]
    if not verified:
        log("  No verified φ to critique")
        return None

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

    verdicts = parse_verdicts(raw)
    (WORKSPACE / f"verdicts_{TAG}.json").write_text(json.dumps(verdicts, indent=2))

    tp = sum(1 for v in verdicts if v.get("verdict","").upper() == "TRUE_POSITIVE")
    fp = sum(1 for v in verdicts if v.get("verdict","").upper() == "FALSE_POSITIVE")
    log(f"  → {tp} TP, {fp} FP in {elapsed:.0f}s")

    return verdicts

# ============================================================
# Main
# ============================================================
def main():
    log(f"Pipeline slab {TAG} — Full run on nanvix slab")
    log(f"Workspace: {WORKSPACE}")

    declarations, exec_info = step1_extract_declarations()
    properties = step2_brainstorm(exec_info)

    if not properties:
        log("ERROR: no properties brainstormed")
        return

    candidates = step3_formalize(declarations, properties)

    if not candidates:
        log("ERROR: no candidates generated")
        return

    candidates = step4_entailment(candidates)
    verdicts = step5_critic(candidates)

    # Summary
    verified = sum(1 for c in candidates if c.get("entailed"))
    failed = sum(1 for c in candidates if not c.get("entailed"))
    log(f"\n{'='*60}")
    log(f"PIPELINE SLAB {TAG} COMPLETE")
    log(f"  Candidates: {len(candidates)}")
    log(f"  Entailment: {verified} verified / {failed} failed")
    if verdicts:
        tp = sum(1 for v in verdicts if v.get("verdict", "").upper() == "TRUE_POSITIVE")
        fp = sum(1 for v in verdicts if v.get("verdict", "").upper() == "FALSE_POSITIVE")
        log(f"  Critic: {tp} TP / {fp} FP")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
