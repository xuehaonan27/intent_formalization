"""Cargo workspace type-source discovery.

Given a nanvix/workspace root, parses the root `Cargo.toml`, expands
`[workspace].members` (supporting `*` globs like `src/libs/*`), and returns
all `.rs` files under each member's `src/` directory. The result is used
by `extract.refine_types` as a transitive type-definition index, so the
per-crate `extra_type_sources` list in configs stops having to be hand-
maintained every time a new dependency is added.

Default behaviour is lazy (read files only when called) and cached per
(workspace root) across a single process.
"""
from __future__ import annotations

import logging
import tomllib
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def _discover(workspace_root_str: str) -> tuple[str, ...]:
    """Return absolute paths of every `.rs` file that lives under a Cargo
    workspace member.

    Cached per workspace root (as a string so lru_cache can hash it).
    """
    root = Path(workspace_root_str)
    root_toml = root / "Cargo.toml"
    if not root_toml.exists():
        logger.warning("workspace: no Cargo.toml at %s", root_toml)
        return ()

    data = tomllib.loads(root_toml.read_text())
    ws = data.get("workspace", {})
    members = ws.get("members", [])
    excludes = set(ws.get("exclude", []))

    crate_dirs: list[Path] = []
    for pattern in members:
        if pattern in excludes:
            continue
        if "*" in pattern or "?" in pattern:
            for d in sorted(root.glob(pattern)):
                rel = str(d.relative_to(root))
                if d.is_dir() and rel not in excludes:
                    crate_dirs.append(d)
        else:
            d = root / pattern
            if d.is_dir() and pattern not in excludes:
                crate_dirs.append(d)

    rs_files: list[Path] = []
    for crate in crate_dirs:
        src = crate / "src"
        if src.is_dir():
            rs_files.extend(sorted(src.rglob("*.rs")))
        # Also pick up ad-hoc `.rs` at the crate root (some tooling crates do this)
        for p in sorted(crate.glob("*.rs")):
            if p.is_file():
                rs_files.append(p)

    logger.info(
        "workspace: discovered %d .rs files across %d members under %s",
        len(rs_files), len(crate_dirs), root,
    )
    return tuple(str(p) for p in rs_files)


def discover_workspace_rs_files(workspace_root: Path | str) -> list[Path]:
    """Public API. Returns paths of all .rs files under workspace members."""
    root = Path(workspace_root).resolve()
    return [Path(p) for p in _discover(str(root))]


@lru_cache(maxsize=None)
def read_source(path_str: str) -> str:
    """Read and cache a source file by path. Cached per-process so successive
    artifact generations don't re-read the same files.
    """
    return Path(path_str).read_text()
