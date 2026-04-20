"""
LLM-assisted equal-fn policy selection.

Given a ``FunctionSpec`` (signature + requires/ensures) and the default
generator's output, ask Copilot CLI to decide whether the function needs
a coarser equivalence than the ``errs_equivalent``-only default. This
handles cases the static heuristics can't reasonably see, e.g.:

* An allocator whose ``Ok(addr: usize)`` payload is an opaque handle —
  set ``opaque_ok=True``.
* A struct whose ``.cache`` / ``.bookkeeping`` field is internal state —
  add it to ``ignore_fields``.
* Pure projections whose output is fully spec-pinned — leave
  ``errs_equivalent=True`` and otherwise strict (the default).

The LLM response is parsed into an ``EqualPolicy`` (or ``None`` if the
default should be kept). Results are cached under
``results/refine_cache/`` alongside the symbol-refine snapshots.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from hashlib import sha256
from pathlib import Path

from .equal_policy import EqualPolicy
from .types import FunctionSpec

logger = logging.getLogger(__name__)


_PROMPT_TEMPLATE = """You are configuring an *equivalence policy* used by a \
Verus-based spec-determinism checker. The checker generates a \
`spec fn det_<fn>_equal(...) -> bool` to compare two runs of the function \
and flag nondeterminism. By default that fn compares outputs field-by-field, \
but that is usually too strict for specs: two `Err` values with different \
`.reason` strings are practically equivalent outcomes, an allocator's \
`Ok(address)` is an opaque handle, internal caches aren't spec-relevant, etc.

The generator already supports these knobs via an `EqualPolicy`:

  errs_equivalent (bool, default TRUE): all Err values are equivalent; \
only Ok payloads are compared. **Leave this TRUE unless the spec explicitly \
pins down the Err variant on given inputs.**

  opaque_ok (bool, default FALSE): all Ok values are equivalent. Use for \
functions whose Ok payload is an opaque handle / index / address (e.g. \
`alloc` returning a raw pointer or slot index). Only set TRUE when the \
spec does NOT constrain which specific handle is returned.

  ignore_fields (list[str]): struct/view field *names* to omit from the \
comparison. Use for internal bookkeeping fields whose value isn't \
spec-relevant (e.g. allocator free-list pointers, internal caches).

  opaque_types (list[str]): type *names* treated as equivalent wholesale. \
Use sparingly — only when a whole type is opaque from the spec's view.

Your job: read the function signature + requires/ensures below (and grep \
the workspace for definitions if needed) and decide which knobs to set.

Workspace directory (you have read access under it): {workspace}

Function: {fn_name}

Signature + spec:
```rust
{spec_source}
```

Return ONLY the policy JSON inside these exact tags, no prose outside. \
If the default (`errs_equivalent=true`, everything else default) is fine, \
return exactly `{{"keep_default": true}}`.

<EQUAL_POLICY>
{{
  "errs_equivalent": true,
  "opaque_ok": false,
  "ignore_fields": [],
  "opaque_types": [],
  "rationale": "<one short sentence>"
}}
</EQUAL_POLICY>
"""


_POLICY_RE = re.compile(r"<EQUAL_POLICY>\s*(.*?)\s*</EQUAL_POLICY>", re.DOTALL)


def _spec_source(spec: FunctionSpec) -> str:
    """Render a function's signature + requires/ensures as Rust-ish text."""
    params = []
    for p in spec.params:
        mods = []
        if p.is_mut_ref:
            mods.append("&mut")
        elif p.is_ref:
            mods.append("&")
        mod_str = " ".join(mods) + (" " if mods else "")
        if p.is_self:
            params.append(f"{mod_str}self")
        else:
            params.append(f"{p.name}: {mod_str}{p.type.name}")
    sig = f"fn {spec.name}({', '.join(params)}) -> {spec.return_type.name}"
    parts = [sig]
    if spec.requires:
        parts.append("requires")
        for c in spec.requires:
            parts.append(f"    {c.strip()},")
    if spec.ensures:
        parts.append("ensures")
        for c in spec.ensures:
            parts.append(f"    {c.strip()},")
    return "\n".join(parts)


