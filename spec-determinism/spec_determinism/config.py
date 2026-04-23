"""Corpus config loader. Expands ~ and {nanvix} substitutions."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CrateConfig:
    name: str
    src: str
    spec: str
    proof: str
    extra_type_sources: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    extra_args: list[str] = field(default_factory=list)
    use_build: bool = True
    timeout: int = 180
    functions: list[str] = field(default_factory=list)
    check_overrides: dict[str, str] = field(default_factory=dict)
    verify_module: str | None = None


@dataclass
class CorpusConfig:
    path: Path
    repo_root: Path
    nanvix: str
    verus_path: str
    artifacts_dir: Path
    full_run_path: Path
    crates: dict[str, CrateConfig]


def _expand(s: str, nanvix: str) -> str:
    return os.path.expanduser(s.replace("{nanvix}", nanvix))


def _expand_list(xs: list[str], nanvix: str) -> list[str]:
    return [_expand(x, nanvix) for x in xs]


def load_config(path: str | Path) -> CorpusConfig:
    cfg_path = Path(path).resolve()
    with open(cfg_path, "rb") as f:
        raw = tomllib.load(f)

    nanvix = os.path.expanduser(raw["nanvix"])
    verus_path = _expand(raw.get("verus_path", "{nanvix}/toolchain/verus"), nanvix)

    # Repo root = directory containing the config file's parent (configs/ ->
    # repo root). If config is elsewhere, callers can override via env
    # SPEC_DETERMINISM_ROOT. Fall back to the config's grandparent.
    env_root = os.environ.get("SPEC_DETERMINISM_ROOT")
    if env_root:
        repo_root = Path(env_root).resolve()
    elif cfg_path.parent.name == "configs":
        repo_root = cfg_path.parent.parent
    else:
        repo_root = cfg_path.parent

    def _as_path(p: str) -> Path:
        pp = Path(_expand(p, nanvix))
        return pp if pp.is_absolute() else (repo_root / pp)

    artifacts_dir = _as_path(raw.get("artifacts_dir", "results/artifacts"))
    full_run_path = _as_path(raw.get("full_run_path", "results/full_run.json"))

    crates: dict[str, CrateConfig] = {}
    for name, c in raw.get("crates", {}).items():
        crates[name] = CrateConfig(
            name=name,
            src=_expand(c["src"], nanvix),
            spec=_expand(c["spec"], nanvix),
            proof=_expand(c["proof"], nanvix),
            extra_type_sources=_expand_list(c.get("extra_type_sources", []), nanvix),
            features=list(c.get("features", [])),
            extra_args=_expand_list(c.get("extra_args", []), nanvix),
            use_build=bool(c.get("use_build", True)),
            timeout=int(c.get("timeout", 180)),
            functions=list(c.get("functions", [])),
            check_overrides=dict(c.get("check_overrides", {})),
            verify_module=c.get("verify_module"),
        )

    return CorpusConfig(
        path=cfg_path,
        repo_root=repo_root,
        nanvix=nanvix,
        verus_path=verus_path,
        artifacts_dir=artifacts_dir,
        full_run_path=full_run_path,
        crates=crates,
    )


def default_config_path() -> Path:
    """Default config path: <repo_root>/configs/nanvix.toml."""
    here = Path(__file__).resolve().parent.parent
    return here / "configs" / "nanvix.toml"
