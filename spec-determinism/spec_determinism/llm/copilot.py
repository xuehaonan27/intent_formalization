"""Shared Copilot CLI client used by view/llm.py and codegen/policy_llm.py.

Both modules need to drive ``copilot -p <meta> --allow-all-tools`` with a
prompt file and read back a JSON-fenced response. This module factors
that out so we have one place to handle:

* subprocess invocation + timeout
* stdout / stderr persistence under ``run_dir``
* retry on transient failures (configurable, default 2 retries with
  exponential 1s / 2s back-off)
* a uniform RuntimeError on exhausted retries

The caller composes its own prompt body and is responsible for parsing
the response. We deliberately do not bake the prompt schema into this
module — it's a transport, not a contract.
"""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)


def _decode(maybe_bytes) -> str:
    if maybe_bytes is None:
        return ""
    if isinstance(maybe_bytes, bytes):
        return maybe_bytes.decode(errors="replace")
    return maybe_bytes


@dataclass
class CopilotCLI:
    """Run a single Copilot CLI request and return its raw response.

    Each :meth:`query` call:
      1. Writes ``prompt`` to ``<run_dir>/prompt.md``.
      2. Spawns ``copilot -p "<meta>" --allow-all-tools --allow-all-paths
         --no-color [--model X] [--effort Y]`` (and a "write your reply to
         <run_dir>/response.md" meta-prompt).
      3. Captures stdout / stderr under ``<run_dir>/copilot_{stdout,stderr}.txt``
         (or ``<...>.attempt<N>.txt`` for subsequent retries).
      4. Returns the contents of ``response.md`` if the agent created it.
      5. Otherwise retries up to ``self.retries`` more times with
         exponential back-off, then raises ``RuntimeError``.

    The caller decides how to parse the returned text (typically a single
    ```json fenced block).
    """

    model: str | None = None
    reasoning_effort: str | None = None
    timeout: int = 600
    retries: int = 2

    def query(self, prompt: str, run_dir: Path) -> str:
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "prompt.md"
        response_path = run_dir / "response.md"
        prompt_path.write_text(prompt)
        if response_path.exists():
            response_path.unlink()

        meta = (
            f"Read the full task at {prompt_path} and execute it. "
            f"Write your reply — the single fenced ```json block described "
            f"in that task — to {response_path}. Do not modify any other "
            f"file. Do not print the reply to stdout. After writing the "
            f"file, exit."
        )
        cmd = [
            "copilot", "-p", meta,
            "--allow-all-tools", "--allow-all-paths", "--no-color",
        ]
        if self.model:
            cmd += ["--model", self.model]
        if self.reasoning_effort:
            cmd += ["--effort", self.reasoning_effort]

        last_err = "no attempts"
        for attempt in range(self.retries + 1):
            suffix = "" if attempt == 0 else f".attempt{attempt + 1}"
            stdout_path = run_dir / f"copilot_stdout{suffix}.txt"
            stderr_path = run_dir / f"copilot_stderr{suffix}.txt"
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=self.timeout,
                )
                stdout_path.write_text(proc.stdout or "")
                stderr_path.write_text(proc.stderr or "")
                if response_path.exists():
                    return response_path.read_text()
                last_err = f"rc={proc.returncode}"
            except subprocess.TimeoutExpired as e:
                stdout_path.write_text(_decode(e.stdout))
                stderr_path.write_text(
                    _decode(e.stderr) + f"\n[timeout after {self.timeout}s]"
                )
                last_err = f"timeout after {self.timeout}s"

            if attempt < self.retries:
                wait = 2 ** attempt
                logger.warning(
                    "copilot attempt %d/%d failed for %s (%s); retrying in %ds",
                    attempt + 1, self.retries + 1, run_dir.name,
                    last_err, wait,
                )
                time.sleep(wait)

        raise RuntimeError(
            f"copilot failed after {self.retries + 1} attempts without "
            f"writing {response_path} (last error: {last_err}). "
            f"See attempt logs in {run_dir}."
        )