def _cache_key(spec: FunctionSpec) -> str:
    payload = json.dumps(
        {"fn": spec.name, "src": _spec_source(spec)},
        sort_keys=True,
    ).encode()
    return sha256(payload).hexdigest()[:16]


def _run_copilot(prompt: str, workspace: str, timeout: int = 180) -> str:
    cmd = [
        "copilot",
        "-p", prompt,
        "--allow-all-tools",
        "--add-dir", workspace,
        "--no-color",
    ]
    logger.info(f"Invoking copilot for equal-policy (fn workspace={workspace})")
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"copilot timed out after {timeout}s")
    if proc.returncode != 0:
        logger.warning(
            f"copilot exited {proc.returncode}; stderr head:\n{proc.stderr[:600]}"
        )
    return proc.stdout


def _parse_policy(output: str) -> EqualPolicy | None:
    m = _POLICY_RE.search(output)
    if not m:
        logger.warning(
            "copilot output missing <EQUAL_POLICY> tags; first 400 chars:\n"
            + output[:400]
        )
        return None
    payload = m.group(1).strip()
    if payload.startswith("```"):
        payload = re.sub(r"^```[a-zA-Z]*\n", "", payload)
        payload = re.sub(r"\n```$", "", payload)
    try:
        d = json.loads(payload)
    except Exception as e:
        logger.warning(f"could not parse policy JSON: {e}; payload:\n{payload[:400]}")
        return None
    if d.get("keep_default"):
        logger.info("LLM kept default equal-policy")
        return None
    rationale = d.pop("rationale", None)
    if rationale:
        logger.info(f"LLM equal-policy rationale: {rationale}")
    return EqualPolicy.from_dict(d)


def suggest_equal_policy(
    spec: FunctionSpec,
    workspace: str,
    cache_dir: str = "results/refine_cache",
    timeout: int = 180,
    force: bool = False,
) -> EqualPolicy | None:
    """Ask the LLM what EqualPolicy fits this function. Returns None if the
    default (``errs_equivalent=True``) should be used.

    Caches by (fn_name, signature+spec) under ``cache_dir``. Same idiom as
    ``llm_refine.refine_with_llm``.
    """
    workspace = os.path.abspath(os.path.expanduser(workspace))
    cache_dir = os.path.abspath(os.path.expanduser(cache_dir))
    os.makedirs(cache_dir, exist_ok=True)

    key = _cache_key(spec)
    cache_path = os.path.join(cache_dir, f"{spec.name}__{key}__policy.json")

    if (not force) and os.path.exists(cache_path):
        try:
            cached = json.loads(Path(cache_path).read_text())
            if cached.get("keep_default"):
                logger.info(f"equal-policy cache hit (keep_default): {cache_path}")
                return None
            logger.info(f"equal-policy cache hit: {cache_path}")
            return EqualPolicy.from_dict(cached)
        except Exception as e:
            logger.warning(f"equal-policy cache read failed: {e}; re-running")

    prompt = _PROMPT_TEMPLATE.format(
        workspace=workspace,
        fn_name=spec.name,
        spec_source=_spec_source(spec),
    )
    raw_path = os.path.join(cache_dir, f"{spec.name}__{key}__policy.raw.txt")
    try:
        raw = _run_copilot(prompt, workspace, timeout=timeout)
    except Exception as e:
        logger.error(f"copilot failed: {e}; falling back to default policy")
        return None
    Path(raw_path).write_text(raw)

    policy = _parse_policy(raw)
    if policy is None:
        Path(cache_path).write_text(json.dumps({"keep_default": True}))
    else:
        Path(cache_path).write_text(json.dumps(policy.to_dict(), indent=2))
    return policy
