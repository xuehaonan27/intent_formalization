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


def render(baseline: dict, candidate: dict, *,
           baseline_commit: str = "", candidate_commit: str = "") -> str:
    lines: list[str] = []

    lines.append("# Corpus rerun comparison\n")
    if baseline_commit or candidate_commit:
        lines.append(
            f"| | commit |\n|---|---|\n"
            f"| baseline  | `{baseline_commit or '?'}` |\n"
            f"| candidate | `{candidate_commit or '?'}` |\n"
        )
    lines.append(
        "Definitions:\n"
        "- **ok_with_witness** — Verus accepted the equal-fn but z3 emitted\n"
        "  a counterexample (`status==\"ok\" AND assumes!=[]`). The A-2\n"
        "  false-positive metric.\n"
        "- **fixed** — was ok_with_witness in baseline, now plain ok in\n"
        "  candidate. **Wins go here.**\n"
        "- **witness → verus_error** — was ok_with_witness, now Verus\n"
        "  rejects the equal-fn. View compiled but blocked verification;\n"
        "  not a clean win.\n"
        "- **regressed** — was clean ok (no witness) in baseline, now\n"
        "  verus_error in candidate. **This number must be ~0**\n"
        "  to consider the change safe to land.\n"
    )

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

        # ok → verus_error (true regression: baseline had a clean ok with
        # no witness; candidate broke compilation). Excludes witness→err
        # — those go in their own bucket so the reader can tell apart
        # 'A-2 witness that turned into a verus error' from 'previously
        # clean target that the new equal-fn broke'.
        regressed = []
        for k in common:
            br, cr = b_map[k], c_map[k]
            b_w = br.get("status") == "ok" and br.get("assumes")
            if (br.get("status") == "ok"
                    and not b_w
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


def _git_commit(path: Path) -> str:
    """Try to recover the last commit that touched ``path`` (or any file
    under it). Returns ``""`` on failure — comparison still works."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", str(path)],
            check=True, capture_output=True, text=True,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, required=True,
                    help="Baseline results-verusage tree (before view registry).")
    ap.add_argument("--candidate", type=Path, required=True,
                    help="Candidate results tree (after --use-view-registry).")
    ap.add_argument("--out", type=Path, default=None,
                    help="Write the markdown report here (also stdout).")
    ap.add_argument("--baseline-commit", default=None,
                    help="Git commit hash for the baseline run (default: "
                         "inferred from git log).")
    ap.add_argument("--candidate-commit", default=None,
                    help="Git commit hash for the candidate run (default: "
                         "inferred from git log; falls back to current HEAD).")
    args = ap.parse_args()

    b_root = args.baseline.expanduser().resolve()
    c_root = args.candidate.expanduser().resolve()

    b = load_run(b_root)
    c = load_run(c_root)
    if not c:
        print(f"!! candidate {args.candidate} contains no full_run.json",
              file=sys.stderr)
        return 2

    baseline_commit = args.baseline_commit or _git_commit(b_root)
    candidate_commit = args.candidate_commit or _git_commit(c_root)
    if not candidate_commit:
        # Candidate is usually un-committed (just written) — fall back to HEAD.
        candidate_commit = _git_commit(Path.cwd()) + " (HEAD, uncommitted)"

    md = render(b, c,
                baseline_commit=baseline_commit,
                candidate_commit=candidate_commit)
    if args.out is not None:
        args.out.write_text(md)
        print(f"wrote {args.out}", file=sys.stderr)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
