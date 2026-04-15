"""
Step 5 (fuzz): LLM oracle — label each case ACCEPT or REJECT.

The oracle sees:
  - The original Rust source's function signature + doc comments (NOT the Verus spec)
  - The project-level intent (inferred from the source filename/path)
  - The concrete case (pre-state, args, post-state, result)

It does NOT see the Verus spec or the exec body — that would bias it to
parrot the artifact under test.

Outputs: <task_dir>/cases_labeled.json  (cases_diversified + oracle labels)

LLM cache: <workspace>/.cache/fuzz/<sha256>.json

Usage:
  python -m src.pipeline_fuzz.step5_oracle --task-dir <path> [--model MODEL]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from pathlib import Path

from src.utils.llm import LLMClient
from src.pipeline_fuzz.schemas import Case, OracleLabel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

ORACLE_SYSTEM = """You are a semantic oracle for Rust function specification testing.

You will be given:
1. A Rust function's SIGNATURE and DOC COMMENTS only (no body, no Verus spec).
2. The project/module context (name and purpose).
3. A concrete test case: a (pre-state, args, post-state, result) tuple.

Your task: decide whether a correct, reasonable implementation of this function
SHOULD be able to produce this (post-state, result) from this (pre-state, args).

- ACCEPT: A correct implementation could legitimately produce this output.
- REJECT: No correct implementation should ever produce this output.

Rules:
- Reason from the function's NAME, DOC COMMENTS, and common-sense semantics.
- Do NOT reason about Verus specs, formal logic, or implementation details.
- Be conservative with REJECT — only reject if the output is clearly wrong
  for ANY reasonable implementation of a function with this name/docs.

Output EXACTLY this format (one line each):
LABEL: ACCEPT|REJECT
JUSTIFICATION: <one sentence>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cache_dir(workspace: Path) -> Path:
    d = workspace / ".cache" / "fuzz"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


def _llm_call_cached(llm: LLMClient, model: str, system: str, user: str,
                     workspace: Path) -> str:
    prompt = system + "\n\n---\n\n" + user
    key = _cache_key(prompt)
    cache_file = _cache_dir(workspace) / f"{key}.json"

    if cache_file.exists():
        data = json.loads(cache_file.read_text())
        logger.debug(f"Cache hit: {key[:12]}")
        return data["content"]

    resp = llm.chat(system, user, model=model)
    content = resp.content
    cache_file.write_text(json.dumps({"key": key, "content": content}, indent=2))
    return content


def _extract_signature_and_docs(source_text: str, fn_name: str) -> str:
    """
    Extract the function's doc comment block + signature (no body, no spec).

    Strategy: find lines that declare `fn <fn_name>`, collect the leading
    doc-comment lines, and return just the signature up to the opening brace.
    """
    lines = source_text.splitlines()
    result_lines: list[str] = []

    for i, line in enumerate(lines):
        # Match the function declaration line
        if re.search(rf'\bfn\s+{re.escape(fn_name)}\s*[(<]', line):
            # Collect doc comments above (going backwards)
            doc_lines: list[str] = []
            j = i - 1
            while j >= 0:
                stripped = lines[j].strip()
                if stripped.startswith("///") or stripped.startswith("//!"):
                    doc_lines.insert(0, lines[j])
                    j -= 1
                elif stripped == "":
                    j -= 1
                    continue
                else:
                    break

            # Collect signature lines (up to opening brace or verus_spec end)
            sig_lines: list[str] = []
            k = i
            while k < len(lines):
                sig_lines.append(lines[k])
                if "{" in lines[k] or lines[k].strip().endswith(")"):
                    break
                k += 1

            result_lines = doc_lines + sig_lines[:5]  # cap at 5 sig lines
            break

    return "\n".join(result_lines) if result_lines else f"fn {fn_name}(...)"


