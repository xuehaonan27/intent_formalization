"""Manual (file-based) LLM client.

Writes the prompt to `<run_dir>/prompt.md`, prints instructions, and waits
for `<run_dir>/response.md` to appear. Workflow: user pastes the prompt
into GitHub Copilot CLI (or wherever), saves the reply to response.md,
then hits Enter.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from .base import LLMResponse, extract_rust_block


class ManualLLMClient:
    source = "manual"

    def __init__(self, poll_seconds: float = 1.0) -> None:
        self.poll_seconds = poll_seconds

    def query(self, prompt: str, run_dir: Path) -> LLMResponse:
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "prompt.md"
        response_path = run_dir / "response.md"
        prompt_path.write_text(prompt)

        print(f"[manual-llm] Prompt written to: {prompt_path}")
        print(f"[manual-llm] Paste the LLM reply (full replacement spec in a ```rust block)")
        print(f"[manual-llm] into:              {response_path}")
        print(f"[manual-llm] Then press <Enter> to continue (or Ctrl-C to abort).")
        try:
            input()
        except EOFError:
            # Non-interactive: block-poll for response file.
            while not response_path.exists():
                time.sleep(self.poll_seconds)

        if not response_path.exists():
            print(f"[manual-llm] {response_path} not found. Waiting ...", file=sys.stderr)
            while not response_path.exists():
                time.sleep(self.poll_seconds)

        raw = response_path.read_text()
        return LLMResponse(
            raw=raw,
            patch_text=extract_rust_block(raw),
            source=self.source,
        )
