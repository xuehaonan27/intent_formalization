"""
Module: llm_refine — one-shot LLM pass to refine a DetCheckSpec's symbol tree.

The static pipeline (extract + gen_det) is best-effort: types defined outside
the crate's main spec file end up as TypeKind.UNKNOWN, and fields that the
parser missed simply aren't in the symbol tree.

This module asks Copilot CLI to read the workspace sources and fix up the
symbol tree: instantiate UNKNOWNs with concrete kind/fields/variants, add
missing symbols, etc. It returns a refined DetCheckSpec.

Usage:
    refined = refine_with_llm(det_spec, workspace_dir="~/nanvix")
"""

import json
import logging
import os
import re
import subprocess
from hashlib import sha256
from pathlib import Path

from .types import DetCheckSpec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """You are refining a symbol table used by a Verus-based \
spec-determinism checker. The static extractor produced a best-effort JSON \
symbol tree but some types are marked `"kind": "unknown"` because they are \
defined outside the crate's main spec files. Some fields may also be missing.

Your job:
1. Read source files under the workspace to understand any type marked \
`"kind": "unknown"`.
2. Produce a refined JSON that instantiates each UNKNOWN as a concrete \
struct, enum, Option, Result, or a primitive. For structs, fill in \
`fields`. For enums, fill in `variants` — **this is mandatory**: every \
`"kind": "enum"` MUST have a non-empty `variants` list, each with \
`{{"name": "..."}}` and an optional `"inner"` for tuple/struct variants. \
If an enum has no variants, you must either list them all or set \
`"kind": "unknown"` instead.
3. If a symbol obviously needs sub-fields that weren't extracted, add them. \
Do not remove existing symbols.
4. Do NOT change `function`, `det_check_template`, or any field named \
`phase` / `name` of existing symbols.
5. Keep `kind` strings in this closed set: \
`int, usize, isize, u8, u16, u32, u64, i8, i16, i32, i64, bool, str, (), \
enum, struct, Set, Seq, Result, Option, unknown`. \
Use `"kind": "str"` for any string type (`&str`, `&'static str`, `String`, \
`Cow<str>`, etc.).
6. If a type truly cannot be determined from the workspace, leave it as \
`unknown` (do NOT guess).

Workspace directory (you have read access to everything under it): {workspace}

Here is the current symbol tree (JSON):
```json
{symbols_json}
```

Relevant source hints (may be empty; you can also grep/cat other files):
{hints}

Return ONLY the refined JSON symbol list inside these exact tags, with no \
prose outside the tags:

<REFINED_SYMBOLS>
[ ...refined array of symbols... ]
</REFINED_SYMBOLS>
"""


def _build_prompt(det_spec: DetCheckSpec, workspace: str, hints: str = "") -> str:
    symbols_json = json.dumps(
        [s.to_dict() for s in det_spec.symbols], indent=2
    )
    return _PROMPT_TEMPLATE.format(
        workspace=workspace,
        symbols_json=symbols_json,
        hints=hints or "(none provided)",
    )


# ---------------------------------------------------------------------------
# Copilot CLI invocation
# ---------------------------------------------------------------------------

def _run_copilot(prompt: str, workspace: str, timeout: int = 300) -> str:
    """Invoke `copilot -p` non-interactively and return stdout."""
    cmd = [
        "copilot",
        "-p", prompt,
        "--allow-all-tools",
        "--add-dir", workspace,
        "--no-color",
    ]
    logger.info(f"Invoking copilot CLI (workspace={workspace}, timeout={timeout}s)")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"copilot CLI timed out after {timeout}s")

    if proc.returncode != 0:
        logger.warning(
            f"copilot exited with code {proc.returncode}; stderr:\n{proc.stderr[:1000]}"
        )
    return proc.stdout


_REFINED_RE = re.compile(
    r"<REFINED_SYMBOLS>\s*(.*?)\s*</REFINED_SYMBOLS>", re.DOTALL
)


def _extract_json(output: str) -> list:
    """Extract the JSON array inside <REFINED_SYMBOLS>...</REFINED_SYMBOLS>."""
    m = _REFINED_RE.search(output)
    if not m:
        raise ValueError(
            "copilot output did not contain <REFINED_SYMBOLS>...</REFINED_SYMBOLS>; "
            f"first 800 chars:\n{output[:800]}"
        )
    payload = m.group(1).strip()
    # Strip ```json fences if the model added them inside the tags
    if payload.startswith("```"):
        payload = re.sub(r"^```[a-zA-Z]*\n", "", payload)
        payload = re.sub(r"\n```$", "", payload)
    return json.loads(payload)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_key(det_spec: DetCheckSpec) -> str:
    """Stable hash of (function, symbols) used as cache filename."""
    payload = json.dumps(
        {"function": det_spec.function,
         "symbols": [s.to_dict() for s in det_spec.symbols]},
        sort_keys=True,
    ).encode()
    return sha256(payload).hexdigest()[:16]


