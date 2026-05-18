"""Tier 1.5 — LLM prompt builder for type completion.

The prompt asks Copilot CLI (with full repo access) to find the
canonical Rust source for a list of missing type names and to emit a
JSON file at a known location. We control the schema strictly.

The prompt has four sections:
    1. Mission (one sentence)
    2. The list of types to resolve, with the gap reason for each
    3. Context: current ``type_defs`` summary + the calling target's
       ensures snippet, so the agent knows what the types are used for
    4. Required output schema + the exact write target

We deliberately don't dump the entire FunctionSpec — too noisy. We dump
just enough that the agent can grep the right files.
"""

from __future__ import annotations

import json
from typing import Iterable

from spec_determinism.extract.types import FunctionSpec, TypeKind

from .gaps import Gap


_PROMPT_TEMPLATE = """\
You are a Rust/Verus type-resolution assistant. The task is to find the
canonical source-level definitions of the listed types in this repository
and emit them as a JSON file.

TARGET FUNCTION
---------------
The pipeline is trying to prove determinism of `{fn_name}`. The current
extractor was unable to fully resolve the types listed below. Your job is
to find their definitions in this repo (any Rust file, including those
guarded by macros) and emit a structured patch.

TYPES TO RESOLVE
----------------
{gap_table}
{shape_mismatch_block}
EXISTING type_defs (for context)
--------------------------------
{type_defs_summary}

ENSURES SNIPPETS (so you can see how each type is used)
-------------------------------------------------------
{ensures_block}

WHAT TO DO
----------
1. Read the relevant files in this repo. Types may be:
   - Plain `pub struct X<T> {{ ... }}` / `pub enum X {{ ... }}`
   - Wrapped in a macro: `define_enum_and_derive_marshalable! {{ pub enum X {{ ... }} }}`
     — these are invisible to AST parsers; you must grep the macro body.
   - Implemented across multiple `impl<T> X<T> {{ ... }}` blocks — collect
     the `view` (or `view_with_args`) fn signature when present.
   - **Type aliases**: `pub type X<T> = Map<K, T>;` — in that case the
     correct patch sets `kind` to the container kind (struct→map/seq/set
     in JSON would be wrong; see SHAPE-MISMATCH section below for
     guidance) AND drops `spec_view`.
2. For each type, identify:
   - kind: "struct" or "enum"
   - type_params (e.g. ["V"], ["K", "V"])
   - struct fields: list of (name, type_str) — use the EXACT Rust type
     expression as written (e.g. "collections::HashMap<EndPoint, V>")
   - enum variants: list of (name, list of inner type_strs)
     For tuple-like variants `V(T1, T2, ...)`, inner_types_str is the list
     of type expressions: `["T1", "T2"]`.
     For struct-like variants `V {{ f1: T1, f2: T2 }}`, you MAY write the
     inner_types_str entries as `"f1: T1", "f2: T2"` — the validator will
     parse out the field names. For unit variants, inner_types_str is `[]`.
   - spec_view: the `view` fn's return type, IF the type has one
3. Always include `source_evidence`: rel_path (relative to repo root),
   line (1-indexed), and a snippet copied VERBATIM from that line so the
   validator can grep-verify it.
4. Do NOT invent types — if you cannot find a type, omit it from the
   output. The validator will reject patches whose evidence does not
   match the source file.

OUTPUT
------
Write a JSON file to `{out_path}` and nothing else.

REQUIRED SCHEMA (strict)
------------------------
{{
  "type_patches": [
    {{
      "name": "<bare type name>",
      "kind": "struct" | "enum",
      "type_params": ["T", "V", ...],
      "fields": [ {{ "name": "...", "type_str": "..." }} ],     // for struct
      "variants": [ {{ "name": "...", "inner_types_str": ["...", "..."] }} ],  // for enum
      "spec_view": {{ "type_str": "Map<AbstractEndPoint, V>" }},   // optional
      "source_evidence": {{
        "rel_path": "src/host_protocol_v.rs",
        "line": 164,
        "snippet": "pub uninterp spec fn view(self) -> Map<AbstractEndPoint, V>;"
      }}
    }}
  ]
}}

Important: write ONLY the JSON document to `{out_path}`. Do not embed
markdown fences, prose, or anything else. After writing, exit cleanly.
"""


