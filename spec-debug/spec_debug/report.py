"""Per-run observation report."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .gap import Witness
from .llm.base import LLMResponse
from .score import Metrics
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


def _fmt_ratio(num: int, den: int) -> str:
    if den == 0:
        return f"{num}/0 (n/a)"
    return f"{num}/{den}"


def write_report(
    run_dir: Path,
    witness: Witness,
    response: LLMResponse,
    patch_text: str,
    verify_report: VerifyReport,
    metrics: Metrics | None = None,
) -> tuple[Path, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    patch_path = run_dir / "patch.spec.rs"
    patch_path.write_text(patch_text)

    data: dict[str, Any] = {
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
    if metrics is not None:
        data["metrics"] = metrics.as_dict()
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
    md_lines.append(f"- response: {len(response.raw)} chars -> `patch.spec.rs`")
    md_lines.append("")
    md_lines.append("## Verify")
    r = verify_report.rerun
    md_lines.append(
        f"- spec-determinism rerun: {'PASS' if r.ok else 'FAIL'} (rc={r.returncode}), "
        f"rounds={r.n_rounds_after}, closed={len(r.closed)}, added={len(r.added)}"
    )
    if verify_report.regen is not None:
        rg = verify_report.regen
        md_lines.append(f"- regen: {'PASS' if rg.ok else 'FAIL'} (rc={rg.returncode})")
    if r.closed:
        md_lines.append("  - closed:")
        md_lines.extend(f"    - `{a}`" for a in r.closed)
    if r.added:
        md_lines.append("  - added:")
        md_lines.extend(f"    - `{a}`" for a in r.added)
    md_lines.append("")

    if metrics is not None:
        gc = metrics.gap_closure
        bp = metrics.bypass
        sf = metrics.structural_fit
        lb = metrics.literal_bleed
        hg = metrics.hard_gates
        md_lines.append("## Metrics")
        md_lines.append("")
        md_lines.append("### Hard gates")
        md_lines.append(f"- **passed**: {'all' if hg.passed else 'FAIL: ' + '; '.join(hg.reject_reasons)}")
        md_lines.append(f"- impl_still_verifies: {hg.impl_still_verifies}")
        md_lines.append(f"- no_new_admissions_in_impl: {hg.no_new_admissions_in_impl}")
        sym_caveat = "" if bp.symbol_table_stable is not None else "  *(unknown - no post-regen snapshot)*"
        eq_caveat = "" if bp.equal_fn_def_stable is not None else "  *(unknown - no post-regen snapshot)*"
        md_lines.append(f"- symbol_table_stable: {hg.symbol_table_stable}{sym_caveat}")
        md_lines.append(f"- equal_fn_def_stable: {hg.equal_fn_def_stable}{eq_caveat}")
        md_lines.append("")
        md_lines.append("### Gap closure (Axis A)")
        md_lines.append(
            f"- **driving_closed_ratio**: {_fmt_ratio(gc.driving_closed, gc.driving_before)} "
            f"(= {gc.driving_closed_ratio})"
        )
        md_lines.append(f"- new_witness_driving: {gc.new_witness_driving} ({gc.new_witness_driving_count} driving in fresh witness)")
        md_lines.append(f"- collateral_closed: {gc.collateral_closed}/{gc.collateral_before}")
        md_lines.append(f"- raw closed/added: {gc.closed_count}/{gc.added_count}")
        md_lines.append(f"- n_rounds: {gc.n_rounds_before} -> {gc.n_rounds_after} (delta {gc.n_rounds_delta:+d})")
        md_lines.append("")
        md_lines.append("### Bypass (Axis C)")
        if bp.new_admissions:
            md_lines.append(f"- new admissions detected ({len(bp.new_admissions)}):")
            md_lines.extend(f"    - `{a}`" for a in bp.new_admissions)
        else:
            md_lines.append("- no new `assume(false)` / `admit()` lines")
        md_lines.append("")
        md_lines.append("### Structural fit (Axis B, observation)")
        md_lines.append(f"- ensures clauses (after / delta): {sf.ensures_clauses_after} / {sf.ensures_clauses_delta:+d}")
        md_lines.append(f"- quantifiers added: {sf.quantifiers_added}")
        helpers_str = f" -- {sf.helper_spec_fns_added_names}" if sf.helper_spec_fns_added_names else ""
        md_lines.append(f"- helper spec_fns added: {sf.helper_spec_fns_added}{helpers_str}")
        md_lines.append("")
        md_lines.append("### Literal bleed (Axis D, observation)")
        md_lines.append(f"- bleed_count: {lb.bleed_count}")
        if lb.bleed_literals:
            md_lines.append(f"- bleed literals: `{lb.bleed_literals}`")
        md_lines.append("")

    if not r.ok:
        md_lines.append("### rerun tail")
        md_lines.append("```")
        md_lines.append(r.stderr_tail)
        md_lines.append("```")
    md_path = run_dir / "report.md"
    md_path.write_text("\n".join(md_lines))
    return json_path, md_path
