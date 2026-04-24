"""LLM-driven EqualPolicy generator.

Rationale
---------
The equal-fn for a determinism check decides "which two outputs count as
the same result?". One mechanical rule lives in :mod:`gen_det` (raw pointers
are opaque by default — their addresses are allocator-nondeterministic and
structural equality on them is meaningless).

Everything else — whether an error-code distinction matters, whether an
allocation bitmap should compare structurally or by cardinality, whether
an opaque handle should collapse — is a **semantic** judgment that depends
on the spec's intent.  Hard-coding those rules risks overfitting to nanvix's
conventions; we let an LLM read the function signature + ensures and emit
an :class:`EqualPolicy` it thinks fits.

Determinism-of-the-determinism-check:
    The LLM is non-deterministic, but its output is persisted in
    ``det_spec.json`` under ``equal_policy.source="llm"`` with a
    ``rationale`` field.  Subsequent ``regen_artifacts`` runs reuse the
    stored policy (they do NOT re-query the LLM), so the overall pipeline
    stays reproducible after the first successful generation.  To
    re-generate, pass ``--force-llm-policy``.

Backend
-------
We reuse the same GitHub Copilot CLI pattern as spec-debug: write a prompt
file, ask Copilot to write its answer to a JSON file, read it back.  A
minimal local client is included here to avoid a cross-package dependency
on ``spec_debug.llm``.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .equal_policy import EqualPolicy
from .types import (
    DetCheckSpec, FunctionSpec, ProjectionInfo, Symbol, TypeInfo,
    TypeKind, TypeProjections,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Minimal Copilot CLI client (mirror of spec-debug's CopilotLLMClient)
# ---------------------------------------------------------------------------

@dataclass
class CopilotPolicyLLM:
    model: str | None = None
    reasoning_effort: str | None = None
    timeout: int = 600

    def query(self, prompt: str, run_dir: Path) -> str:
        """Send `prompt` to Copilot CLI; return raw response text."""
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "prompt.md"
        response_path = run_dir / "response.md"
        prompt_path.write_text(prompt)
        if response_path.exists():
            response_path.unlink()

        meta = (
            f"Read the full task at {prompt_path} and execute it. "
            f"Write your reply — the single fenced ```json block described "
            f"in that task — to {response_path}. Do not modify any other file. "
            f"Do not print the reply to stdout. After writing the file, exit."
        )
        cmd = ["copilot", "-p", meta, "--allow-all-tools", "--allow-all-paths", "--no-color"]
        if self.model:
            cmd += ["--model", self.model]
        if self.reasoning_effort:
            cmd += ["--effort", self.reasoning_effort]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        (run_dir / "copilot_stdout.txt").write_text(proc.stdout or "")
        (run_dir / "copilot_stderr.txt").write_text(proc.stderr or "")
        if not response_path.exists():
            raise RuntimeError(
                f"copilot exited rc={proc.returncode} without writing {response_path}. "
                f"See stdout/stderr in {run_dir}."
            )
        return response_path.read_text()


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_PROMPT_HEADER = """\
You are helping decide how to compare two outputs of a Verus function for
**determinism-check equivalence**. The function's post-state can differ in
ways that are semantically equivalent (different allocator addresses, same
abstract allocation), and the spec may leave some dimensions implementation-
defined. Your job is to produce an **EqualPolicy** that captures the
coarsening rules appropriate for this function.

Think about: given the ensures contract, if two runs of this function with
the same inputs produce outputs O1 and O2, under what conditions should
those outputs be considered "the same result"? Anything the spec does not
pin down is, by construction, implementation-defined and should be
coarsened (returned as equivalent) — otherwise the determinism check will
flag spurious nondeterminism that the spec author didn't intend to rule out.
"""


_POLICY_SCHEMA_DOC = """\
## Policy fields (output this as JSON)

- `errs_equivalent` (bool, default true): two `Err` values count as equal
  regardless of which specific ErrorCode was returned. Set false only if
  the spec clearly distinguishes between error reasons.
- `opaque_ok` (bool, default false): two `Ok` values count as equal
  regardless of their payload. Set true when the Ok payload is an entirely
  opaque handle/index/address that the spec treats as existential.
