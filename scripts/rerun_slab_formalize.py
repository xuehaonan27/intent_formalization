#!/home/chentianyu/miniconda3/bin/python3
"""Re-run only the failed formalize batches for slab, then entailment + critic."""
import json, sys, time, re, subprocess, shutil
from pathlib import Path

BASE = Path.home() / "intent_formalization"
sys.path.insert(0, str(BASE / "src" / "utils"))
sys.path.insert(0, str(BASE / "src" / "pipeline"))

from step3_formalize import FORMALIZE_PROMPT, assemble_proof_fn, formalize_batch, parse_phi_blocks
from step5_critic import CRITIC_PROMPT
from pipeline_common import parse_verdicts
from llm import LLMClient

WORKSPACE = BASE / "nanvix" / "workspace" / "slab"
NANVIX_ROOT = Path.home() / "nanvix"
ORIGINAL_RS = WORKSPACE / "original.rs"
SLAB_TEST_RS = NANVIX_ROOT / "src" / "libs" / "slab" / "src" / "test.rs"
SLAB_TEST_RS_BAK = SLAB_TEST_RS.with_suffix(".rs.bak")
TAG = "v2"

def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def main():
    log("=== Re-run failed formalize batches for slab ===")

    # Load existing data
    properties = json.loads((WORKSPACE / "brainstorm.json").read_text())
    exec_info = json.loads((WORKSPACE / "exec_functions.json").read_text())
    declarations = {fn["name"]: fn["declaration"] for fn in exec_info}

    # Load existing candidates from v1 (batch 2 succeeded with 19 φ)
    existing_candidates = json.loads((WORKSPACE / "candidates_v1.json").read_text())
    log(f"  Existing candidates from v1: {len(existing_candidates)}")

    # Failed batches: 1 (props 0-4), 3 (props 10-14), 4 (props 15-17)
    BATCH_SIZE = 5
    failed_batches = []
    for batch_start in range(0, len(properties), BATCH_SIZE):
        batch_num = batch_start // BATCH_SIZE + 1
        if batch_num in (1, 3, 4):  # these failed
            failed_batches.append((batch_num, properties[batch_start:batch_start + BATCH_SIZE]))

    llm = LLMClient(timeout=1200)
    source_path = str(ORIGINAL_RS.resolve())
    MAX_RETRIES = 3

    new_candidates = []
    all_raw = []

    for batch_num, batch in failed_batches:
        raw = ""
        candidates = []
        for attempt in range(1, MAX_RETRIES + 1):
            log(f"  batch {batch_num} ({len(batch)} props) attempt {attempt}/{MAX_RETRIES}...")
            t0 = time.time()
            raw, candidates = formalize_batch(llm, "claude-opus-4.6", source_path, batch, declarations)
            elapsed = time.time() - t0

            if candidates or "ERROR" not in raw:
                break
            log(f"  ⚠ attempt {attempt} failed ({elapsed:.0f}s): {raw[:100]}")
            if attempt < MAX_RETRIES:
                log(f"  retrying in 10s...")
                time.sleep(10)

        for c in candidates:
            if "body" in c:
                c["code"] = assemble_proof_fn(c, declarations)

        all_raw.append(f"=== BATCH {batch_num} (attempt {attempt}) ===\n{raw}")
        new_candidates.extend(candidates)
        log(f"  → {len(candidates)} φ in {elapsed:.0f}s")

    # Merge with existing
    all_candidates = existing_candidates + new_candidates
    (WORKSPACE / f"formalize_{TAG}_raw.txt").write_text("\n\n".join(all_raw))
    (WORKSPACE / f"candidates_{TAG}.json").write_text(json.dumps(all_candidates, indent=2))
    log(f"  → Total: {len(all_candidates)} candidates ({len(existing_candidates)} existing + {len(new_candidates)} new)")

    if not all_candidates:
        log("ERROR: no candidates")
        return

    # === Step 4: Entailment ===
    log("=== STEP 4: Entailment ===")
    if not SLAB_TEST_RS_BAK.exists():
        if SLAB_TEST_RS.exists():
            shutil.copy2(SLAB_TEST_RS, SLAB_TEST_RS_BAK)
        else:
            SLAB_TEST_RS_BAK.write_text("verus! {\n\n} // verus!\n")

    original_test = SLAB_TEST_RS_BAK.read_text()
    insert_marker = "\n} // verus!"
    if insert_marker in original_test:
        idx = original_test.index(insert_marker)
        base = original_test[:idx]
        suffix = original_test[idx:]
    else:
        idx = original_test.rstrip().rfind("}")
        base = original_test[:idx]
        suffix = original_test[idx:]

    phi_code = f"\n\n// ===== GENERATED PHI TESTS (slab {TAG}) =====\n\n"
    written = 0
    for c in all_candidates:
        code = c.get("code", "")
        if code and "proof fn" in code:
            phi_code += f"{code}\n\n"
            written += 1

    full_test = base + phi_code + suffix
    SLAB_TEST_RS.write_text(full_test)
    log(f"  Written {len(full_test)} chars, {written} proof fns")

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

    failed_fns = set()
    for m in re.finditer(r'proof fn (phi_\S+)\(', stderr):
        failed_fns.add(m.group(1))

    summary_m = re.search(r'(\d+) verified, (\d+) errors', stderr)
    if summary_m:
        log(f"  Results: {summary_m.group(1)} verified, {summary_m.group(2)} errors")

    for c in all_candidates:
        code = c.get("code", "")
        fn_m = re.search(r'proof fn (\S+)\(', code)
        if fn_m:
            c["code_fn"] = fn_m.group(1)
            c["entailed"] = c["code_fn"] not in failed_fns
        else:
            c["code_fn"] = ""
            c["entailed"] = False

    verified = [c for c in all_candidates if c.get("entailed")]
    failed = [c for c in all_candidates if not c.get("entailed")]
    log(f"  → {len(verified)} verified (incomplete), {len(failed)} failed (complete)")

    (WORKSPACE / f"entailment_{TAG}.json").write_text(json.dumps(all_candidates, indent=2))

    # === Step 5: Critic ===
    log("=== STEP 5: Critic ===")
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

    t0 = time.time()
    resp = llm.chat(CRITIC_PROMPT, user_prompt, model="claude-opus-4.6")
    raw = resp.content
    elapsed = time.time() - t0

    (WORKSPACE / f"critic_{TAG}_raw.txt").write_text(raw)
    verdicts = parse_verdicts(raw)
    (WORKSPACE / f"verdicts_{TAG}.json").write_text(json.dumps(verdicts, indent=2))

    tp = sum(1 for v in verdicts if v.get("verdict", "").upper() == "TRUE_POSITIVE")
    fp = sum(1 for v in verdicts if v.get("verdict", "").upper() == "FALSE_POSITIVE")
    log(f"  → {tp} TP, {fp} FP in {elapsed:.0f}s")

    log(f"\n{'='*60}")
    log(f"PIPELINE SLAB {TAG} COMPLETE")
    log(f"  Candidates: {len(all_candidates)}")
    log(f"  Entailment: {len(verified)} verified / {len(failed)} failed")
    log(f"  Critic: {tp} TP / {fp} FP")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()