_SHAPE_MISMATCH_TEMPLATE = """
PREVIOUS PATCH FAILED — gen_det compile error
---------------------------------------------
A prior Tier 1.5 round patched the type(s) below, but the synthesized
det-fn fails to type-check with Verus. The error pattern is::

    error[E0599]: no method named `view` found for struct
    `vstd::{{seq,map,set}}::<container>` in the current scope

Verus stderr (tail)::
{compile_stderr_tail}

This means the patch set ``kind=struct`` with ``spec_view=<container>``
but the actual type in source is one of:

  (A) a TYPE ALIAS to the container (e.g. ``pub type T<K,V> = Map<K,V>;``).
      Verus resolves T post-alias, so calling ``T::view()`` is invalid.
      Correct fix: do NOT patch T as a struct. Instead, return the patch
      with ``kind`` reflecting the container head and omit ``spec_view``.
      In JSON, since the schema only accepts "struct" or "enum", the
      cleanest action is to OMIT the patch for T altogether (the
      validator will drop it; the pipeline then falls back to the
      prelude rule for the container, which is correct).

  (B) a one-field wrapper struct (e.g. ``pub struct T<K,V> {{ m: Map<K,V> }}``).
      Correct fix: re-patch with ``kind=struct`` and an explicit
      ``fields`` list naming the inner field and its container type.
      Keep or drop ``spec_view`` according to whether T actually has an
      inherent ``spec fn view`` returning the container; if you keep
      ``spec_view``, the source MUST contain that view fn.

  (C) something else this assistant can't tell — drop the patch by
      omitting it from the output.

Re-grep the source to determine A vs B for each type listed in the
TYPES TO RESOLVE table (rows tagged `shape_mismatch`). DO NOT re-emit
the previous broken patch.
"""


def _format_gap_table(gaps: Iterable[Gap]) -> str:
    rows: list[str] = []
    seen = set()
    for g in gaps:
        if g.name in seen:
            continue
        seen.add(g.name)
        rows.append(f"  - {g.name}    [{g.reason}]    hint: {g.hint}")
    return "\n".join(rows) if rows else "  (none)"


def _format_type_defs_summary(spec: FunctionSpec, max_entries: int = 25) -> str:
    """Compact dump of currently-resolved types so the agent has context
    without seeing the full deep JSON."""
    lines: list[str] = []
    for i, (k, ti) in enumerate(spec.type_defs.items()):
        if i >= max_entries:
            lines.append(f"  ... +{len(spec.type_defs) - max_entries} more")
            break
        kind = ti.kind.value if hasattr(ti.kind, "value") else str(ti.kind)
        nfields = len(ti.fields)
        nvariants = len(ti.variants)
        view = ""
        if ti.spec_view is not None:
            view = f", view={ti.spec_view.name}"
        lines.append(
            f"  - {k}  kind={kind} fields={nfields} variants={nvariants}{view}"
        )
    return "\n".join(lines) if lines else "  (empty)"


def _format_ensures_block(spec: FunctionSpec, max_lines: int = 8) -> str:
    lines: list[str] = []
    for e in spec.ensures[:max_lines]:
        s = str(e) if not isinstance(e, str) else e
        s = s.strip()
        if not s:
            continue
        if len(s) > 240:
            s = s[:237] + "..."
        lines.append(f"  | {s}")
    if len(spec.ensures) > max_lines:
        lines.append(f"  | ... +{len(spec.ensures) - max_lines} more")
    return "\n".join(lines) if lines else "  (no ensures)"


def build_prompt(
    spec: FunctionSpec,
    gaps: list[Gap],
    out_path: str,
    *,
    compile_stderr_tail: str = "",
) -> str:
    # NOTE: _PROMPT_TEMPLATE uses ``str.format`` interpolation. Any literal
    # ``{`` / ``}`` in the template must be escaped as ``{{`` / ``}}``.
    from .gaps import REASON_SHAPE_MISMATCH
    shape_block = ""
    has_shape = any(g.reason == REASON_SHAPE_MISMATCH for g in gaps)
    if has_shape and compile_stderr_tail:
        # Indent the stderr tail so it nests under the template heading.
        indented = "\n".join(
            "    " + ln for ln in compile_stderr_tail.splitlines()
        )[:3000]
        try:
            shape_block = _SHAPE_MISMATCH_TEMPLATE.format(
                compile_stderr_tail=indented,
            )
        except (KeyError, IndexError) as e:
            raise RuntimeError(
                f"build_prompt: shape-mismatch template has unescaped braces: {e}"
            ) from e
    try:
        return _PROMPT_TEMPLATE.format(
            fn_name=spec.name,
            gap_table=_format_gap_table(gaps),
            shape_mismatch_block=shape_block,
            type_defs_summary=_format_type_defs_summary(spec),
            ensures_block=_format_ensures_block(spec),
            out_path=out_path,
        )
    except (KeyError, IndexError) as e:
        # _PROMPT_TEMPLATE contains an unescaped brace — bug in this file.
        raise RuntimeError(
            f"build_prompt: template has an unescaped {{...}} placeholder: {e}. "
            "Escape literal braces as {{ and }}."
        ) from e