def _format_case_for_oracle(case: Case) -> str:
    """Render a case as readable text for the oracle prompt."""
    lines = []
    if case.pre_assumes:
        lines.append("Pre-state:")
        for a in case.pre_assumes:
            if not a.startswith("//"):
                lines.append(f"  {a}")
    if case.arg_assumes:
        lines.append("Arguments:")
        for a in case.arg_assumes:
            lines.append(f"  {a}")
    if case.post_assumes:
        lines.append("Post-state:")
        for a in case.post_assumes:
            lines.append(f"  {a}")
    if case.result_assume:
        lines.append(f"Return value: {case.result_assume}")
    return "\n".join(lines) if lines else "(no constraints — unconstrained case)"


def _parse_oracle_response(raw: str) -> tuple[OracleLabel | None, str | None]:
    label_m = re.search(r'\bLABEL:\s*(ACCEPT|REJECT)\b', raw, re.IGNORECASE)
    just_m = re.search(r'JUSTIFICATION:\s*(.+)', raw)

    label: OracleLabel | None = None
    if label_m:
        label = label_m.group(1).upper()  # type: ignore[assignment]

    justification = just_m.group(1).strip() if just_m else None
    return label, justification


# ---------------------------------------------------------------------------
# process_one
# ---------------------------------------------------------------------------

def process_one(task_dir: Path, llm: LLMClient, model: str,
                workspace: Path | None = None) -> list[Case]:
    """
    Label all cases in cases_diversified.json with ACCEPT/REJECT.

    Reads: cases_diversified.json, exec_functions.json, original.rs
    Writes: cases_labeled.json
    Returns: labeled cases
    """
    if workspace is None:
        workspace = task_dir.parent

    div_path = task_dir / "cases_diversified.json"
    if not div_path.exists():
        raise FileNotFoundError(f"cases_diversified.json not found in {task_dir}")

    cases = [Case.from_dict(d) for d in json.loads(div_path.read_text())]

    orig_path = task_dir / "original.rs"
    source_text = orig_path.read_text() if orig_path.exists() else ""

    # Module/project context from path
    project_context = task_dir.name.replace("__", " / ").replace("_", " ")

    labeled: list[Case] = []
    for i, case in enumerate(cases):
        sig_text = _extract_signature_and_docs(source_text, case.fn)
        case_text = _format_case_for_oracle(case)

        user = (
            f"## Project context:\n{project_context}\n\n"
            f"## Function (signature + docs only — no spec, no body):\n"
            f"```rust\n{sig_text}\n```\n\n"
            f"## Concrete test case:\n{case_text}\n\n"
            f"Is this a valid (ACCEPT) or invalid (REJECT) output for this function?"
        )

        try:
            raw = _llm_call_cached(llm, model, ORACLE_SYSTEM, user, workspace)
            label, justification = _parse_oracle_response(raw)
        except Exception as e:
            logger.warning(f"[step5] Oracle failed for case {case.case_id}: {e}")
            label, justification = None, str(e)

        case.oracle = label
        case.oracle_justification = justification
        labeled.append(case)

        if (i + 1) % 10 == 0:
            logger.info(f"[step5] Labeled {i+1}/{len(cases)}")

    (task_dir / "cases_labeled.json").write_text(
        json.dumps([c.to_dict() for c in labeled], indent=2)
    )
    return labeled


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 5 (fuzz): LLM oracle labeling (ACCEPT/REJECT)"
    )
    parser.add_argument("--task-dir", type=str, required=True)
    parser.add_argument("--model", type=str, default="claude-opus-4.6")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    task_dir = Path(args.task_dir).resolve()
    workspace = task_dir.parent

    print(f"[step5] Oracle labeling for {task_dir.name}")
    llm = LLMClient(timeout=600)

    try:
        cases = process_one(task_dir, llm, args.model, workspace)
    except FileNotFoundError as e:
        print(f"[step5] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    accept = sum(1 for c in cases if c.oracle == "ACCEPT")
    reject = sum(1 for c in cases if c.oracle == "REJECT")
    unlabeled = sum(1 for c in cases if c.oracle is None)
    print(f"[step5] Labels: ACCEPT={accept}  REJECT={reject}  unlabeled={unlabeled}")
    print(f"[step5] Wrote cases_labeled.json → {task_dir / 'cases_labeled.json'}")


if __name__ == "__main__":
    main()