- `opaque_types` (list[str], default []): full type names to treat as
  opaque (all values of the type compare equal). Use this for
  handle/identity types where the spec never pins down a concrete value.
- `ignore_fields` (list[str], default []): unqualified field names to omit
  from structural comparison (applied in view/struct comparison).
- `custom_body` (string | null, default null): if the coarsening cannot be
  expressed via the above, provide the ENTIRE body of the equal-fn as a
  Verus spec expression. Parameters are `r1`/`r2` for the return value
  and `post1_<name>` / `post2_<name>` for `&mut` post-states (viewed if
  the underlying struct has `@`/`spec_view`). Example for two Maps
  compared by cardinality only:
    `((r1 is Ok) == (r2 is Ok)) && (post1_self_@.allocations.dom().len() == post2_self_@.allocations.dom().len())`
- `rationale` (string): 1-3 sentences explaining the decision. This is
  stored for human review.

The raw-pointer opacity rule (`*mut T` / `*const T`) is applied
automatically by the equal-fn generator — you do NOT need to handle it
in custom_body.

Do not set fields beyond those above; extra keys will be rejected.
"""


_FEW_SHOT = """\
## Examples

### Example A — error-collapsing but strict Ok
Function: `fn lookup(key: usize) -> Result<Entry, LookupError>` where
`Entry` contains a numeric id pinned down by ensures.

```json
{
  "errs_equivalent": true,
  "opaque_ok": false,
  "opaque_types": [],
  "ignore_fields": [],
  "custom_body": null,
  "rationale": "Ensures pin the Entry.id to the lookup key, so Ok payloads must match structurally. LookupError variants are just diagnostic categories."
}
```

### Example B — opaque handle return
Function: `fn create_channel() -> Result<ChannelId, SysError>` where
`ChannelId` is a fresh existential handle and the spec only ensures
`result is Ok ==> channels.contains(result->Ok_0)`.

```json
{
  "errs_equivalent": true,
  "opaque_ok": true,
  "opaque_types": [],
  "ignore_fields": [],
  "custom_body": null,
  "rationale": "ChannelId is existential — spec only ensures it exists in the channels ghost state, not a specific value. Two different successful calls should compare equal."
}
```

### Example C — allocator with ghost allocation map (cardinality only)
Function: `fn alloc(&mut self, size: usize) -> Result<*mut u8, AllocError>`
with ghost state `allocations: Map<int, nat>` (address -> size), and the
only ensures is `old(allocations).len() + 1 == allocations.len()`.

