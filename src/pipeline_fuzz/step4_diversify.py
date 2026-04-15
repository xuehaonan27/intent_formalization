"""
Step 4 (fuzz): LLM diversification + semantic dedup of seed cases.

Sends the Verus spec + seed cases to the LLM and asks for additional cases
that stress edges (empty/full state, boundary args, error paths, unusual
orderings). Deduplicates by normalising the assume-set fingerprint.

Outputs: <task_dir>/cases_diversified.json  (seed + LLM-generated, deduped)

LLM cache: <workspace>/.cache/fuzz/<sha256>.json

Usage:
  python -m src.pipeline_fuzz.step4_diversify --task-dir <path> [--model MODEL]
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
from src.utils.pipeline_common import extract_spec_portion
from src.pipeline_fuzz.schemas import Case

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

DIVERSIFY_SYSTEM = """You are a test-case diversifier for Verus spec fuzzing.

You will be given:
1. A Rust/Verus source file (for context on types and spec functions).
2. A set of SEED cases — each is a (pre-state, args, post-state, result) tuple
   represented as Verus assume() statement lists.
3. The declaration of the function being tested (requires + ensures).

Your job: generate ADDITIONAL concrete cases that are NOT covered by the seeds.
Focus on:
- Empty/full pre-states
- Boundary arguments (0, 1, max, max-1)
- Error-path pre-states (inputs that should trigger Err returns)
- Sequential/multi-step state transitions
- Cases that could reveal INCOMPLETENESS (spec too weak, admits bad output)
- Cases that could reveal INCORRECTNESS (spec too strong, rejects valid output)

## Output format

For each new case, output a block:

===CASE_START===
FN: <function name>
PRE_ASSUMES: <one assume per line, or NONE>
ARG_ASSUMES: <one assume per line, or NONE>
POST_ASSUMES: <one assume per line, or NONE>
RESULT_ASSUME: <single assume, or NONE>
RATIONALE: <one sentence why this case is interesting>
===CASE_END===

