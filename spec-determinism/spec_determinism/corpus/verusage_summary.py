"""Aggregate verusage batch results into a single summary.

Usage:
    python -m spec_determinism.corpus.verusage_summary \\
        --results results-verusage \\
        --out results-verusage/SUMMARY.md

Reads every ``results-verusage/<proj>/full_run.json`` and produces a
Markdown report with:
  * per-project status breakdown table
  * per-project witness-bearing target listing
  * per-status failure-mode samples (first N stderr tails) so the
    most common breakages surface without a manual grep
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from spec_determinism.classify import (
    BUCKET_INCONCLUSIVE,
    BUCKET_PROVED,
    BUCKET_UNKNOWN_KIND,
    BUCKET_WITNESS,
    OK_BUCKETS,
    classify_ok,
)


def load_per_project(results_root: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for proj_dir in sorted(results_root.iterdir()):
        if not proj_dir.is_dir():
            continue
        fr = proj_dir / "full_run.json"
        if not fr.exists():
            continue
        try:
            out[proj_dir.name] = json.loads(fr.read_text())
        except Exception as e:
            out[proj_dir.name] = [{"status": "load_error", "error": str(e)}]
    return out


def render(per_project: dict[str, list[dict]]) -> str:
    lines: list[str] = []
    lines.append("# verusage spec-determinism — batch summary")
    lines.append("")
    lines.append("> `ok` results are classified by the **R0** z3 verdict (initial "
                 "determinism check before any schema narrowing):")
    lines.append(">")
    lines.append("> * **`ok_proved`** — R0 = `unsat` → function is provably deterministic.")
    lines.append("> * **`ok_witness`** — R0 = `sat` → z3 produced a real "
                 "nondeterminism counterexample.")
    lines.append("> * **`ok_inconclusive`** — R0 = `unknown` (or legacy run without "
                 "`r0_z3`) → z3 surrendered; assumes from narrowing are not a "
                 "witness, just refinement attempts.")
    lines.append("")

    # --- Overview table ---
    lines.append("## Per-project overview")
    lines.append("")
    lines.append("| project | n | ok_proved | ok_witness | ok_inconclusive | search_error | verus_error | extract_error | other |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    total = Counter()
    proved_total = witness_total = inconc_total = unk_total = 0
    for proj, results in per_project.items():
        c = Counter(r.get("status", "?") for r in results)
        ok = c.get("ok", 0)
        se = c.get("search_error", 0)
        ve = c.get("verus_error", 0)
        ee = c.get("extract_error", 0)
        other = sum(v for k, v in c.items() if k not in {"ok", "search_error", "verus_error", "extract_error"})
        buckets = Counter()
        for r in results:
            if r.get("status") == "ok":
                buckets[classify_ok(r)] += 1
        proved = buckets[BUCKET_PROVED]
        witness = buckets[BUCKET_WITNESS]
        inconc = buckets[BUCKET_INCONCLUSIVE]
        unk = buckets[BUCKET_UNKNOWN_KIND]
        total.update(c)
        proved_total += proved
        witness_total += witness
        inconc_total += inconc
        unk_total += unk
        if (proved + witness + inconc + unk) != ok:
            other += ok - (proved + witness + inconc + unk)
        lines.append(f"| {proj} | {len(results)} | {proved} | {witness} | {inconc} | {se} | {ve} | {ee} | {other} |")
    n_total = sum(len(r) for r in per_project.values())
    lines.append(
        f"| **TOTAL** | **{n_total}** | **{proved_total}** | **{witness_total}** "
        f"| **{inconc_total}** | **{total.get('search_error',0)}** "
        f"| **{total.get('verus_error',0)}** | **{total.get('extract_error',0)}** | — |"
    )
    if unk_total:
        lines.append("")
        lines.append(f"_{unk_total} `ok` results had an unexpected `r0_z3` value "
                     f"(`{BUCKET_UNKNOWN_KIND}`)._")
    lines.append("")

    # --- Real witnesses (R0=sat) ---
    lines.append("## Real determinism witnesses (R0 = sat)")
    lines.append("")
    any_real = False
    for proj, results in per_project.items():
        rw = [r for r in results
              if r.get("status") == "ok" and classify_ok(r) == BUCKET_WITNESS]
        if not rw:
            continue
        any_real = True
        lines.append(f"### {proj} ({len(rw)} real-witness)")
        lines.append("")
        for r in rw:
            key = r.get("artifact_key", r.get("file", "?"))
            rounds = r.get("n_rounds", "?")
            assumes = r.get("assumes", [])
            lines.append(f"- `{key}`  (rounds={rounds})")
            for a in assumes:
                al = a if len(a) < 180 else a[:180] + "…"
                lines.append(f"  - `{al}`")
        lines.append("")
    if not any_real:
        lines.append("*(none — no z3-confirmed nondeterminism witnesses in this run)*")
        lines.append("")

    # --- Inconclusive targets (R0 = unknown) ---
    lines.append("## Inconclusive targets (R0 = unknown)")
    lines.append("")
    lines.append("These cases reached the schema-narrowing phase but z3 returned "
                 "`unknown` on the baseline check; any `assumes` below are search "
                 "artifacts, **not** verified witnesses.")
    lines.append("")
    any_inc = False
    for proj, results in per_project.items():
        inc = [r for r in results
               if r.get("status") == "ok" and classify_ok(r) == BUCKET_INCONCLUSIVE]
        if not inc:
            continue
        any_inc = True
        lines.append(f"### {proj} ({len(inc)} inconclusive)")
        lines.append("")
        for r in inc[:40]:
            key = r.get("artifact_key", r.get("file", "?"))
            rounds = r.get("n_rounds", "?")
            n_a = len(r.get("assumes", []))
            lines.append(f"- `{key}`  (rounds={rounds}, narrowed_assumes={n_a})")
        if len(inc) > 40:
            lines.append(f"- _…and {len(inc)-40} more_")
        lines.append("")
    if not any_inc:
        lines.append("*(none)*")
        lines.append("")

    # --- Failure-mode samples ---
    lines.append("## Failure-mode samples")
    lines.append("")
    by_status: dict[str, list[dict]] = defaultdict(list)
    for proj, results in per_project.items():
        for r in results:
            s = r.get("status", "?")
            if s in {"ok", "no_ensures"}:
                continue
            r2 = dict(r)
            r2["_project"] = proj
            by_status[s].append(r2)
    if not by_status:
        lines.append("*(no non-ok non-trivial statuses)*")
        lines.append("")
    for status, items in sorted(by_status.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"### status=`{status}`  ({len(items)} cases)")
        lines.append("")
        for r in items[:5]:
            key = r.get("artifact_key", r.get("file", "?"))
            lines.append(f"**{r['_project']} / {key}**")
            lines.append("")
            err_tail = r.get("stderr_tail") or r.get("error") or "(no message)"
            err_tail = err_tail.strip()
            if len(err_tail) > 1400:
                err_tail = err_tail[-1400:]
            lines.append("```")
            lines.append(err_tail)
            lines.append("```")
            lines.append("")
        if len(items) > 5:
            lines.append(f"_...and {len(items)-5} more_")
            lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, required=True,
                    help="results-verusage root")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output markdown file")
    args = ap.parse_args()
    root = args.results.expanduser().resolve()
    per_project = load_per_project(root)
    md = render(per_project)
    args.out.write_text(md)
    # Also write JSON summary for programmatic use
    summary_json = {}
    for proj, results in per_project.items():
        buckets = Counter()
        for r in results:
            if r.get("status") == "ok":
                buckets[classify_ok(r)] += 1
        summary_json[proj] = {
            "n": len(results),
            "by_status": dict(Counter(r.get("status", "?") for r in results)),
            "ok_proved": buckets[BUCKET_PROVED],
            "ok_witness": buckets[BUCKET_WITNESS],
            "ok_inconclusive": buckets[BUCKET_INCONCLUSIVE],
            # Legacy compatibility: pre-T0 callers expected this single number.
            # It now equals ok_witness + ok_inconclusive (everything with assumes).
            "ok_with_witness": buckets[BUCKET_WITNESS] + buckets[BUCKET_INCONCLUSIVE],
        }
    (args.out.with_suffix(".json")).write_text(
        json.dumps(summary_json, indent=2, sort_keys=True)
    )
    print(f"wrote {args.out} + {args.out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
