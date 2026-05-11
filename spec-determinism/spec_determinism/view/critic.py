"""Critic step that double-checks LLM-synthesized impl Views.

After ``view/llm.py:synthesize_view`` gets a candidate ``viewed_type`` +
``view_decl`` from Copilot and it passes tree-sitter parse validation,
we hand it off to a second LLM (codex) for a *semantic* sanity check.
Tree-sitter only confirms the text parses as Rust/Verus; the critic
catches mistakes like:

  - dropping a field that the spec actually inspects
  - mapping ``Vec<T>`` to ``Set<T@>`` when the spec accesses by index
  - calling ``@`` on a primitive (won't compile)
  - viewed_type does not match the ``type V = …`` actually declared
  - collapsing a struct full of real state to ``()`` when only the
    pointers were ghost

The critic *records* its verdict on the cache entry; behaviour:

  - ``accept`` / ``revise``: cache the entry with critic_verdict + issues.
    On ``revise`` we accept the candidate but persist the suggestions for
    later manual review (user's decision 2026-05-11).
  - ``reject``: do NOT cache; append a row to ``_rejected.jsonl`` so the
    type re-runs on the next prefill but the rejection event is durable.
  - ``error``: codex itself failed (timeout / bad JSON). Cache normally
    but record the error in ``critic_issues``; do not block.

The actual codex invocation is ``codex exec`` — no ``--skip-git-repo-check``
needed because we're inside the repo cwd.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


_VERDICTS = {"accept", "revise", "reject"}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class CriticResult:
    """One critique pass."""
    verdict: str  # "accept" | "revise" | "reject" | "error"
    issues: list[str] = field(default_factory=list)
    raw_response: str = ""
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "issues": list(self.issues),
            "duration_s": round(self.duration_s, 2),
        }


# ---------------------------------------------------------------------------
# Codex backend
# ---------------------------------------------------------------------------


@dataclass
class CodexCritic:
    """Minimal codex-CLI client; mirror of CopilotCLI but for critique."""
    model: str | None = None
    timeout: int = 180

    def query(self, prompt: str, run_dir: Path) -> str:
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "critic_prompt.md"
        last_msg_path = run_dir / "critic_last_message.txt"
        prompt_path.write_text(prompt)
        if last_msg_path.exists():
            last_msg_path.unlink()

        cmd = [
            "codex", "exec",
            "--output-last-message", str(last_msg_path),
            "--sandbox", "read-only",
            prompt,
        ]
        if self.model:
            cmd += ["-m", self.model]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:
            (run_dir / "codex_stdout.txt").write_text(
                _decode(e.stdout) + f"\n[timeout after {self.timeout}s]"
            )
            (run_dir / "codex_stderr.txt").write_text(_decode(e.stderr))
            raise RuntimeError(f"codex timeout after {self.timeout}s") from e

        (run_dir / "codex_stdout.txt").write_text(proc.stdout or "")
        (run_dir / "codex_stderr.txt").write_text(proc.stderr or "")

        if last_msg_path.exists():
            text = last_msg_path.read_text()
            if text.strip():
                return text
        # Fall back to stdout's last fenced block — rare path.
        if proc.returncode != 0:
            raise RuntimeError(
                f"codex exited rc={proc.returncode}; see {run_dir}"
            )
        return proc.stdout or ""


def _decode(maybe_bytes) -> str:
    if maybe_bytes is None:
        return ""
    if isinstance(maybe_bytes, bytes):
        return maybe_bytes.decode(errors="replace")
    return maybe_bytes


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


_CRITIC_PROMPT_HEADER = """\
You are auditing a Verus `impl View` block that another LLM just generated.
A view is a pure spec-level projection of a runtime type to its
information content: anything spec assertions need to compare semantically
should survive; runtime ghost fields / permissions / raw pointers should
be collapsed away.

Your job is to spot **semantic** mistakes — the text already parses.
Report only mistakes that matter. Do not nitpick style.

## Common mistakes (non-exhaustive)

1. **Lost information.** A struct field is used in spec ensures (e.g.
   `post.field == old(self).field` or `self.field@`) but the view drops
   it or replaces it with `()`.
2. **Wrong container shape.** `Vec<T>` viewed as `Set<T@>` or `Multiset<T@>`
   when spec accesses by index (`v[i]`) — should be `Seq<T@>`.
3. **Primitive `@`.** A primitive (usize/u32/bool/char/…) cannot be
   `@`-projected — Verus rejects `5_usize@`. Primitives stay verbatim.
