"""spec-debug config loader. Delegates the corpus parts to spec-determinism."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from spec_determinism.config import CorpusConfig, load_config as _load_corpus


@dataclass
class DebugConfig:
    path: Path
    repo_root: Path
    runs_dir: Path
    corpus: CorpusConfig


def _expand(s: str) -> str:
    return os.path.expanduser(s)


def load_config(path: str | Path) -> DebugConfig:
    cfg_path = Path(path).resolve()
    with open(cfg_path, "rb") as f:
        raw = tomllib.load(f)

    if cfg_path.parent.name == "configs":
        repo_root = cfg_path.parent.parent
    else:
        repo_root = cfg_path.parent

    corpus_cfg_path = _expand(raw["spec_determinism_config"])
    corpus = _load_corpus(corpus_cfg_path)

    sd = raw.get("spec_debug", {})
    runs_dir = Path(_expand(sd.get("runs_dir", "runs")))
    if not runs_dir.is_absolute():
        runs_dir = repo_root / runs_dir

    return DebugConfig(
        path=cfg_path,
        repo_root=repo_root,
        runs_dir=runs_dir,
        corpus=corpus,
    )


def default_config_path() -> Path:
    here = Path(__file__).resolve().parent.parent
    return here / "configs" / "nanvix.toml"
