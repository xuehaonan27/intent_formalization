#!/usr/bin/env python3
"""Tiny spec-generation + determinism-feedback experiment.

This is intentionally small: one Verus-SpecGym task at a time.

Loop:
  1. Ask an LLM to generate and freeze the semantic output equivalence.
  2. Ask an LLM to fill `pre_spec` / `post_spec` against that frozen oracle.
  3. Add a synthetic exec wrapper whose ensures is `post_spec(in1, out)`.
  4. Run the existing spec-determinism checker on that wrapper, comparing
     outputs with the frozen semantic equivalence.
  5. For up to N fixed debugging rounds, feed the witness back to the LLM
     and rerun the determinism check.

The point is not to build a new spec-generation framework; it is to show that
determinism checking gives actionable feedback when an LLM-written `post_spec`
is too weak.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spec_determinism.codegen.equal_policy import EqualPolicy
from spec_determinism.codegen.gen_det import build_det_check_spec
from spec_determinism.extract.extractor import extract_spec
from spec_determinism.schema_search import enumerate_schemas, render_guarded_template
from spec_determinism.schema_search.search import build_schema_ctx, run_schema_search
from spec_determinism.verus.single_file import _DEFAULT_VERUS, _inject_into_source, run_verus_file


WRAPPER_FN = "__specgen_det_post"
DET_OUT = "__SpecGenDetOut"
SEMANTIC_EQ = "specgen_output_equiv"
ORACLE_PREFIX = "specgen_oracle_"


ORACLE_PROMPT = """\
You are working on a Verus-SpecGym specification task.

Files:
- Verus file to edit: {solve_path}
- Problem statement: {problem_path}

You are running as the Copilot CLI agent with shell/file tools. Edit the file
in place.

Task:
Generate ONLY the independent semantic output-equivalence oracle:

- `pub open spec fn specgen_output_equiv(in1: In1, out1: Out, out2: Out) -> bool`
- optional helper spec/proof functions, all named with prefix `specgen_oracle_`

Do not change type definitions, function names/signatures, check wrappers,
paste-marker comments, runtime entrypoints, `main`, `pre_spec`, or `post_spec`.

This oracle is generated BEFORE `post_spec` and will be frozen. It is used to
audit `post_spec`, so it must be independent:

- It must NOT call `pre_spec`.
- It must NOT call `post_spec`.
- It must NOT be the constant `true`.
- For unique-output problems, it should usually compare the observable `Out`
  fields for equality.
- For multi-solution problems, it should say when two concrete outputs are both
  acceptable answers for the same input, using only `specgen_oracle_*` helpers
  and the problem statement semantics.

At the end, prefer leaving `{solve_path}` edited in place. If you output a
```rust code block, it MUST contain the complete file, not just helper
functions.
"""


SPEC_PROMPT = """\
You are working on a Verus-SpecGym specification task.

Files:
- Verus file to edit: {solve_path}
- Problem statement: {problem_path}

The semantic output-equivalence oracle has already been generated and is frozen:

```rust
{oracle_block}
```

Do NOT edit, delete, rename, or redefine `specgen_output_equiv` or any
`specgen_oracle_*` helper. The harness will restore the frozen oracle after your
edit anyway.

Task:
Fill only:
- `pre_spec`
- `post_spec`
- the four proof helper bodies, if needed for basic checking
- optional non-oracle spec/proof helper definitions

`post_spec` should characterize the problem's expected output relation. It may
use `specgen_oracle_*` helper predicates, but it must NOT call
`specgen_output_equiv` directly.

After editing, run this lightweight determinism self-check if possible:

```bash
{selfcheck_cmd}
```

If it reports `verus_error`, syntax/type errors, trigger errors, or a semantic
non-equivalence witness, fix `{solve_path}` and rerun the self-check. It is OK
if the check remains inconclusive after a reasonable attempt; return your best
file. At the end, prefer leaving `{solve_path}` edited in place. If you output a
```rust code block, it MUST contain the complete file, not just helper
functions.
"""


FIX_PROMPT = """\
The previous Verus-SpecGym `post_spec` needs determinism-feedback repair.

