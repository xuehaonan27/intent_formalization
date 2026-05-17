"""Agentic Copilot CLI driver for closing z3-unknown determinism checks.

Single-shot mode (the original :func:`run_llm_proof_loop`) spawns one
``copilot -p ...`` process per *attempt* and uses the Python side to
iterate. The model never sees Verus's actual error during its own
reasoning — it only ever sees a stderr tail that the Python wrapper
glues into the *next* prompt as text.

This module implements **agentic mode**: one ``copilot -p ...
--allow-all-tools`` session per *target*. The CLI is told to edit a
file in a workdir, run ``verus`` itself, read the error, and iterate
*inside the same model session*. We only re-verify Verus ourselves
at the end as a soundness check.

The result shape (:class:`ProofResult`) is the same as single-shot so
the rest of the pipeline (``single_file.py`` → ``verusage_run.py``)
doesn't care which mode produced it. The cache layer's namespace is
extended with a per-mode subdir so the two modes can co-exist for
A/B comparison without overwriting each other.

Threat model: same as single-shot. The agentic prompt forbids
``assume``/``admit``/``assume_specification`` and our final
:func:`scan_proof_block` re-applies the regex sandbox to the inserted
proof block. The CLI is given ``--allow-all-tools`` so it can run
``verus`` and edit the workdir, but the *prompt* (and post-hoc file
diff) is the trust boundary: the Verus re-run we do after the session
ends is the only soundness check.

Self-test (``python -m spec_determinism.llm_proof.agentic``) PASS.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from spec_determinism.extract.types import DetCheckSpec, FunctionSpec
from spec_determinism.schema_search import enumerate_schemas, render_guarded_template

logger = logging.getLogger(__name__)


# Markers that delimit the agent's editable region inside det.rs. These
# match the markers render_guarded_template emits when proof_prelude is
# non-empty, so the post-session diff is a single regex away.
_AGENT_REGION_BEGIN = "// === LLM PROOF BLOCK ==="
_AGENT_REGION_END = "// === END LLM PROOF BLOCK ==="
_INITIAL_PLACEHOLDER = (
    "// TODO(agent): insert proof statements here. Replace this line.\n"
    "    // You may use assert / assert ... by { ... } / lemma calls.\n"
    "    // FORBIDDEN: assume(), admit(), assume_specification, external_body.\n"
    "    // The line markers above and below MUST be preserved verbatim."
)


# ---------------------------------------------------------------------------
# Result dataclasses (kept lightweight; the prover wraps these into the
# existing ProofResult/ProofAttempt shape so downstream tooling is
# mode-agnostic).
# ---------------------------------------------------------------------------


@dataclass
class AgenticSession:
    """One Copilot CLI agentic session. The CLI ran or it didn't."""

    started_at: str = ""
    finished_at: str = ""
    cli_returncode: Optional[int] = None
    cli_stderr_tail: str = ""
    cli_timed_out: bool = False
    cli_ms: int = 0
    # What the agent itself reported (if it wrote result.json before exit).
    agent_status: str = ""           # one of "pass" | "fail" | "give_up" | ""
    agent_iterations: Optional[int] = None
    agent_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cli_returncode": self.cli_returncode,
            "cli_stderr_tail": self.cli_stderr_tail,
            "cli_timed_out": self.cli_timed_out,
            "cli_ms": self.cli_ms,
            "agent_status": self.agent_status,
            "agent_iterations": self.agent_iterations,
            "agent_notes": self.agent_notes,
        }