```json
{
  "errs_equivalent": true,
  "opaque_ok": false,
  "opaque_types": [],
  "ignore_fields": [],
  "custom_body": "((r1 is Ok) == (r2 is Ok)) && (post1_self_@.allocations.dom().len() == post2_self_@.allocations.dom().len())",
  "rationale": "Spec only constrains allocation count, not specific addresses or sizes. Comparing by dom().len() captures 'one more allocation happened' without forcing the same address or size."
}
```
"""


def _render_type_tree(ty: TypeInfo, depth: int = 0, max_depth: int = 4) -> str:
    """Render a TypeInfo as indented tree text (for human-readable prompt)."""
    indent = "  " * depth
    head = f"{indent}{ty.kind.value}:{ty.name}"
    if depth >= max_depth:
        return head + " ..."
    lines = [head]
    for fld in ty.fields:
        lines.append(f"{indent}  field {fld.name}:")
        lines.append(_render_type_tree(fld.type, depth + 2, max_depth))
    for v in ty.variants:
        lines.append(f"{indent}  variant {v.name}:")
        if v.inner is not None:
            lines.append(_render_type_tree(v.inner, depth + 2, max_depth))
    for a in ty.type_args:
        lines.append(_render_type_tree(a, depth + 1, max_depth))
    if ty.spec_view:
        lines.append(f"{indent}  [spec_view @]:")
        lines.append(_render_type_tree(ty.spec_view, depth + 2, max_depth))
    return "\n".join(lines)


def build_policy_prompt(
    fn_spec: FunctionSpec,
    det_spec: DetCheckSpec,
    crate_name: str = "",
) -> str:
    """Build the full prompt text to send to the LLM."""
    # Signature in Verus-ish form
    param_strs = []
    for p in fn_spec.params:
        pfx = "&mut " if p.is_mut_ref else ("&" if p.is_ref else "")
        nm = "self" if p.is_self else p.name
        param_strs.append(f"{nm}: {pfx}{p.type.name}")
    sig = f"fn {fn_spec.name}({', '.join(param_strs)}) -> {fn_spec.return_type.name}"

    ensures = "\n".join(f"  - {e}" for e in fn_spec.ensures) or "  (none)"
    requires = "\n".join(f"  - {r}" for r in fn_spec.requires) or "  (none)"

    # Output symbol types — these are what the equal-fn actually compares.
    out_symbols = [s for s in det_spec.symbols
                   if s.phase in ("output_simple", "output_compound")]
    out_lines = []
    for s in out_symbols:
        out_lines.append(f"symbol `{s.name}` (phase={s.phase}):")
        out_lines.append(_render_type_tree(s.type, depth=1))
    out_rendered = "\n".join(out_lines) or "(no output symbols)"

    return (
        _PROMPT_HEADER
        + "\n## Function under analysis\n\n"
        + (f"Crate: `{crate_name}`\n" if crate_name else "")
        + f"Signature:\n```\n{sig}\n```\n\n"
        + f"Requires clauses:\n{requires}\n\n"
        + f"Ensures clauses:\n{ensures}\n\n"
        + "## Output symbols (what the equal-fn compares)\n\n"
        + f"```\n{out_rendered}\n```\n\n"
        + _POLICY_SCHEMA_DOC
        + "\n"
        + _FEW_SHOT
        + "\n## Your task\n\n"
        + "Analyse the ensures above. Produce a single fenced ```json block\n"
        + "with the EqualPolicy fields. Do not output anything else.\n"
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


def parse_policy_response(text: str) -> dict:
    """Extract the first JSON object from a fenced ```json block (or bare)."""
    m = _JSON_FENCE_RE.search(text)
    blob = m.group(1) if m else text.strip()
    try:
        return json.loads(blob)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM response was not valid JSON:\n{text}") from e


_ALLOWED_KEYS = {
    "errs_equivalent", "opaque_ok", "opaque_types",
    "ignore_fields", "custom_body", "rationale",
}


def policy_from_llm_dict(d: dict) -> EqualPolicy:
    extra = set(d.keys()) - _ALLOWED_KEYS
    if extra:
        logger.warning("LLM policy has unknown keys (ignored): %s", sorted(extra))
    return EqualPolicy(
        errs_equivalent=bool(d.get("errs_equivalent", True)),
        opaque_ok=bool(d.get("opaque_ok", False)),
        compare_raw_pointers=False,  # mechanical rule, LLM cannot override
        ignore_fields=set(d.get("ignore_fields") or []),
        opaque_types=set(d.get("opaque_types") or []),
        custom_body=d.get("custom_body"),
        rationale=d.get("rationale"),
        source="llm",
    )


# ---------------------------------------------------------------------------
# End-to-end hook
# ---------------------------------------------------------------------------

def generate_policy_with_llm(
    fn_spec: FunctionSpec,
    det_spec: DetCheckSpec,
    run_dir: Path,
    crate_name: str = "",
    client: CopilotPolicyLLM | None = None,
) -> EqualPolicy:
    """Query the LLM for an EqualPolicy; persist prompt/response in run_dir."""
    if client is None:
        client = CopilotPolicyLLM()
    prompt = build_policy_prompt(fn_spec, det_spec, crate_name=crate_name)
    raw = client.query(prompt, run_dir)
    d = parse_policy_response(raw)
    policy = policy_from_llm_dict(d)
    logger.info("LLM policy for %s::%s: %s",
                crate_name or "?", fn_spec.name, policy.to_dict())
    return policy


# ---------------------------------------------------------------------------
# Opaque-type projection discovery (LLM-driven)
# ---------------------------------------------------------------------------
#
# We supply the LLM only with (a) the opaque type name(s), (b) a repo root
# path where it can grep/read spec files itself, and (c) an output schema.
# We validate the returned projections against the full type-source corpus
# before persisting — so a hallucinated spec-fn name never reaches the
# generated Verus template.

_SUPPORTED_SCALAR_KINDS = {
    TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
    TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
    TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
    TypeKind.BOOL,
}

_SCALAR_NAME_TO_KIND: dict[str, TypeKind] = {
    "int": TypeKind.INT, "nat": TypeKind.INT,
    "usize": TypeKind.USIZE, "isize": TypeKind.ISIZE,
    "u8": TypeKind.U8, "u16": TypeKind.U16,
    "u32": TypeKind.U32, "u64": TypeKind.U64,
    "i8": TypeKind.I8, "i16": TypeKind.I16,
    "i32": TypeKind.I32, "i64": TypeKind.I64,
    "bool": TypeKind.BOOL,
}


_PROJ_PROMPT_HEADER = """\
You are helping a Verus-based determinism checker narrow opaque input
types down to concrete integer/bool witnesses. The tool cannot inspect
the internals of **foreign opaque types** (e.g. `core::alloc::Layout`),
but the spec in the repo may define **projection spec functions** —
unary `uninterp spec fn` or `pub spec fn` declarations taking that
opaque type and returning a primitive scalar (usize/nat/int/bool/...)
— that expose the semantically relevant integer/bool dimensions.

Your job: for each opaque type name given, grep the repo for such
projection spec functions and list the ones whose return type is a
primitive scalar.
"""


_PROJ_SCHEMA_DOC = """\
## Output format

Emit a single fenced ```json block. Top-level object keys are the
opaque type names given below. Values are arrays of projections.

