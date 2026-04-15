"""
Step 1 (fuzz): Extract executable functions from a source file.

Thin wrapper around src/pipeline/step1_extract — re-exports its public API
and adds a standalone CLI that writes exec_functions.json into a task dir.

Note: The upstream step1_extract.py depends on tree_sitter (verus_parser).
All calls to the upstream module are done lazily inside functions so that
importing this module alone does not crash if tree_sitter is unavailable.

Usage:
  python -m src.pipeline_fuzz.step1_extract --task-dir <path>
  python -m src.pipeline_fuzz.step1_extract --source <file.rs> --task-dir <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_path() -> None:
    """Ensure src and src/utils are on sys.path for legacy imports."""
    src_root = Path(__file__).resolve().parents[2]
    for p in [str(src_root / "src" / "utils"), str(src_root / "src")]:
        if p not in sys.path:
            sys.path.insert(0, p)


def extract_fn_name(decl_node) -> str:
    """Re-export of pipeline.step1_extract.extract_fn_name (lazy)."""
    _ensure_path()
    from src.pipeline.step1_extract import extract_fn_name as _impl
    return _impl(decl_node)


def strip_body(decl_node) -> str:
    """Re-export of pipeline.step1_extract.strip_body (lazy)."""
    _ensure_path()
    from src.pipeline.step1_extract import strip_body as _impl
    return _impl(decl_node)


def extract_from_file(fpath: Path) -> dict | None:
    """Re-export of pipeline.step1_extract.extract_from_file (lazy)."""
    _ensure_path()
    from src.pipeline.step1_extract import extract_from_file as _impl
    return _impl(fpath)


def task_name_for(source_path: Path) -> str:
    """Re-export of pipeline.step1_extract.task_name_for (lazy)."""
    _ensure_path()
    from src.pipeline.step1_extract import task_name_for as _impl
    return _impl(source_path)


def process_one(source_path: Path, task_dir: Path) -> dict:
    """
    Extract exec functions from *source_path* and write exec_functions.json
    + original.rs into *task_dir*.

    Returns the entry dict (same shape as pipeline step1_extract.extract_from_file).
    Raises ValueError if no exec functions are found.
    """
    entry = extract_from_file(source_path)
    if not entry:
        raise ValueError(f"No exec functions found in {source_path}")

    task_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    shutil.copy2(source_path, task_dir / "original.rs")

    # Write exec_functions.json (list form, same as pipeline convention)
    (task_dir / "exec_functions.json").write_text(
        json.dumps(entry["exec_functions"], indent=2)
    )

    return entry


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 1 (fuzz): Extract exec functions from a Rust source file"
    )
    parser.add_argument("--source", type=str, required=True, help="Path to .rs source file")
    parser.add_argument("--task-dir", type=str, required=True, help="Task directory to write outputs")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    task_dir = Path(args.task_dir).resolve()

    print(f"[step1] Extracting from {source}")
    try:
        entry = process_one(source, task_dir)
    except (ValueError, Exception) as e:
        print(f"[step1] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    fns = [f["name"] for f in entry["exec_functions"]]
    print(f"[step1] Found {len(fns)} exec functions: {fns}")
    print(f"[step1] Wrote exec_functions.json → {task_dir / 'exec_functions.json'}")


if __name__ == "__main__":
    main()
