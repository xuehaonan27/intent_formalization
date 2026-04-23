"""Whole-file patch apply / revert.

v0 scope: the LLM returns the full replacement `.spec.rs`. We back up the
original, overwrite, and let the verifier run. The returned Patch is a
context-manager-style record; callers must call revert explicitly (or use
apply_and_revert).
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Patch:
    target: Path
    original_text: str
    new_text: str

    def revert(self) -> None:
        self.target.write_text(self.original_text)


def apply_patch(target: Path, new_text: str) -> Patch:
    original = target.read_text()
    target.write_text(new_text)
    return Patch(target=target, original_text=original, new_text=new_text)


@contextmanager
def apply_and_revert(target: Path, new_text: str):
    patch = apply_patch(target, new_text)
    try:
        yield patch
    finally:
        patch.revert()