```json
{
  "<TypeName>": [
    {
      "spec_fn": "<unqualified_spec_fn_name>",
      "return_type": "<usize|nat|int|bool|u8|u16|u32|u64|i8|i16|i32|i64|isize>",
      "rationale": "<1 short sentence: what dimension this captures>"
    }
  ]
}
```

Rules:
- Include ONLY unary spec fns (one parameter) whose single argument is
  the opaque type (by reference or by value).
- The spec fn must have a primitive scalar return type from the list
  above. Do NOT include projections that return composite types.
- Prefer projections actually referenced by `ensures` / `requires` /
  `open spec fn` / `assume_specification` clauses elsewhere in the
  repo — those are the dimensions that drive the function's behavior.
- If no projections exist for a type, emit an empty array `[]` for it.
- Use the UNQUALIFIED name for `spec_fn` (e.g. `spec_layout_size`, not
  `alloc::spec_layout_size`), as it would appear inside a `verus!{}`
  block after the usual `use` imports.
- Output the JSON block and nothing else (no prose before or after).
"""


_PROJ_FEW_SHOT = """\
## Example

Given: opaque type `Layout`, repo root `/home/alice/nanvix`

After grep: you find in `src/kernel/src/mm/kheap.spec.rs`:
```
pub uninterp spec fn spec_layout_size(layout: core::alloc::Layout) -> usize;
pub uninterp spec fn spec_layout_align(layout: core::alloc::Layout) -> usize;
```