The checker encoded `post_spec(in1, out)` as an exec-function postcondition and
asked whether two valid runs on the same `in1` must produce semantically
equivalent `Out` values under `specgen_output_equiv`.
Outcome: {outcome_text}

Checker result:
```json
{det_summary}
```

Witness assumptions retained by the checker:
```text
{assumes}
```

The semantic output-equivalence oracle is frozen; do NOT edit
`specgen_output_equiv` or any `specgen_oracle_*` helper.

Please edit `{solve_path}` in place. First fix any basic Verus/checker error
reported above. If the checker reached a distinct-output witness, repair either:

- `post_spec`, if it admits outputs outside the problem's expected output
  relation; or
- non-oracle helper functions used by `post_spec`.

Preserve the intended problem semantics from `{problem_path}`. Do not "fix" this
by making `pre_spec` false or by adding contradictory conditions; the spec must
still accept valid samples. `post_spec` may use `specgen_oracle_*` helpers but
must NOT call `specgen_output_equiv` directly.

After editing, run this self-check if possible:

```bash
{selfcheck_cmd}
```

If it still reports an error or a witness, iterate once or twice using the
diagnostic. At the end, prefer leaving `{solve_path}` edited in place. If you
output a ```rust code block, it MUST contain the complete file, not just helper
functions.
"""


def _read(path: Path) -> str:
    return path.read_text(errors="replace")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _extract_code_block(text: str) -> str:
    blocks = re.findall(r"```(?:rust|verus)?\s*\n(.*?)```", text, flags=re.DOTALL)
    if blocks:
        return blocks[-1].strip() + "\n"
    return text.strip() + "\n"


def _maybe_update_from_response(path: Path, response: str) -> None:
    blocks = re.findall(r"```(?:rust|verus)?\s*\n(.*?)```", response, flags=re.DOTALL)
    if blocks:
        candidate = blocks[-1].strip() + "\n"
        # Only overwrite solve.rs with a full-file response. Copilot often
        # returns a small helper/function block even after editing in place; if
        # we wrote that over the file, the next phase would lose `verus! { ... }`.
        if "verus!" in candidate and "pre_spec" in candidate and "post_spec" in candidate:
            _write(path, candidate)


def call_copilot(
    *,
    prompt: str,
    model: str | None,
    copilot_bin: str,
    timeout_s: int,
) -> str:
    cmd = [
        copilot_bin,
        "-s",
        "--no-auto-update",
        "--allow-all-tools",
        "--allow-all-paths",
        "-p",
        prompt,
    ]
    if model:
        cmd[1:1] = ["--model", model]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"copilot exited {proc.returncode}")
    return proc.stdout


def _find_matching_brace(text: str, open_idx: int) -> int:
    depth = 0
    i = open_idx
    while i < len(text):
        c = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if c == "/" and nxt == "/":
            nl = text.find("\n", i + 2)
            i = len(text) if nl == -1 else nl + 1
            continue
        if c == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
            continue
        if c == '"':
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"unmatched brace at byte {open_idx}")


def replace_fn_body(source: str, fn_name: str, new_body: str) -> str:
    pat = re.compile(
        rf"\b(?:pub(?:\([^)]*\))?\s+)?(?:open\s+)?(?:proof\s+)?fn\s+"
        rf"{re.escape(fn_name)}\b"
    )
    match = pat.search(source)
    if match is None:
        return source
    brace = source.find("{", match.end())
    if brace == -1:
        return source
    end = _find_matching_brace(source, brace)
    return source[:brace] + "{\n" + new_body.rstrip() + "\n}" + source[end + 1 :]


def find_verus_block_close(source: str) -> int:
    match = re.search(r"\bverus\s*!\s*\{", source)
    if match is None:
        raise ValueError("source has no `verus! { ... }` block")
    return _find_matching_brace(source, match.end() - 1)


def find_spec_fn_body(source: str, fn_name: str) -> str | None:
    pat = re.compile(
        rf"\b(?:pub\s+)?(?:open\s+|closed\s+)?spec\s+fn\s+{re.escape(fn_name)}\b"
    )
    match = pat.search(source)
    if match is None:
        return None
    brace = source.find("{", match.end())
    if brace == -1:
        return None
    end = _find_matching_brace(source, brace)
    return source[brace + 1:end].strip()


def iter_oracle_fn_names(source: str) -> list[str]:
    pat = re.compile(
        rf"\b(?:pub\s+)?(?:(?:open|closed)\s+)?(?:spec|proof)\s+fn\s+"
        rf"({SEMANTIC_EQ}|{ORACLE_PREFIX}[A-Za-z0-9_]*)\b"
    )
    names: list[str] = []
    for match in pat.finditer(source):
        name = match.group(1)
        if name not in names:
            names.append(name)
    return names


def find_fn_item_span(source: str, fn_name: str) -> tuple[int, int] | None:
    pat = re.compile(
        rf"(?m)^[ \t]*(?:pub(?:\([^)]*\))?\s+)?(?:(?:open|closed)\s+)?"
        rf"(?:spec|proof)\s+fn\s+{re.escape(fn_name)}\b"
    )
    match = pat.search(source)
    if match is None:
        return None
    brace = source.find("{", match.end())
    if brace == -1:
        return None
    end = _find_matching_brace(source, brace)
    while end + 1 < len(source) and source[end + 1] in " \t\r\n":
        end += 1
    return match.start(), end + 1


def extract_oracle_block(source: str) -> str:
    names = iter_oracle_fn_names(source)
    if SEMANTIC_EQ not in names:
        raise ValueError(f"oracle pass did not define `{SEMANTIC_EQ}`")
    spans = []
    for name in names:
        span = find_fn_item_span(source, name)
        if span is not None:
            spans.append((span[0], span[1], name))
    spans.sort()
    block = "\n\n".join(source[start:end].strip() for start, end, _ in spans)
    err = validate_semantic_equiv_source(block)
    if err:
        raise ValueError(err)
    return block + "\n"


def extract_oracle_block_from_response(response: str) -> str | None:
    blocks = re.findall(r"```(?:rust|verus)?\s*\n(.*?)```", response, flags=re.DOTALL)
    for block in reversed(blocks):
        if SEMANTIC_EQ not in block:
            continue
        try:
            return extract_oracle_block(block)
        except Exception:
            # If the block contains only oracle functions, not a whole Verus
            # module, direct item extraction still works via regex spans.
            names = iter_oracle_fn_names(block)
            if SEMANTIC_EQ not in names:
                continue
            spans = []
            for name in names:
                span = find_fn_item_span(block, name)
                if span is not None:
                    spans.append((span[0], span[1], name))
            if not spans:
                continue
            spans.sort()
            oracle = "\n\n".join(block[start:end].strip() for start, end, _ in spans) + "\n"
            if validate_semantic_equiv_source(oracle) is None:
                return oracle
    return None


def remove_oracle_items(source: str) -> str:
    spans = []
    for name in iter_oracle_fn_names(source):
        span = find_fn_item_span(source, name)
        if span is not None:
            spans.append(span)
    for start, end in sorted(spans, reverse=True):
        source = source[:start] + source[end:]
    return source


def restore_oracle_block(source: str, oracle_block: str | None) -> str:
    if not oracle_block:
        return source
    source = remove_oracle_items(source)
    close = find_verus_block_close(source)
    return source[:close].rstrip() + "\n\n" + oracle_block.strip() + "\n\n" + source[close:]


def validate_semantic_equiv_source(source: str) -> str | None:
    body = find_spec_fn_body(source, SEMANTIC_EQ)
    if body is None:
        return None
    body_no_comments = re.sub(r"//.*?$|/\*.*?\*/", "", body, flags=re.MULTILINE | re.DOTALL)
    if re.search(r"\bpre_spec\s*\(", body_no_comments):
        return (
            f"`{SEMANTIC_EQ}` must be generated before `pre_spec`, but its "
            "body calls `pre_spec(...)`."
        )
    if re.search(r"\bpost_spec\s*\(", body_no_comments):
        return (
            f"`{SEMANTIC_EQ}` must be independent from `post_spec`, but its "
            "body calls `post_spec(...)`."
        )
    if body_no_comments.strip().strip("()") == "true":
        return f"`{SEMANTIC_EQ}` must not be the constant `true`."
    for name in iter_oracle_fn_names(source):
        helper_body = find_spec_fn_body(source, name) or ""
        helper_no_comments = re.sub(
            r"//.*?$|/\*.*?\*/", "", helper_body,
            flags=re.MULTILINE | re.DOTALL,
        )
        if re.search(r"\b(?:pre_spec|post_spec)\s*\(", helper_no_comments):
            return (
                f"oracle helper `{name}` must not call `pre_spec` or "
                "`post_spec`."
            )
    return None


def validate_post_spec_source(source: str) -> str | None:
    body = find_spec_fn_body(source, "post_spec")
    if body is None:
        return None
    body_no_comments = re.sub(r"//.*?$|/\*.*?\*/", "", body, flags=re.MULTILINE | re.DOTALL)
    if re.search(rf"\b{SEMANTIC_EQ}\s*\(", body_no_comments):
        return f"`post_spec` must not call `{SEMANTIC_EQ}` directly."
    return None


def unwrap_exec_spec_macro(source: str) -> str:
    """Expose SpecGym's macro-wrapped type/spec declarations to tree-sitter.

    `exec_spec_unverified! { ... }` generates exec wrappers that are irrelevant
    to this experiment. The determinism checker needs to *see* `In1` / `Out`
    fields, so for the temporary det-check file we replace the macro invocation
    by its raw contents.
    """
    pat = re.compile(r"\bexec_spec(?:_unverified)?\s*!\s*\{")
    while True:
        match = pat.search(source)
        if match is None:
            return source
        open_idx = match.end() - 1
        close_idx = _find_matching_brace(source, open_idx)
        source = source[: match.start()] + source[match.end() : close_idx] + source[close_idx + 1 :]


def make_detcheck_source(source: str) -> str:
    """Remove SpecGym testcase boilerplate and append the determinism wrapper."""
    source = unwrap_exec_spec_macro(source)

    # The benchmark template writes `pub open proof fn ...`; current Verus
    # accepts `open` only on spec fns. These proof helpers are irrelevant to
    # the post_spec determinism check, so normalize them before typechecking.
    source = re.sub(r"\bpub\s+open\s+proof\s+fn\b", "pub proof fn", source)
    source = re.sub(r"\bopen\s+proof\s+fn\b", "proof fn", source)

    for fn in (
        "pre_spec_soundness_proof",
        "pre_spec_completeness_proof",
        "post_spec_soundness_proof",
        "post_spec_completeness_proof",
    ):
        source = replace_fn_body(source, fn, "    true")
    for fn in (
        "check_pre_spec_completeness",
        "check_pre_spec_soundness",
        "check_post_spec_completeness",
        "check_post_spec_soundness",
        "main_exec_pre_spec_check",
        "main_exec_post_spec_check",
        "main",
    ):
        source = replace_fn_body(source, fn, "")

    semantic_eq = ""
    if not re.search(rf"\b(?:pub\s+)?(?:open\s+)?spec\s+fn\s+{SEMANTIC_EQ}\b", source):
        semantic_eq = f"""

pub open spec fn {SEMANTIC_EQ}(in1: In1, out1: Out, out2: Out) -> bool {{
    out1 == out2
}}
"""

    wrapper = f"""

pub struct {DET_OUT} {{
    pub in1: In1,
    pub out: Out,
}}

#[verifier::external_body]
pub fn {WRAPPER_FN}(in1: In1) -> (pair: {DET_OUT})
    requires
        pre_spec(in1),
    ensures
        pair.in1 == in1,
        post_spec(in1, pair.out),
{{
    unimplemented!()
}}
"""
    close = find_verus_block_close(source)
    return source[:close] + semantic_eq + wrapper + "\n" + source[close:]


def run_detcheck(
    *,
    solve_path: Path,
    out_dir: Path,
    verus_path: str,
    timeout_s: int,
) -> dict:
    original_src = _read(solve_path)
    invalid_equiv_reason = validate_semantic_equiv_source(original_src)
    if invalid_equiv_reason is not None:
        result = {
            "file": str(solve_path),
            "function": WRAPPER_FN,
            "status": "invalid_equiv",
            "error": invalid_equiv_reason,
            "permitted": False,
        }
        _write(out_dir / "det_result.json", json.dumps(result, indent=2, ensure_ascii=False))
        return result
    invalid_post_reason = validate_post_spec_source(original_src)
    if invalid_post_reason is not None:
        result = {
            "file": str(solve_path),
            "function": WRAPPER_FN,
            "status": "invalid_spec",
            "error": invalid_post_reason,
            "permitted": False,
        }
        _write(out_dir / "det_result.json", json.dumps(result, indent=2, ensure_ascii=False))
        return result

    det_src = make_detcheck_source(original_src)
    det_path = out_dir / "specgen_detcheck.rs"
    _write(det_path, det_src)
    artifact_dir = out_dir / "det_artifacts"
    result: dict = {
        "file": str(det_path),
        "function": WRAPPER_FN,
        "permitted": False,
    }
    t0 = time.monotonic()

    equal_policy = EqualPolicy(
        custom_body=(
            f"{SEMANTIC_EQ}(r1.in1, r1.out, r2.out)"
        ),
        rationale=(
            "SpecGym semantic output equivalence: multi-solution tasks may "
            "treat distinct concrete Out values as equal when both are valid "
            "answers for the same input."
        ),
        source="manual",
    )

    try:
        spec = extract_spec(det_src, WRAPPER_FN, type_sources=[])
    except Exception as exc:
        result["status"] = "extract_error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        _write(out_dir / "det_result.json", json.dumps(result, indent=2, ensure_ascii=False))
        return result

    if not spec.ensures:
        result["status"] = "no_ensures"
        _write(out_dir / "det_result.json", json.dumps(result, indent=2, ensure_ascii=False))
        return result

    det_spec = build_det_check_spec(spec, source=det_src, equal_policy=equal_policy)
    fn_det_name = det_spec.check_fn_name
    tmp_root = Path(tempfile.mkdtemp(prefix=f"specgen_det_{WRAPPER_FN}_"))
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "det_spec.json").write_text(det_spec.to_json())

        schemas = enumerate_schemas(det_spec)
        code = det_spec.equal_fn_def + "\n\n" + render_guarded_template(det_spec, schemas)
        injected = _inject_into_source(
            det_src,
            code,
            open_closed_specs=det_spec.opened_closed_specs,
        )
        (artifact_dir / "injected.rs").write_text(injected)
        injected_path = tmp_root / f"{det_path.stem}.rs"
        injected_path.write_text(injected)

        log_dir = tmp_root / "verus_log"
        log_dir.mkdir()

        result["n_schemas"] = len(schemas)
        result["n_params"] = sum(1 + len(s.k_params) for s in schemas)

        t_v = time.monotonic()
        raw = run_verus_file(
            injected_path,
            verus_path,
            log_dir,
            timeout=timeout_s,
            verify_function=fn_det_name,
            rlimit=60,
        )
        result["verus_ms"] = int((time.monotonic() - t_v) * 1000)
        if raw["returncode"] != 0:
            stderr = raw["stderr"]
            if (
                "postcondition not satisfied" not in stderr
                and "assertion failed" not in stderr.lower()
                and "error:" in stderr
            ):
                result["status"] = "verus_error"
                result["stderr_tail"] = stderr[-2000:]
                return result

        smt2_candidates = list(log_dir.rglob("*.smt2"))
        smt2_candidates.sort(key=lambda p: (p.name == "root.smt2", p.stat().st_size))
        if not smt2_candidates:
            result["status"] = "no_smt2"
            return result
        smt2 = smt2_candidates[-1]
        result["smt2_bytes"] = smt2.stat().st_size

        try:
            t_c = time.monotonic()
            schema_ctx = build_schema_ctx(smt2, fn_det_name, schemas, det_path.stem)
            result["ctx_ms"] = int((time.monotonic() - t_c) * 1000)

            t_s = time.monotonic()
            witness = run_schema_search(det_spec, schema_ctx)
            result["search_ms"] = int((time.monotonic() - t_s) * 1000)
            result["n_rounds"] = len(witness.trace) if witness.trace else 0
            result["assumes"] = [a.expression for a in (witness.assumes or [])]
            result["r0_z3"] = witness.r0_z3
            result["status"] = "ok"
        except Exception as exc:
            result["status"] = "search_error"
            result["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-800:]}"
    finally:
        stray_bin = REPO_ROOT / det_path.stem
        if stray_bin.exists() and stray_bin.is_file():
            stray_bin.unlink()
        result["total_ms"] = int((time.monotonic() - t0) * 1000)
        _write(out_dir / "det_result.json", json.dumps(result, indent=2, ensure_ascii=False))
    _write(out_dir / "det_result.json", json.dumps(result, indent=2, ensure_ascii=False))
    return result


def det_summary(result: dict) -> dict:
    keys = (
        "status",
        "r0_z3",
        "n_schemas",
        "n_rounds",
        "verus_ms",
        "ctx_ms",
        "search_ms",
        "error",
        "stderr_tail",
    )
    return {k: result[k] for k in keys if k in result}


def is_confirmed_incomplete(result: dict) -> bool:
    return result.get("status") == "ok" and result.get("r0_z3") == "sat"


def needs_det_feedback(result: dict) -> bool:
    if result.get("status") != "ok":
        return False
    if result.get("r0_z3") == "unsat":
        return False
    return any(str(a).startswith("!") and "_equal" in str(a) for a in result.get("assumes") or [])


def needs_repair_feedback(result: dict) -> bool:
    if result.get("status") == "ok":
        return needs_det_feedback(result)
    return result.get("status") in {
        "verus_error",
        "extract_error",
        "search_error",
        "no_smt2",
        "no_ensures",
        "invalid_equiv",
        "invalid_spec",
    }


def write_feedback_prompt(
    *,
    result: dict,
    solve_path: Path,
    task_dir: Path,
    problem_path: Path,
    out_dir: Path,
) -> Path:
    assumes = result.get("assumes") or []
    status = result.get("status")
    if status != "ok":
        outcome_text = (
            f"The determinism wrapper did not typecheck/run cleanly "
            f"(`status={status}`). This is a basic checker/Verus/equivalence "
            "error, not yet a determinism verdict. Fix the specification so "
            "the checker can run."
        )
    elif result.get("r0_z3") == "sat":
        outcome_text = (
            "z3 confirmed nondeterminism: the current spec permits two "
            "outputs for one input that are NOT equivalent under "
            f"`{SEMANTIC_EQ}`."
        )
    else:
        outcome_text = (
            "z3 did not prove determinism, and schema search retained a "
            "distinct-output candidate witness under the current semantic "
            f"equivalence `{SEMANTIC_EQ}`. Treat this as actionable feedback: "
            "strengthen `post_spec` or coarsen the semantic equivalence for "
            "intentional multi-solution outputs until the determinism check "
            "becomes UNSAT."
        )
    prompt = FIX_PROMPT.format(
        solve_path=solve_path,
        problem_path=problem_path,
        selfcheck_cmd=selfcheck_cmd(task_dir, solve_path, out_dir / "agent_selfcheck"),
        outcome_text=outcome_text,
        det_summary=json.dumps(det_summary(result), indent=2, ensure_ascii=False),
        assumes="\n".join(f"- {a}" for a in assumes) if assumes else "(none)",
    )
    path = out_dir / "det_feedback_prompt.md"
    _write(path, prompt)
    return path


def det_status_label(result: dict) -> str:
    if result.get("status") != "ok":
        return str(result.get("status", "error"))
    r0 = result.get("r0_z3")
    if r0 == "unsat":
        return "deterministic"
    if r0 == "sat":
        return "confirmed_incomplete"
    if needs_det_feedback(result):
        return "feedback_candidate"
    return f"inconclusive_{r0}"


def selfcheck_cmd(task_dir: Path, solve_path: Path, out_dir: Path) -> str:
    return (
        f"cd {REPO_ROOT} && "
        f"python scripts/specgen_det_feedback.py "
        f"--task-dir {task_dir} "
        f"--initial-file {solve_path} "
        f"--out-dir {out_dir} "
        f"--feedback-rounds 0 --det-timeout 120"
    )


def init_work_file(task_dir: Path, out_dir: Path, initial_file: Path | None) -> Path:
    solve_path = out_dir / "solve.rs"
    if initial_file is not None:
        _write(solve_path, _read(initial_file))
        return solve_path
    template = task_dir / "solution" / "solve_template.rs"
    if not template.is_file():
        raise FileNotFoundError(f"missing template: {template}")
    _write(solve_path, _read(template))
    return solve_path


def problem_path_for(task_dir: Path) -> Path:
    path = task_dir / "environment" / "build_context" / "task_specific_artifacts" / "problem_statement.md"
    if not path.is_file():
        raise FileNotFoundError(f"missing problem statement: {path}")
    return path


def run_round(
    *,
    solve_path: Path,
    round_dir: Path,
    verus_path: str,
    det_timeout: int,
) -> dict:
    result = run_detcheck(
        solve_path=solve_path,
        out_dir=round_dir,
        verus_path=verus_path,
        timeout_s=det_timeout,
    )
    return {
        "round": round_dir.name,
        "solve_path": str(solve_path),
        "det": det_summary(result),
        "status_label": det_status_label(result),
        "confirmed_incomplete": is_confirmed_incomplete(result),
        "det_feedback_needed": needs_det_feedback(result),
        "assumes": result.get("assumes") or [],
        "raw_result_path": str(round_dir / "det_result.json"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--initial-file", type=Path, default=None,
                    help="Use an existing generated solve.rs instead of calling the LLM.")
    ap.add_argument("--call-llm-initial", action="store_true")
    ap.add_argument("--call-llm-fix", action="store_true")
    ap.add_argument("--feedback-rounds", type=int, default=1,
                    help="Fixed number of determinism-feedback repair rounds.")
    ap.add_argument("--model", default=None)
    ap.add_argument("--copilot-bin", default=os.environ.get("COPILOT_BIN", "copilot"))
    ap.add_argument("--llm-timeout", type=int, default=900)
    ap.add_argument("--verus-path", default=_DEFAULT_VERUS)
    ap.add_argument("--det-timeout", type=int, default=120)
    args = ap.parse_args()

    task_dir = args.task_dir.expanduser().resolve()
    out_dir = (
        args.out_dir.expanduser().resolve()
        if args.out_dir
        else REPO_ROOT / "results" / "specgen_det_feedback" / task_dir.name
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    problem_path = problem_path_for(task_dir)
    solve_path = init_work_file(task_dir, out_dir, args.initial_file)
    oracle_block: str | None = None

    if args.call_llm_initial:
        oracle_prompt = ORACLE_PROMPT.format(
            solve_path=solve_path,
            problem_path=problem_path,
        )
        _write(out_dir / "oracle_prompt.md", oracle_prompt)
        raw = call_copilot(
            prompt=oracle_prompt,
            model=args.model,
            copilot_bin=args.copilot_bin,
            timeout_s=args.llm_timeout,
        )
        _write(out_dir / "oracle_response.txt", raw)
        _maybe_update_from_response(solve_path, raw)
        try:
            oracle_block = extract_oracle_block(_read(solve_path))
        except Exception:
            oracle_block = extract_oracle_block_from_response(raw)
            if oracle_block is None:
                raise
        _write(out_dir / "oracle_block.rs", oracle_block)
        _write(solve_path, restore_oracle_block(_read(solve_path), oracle_block))

        prompt = SPEC_PROMPT.format(
            solve_path=solve_path,
            problem_path=problem_path,
            oracle_block=oracle_block.strip(),
            selfcheck_cmd=selfcheck_cmd(task_dir, solve_path, out_dir / "initial_selfcheck"),
        )
        _write(out_dir / "initial_prompt.md", prompt)
        raw = call_copilot(
            prompt=prompt,
            model=args.model,
            copilot_bin=args.copilot_bin,
            timeout_s=args.llm_timeout,
        )
        _write(out_dir / "initial_response.txt", raw)
        _maybe_update_from_response(solve_path, raw)
        _write(solve_path, restore_oracle_block(_read(solve_path), oracle_block))
    else:
        try:
            oracle_block = extract_oracle_block(_read(solve_path))
            _write(out_dir / "oracle_block.rs", oracle_block)
        except Exception:
            oracle_block = None

    rounds = []
    current_solve = solve_path
    result = None
    for idx in range(args.feedback_rounds + 1):
        round_dir = out_dir / f"round_{idx:02d}"
        result = run_detcheck(
            solve_path=current_solve,
            out_dir=round_dir,
            verus_path=args.verus_path,
            timeout_s=args.det_timeout,
        )
        round_record = {
            "round": idx,
            "solve_path": str(current_solve),
            "det": det_summary(result),
            "status_label": det_status_label(result),
            "confirmed_incomplete": is_confirmed_incomplete(result),
            "det_feedback_needed": needs_det_feedback(result),
            "repair_feedback_needed": needs_repair_feedback(result),
            "assumes": result.get("assumes") or [],
            "raw_result_path": str(round_dir / "det_result.json"),
        }
        rounds.append(round_record)
        _write(out_dir / "rounds.json", json.dumps(rounds, indent=2, ensure_ascii=False))

        if idx >= args.feedback_rounds:
            break
        if not needs_repair_feedback(result):
            break
        feedback_path = write_feedback_prompt(
            result=result,
            solve_path=current_solve,
            task_dir=task_dir,
            problem_path=problem_path,
            out_dir=round_dir,
        )
        round_record["feedback_prompt"] = str(feedback_path)
        _write(out_dir / "rounds.json", json.dumps(rounds, indent=2, ensure_ascii=False))
        if not args.call_llm_fix:
            break
        _write(current_solve, restore_oracle_block(_read(current_solve), oracle_block))
        raw = call_copilot(
            prompt=_read(feedback_path),
            model=args.model,
            copilot_bin=args.copilot_bin,
            timeout_s=args.llm_timeout,
        )
        response_path = out_dir / f"fix_round_{idx + 1:02d}_response.txt"
        _write(response_path, raw)
        next_solve = out_dir / f"solve.round_{idx + 1:02d}.rs"
        _write(next_solve, _read(current_solve))
        _maybe_update_from_response(next_solve, raw)
        _write(next_solve, restore_oracle_block(_read(next_solve), oracle_block))
        round_record["fix_response"] = str(response_path)
        round_record["next_solve_path"] = str(next_solve)
        _write(out_dir / "rounds.json", json.dumps(rounds, indent=2, ensure_ascii=False))
        current_solve = next_solve

    summary = {
        "task": task_dir.name,
        "solve_path": str(solve_path),
        "oracle_block_path": str(out_dir / "oracle_block.rs") if oracle_block else None,
        "feedback_rounds": args.feedback_rounds,
        "rounds": rounds,
        "final": rounds[-1] if rounds else None,
    }
    _write(out_dir / "summary.json", json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
