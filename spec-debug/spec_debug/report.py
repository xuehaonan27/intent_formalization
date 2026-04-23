"""Per-run observation report."""
from __future__ import annotations

import dataclasses
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .gap import Witness
from .llm.base import LLMResponse
from .verify import VerifyReport


def _jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    return obj


def write_report(
    run_dir: Path,
    witness: Witness,
    response: LLMResponse,
    patch_text: str,
    verify_report: VerifyReport,
) -> tuple[Path, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    patch_path = run_dir / "patch.spec.rs"
    patch_path.write_text(patch_text)

    data = {
        "function": witness.qualified_name,
        "before": {
            "assumes": witness.assumes,
            "n_rounds": witness.n_rounds,
            "n_schemas": witness.n_schemas,
            "status": witness.status,
        },
        "llm": {"source": response.source, "raw_len": len(response.raw)},
        "verify": _jsonable(verify_report),
    }
    json_path = run_dir / "report.json"
    json_path.write_text(json.dumps(data, indent=2))

    md_lines: list[str] = []
    md_lines.append(f"# spec-debug report: {witness.qualified_name}")
    md_lines.append("")
    md_lines.append("## Witness (before)")
    md_lines.append(f"- rounds: {witness.n_rounds}, schemas: {witness.n_schemas}, status: {witness.status}")
    md_lines.append("")
    md_lines.append("```text")
    md_lines.extend(witness.assumes or ["(none)"])
    md_lines.append("```")
    md_lines.append("")
    md_lines.append(f"## LLM ({response.source})")
    md_lines.append(f"- response: {len(response.raw)} chars → `patch.spec.rs`")
    md_lines.append("")
    md_lines.append("## Verify")
    r = verify_report.rerun
    md_lines.append(
        f"- spec-determinism rerun: {'PASS' if r.ok else 'FAIL'} (rc={r.returncode}), "
        f"rounds={r.n_rounds_after}, closed={len(r.closed)}, added={len(r.added)}"
    )
    if r.closed:
        md_lines.append("  - closed:")
        md_lines.extend(f"    - `{a}`" for a in r.closed)
    if r.added:
        md_lines.append("  - added:")
        md_lines.extend(f"    - `{a}`" for a in r.added)
    md_lines.append("")
    if not r.ok:
        md_lines.append("### rerun tail")
        md_lines.append("```")
        md_lines.append(r.stderr_tail)
        md_lines.append("```")
    md_path = run_dir / "report.md"
    md_path.write_text("\n".join(md_lines))
    return json_path, md_path