Correct output:
```json
{
  "Layout": [
    {"spec_fn": "spec_layout_size", "return_type": "usize", "rationale": "Drives allocator size-class selection in ensures."},
    {"spec_fn": "spec_layout_align", "return_type": "usize", "rationale": "Required alignment; referenced by layout_ok_for_kheap."}
  ]
}
```
"""


def build_projections_prompt(
    opaque_type_names: list[str],
    repo_root: Path,
    crate_name: str = "",
) -> str:
    """Build the projection-discovery prompt."""
    type_list = ", ".join(f"`{n}`" for n in opaque_type_names)
    ctx_lines = [f"- Repo root: `{repo_root}`"]
    if crate_name:
        ctx_lines.append(f"- Originating crate: `{crate_name}`")
    ctx_lines.append(
        "- Spec files typically have the suffix `.spec.rs`; also check "
        "any `*.rs` file with a `verus!{}` block."
    )
    ctx = "\n".join(ctx_lines)
    return (
        _PROJ_PROMPT_HEADER
        + "\n## Your task\n\n"
        + f"Opaque types to analyse: {type_list}\n\n"
        + f"Context:\n{ctx}\n\n"
        + _PROJ_SCHEMA_DOC
        + "\n"
        + _PROJ_FEW_SHOT
    )


def parse_projections_response(text: str) -> dict:
    """Extract the JSON block from the projection-LLM response.

    Shape: ``{type_name: [{spec_fn, return_type, rationale?}, ...]}``.
    """
    m = _JSON_FENCE_RE.search(text)
    blob = m.group(1) if m else text.strip()
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM projection response was not valid JSON:\n{text}") from e
    if not isinstance(obj, dict):
        raise ValueError("LLM projection response is not a JSON object")
    return obj


_SPEC_FN_DECL_RE_TMPL = (
    # Matches `spec fn NAME(` / `uninterp spec fn NAME(` with optional
    # `pub` / `open` / `closed` / `broadcast` modifiers before.
    r"(?:pub\s+)?(?:open\s+|closed\s+)?(?:broadcast\s+)?"
    r"(?:uninterp\s+)?spec\s+fn\s+{name}\s*\("
)


def _validate_projection(
    raw: dict,
    type_source_blob: str,
) -> Optional[ProjectionInfo]:
    """Validate one projection dict from the LLM. Returns None if invalid."""
    spec_fn = (raw.get("spec_fn") or "").strip()
    rt_raw = (raw.get("return_type") or "").strip()
    rationale = raw.get("rationale")
    if not spec_fn or not rt_raw:
        logger.warning("projection missing spec_fn/return_type: %r", raw)
        return None
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", spec_fn):
        logger.warning("projection spec_fn %r is not a bare identifier", spec_fn)
        return None
    kind = _SCALAR_NAME_TO_KIND.get(rt_raw)
    if kind is None:
        logger.warning("projection %s has unsupported return_type %r",
                       spec_fn, rt_raw)
        return None
    # Must find a declaration in the corpus.
    pattern = _SPEC_FN_DECL_RE_TMPL.format(name=re.escape(spec_fn))
    if not re.search(pattern, type_source_blob):
        logger.warning("projection spec fn %s not found in type source corpus",
                       spec_fn)
        return None
    return ProjectionInfo(
        spec_fn=spec_fn,
        return_type=TypeInfo(kind=kind, name=rt_raw),
        rationale=rationale if isinstance(rationale, str) else None,
    )


def projections_from_llm_dict(
    d: dict,
    opaque_type_names: list[str],
    type_source_blob: str,
) -> dict[str, TypeProjections]:
    """Validate and normalize the LLM response into a ``type_projections``
    mapping suitable for ``DetCheckSpec.type_projections``.

    Types present in ``opaque_type_names`` but absent from ``d`` (or with
    an empty/invalid list) receive a ``status="empty"`` entry so future
    runs don't re-query.
    """
    result: dict[str, TypeProjections] = {}
    for name in opaque_type_names:
        entries = d.get(name)
        validated: list[ProjectionInfo] = []
        if isinstance(entries, list):
            for raw in entries:
                if not isinstance(raw, dict):
                    continue
                proj = _validate_projection(raw, type_source_blob)
                if proj is not None:
                    validated.append(proj)
        status = "ok" if validated else "empty"
        result[name] = TypeProjections(
            status=status, projections=validated, source="llm"
        )
    return result


def generate_projections_with_llm(
    opaque_type_names: list[str],
    repo_root: Path,
    run_dir: Path,
    type_source_blob: str,
    crate_name: str = "",
    client: CopilotPolicyLLM | None = None,
) -> dict[str, TypeProjections]:
    """Query the LLM for projections of the given opaque types.

    ``type_source_blob`` is the concatenated spec-source text used to
    validate that each returned ``spec_fn`` actually exists.
    """
    if client is None:
        client = CopilotPolicyLLM()
    prompt = build_projections_prompt(opaque_type_names, repo_root,
                                      crate_name=crate_name)
    raw = client.query(prompt, run_dir)
    parsed = parse_projections_response(raw)
    out = projections_from_llm_dict(parsed, opaque_type_names, type_source_blob)
    for name, tp in out.items():
        logger.info("LLM projections for %s: status=%s, %d fns",
                    name, tp.status, len(tp.projections))
    return out

