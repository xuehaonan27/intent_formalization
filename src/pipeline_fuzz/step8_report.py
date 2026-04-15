"""
Step 8 (fuzz): Verdict matrix analysis → findings.json + findings.md

Reads verus_results.json, applies the verdict matrix, detects
requires-violating cases (heuristic), and writes:
  <task_dir>/cases.json      — all cases with verdicts + discard flags
  <task_dir>/findings.json   — only INCORRECTNESS / INCOMPLETENESS rows
  <task_dir>/findings.md     — human-readable summary

Usage:
  python -m src.pipeline_fuzz.step8_report --task-dir <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.pipeline_fuzz.schemas import Case, Finding, compute_verdict


# ---------------------------------------------------------------------------
# Requires-violation heuristic
# ---------------------------------------------------------------------------

def _is_requires_violated(case_dict: dict) -> bool:
    """
    Heuristic: a case violates the requires clause if Verus's failure log
    mentions the requires clause failing. We also mark cases with no pre_assumes
    but a full set of arg_assumes as potentially unconstrained (not discard).

    Real detection requires Verus's structured output; this is a best-effort
    heuristic from the log text.
    """
    log = case_dict.get("verus_log", "") or ""
    lower = log.lower()

    # Verus emits "requires not satisfied" or similar for precondition failures
    requires_patterns = [
        "requires not satisfied",
        "precondition not satisfied",
        "requires clause",
        "pre-condition",
    ]
    return any(p in lower for p in requires_patterns)


# ---------------------------------------------------------------------------
# process_one
# ---------------------------------------------------------------------------

def process_one(task_dir: Path) -> dict:
    """
    Compute verdicts, identify findings, and write report files.

    Reads: verus_results.json
    Writes: cases.json, findings.json, findings.md
    Returns: summary dict
    """
    results_path = task_dir / "verus_results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"verus_results.json not found in {task_dir}")

    raw_results = json.loads(results_path.read_text())

    cases: list[Case] = []
    findings: list[Finding] = []

    # Per-function discard counts (overconstrained-precondition diagnostic)
    discard_counts: dict[str, int] = {}

    for d in raw_results:
        case = Case.from_dict(d)
        # verus_outcome may be stored directly in dict from step7
        if case.verus_outcome is None:
            case.verus_outcome = d.get("verus_outcome")

        # Detect requires-violation
        if _is_requires_violated(d):
            case.requires_violated = True
            discard_counts[case.fn] = discard_counts.get(case.fn, 0) + 1
            case.verdict = None  # discarded
        elif case.oracle is not None and case.verus_outcome is not None:
            case.verdict = compute_verdict(case.oracle, case.verus_outcome)
            if case.verdict in ("INCORRECTNESS", "INCOMPLETENESS"):
                findings.append(Finding.from_case(case))
        else:
            case.verdict = "UNKNOWN"

        cases.append(case)

    # Write cases.json (all cases, annotated)
    cases_with_discards: list[dict] = []
    for c in cases:
        d = c.to_dict()
        cases_with_discards.append(d)

    # Append discard summary per function
    cases_summary = {
        "total": len(cases),
        "labeled": sum(1 for c in cases if c.oracle is not None),
        "discarded_requires_violated": sum(discard_counts.values()),
        "discard_by_fn": discard_counts,
        "verdicts": {
            "OK": sum(1 for c in cases if c.verdict == "OK"),
            "INCORRECTNESS": sum(1 for c in cases if c.verdict == "INCORRECTNESS"),
            "INCOMPLETENESS": sum(1 for c in cases if c.verdict == "INCOMPLETENESS"),
            "UNKNOWN": sum(1 for c in cases if c.verdict == "UNKNOWN"),
            "discarded": sum(1 for c in cases if c.requires_violated),
        },
        "cases": cases_with_discards,
    }
    (task_dir / "cases.json").write_text(json.dumps(cases_summary, indent=2))

    # Write findings.json
    (task_dir / "findings.json").write_text(
        json.dumps([f.to_dict() for f in findings], indent=2)
    )

    # Write findings.md
    _write_findings_md(task_dir, findings, cases_summary)

    return {
        "task": task_dir.name,
        "total_cases": len(cases),
        "findings": len(findings),
        "incorrectness": sum(1 for f in findings if f.verdict == "INCORRECTNESS"),
        "incompleteness": sum(1 for f in findings if f.verdict == "INCOMPLETENESS"),
        "discard_counts": discard_counts,
        "verdicts": cases_summary["verdicts"],
    }


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _write_findings_md(task_dir: Path, findings: list[Finding],
                       summary: dict) -> None:
    v = summary["verdicts"]
    lines = [
        f"# Spec-Fuzz Findings: `{task_dir.name}`",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total cases | {summary['total']} |",
        f"| Oracle labeled | {summary['labeled']} |",
        f"| Discarded (requires violated) | {summary['discarded_requires_violated']} |",
        f"| OK | {v.get('OK', 0)} |",
        f"| INCORRECTNESS | {v.get('INCORRECTNESS', 0)} |",
        f"| INCOMPLETENESS | {v.get('INCOMPLETENESS', 0)} |",
        f"| UNKNOWN / timeout | {v.get('UNKNOWN', 0)} |",
        "",
    ]

    if summary["discard_by_fn"]:
        lines += [
            "## Discard counts by function (requires-violated)",
            "",
            "| Function | Discarded |",
            "|----------|-----------|",
        ]
        for fn, cnt in sorted(summary["discard_by_fn"].items()):
            lines.append(f"| `{fn}` | {cnt} |")
        lines.append("")

    if not findings:
        lines += ["## Findings", "", "_No INCORRECTNESS or INCOMPLETENESS cases found._", ""]
    else:
        lines += ["## Findings", ""]
        for i, f in enumerate(findings, 1):
            lines += [
                f"### Finding {i}: {f.verdict} in `{f.fn}`",
                "",
                f"- **Oracle**: {f.oracle}",
                f"- **Verus**: {f.verus_outcome}",
                f"- **Justification**: {f.oracle_justification or '(none)'}",
                "",
                "**Case:**",
            ]
            if f.pre_assumes:
                lines.append("Pre-state:")
                for a in f.pre_assumes:
                    if not a.startswith("//"):
                        lines.append(f"  - `{a}`")
            if f.arg_assumes:
                lines.append("Args:")
                for a in f.arg_assumes:
                    lines.append(f"  - `{a}`")
            if f.result_assume:
                lines.append(f"Result: `{f.result_assume}`")
            if f.post_assumes:
                lines.append("Post-state:")
                for a in f.post_assumes:
                    lines.append(f"  - `{a}`")
            lines.append("")

    (task_dir / "findings.md").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 8 (fuzz): Verdict matrix → findings.json + findings.md"
    )
    parser.add_argument("--task-dir", type=str, required=True)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).resolve()
    print(f"[step8] Generating report for {task_dir.name}")

    try:
        summary = process_one(task_dir)
    except FileNotFoundError as e:
        print(f"[step8] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    v = summary["verdicts"]
    print(f"[step8] Total cases: {summary['total_cases']}")
    print(f"[step8] Findings: {summary['findings']} "
          f"(INCORRECTNESS={summary['incorrectness']}, "
          f"INCOMPLETENESS={summary['incompleteness']})")
    print(f"[step8] Verdicts: OK={v.get('OK',0)}  UNKNOWN={v.get('UNKNOWN',0)}  "
          f"discarded={v.get('discarded',0)}")
    print(f"[step8] Wrote findings.json + findings.md → {task_dir}/")


if __name__ == "__main__":
    main()
