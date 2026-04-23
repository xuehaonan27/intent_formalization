"""LLM client abstraction.

v0 only has a manual (file-based) client; an API-backed client can be
plugged in later without touching the rest of the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class LLMResponse:
    raw: str            # full model output as text
    patch_text: str     # extracted replacement file content (first fenced rust block)
    source: str         # origin tag, e.g. "manual", "copilot-cli"


class LLMClient(Protocol):
    def query(self, prompt: str, run_dir: Path) -> LLMResponse: ...


def extract_rust_block(text: str) -> str:
    """Pull the first fenced ```rust ... ``` block out of a response.

    Falls back to the whole text if no fence is present.
    """
    lines = text.splitlines()
    in_block = False
    buf: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```"):
                lang = stripped.removeprefix("```").strip().lower()
                if lang in ("", "rust", "verus"):
                    in_block = True
            continue
        if stripped.startswith("```"):
            return "\n".join(buf)
        buf.append(line)
    if buf:
        return "\n".join(buf)
    return text