def _cache_paths(cache_dir: str, fn_name: str, key: str) -> tuple[str, str, str]:
    """Return (pre_path, post_path, refined_path) for a given cache key."""
    base = os.path.join(cache_dir, f"{fn_name}__{key}")
    return f"{base}__pre.json", f"{base}__post.json", f"{base}__refined.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def refine_with_llm(
    det_spec: DetCheckSpec,
    workspace: str,
    cache_dir: str = "results/refine_cache",
    hints: str = "",
    timeout: int = 300,
    force: bool = False,
) -> DetCheckSpec:
    """
    Refine a DetCheckSpec's symbol tree using Copilot CLI.

    Saves pre/post/raw-output snapshots under ``cache_dir``. If a cache hit
    exists for this (function, symbols) fingerprint, the cached refined spec
    is returned unless ``force=True``.

    Parameters
    ----------
    det_spec   : DetCheckSpec produced by ``build_det_check_spec``.
    workspace  : absolute directory to expose to copilot via ``--add-dir``.
    cache_dir  : directory for pre/post/raw snapshots and cache lookup.
    hints      : optional free-form text appended to the prompt (e.g. known
                 file paths for external types).
    timeout    : seconds to allow the copilot subprocess.
    force      : if True, ignore cache and re-invoke copilot.
    """
    workspace = os.path.abspath(os.path.expanduser(workspace))
    cache_dir = os.path.abspath(os.path.expanduser(cache_dir))
    os.makedirs(cache_dir, exist_ok=True)

    key = _cache_key(det_spec)
    pre_path, post_path, refined_path = _cache_paths(
        cache_dir, det_spec.function, key
    )

    # Always persist "pre" snapshot
    with open(pre_path, "w") as f:
        f.write(det_spec.to_json())
    logger.info(f"saved pre-refine snapshot: {pre_path}")

    # Cache hit?
    if (not force) and os.path.exists(post_path):
        logger.info(f"cache hit: {post_path}")
        cached = DetCheckSpec.from_json(Path(post_path).read_text())
        # Always rebuild the equal fn from the (possibly updated) gen_det
        # logic, even on cache hits. The cached post.json may have been
        # produced by an older version of `rebuild_equal_fn`.
        try:
            from .gen_det import rebuild_equal_fn
            cached = rebuild_equal_fn(cached)
        except Exception as e:
            logger.warning(f"cache-hit equal fn rebuild failed: {e}")
        return cached

    # Build prompt + call copilot
    prompt = _build_prompt(det_spec, workspace, hints)
    raw = _run_copilot(prompt, workspace, timeout=timeout)

    # Save raw copilot output for debugging
    with open(refined_path, "w") as f:
        f.write(raw)
    logger.info(f"saved raw copilot output: {refined_path}")

    try:
        refined_symbols_dicts = _extract_json(raw)
    except Exception as e:
        logger.error(f"could not parse copilot output: {e}; returning pre-refine spec")
        return det_spec

    # Build refined DetCheckSpec (keep template/function/verus_config intact)
    refined_dict = det_spec.to_dict()
    refined_dict["symbols"] = refined_symbols_dicts
    try:
        refined = DetCheckSpec.from_dict(refined_dict)
    except Exception as e:
        logger.error(
            f"refined symbols failed schema validation: {e}; returning pre-refine spec"
        )
        return det_spec

    # Persist "post" snapshot
    with open(post_path, "w") as f:
        f.write(refined.to_json())
    logger.info(f"saved post-refine snapshot: {post_path}")

    # After refine, the equal fn may need to be rebuilt from richer type info
    # (e.g., Error went from UNKNOWN to struct, so `r1->Err_0 == r2->Err_0`
    # should now expand to a field-level comparison). We rebuild it by calling
    # `rebuild_equal_fn` which replays gen_det's equal-fn logic on the refined
    # symbols.
    try:
        from .gen_det import rebuild_equal_fn
        rebuilt = rebuild_equal_fn(refined)
        refined.equal_fn_def = rebuilt.equal_fn_def
        refined.equal_fn_name = rebuilt.equal_fn_name
        refined.equal_arg_pairs = rebuilt.equal_arg_pairs
        with open(post_path, "w") as f:
            f.write(refined.to_json())
        logger.info("rebuilt equal fn using refined types")
    except Exception as e:
        logger.warning(f"equal fn rebuild failed: {e}; using pre-refine equal fn")

    # Log a short diff summary
    pre_unknowns = _count_unknowns(det_spec)
    post_unknowns = _count_unknowns(refined)
    logger.info(
        f"refine summary: UNKNOWN types {pre_unknowns} → {post_unknowns}; "
        f"symbols {len(det_spec.symbols)} → {len(refined.symbols)}"
    )

    return refined


def _count_unknowns(spec: DetCheckSpec) -> int:
    count = 0

    def walk(ty_dict):
        nonlocal count
        if ty_dict.get("kind") == "unknown":
            count += 1
        for f in ty_dict.get("fields", []):
            walk(f["type"])
        for v in ty_dict.get("variants", []):
            if v.get("inner"):
                walk(v["inner"])
        for t in ty_dict.get("type_args", []):
            walk(t)
        if ty_dict.get("spec_view"):
            walk(ty_dict["spec_view"])

    for sym in spec.symbols:
        walk(sym.type.to_dict())
    return count