@dataclass
class AgenticOutcome:
    """Soundness-checked outcome of one agentic session.

    The :class:`AgenticSession` is what the CLI did. This class is what
    *our* re-verification says about the result — the trust boundary.
    """

    final_proof_block: str = ""
    verus_returncode: Optional[int] = None
    verus_stderr_tail: str = ""
    verus_ms: int = 0
    sandbox_violations: list[dict] = field(default_factory=list)
    status: str = "init"   # see _STATUSES below
    session: AgenticSession = field(default_factory=AgenticSession)

    def to_dict(self) -> dict:
        return {
            "final_proof_block": self.final_proof_block,
            "verus_returncode": self.verus_returncode,
            "verus_stderr_tail": self.verus_stderr_tail,
            "verus_ms": self.verus_ms,
            "sandbox_violations": self.sandbox_violations,
            "status": self.status,
            "session": self.session.to_dict(),
        }


# Possible final status values:
_STATUSES = (
    "init",
    "cli_failure",        # copilot subprocess crashed / hung
    "cli_timeout",        # CLI did not finish within budget
    "no_diff",            # session ended but the agent never edited det.rs
    "sandbox_reject",     # agent's final proof contained a forbidden construct
    "verus_pass",         # we re-ran Verus, it accepted with the final proof
    "verus_fail",         # we re-ran Verus, it rejected the final proof
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_skeleton(det_spec: DetCheckSpec) -> str:
    """Build the full synthetic .rs the agent will edit.

    Layout (same as single-shot's :func:`_render_det_body_with_proof`):
      * ``det_spec.equal_fn_def`` (the equality predicate)
      * ``render_guarded_template(...)`` with an empty placeholder where
        the agent should insert its proof.
    """
    schemas = enumerate_schemas(det_spec)
    inner = render_guarded_template(
        det_spec, schemas, proof_prelude=_INITIAL_PLACEHOLDER,
    )
    return det_spec.equal_fn_def + "\n\n" + inner


def _extract_proof_block(rs_text: str) -> Optional[str]:
    """Return the text between the agent-region markers, or None.

    Whitespace inside the block is preserved verbatim; the markers
    themselves are stripped. Returns None if either marker is missing
    (e.g. the agent deleted them).
    """
    pat = re.compile(
        r"//\s*===\s*LLM PROOF BLOCK\s*===\s*\n(.*?)//\s*===\s*END LLM PROOF BLOCK\s*===",
        re.DOTALL,
    )
    m = pat.search(rs_text)
    if not m:
        return None
    return m.group(1).rstrip("\n")


def _block_is_placeholder(block: str) -> bool:
    """True when the agent never replaced the initial TODO."""
    return "TODO(agent): insert proof statements here" in block


def _build_prompt(
    *,
    det_spec: DetCheckSpec,
    fn_spec: Optional[FunctionSpec],
    source: str,
    workdir: Path,
    det_rs: Path,
    result_json: Path,
    verus_path: str,
    timeout_min: int,
    prior_verus_tail: Optional[str],
    source_project_root: Optional[Path] = None,
    source_file_path: Optional[Path] = None,
) -> str:
    """Compose the single mega-prompt that drives the agentic session."""
    fn_ctx = ""
    if fn_spec is not None and getattr(fn_spec, "source", ""):
        fn_ctx = (
            "\n## Function under analysis (read-only reference)\n\n"
            "```rust\n"
            f"{fn_spec.source.rstrip()}\n"
            "```\n"
        )
    elif source:
        fn_ctx = (
            "\n## Source file (full text; the relevant fn is "
            f"`{det_spec.function}`)\n\n"
            "```rust\n"
            f"{source.rstrip()}\n"
            "```\n"
        )

    root_section = ""
    if source_project_root is not None:
        sfp = (
            f"\nFile containing this function: `{source_file_path}`\n"
            if source_file_path is not None
            else ""
        )
        root_section = (
            "\n## Source-project root (read-only; grep here for missing types)\n\n"
            f"```\n{source_project_root}\n```\n"
            f"{sfp}\n"
            "The synthetic `det.rs` in the workdir is a **stub** — it lacks "
            "imports and most type/struct/enum/impl/trait definitions. "
            "**The proof block you write will be re-injected back into the "
            "REAL source file** above and re-verified by us as the final "
            "soundness check, so:\n\n"
            "* **Do NOT invent struct fields, enum variants, or lemma names.** "
            "If your proof references `r.id.data`, that field must actually "
            "exist on the real type — otherwise the re-verify will fail with "
            "`E0609: no field …`.\n"
            "* When you don't know how a type is defined, `grep -rn` the "
            "project root above. Type defs are often in sibling files. "
            "Example:\n"
            "  ```\n"
            f"  grep -rn 'pub struct EndPoint' {source_project_root}\n"
            f"  grep -rn 'pub enum CMessage' {source_project_root}\n"
            f"  grep -rn 'fn view\\b' {source_project_root} | head -20\n"
            "  ```\n"
            "* Reason from the **real** types, not the synthetic stub.\n"
        )

    prior_section = ""
    if prior_verus_tail:
        prior_section = (
            "\n## Prior single-shot Verus error (for context only)\n\n"
            "```\n"
            f"{prior_verus_tail.rstrip()[-2000:]}\n"
            "```\n"
            "The above proof attempt is **NOT** present in the workdir; "
            "you are starting fresh. Use this only as a hint about which "
            "obligations Verus had trouble with.\n"
        )

    return f"""\
You are an autonomous Verus proof engineer. Your task is to write
proof annotations that close a synthetic determinism check.

## Workdir
```
{workdir}
├── det.rs            # ← the file you EDIT IN PLACE
└── logs/             # ← verus puts its logs here when invoked
```

`det.rs` contains:
1. A definition of `{det_spec.equal_fn_name}(...)` (the equality
   predicate for the deterministic result).
2. The synthetic `proof fn det_{det_spec.function}_proof(...)` whose
   body has a placeholder region marked

       // === LLM PROOF BLOCK ===
       // TODO(agent): insert proof statements here. Replace this line.
       // === END LLM PROOF BLOCK ===

   You must replace the TODO line(s) with **Verus proof statements**
   (assertions, lemma calls, case splits, …) that let Verus discharge
   the postcondition `{det_spec.equal_fn_name}(r1, r2)`.

## Goal
Make `{verus_path}/verus {det_rs}` exit 0. Run that command yourself
via bash to test. Read its stderr. Iterate.

## Workflow
1. `cat {det_rs}` — understand the obligations.
2. Edit `{det_rs}` (in place — preserve the marker comments verbatim;
   they delimit the region we extract afterwards).
3. Run: `{verus_path}/verus {det_rs} --log-all --log-dir {workdir}/logs`
   * exit 0  → success, you're done
   * exit ≠0 → read stderr, refine, go to step 2
4. When done (pass OR you've given up after honest effort), write
   `{result_json}` with this exact JSON shape and then exit:

   ```json
   {{
     "status": "pass" | "fail" | "give_up",
     "iterations": <integer count of verus runs you did>,
     "notes": "<short free-form summary of what you tried>"
   }}
   ```

## Hard constraints
* Do **not** modify any file outside the workdir.
* Do **not** introduce `assume(...)`, `admit()`, `assume_specification(...)`,
  `unimplemented!()`, `unreachable!()`, or `#[verifier::external_body]`.
  These are axioms that bypass Verus; we will reject the final proof
  via a static sandbox scan if any appears in the inserted region.
* Do **not** introduce new `fn` / `spec fn` / `proof fn` / `impl` /
  `trait` items inside the proof body. Only statements.
* Do **not** delete or rename the marker comments
  `// === LLM PROOF BLOCK ===` / `// === END LLM PROOF BLOCK ===`.
* Time budget: **{timeout_min} minutes** for this whole session.
  Plan accordingly; if you've spent ~80% of the budget without
  closing it, write a `give_up` result and exit so we can record
  the attempt.

{root_section}{fn_ctx}{prior_section}
## Begin
Start now. Don't print plans or commentary to stdout — operate by
editing the file and running verus. Exit cleanly when done.
"""


def _run_copilot_session(
    *,
    prompt: str,
    timeout_s: int,
    cwd: Path,
    log_dir: Path,
) -> AgenticSession:
    """Spawn one ``copilot -p PROMPT --allow-all-tools --allow-all-paths``.

    We pass the prompt directly (not via a file) so the agent's
    instructions are always pinned to the exact bytes we control. The
    transcript that the CLI itself writes goes to ``stderr`` / ``stdout``,
    which we capture under ``log_dir/cli.stdout`` and ``log_dir/cli.stderr``.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    session = AgenticSession()
    session.started_at = _utc_now()

    cmd = [
        "copilot",
        "-p", prompt,
        "--allow-all-tools",
        "--allow-all-paths",
        "--no-color",
    ]
    t0 = time.monotonic()
    try:
        p = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout_s,
        )
        session.cli_returncode = p.returncode
        (log_dir / "cli.stdout").write_text(p.stdout or "")
        (log_dir / "cli.stderr").write_text(p.stderr or "")
        session.cli_stderr_tail = (p.stderr or "")[-2000:]
    except subprocess.TimeoutExpired as e:
        session.cli_timed_out = True
        session.cli_returncode = -1
        (log_dir / "cli.stdout").write_text(
            (e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))
        )
        (log_dir / "cli.stderr").write_text(
            (e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or ""))
            + f"\n[copilot CLI timeout after {timeout_s}s]"
        )
        session.cli_stderr_tail = f"copilot CLI timeout after {timeout_s}s"
    except FileNotFoundError as e:
        session.cli_returncode = -1
        session.cli_stderr_tail = f"copilot CLI not found: {e}"
        (log_dir / "cli.stderr").write_text(session.cli_stderr_tail)
    finally:
        session.cli_ms = int((time.monotonic() - t0) * 1000)
        session.finished_at = _utc_now()

    return session


def _read_agent_result(result_json: Path) -> dict:
    """Best-effort read of the agent's self-report. Empty dict on failure."""
    if not result_json.exists():
        return {}
    try:
        return json.loads(result_json.read_text())
    except Exception as e:
        logger.warning("agentic: failed to parse %s: %s", result_json, e)
        return {}


def _utc_now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def run_agentic_session(
    *,
    det_spec: DetCheckSpec,
    fn_spec: Optional[FunctionSpec],
    source: str,
    verus_path: str,
    work_root: Path,
    session_timeout: int = 1800,
    verus_timeout: int = 180,
    prior_verus_tail: Optional[str] = None,
    sandbox_scan,  # callable: (proof_block: str) -> list[SandboxViolation]
    file_stem: str = "det_verify",
    source_project_root: Optional[Path] = None,
    source_file_path: Optional[Path] = None,
) -> AgenticOutcome:
    """Run a single Copilot-CLI agentic session against a synthetic det.rs.

    Parameters
    ----------
    det_spec, fn_spec, source: same payload as ``single_file.py`` /
        :func:`run_llm_proof_loop`.
    verus_path: directory containing the ``verus`` binary (we pass this
        to the agent so it can invoke verus itself).
    work_root: a per-target directory where we write ``det.rs``, the
        agent's ``result.json``, and CLI logs. Caller is responsible for
        making sure it's writeable and dedicated to this target.
    session_timeout: hard wall-clock cap on the Copilot CLI session.
    verus_timeout: timeout for our post-session re-verification.
    prior_verus_tail: optional stderr tail from a previous single-shot
        attempt, surfaced to the agent as background.
    sandbox_scan: callable that takes a proof block string and returns
        a list of :class:`SandboxViolation`. Injected to avoid a
        circular import.

    Returns
    -------
    :class:`AgenticOutcome` whose ``status`` is one of:
        - ``verus_pass``: agent closed it, we re-verified
        - ``verus_fail``: agent's proof did not survive Verus
        - ``sandbox_reject``: agent emitted a forbidden construct
        - ``no_diff``: agent never edited det.rs
        - ``cli_timeout`` / ``cli_failure``
    """
    work_root.mkdir(parents=True, exist_ok=True)
    det_rs = work_root / "det.rs"
    result_json = work_root / "result.json"
    log_dir = work_root / "agentic"

    # 1. Write the initial skeleton (atomic to avoid mid-write reads).
    skeleton = _render_skeleton(det_spec)
    tmp = det_rs.with_suffix(det_rs.suffix + ".tmp")
    tmp.write_text(skeleton)
    os.replace(tmp, det_rs)
    initial_block = _extract_proof_block(skeleton) or ""

    # 2. Build the prompt + run the CLI session.
    timeout_min = max(1, session_timeout // 60)
    prompt = _build_prompt(
        det_spec=det_spec, fn_spec=fn_spec, source=source,
        workdir=work_root, det_rs=det_rs, result_json=result_json,
        verus_path=verus_path, timeout_min=timeout_min,
        prior_verus_tail=prior_verus_tail,
        source_project_root=source_project_root,
        source_file_path=source_file_path,
    )
    (log_dir / "prompt.md").parent.mkdir(parents=True, exist_ok=True)
    (log_dir / "prompt.md").write_text(prompt)

    session = _run_copilot_session(
        prompt=prompt, timeout_s=session_timeout,
        cwd=work_root, log_dir=log_dir,
    )

    # 3. Parse the agent's self-report (best-effort).
    agent_report = _read_agent_result(result_json)
    session.agent_status = str(agent_report.get("status", "")).lower()
    iters = agent_report.get("iterations")
    if isinstance(iters, int):
        session.agent_iterations = iters
    session.agent_notes = str(agent_report.get("notes", ""))[:1000]

    outcome = AgenticOutcome(session=session)

    # 4. Did the CLI run at all? Did it touch det.rs?
    if session.cli_timed_out:
        outcome.status = "cli_timeout"
    elif session.cli_returncode is None or session.cli_returncode < 0:
        outcome.status = "cli_failure"

    final_text = det_rs.read_text() if det_rs.exists() else ""
    block = _extract_proof_block(final_text)
    if block is None or _block_is_placeholder(block):
        outcome.final_proof_block = ""
        if outcome.status == "init":
            outcome.status = "no_diff"
    else:
        outcome.final_proof_block = block.strip()

    # Run sandbox scan on the agent's proof block.
    if outcome.final_proof_block:
        violations = sandbox_scan(outcome.final_proof_block)
        if violations:
            outcome.sandbox_violations = [
                v.__dict__ if hasattr(v, "__dict__") else dict(v)
                for v in violations
            ]
            outcome.status = "sandbox_reject"
            return outcome

    # 6. Re-run Verus ourselves as the final soundness check.
    #
    # IMPORTANT: We inject the proof_block back into the ORIGINAL source
    # (not the agent's standalone det.rs), exactly like single-shot's
    # cache-verify path does. This way the soundness model is identical
    # between the two modes:
    #
    #   * The trust delta is exactly `proof_block` (one Verus statement
    #     block prepended to the synthetic proof fn body).
    #   * Everything else — the original `verus! { ... }` wrapper, the
    #     real fn body, the existing imports — comes from the source.
    #
    # If we instead trusted the agent's edited det.rs (which it may have
    # restructured with its own type stubs, weakened postconditions,
    # etc.), the regex sandbox alone wouldn't catch axiom-style tricks
    # outside the marker region. Injecting forces the agent's only
    # actual contribution back through Verus.
    if outcome.status == "init":
        # Lazy imports — avoid circular at module load.
        from .prover import (
            _render_det_body_with_proof, _inject_into_source,
        )
        code = _render_det_body_with_proof(det_spec, outcome.final_proof_block)
        injected_text = _inject_into_source(source, code)
        verify_dir = work_root / "verify"
        verify_dir.mkdir(exist_ok=True)
        verify_rs = verify_dir / f"{file_stem}.rs"
        verify_rs.write_text(injected_text)
        verus_log_dir = verify_dir / "verus_logs"
        verus_log_dir.mkdir(exist_ok=True)
        rc, tail, ms = _run_verus(
            verify_rs, verus_path, verus_log_dir, timeout=verus_timeout,
        )
        outcome.verus_returncode = rc
        outcome.verus_stderr_tail = tail
        outcome.verus_ms = ms
        outcome.status = "verus_pass" if rc == 0 else "verus_fail"

    return outcome


def _run_verus(
    rs_path: Path,
    verus_path: str,
    log_dir: Path,
    *,
    timeout: int,
) -> tuple[int, str, int]:
    """Same shape as prover._run_verus (duplicated to avoid cyclic import)."""
    verus_bin = Path(verus_path) / "verus"
    env = os.environ.copy()
    env["PATH"] = verus_path + ":" + env.get("PATH", "")
    env["RUSTC_BOOTSTRAP"] = "1"
    cmd = [
        str(verus_bin), str(rs_path),
        "--log-all", "--log-dir", str(log_dir),
    ]
    t0 = time.monotonic()
    try:
        p = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=timeout,
        )
        return (
            p.returncode,
            (p.stdout + "\n" + p.stderr)[-4000:],
            int((time.monotonic() - t0) * 1000),
        )
    except subprocess.TimeoutExpired as e:
        tail = ((e.stderr or "") + f"\n[verus timeout after {timeout}s]")[-4000:]
        return -1, tail, int((time.monotonic() - t0) * 1000)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _self_test() -> bool:
    """Round-trip the marker extraction logic without needing a full DetCheckSpec."""

    # Synthetic .rs roughly the shape render_guarded_template produces.
    skeleton = (
        "fn body { ... }\n"
        "    // === LLM PROOF BLOCK ===\n"
        f"    {_INITIAL_PLACEHOLDER}\n"
        "    // === END LLM PROOF BLOCK ===\n"
        "}\n"
    )
    assert _AGENT_REGION_BEGIN in skeleton, "begin marker missing"
    assert _AGENT_REGION_END in skeleton, "end marker missing"

    block = _extract_proof_block(skeleton)
    assert block is not None, "could not extract initial block"
    assert _block_is_placeholder(block), "initial block should be placeholder"

    # Simulate the agent replacing the placeholder.
    new_rs = skeleton.replace(
        _INITIAL_PLACEHOLDER,
        "assert(r1 == r2);  // pretend proof",
    )
    block2 = _extract_proof_block(new_rs)
    assert block2 is not None
    assert "assert(r1 == r2)" in block2
    assert not _block_is_placeholder(block2)

    # Simulate the agent deleting the markers.
    busted = skeleton.replace(_AGENT_REGION_END, "// agent broke marker")
    assert _extract_proof_block(busted) is None

    # The prompt builder shouldn't crash with no fn_spec / no source.
    class _FakeSpec:
        function = "demo"
        equal_fn_name = "det_demo_equal"
    fake = _FakeSpec()
    p = _build_prompt(
        det_spec=fake, fn_spec=None, source="",
        workdir=Path("/tmp/wd"), det_rs=Path("/tmp/wd/det.rs"),
        result_json=Path("/tmp/wd/result.json"),
        verus_path="/opt/verus", timeout_min=30,
        prior_verus_tail=None,
    )
    assert "det.rs" in p and "verus" in p and "agentic" not in p.lower()[:200], "prompt looks wrong"
    assert _AGENT_REGION_BEGIN in p and _AGENT_REGION_END in p

    print("agentic self-test: PASS")
    return True


if __name__ == "__main__":  # pragma: no cover
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ok = _self_test()
    raise SystemExit(0 if ok else 1)