4. **type V mismatch.** The declared `type V = X;` doesn't match the body
   of `spec fn view(&self) -> Self::V { … }` — different shape or fields.
5. **Over-aggressive collapse.** A struct with real state (not just
   pointers) collapsed to `type V = ();` — fine only when all fields are
   ghost / raw-pointer.
6. **Missing dep view.** Field of type `T` (which has a known view) used
   as `self.field` instead of `self.field@`, leaving structural eq.
7. **Wrong dep view.** Field of type `Vec<T>` viewed as `Seq<T>` (no `@`
   on element) when spec actually inspects element fields.

## Output

Reply with a SINGLE fenced ```json block of this exact shape, nothing
else (no prose before or after):

```json
{
  "verdict": "accept" | "revise" | "reject",
  "issues": ["<short string per issue>", "..."]
}
```

- `accept`: no issues found, view looks correct.
- `revise`: minor concerns (cosmetic, edge cases) but the view still
  compiles and preserves enough info. List concerns in `issues`.
- `reject`: a hard mistake from the list above (or equivalent). The
  view will fail typecheck or lose spec-relevant information.

If you cannot tell whether the view is correct because of missing
context (e.g. the dependency view is unknown), prefer `accept` with an
issue noting the uncertainty. Do not reject for missing context alone.
"""


def build_critic_prompt(
    *,
    type_short: str,
    qualified_name: str,
    type_source: str,
    viewed_type: str,
    view_decl: str,
    dep_views: dict[str, str],
    rationale: str,
    project: str = "",
) -> str:
    """Compose a critic prompt around the candidate view."""
    deps_text = (
        "\n".join(f"  - {k}: {v}" for k, v in dep_views.items())
        if dep_views else "  (no dependency views resolved)"
    )
    return f"""{_CRITIC_PROMPT_HEADER}

## Target type ({project})

Qualified name: `{qualified_name}`
Short name: `{type_short}`

```rust
{type_source}
```

## Dependency views already in scope

{deps_text}

## Candidate view (from the generator LLM)

Declared `viewed_type`: `{viewed_type}`

```rust
{view_decl}
```

Generator's rationale: {rationale or '(none)'}
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.DOTALL,
)


def parse_critic_response(raw: str) -> CriticResult:
    """Extract verdict + issues from the codex reply.

    Tolerant: tries fenced ```json first; falls back to the first
    well-formed top-level JSON object in the text. If parsing fails we
    return ``verdict="error"`` with a single issue describing the
    failure — the caller decides whether to cache the candidate anyway.
    """
    blocks = _FENCED_JSON_RE.findall(raw)
    candidates: list[str] = list(blocks)
    if not candidates:
        # Last-ditch: maybe the model dumped raw JSON.
        s = raw.strip()
        if s.startswith("{") and s.endswith("}"):
            candidates.append(s)

    for body in candidates:
        try:
            d = json.loads(body)
        except json.JSONDecodeError:
            continue
        verdict = str(d.get("verdict", "")).strip().lower()
        if verdict not in _VERDICTS:
            continue
        issues_raw = d.get("issues") or []
        if not isinstance(issues_raw, list):
            issues_raw = [str(issues_raw)]
        issues = [str(x) for x in issues_raw if str(x).strip()]
        return CriticResult(
            verdict=verdict, issues=issues, raw_response=raw,
        )

    return CriticResult(
        verdict="error",
        issues=[f"could not parse critic response (len={len(raw)})"],
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------


def critique_view(
    *,
    type_short: str,
    qualified_name: str,
    type_source: str,
    viewed_type: str,
    view_decl: str,
    dep_views: dict[str, str],
    rationale: str = "",
    project: str = "",
    run_dir: Path,
    critic: Optional[CodexCritic] = None,
) -> CriticResult:
    """Run one critic pass; persist artifacts under ``run_dir``."""
    import time

    if critic is None:
        critic = CodexCritic()
    prompt = build_critic_prompt(
        type_short=type_short,
        qualified_name=qualified_name,
        type_source=type_source,
        viewed_type=viewed_type,
        view_decl=view_decl,
        dep_views=dep_views,
        rationale=rationale,
        project=project,
    )

    t0 = time.time()
    try:
        raw = critic.query(prompt, run_dir)
    except RuntimeError as e:
        logger.warning("critic for %s: codex failed (%s)", type_short, e)
        result = CriticResult(
            verdict="error",
            issues=[f"codex invocation failed: {e}"],
            duration_s=time.time() - t0,
        )
        (run_dir / "critique.json").write_text(
            json.dumps(result.to_dict(), indent=2) + "\n"
        )
        return result

    result = parse_critic_response(raw)
    result.duration_s = time.time() - t0
    (run_dir / "critique.json").write_text(
        json.dumps(result.to_dict(), indent=2) + "\n"
    )
    logger.info(
        "critic for %s: %s (%d issues, %.1fs)",
        type_short, result.verdict, len(result.issues), result.duration_s,
    )
    return result


def append_rejected(
    cache_root: Path,
    *,
    type_short: str,
    qualified_name: str,
    issues: list[str],
    viewed_type: str,
    view_decl: str,
    source_hash: str,
) -> None:
    """Record a rejection to ``<cache_root>/_rejected.jsonl``.

    One JSON object per line. Rejections accumulate across runs so the
    user can review them; the file is never pruned automatically.
    """
    path = cache_root / "_rejected.jsonl"
    entry = {
        "type_short": type_short,
        "qualified_name": qualified_name,
        "source_hash": source_hash,
        "viewed_type": viewed_type,
        "view_decl": view_decl,
        "issues": list(issues),
    }
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------


def _run_self_tests() -> int:
    passes = 0
    fails: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passes
        if cond:
            passes += 1
            print(f"  ok    {name}")
        else:
            fails.append(f"{name}: {detail}")
            print(f"  FAIL  {name}  {detail}")

    # Fenced json block
    r = parse_critic_response(
        'some preamble\n```json\n{"verdict":"accept","issues":[]}\n```\n'
    )
    check("fenced accept", r.verdict == "accept" and r.issues == [])

    # Fenced json with issues
    r = parse_critic_response(
        '```json\n{"verdict": "revise", '
        '"issues": ["minor: rationale stale"]}\n```'
    )
    check("fenced revise + issues",
          r.verdict == "revise" and r.issues == ["minor: rationale stale"])

    # No fence, raw object
    r = parse_critic_response('{"verdict":"reject","issues":["lost field x"]}')
    check("raw json reject",
          r.verdict == "reject" and r.issues == ["lost field x"])

    # Multiple fenced blocks, second one valid
    r = parse_critic_response(
        '```\nbad text\n```\n```json\n{"verdict":"accept","issues":[]}\n```'
    )
    check("second fence wins", r.verdict == "accept")

    # Malformed → error
    r = parse_critic_response("the model rambled but never produced json")
    check("malformed → error", r.verdict == "error" and r.issues)

    # Bad verdict → error
    r = parse_critic_response('```json\n{"verdict":"maybe","issues":[]}\n```')
    check("bad verdict → error", r.verdict == "error")

    # Non-list issues coerce to list
    r = parse_critic_response('```json\n{"verdict":"revise","issues":"x"}\n```')
    check("issues coerce", r.verdict == "revise" and r.issues == ["x"])

    # Build prompt contains key markers
    p = build_critic_prompt(
        type_short="Foo",
        qualified_name="crate::m::Foo",
        type_source="pub struct Foo { x: usize }",
        viewed_type="FooView",
        view_decl="impl View for Foo { type V = FooView; }",
        dep_views={"Bar": "L1 → Seq<Bar>"},
        rationale="kept x",
        project="my-proj",
    )
    check("prompt has type src", "pub struct Foo" in p)
    check("prompt has view decl", "impl View for Foo" in p)
    check("prompt has dep", "Bar: L1 → Seq<Bar>" in p)
    check("prompt has project", "my-proj" in p)

    # append_rejected writes a line
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        append_rejected(
            root,
            type_short="Foo", qualified_name="crate::Foo",
            issues=["bad"], viewed_type="V", view_decl="...",
            source_hash="abc",
        )
        append_rejected(
            root,
            type_short="Bar", qualified_name="crate::Bar",
            issues=["worse"], viewed_type="V", view_decl="...",
            source_hash="def",
        )
        lines = (root / "_rejected.jsonl").read_text().splitlines()
        check("rejected jsonl lines", len(lines) == 2)
        d = json.loads(lines[1])
        check("rejected jsonl content",
              d["type_short"] == "Bar" and d["issues"] == ["worse"])

    print(f"\n{passes}/{passes + len(fails)} passed")
    if fails:
        print("FAILED:")
        for f in fails:
            print(" -", f)
        return 1
    return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        sys.exit(_run_self_tests())
    print("usage: python -m spec_determinism.view.critic test")
    sys.exit(2)
