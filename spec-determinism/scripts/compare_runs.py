#!/usr/bin/env python3
"""Compare verusage corpus results between two runs.

Usage::

    python -m scripts.compare_runs \
        --baseline results-verusage \
        --candidate results-verusage-viewreg \
        [--out compare.md]

For each project, prints a side-by-side table:

* per-status target counts (ok, verus_error, runner_crash, ...)
* ``ok_with_witness`` count (the A-2 false-positive metric)
* set-diff of targets that flipped ok-with-witness → ok (good — A-2 fixed)
  and ok → verus_error (bad — view broke compilation)

The script is read-only; it touches no caches and runs in milliseconds.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def load_run(root: Path) -> dict[str, list[dict]]:
    """Return ``{project_name: [target_record, ...]}`` for a results tree."""
    out: dict[str, list[dict]] = {}
    for proj_dir in sorted(root.iterdir()):
        if not proj_dir.is_dir():
            continue
        f = proj_dir / "full_run.json"
        if not f.exists():
            continue
        try:
            out[proj_dir.name] = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
    return out


def witness_set(targets: list[dict]) -> set[str]:
    """Targets that verified ok but emitted a z3 counterexample witness.

    Matches verusage_summary.py's ok_with_witness definition.
    """
    return {
        _key(r) for r in targets
        if r.get("status") == "ok" and r.get("assumes")
    }


def _key(r: dict) -> str:
    # Stable identity per target — adjust if verusage_run schema changes.
    return r.get("artifact_key") or r.get("target") or r.get("fn", "?")


def status_counts(targets: list[dict]) -> dict[str, int]:
    return dict(Counter(r.get("status", "?") for r in targets))


def render(baseline: dict, candidate: dict) -> str:
    lines: list[str] = []

    lines.append("# Corpus rerun comparison\n")

    projects = sorted(set(baseline) | set(candidate))

    # Per-project totals
    lines.append("## Per-project totals\n")
    lines.append(
        "| project | n | ok | verus_err | ok_with_witness (base → cand) | Δ witness |\n"
        "|---|---:|---:|---:|---|---:|"
    )

    sum_n = sum_ok_base = sum_ok_cand = 0
    sum_err_base = sum_err_cand = 0
    sum_w_base = sum_w_cand = 0
    for proj in projects:
        b = baseline.get(proj, [])
        c = candidate.get(proj, [])
        bc = status_counts(b)
        cc = status_counts(c)
        bw = len(witness_set(b))
        cw = len(witness_set(c))
        n = len(c) or len(b)
        sum_n += n
        sum_ok_base += bc.get("ok", 0); sum_ok_cand += cc.get("ok", 0)
        sum_err_base += bc.get("verus_error", 0)
        sum_err_cand += cc.get("verus_error", 0)
        sum_w_base += bw; sum_w_cand += cw
        delta = cw - bw
        delta_str = f"**{delta:+d}**" if delta else "0"
        lines.append(
            f"| {proj} | {n} | "
            f"{bc.get('ok',0)} → {cc.get('ok',0)} | "
            f"{bc.get('verus_error',0)} → {cc.get('verus_error',0)} | "
            f"{bw} → {cw} | {delta_str} |"
        )
    delta_w = sum_w_cand - sum_w_base
    lines.append(
        f"| **TOTAL** | **{sum_n}** | "
        f"**{sum_ok_base} → {sum_ok_cand}** | "
        f"**{sum_err_base} → {sum_err_cand}** | "
        f"**{sum_w_base} → {sum_w_cand}** | "
        f"**{delta_w:+d}** |"
    )

    # Per-project transitions
    lines.append("\n## Per-project A-2 transitions\n")
    lines.append(
        "*fixed* = was ok-with-witness in baseline, now plain ok in candidate. "
        "*regressed* = was ok in baseline, now verus_error in candidate "
        "(view broke compilation).\n"
    )
    for proj in projects:
        b = baseline.get(proj, [])
        c = candidate.get(proj, [])
        b_map = {_key(r): r for r in b}
        c_map = {_key(r): r for r in c}
        common = set(b_map) & set(c_map)

        # Witness → not-witness
        fixed = []
        for k in common:
            br, cr = b_map[k], c_map[k]
            b_w = br.get("status") == "ok" and br.get("assumes")
            c_w = cr.get("status") == "ok" and cr.get("assumes")
            if b_w and not c_w and cr.get("status") == "ok":
                fixed.append(k)

        # ok → verus_error
        regressed = []
        for k in common:
            br, cr = b_map[k], c_map[k]
            if (br.get("status") == "ok"
                    and cr.get("status") == "verus_error"):
                regressed.append(k)

        # ok-with-witness → verus_error (also bad — view broke equal-fn)
        witness_to_err = []
        for k in common:
            br, cr = b_map[k], c_map[k]
            b_w = br.get("status") == "ok" and br.get("assumes")
            if b_w and cr.get("status") == "verus_error":
                witness_to_err.append(k)

        if not (fixed or regressed or witness_to_err):
            continue
        lines.append(f"\n### {proj}")
        if fixed:
            lines.append(
                f"\n**fixed** ({len(fixed)} targets — witness → ok):"
            )
            for k in sorted(fixed)[:30]:
                lines.append(f"- `{k}`")
            if len(fixed) > 30:
                lines.append(f"- … +{len(fixed) - 30} more")
        if witness_to_err:
            lines.append(
                f"\n**witness → verus_error** ({len(witness_to_err)} "
                f"targets — view compiled but blocked verification):"
            )
            for k in sorted(witness_to_err)[:30]:
                lines.append(f"- `{k}`")
            if len(witness_to_err) > 30:
                lines.append(f"- … +{len(witness_to_err) - 30} more")
        if regressed:
            lines.append(
                f"\n**regressed** ({len(regressed)} targets — clean ok "
                f"→ verus_error):"
            )
            for k in sorted(regressed)[:30]:
                lines.append(f"- `{k}`")
            if len(regressed) > 30:
                lines.append(f"- … +{len(regressed) - 30} more")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, required=True,
                    help="Baseline results-verusage tree (before view registry).")
    ap.add_argument("--candidate", type=Path, required=True,
                    help="Candidate results tree (after --use-view-registry).")
    ap.add_argument("--out", type=Path, default=None,
                    help="Write the markdown report here (also stdout).")
    args = ap.parse_args()

    b = load_run(args.baseline.expanduser().resolve())
    c = load_run(args.candidate.expanduser().resolve())
    if not c:
        print(f"!! candidate {args.candidate} contains no full_run.json",
              file=sys.stderr)
        return 2

    md = render(b, c)
    if args.out is not None:
        args.out.write_text(md)
        print(f"wrote {args.out}", file=sys.stderr)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