def parse_llm_output(raw_json: str) -> list[dict]:
    """Strict-parse the agent's output. Returns the ``type_patches`` array.

    The agent is told to write *only* JSON. In practice it sometimes wraps
    the JSON in fences; tolerate that gracefully.
    """
    text = raw_json.strip()
    if text.startswith("```"):
        # strip fences
        lines = text.splitlines()
        lines = [ln for ln in lines if not ln.startswith("```")]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"parse_llm_output: invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("parse_llm_output: top-level must be a JSON object")
    patches = data.get("type_patches")
    if not isinstance(patches, list):
        raise ValueError("parse_llm_output: 'type_patches' must be a list")
    return patches


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    from spec_determinism.extract.types import (
        FunctionSpec, Param, TypeInfo as TI, TypeKind as TK,
    )
    from .gaps import Gap, REASON_GENERIC_UNRESOLVED, REASON_MACRO_WRAPPED

    spec = FunctionSpec(
        name="receive_ack_impl",
        params=[Param(name="h", type=TI(TK.UNKNOWN, "HashMap<u8>"))],
        return_type=TI(TK.UNIT, "()"),
        requires=[], ensures=["self.un_acked@ == post.un_acked@"],
        type_defs={"u64": TI(TK.U64, "u64")},
    )
    gaps = [
        Gap(
            name="HashMap", reason=REASON_GENERIC_UNRESOLVED,
            where_seen="param h", hint="bare name not in type_defs",
        ),
        Gap(
            name="CSingleMessage", reason=REASON_MACRO_WRAPPED,
            where_seen="param m",
            hint="enum wrapped in define_enum_and_derive_marshalable!",
        ),
    ]
    prompt = build_prompt(spec, gaps, "/tmp/test_patches.json")

    ok = True
    must_contain = [
        "receive_ack_impl",
        "HashMap",
        "CSingleMessage",
        "/tmp/test_patches.json",
        "JSON",
        "source_evidence",
        "spec_view",
        "un_acked",
    ]
    for needle in must_contain:
        if needle not in prompt:
            print(f"FAIL: prompt missing {needle!r}")
            ok = False

    # parse_llm_output: well-formed
    raw = '{"type_patches": [{"name": "HashMap", "kind": "struct"}]}'
    out = parse_llm_output(raw)
    if len(out) != 1 or out[0]["name"] != "HashMap":
        print(f"FAIL: parse_llm_output round-trip: {out}")
        ok = False

    # parse_llm_output: fenced
    fenced = "```json\n" + raw + "\n```"
    out = parse_llm_output(fenced)
    if len(out) != 1:
        print(f"FAIL: parse_llm_output fenced: {out}")
        ok = False

    # parse_llm_output: bad input
    try:
        parse_llm_output("not json at all")
    except ValueError:
        pass
    else:
        print("FAIL: parse_llm_output should reject non-JSON")
        ok = False

    # build_prompt with shape_mismatch context — must include shape-block.
    from .gaps import REASON_SHAPE_MISMATCH
    shape_gaps = [Gap(
        name="AckList", reason=REASON_SHAPE_MISMATCH,
        where_seen="gen_det probe",
        hint="prior patch set kind=struct, spec_view=Seq<...>",
    )]
    prompt_sm = build_prompt(
        spec, shape_gaps, "/tmp/test_patches.json",
        compile_stderr_tail=(
            "error[E0599]: no method named `view` found for struct "
            "`vstd::seq::Seq<A>`"
        ),
    )
    for needle in ("PREVIOUS PATCH FAILED", "shape_mismatch",
                   "Seq<A>", "TYPE ALIAS"):
        if needle not in prompt_sm:
            print(f"FAIL: shape_mismatch prompt missing {needle!r}")
            ok = False

    # build_prompt without shape_mismatch context — must NOT include shape-block.
    prompt_plain = build_prompt(spec, gaps, "/tmp/test_patches.json")
    if "PREVIOUS PATCH FAILED" in prompt_plain:
        print("FAIL: non-shape_mismatch prompt should not include shape-block")
        ok = False

    print("prompt self-test:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