Produce at most 20 new cases per function.
Only use types/identifiers/spec functions present in the source.
"""


# ---------------------------------------------------------------------------
# LLM caching
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


# ---------------------------------------------------------------------------
# Parse LLM output
# ---------------------------------------------------------------------------

def _parse_multiline_field(text: str, field: str) -> list[str]:
    """Extract lines after 'FIELD:' up to next 'ALL_CAPS_WORD:' or ===."""
    pattern = rf'{field}:(.*?)(?=\n[A-Z_]+:|\n===|$)'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return []
    raw = m.group(1).strip()
    if raw.upper() in ("NONE", ""):
        return []
    lines = [l.strip() for l in raw.splitlines() if l.strip() and l.strip().upper() != "NONE"]
    return lines


def _parse_cases_from_llm(raw: str, task: str) -> list[Case]:
    cases: list[Case] = []
    counter = 0

    for block_m in re.finditer(r'===CASE_START===(.*?)===CASE_END===', raw, re.DOTALL):
        block = block_m.group(1)

        fn_m = re.search(r'FN:\s*(\S+)', block)
        if not fn_m:
            continue
        fn_name = fn_m.group(1).strip()

        pre_assumes = _parse_multiline_field(block, 'PRE_ASSUMES')
        arg_assumes = _parse_multiline_field(block, 'ARG_ASSUMES')
        post_assumes = _parse_multiline_field(block, 'POST_ASSUMES')

        result_m = re.search(r'RESULT_ASSUME:\s*(.+)', block)
        result_assume: str | None = None
        if result_m:
            v = result_m.group(1).strip()
            if v.upper() != "NONE":
                result_assume = v

        case_id = f"{fn_name}_div_{counter}"
        counter += 1

        cases.append(Case(
            task=task,
            fn=fn_name,
            case_id=case_id,
            pre_assumes=pre_assumes,
            arg_assumes=arg_assumes,
            post_assumes=post_assumes,
            result_assume=result_assume,
        ))

    return cases


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------

def _fingerprint(case: Case) -> str:
    """Normalised fingerprint for semantic dedup."""
    parts = (
        sorted(case.pre_assumes)
        + sorted(case.arg_assumes)
        + sorted(case.post_assumes)
        + [case.result_assume or ""]
    )
    return "|".join(p.strip().replace(" ", "") for p in parts)


def dedup_cases(cases: list[Case]) -> list[Case]:
    seen: set[str] = set()
    result: list[Case] = []
    for c in cases:
        fp = _fingerprint(c)
        if fp not in seen:
            seen.add(fp)
            result.append(c)
    return result


# ---------------------------------------------------------------------------
# Per-function diversification
# ---------------------------------------------------------------------------

def _diversify_fn(fn_name: str, fn_seeds: list[Case], declaration: str,
                  source_text: str, llm: LLMClient, model: str,
                  workspace: Path, task: str) -> list[Case]:
    spec_text = extract_spec_portion(source_text, max_lines=300)

    seed_summary = ""
    for i, c in enumerate(fn_seeds[:10]):  # show at most 10 seeds
        seed_summary += f"\n--- Seed case {i+1} (fn={c.fn}) ---\n"
        if c.pre_assumes:
            seed_summary += "PRE: " + "; ".join(c.pre_assumes) + "\n"
        if c.arg_assumes:
            seed_summary += "ARGS: " + "; ".join(c.arg_assumes) + "\n"
        if c.post_assumes:
            seed_summary += "POST: " + "; ".join(c.post_assumes) + "\n"
        if c.result_assume:
            seed_summary += f"RESULT: {c.result_assume}\n"

    user = (
        f"## Source file (excerpt):\n```rust\n{spec_text}\n```\n\n"
        f"## Function declaration:\n```rust\n{declaration}\n```\n\n"
        f"## Existing seed cases for `{fn_name}`:\n{seed_summary}\n\n"
        f"Generate additional concrete test cases for `{fn_name}` that go "
        f"beyond the seeds above. Focus on boundary/edge/error inputs."
    )

    raw = _llm_call_cached(llm, model, DIVERSIFY_SYSTEM, user, workspace)
    new_cases = _parse_cases_from_llm(raw, task)

    # Filter to only cases for this fn
    new_cases = [c for c in new_cases if c.fn == fn_name or not c.fn]
    for c in new_cases:
        c.fn = fn_name  # normalise

    return new_cases


# ---------------------------------------------------------------------------
# process_one
# ---------------------------------------------------------------------------

def process_one(task_dir: Path, llm: LLMClient, model: str,
                workspace: Path | None = None) -> list[Case]:
    """
    Diversify seed cases for all functions.

    Reads: seed_cases.json, exec_functions.json, original.rs
    Writes: cases_diversified.json
    Returns: deduped list of all cases (seeds + LLM-generated)
    """
    if workspace is None:
        workspace = task_dir.parent

    seed_path = task_dir / "seed_cases.json"
    exec_fns_path = task_dir / "exec_functions.json"
    orig_path = task_dir / "original.rs"

    if not seed_path.exists():
        raise FileNotFoundError(f"seed_cases.json not found in {task_dir}")

    seeds = [Case.from_dict(d) for d in json.loads(seed_path.read_text())]
    exec_fns = json.loads(exec_fns_path.read_text()) if exec_fns_path.exists() else []
    source_text = orig_path.read_text() if orig_path.exists() else ""
    task_name = task_dir.name

    # Build declaration lookup
    decl_map: dict[str, str] = {}
    for fn in exec_fns:
        decl_map[fn["name"]] = fn.get("declaration", fn.get("code", ""))

    # Group seeds by fn
    by_fn: dict[str, list[Case]] = {}
    for c in seeds:
        by_fn.setdefault(c.fn, []).append(c)

    all_cases: list[Case] = list(seeds)

    for fn_name, fn_seeds in by_fn.items():
        declaration = decl_map.get(fn_name, "")
        logger.info(f"[step4] Diversifying {fn_name} ({len(fn_seeds)} seeds)")
        try:
            new_cases = _diversify_fn(
                fn_name, fn_seeds, declaration,
                source_text, llm, model, workspace, task_name
            )
            all_cases.extend(new_cases)
        except Exception as e:
            logger.warning(f"[step4] LLM failed for {fn_name}: {e}")

    deduped = dedup_cases(all_cases)

    (task_dir / "cases_diversified.json").write_text(
        json.dumps([c.to_dict() for c in deduped], indent=2)
    )
    return deduped


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 4 (fuzz): LLM diversification + dedup of seed cases"
    )
    parser.add_argument("--task-dir", type=str, required=True)
    parser.add_argument("--model", type=str, default="claude-opus-4.6")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    task_dir = Path(args.task_dir).resolve()
    workspace = task_dir.parent

    print(f"[step4] Diversifying cases for {task_dir.name}")
    llm = LLMClient(timeout=600)

    try:
        cases = process_one(task_dir, llm, args.model, workspace)
    except FileNotFoundError as e:
        print(f"[step4] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[step4] Total cases after diversification + dedup: {len(cases)}")
    print(f"[step4] Wrote cases_diversified.json → {task_dir / 'cases_diversified.json'}")


if __name__ == "__main__":
    main()
