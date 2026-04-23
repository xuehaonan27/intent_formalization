"""Copilot CLI LLM client.

Drives the GitHub Copilot CLI (`copilot -p ...`) in non-interactive mode.
We hand Copilot a short meta-prompt that points it at `prompt.md` and
asks it to write the reply to `response.md`, using its built-in file
tools. This avoids having to parse stdout (which includes a changes /
tokens footer), and is robust for large prompts.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .base import LLMResponse, extract_rust_block


@dataclass
class CopilotLLMClient:
    source: str = "copilot-cli"
    model: str | None = None
    reasoning_effort: str | None = None
    timeout: int = 900

    def query(self, prompt: str, run_dir: Path) -> LLMResponse:
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "prompt.md"
        response_path = run_dir / "response.md"
        prompt_path.write_text(prompt)
        # Clear any stale response so we can detect failure-to-write.
        if response_path.exists():
            response_path.unlink()

        meta = (
            f"Read the full task at {prompt_path} and execute it. "
            f"Write your reply — the single fenced ```rust block described "
            f"in that task — to {response_path}. Do not modify any other file. "
            f"Do not print the reply to stdout. After writing the file, exit."
        )
        cmd = ["copilot", "-p", meta, "--allow-all-tools", "--allow-all-paths", "--no-color"]
        if self.model:
            cmd += ["--model", self.model]
        if self.reasoning_effort:
            cmd += ["--effort", self.reasoning_effort]

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self.timeout,
        )
        stdout_path = run_dir / "copilot_stdout.txt"
        stderr_path = run_dir / "copilot_stderr.txt"
        stdout_path.write_text(proc.stdout or "")
        stderr_path.write_text(proc.stderr or "")

        if not response_path.exists():
            raise RuntimeError(
                f"copilot exited rc={proc.returncode} without writing {response_path}. "
                f"See {stdout_path} / {stderr_path}."
            )
        raw = response_path.read_text()
        return LLMResponse(
            raw=raw,
            patch_text=extract_rust_block(raw),
            source=self.source,
        )
