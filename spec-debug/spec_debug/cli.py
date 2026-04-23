"""spec-debug CLI."""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

from .config import DebugConfig, default_config_path, load_config
from .gap import Witness, crate_for, load_witness
from .llm.copilot import CopilotLLMClient
from .llm.manual import ManualLLMClient
from .patch import apply_patch
from .prompt import build_prompt
from .report import write_report
from .verify import verify


def _split_qualified(name: str) -> tuple[str, str]:
    if "::" not in name:
        raise SystemExit(f"expected <crate>::<function>, got: {name!r}")
    crate, fn = name.split("::", 1)
    return crate, fn


def _run_dir_for(cfg: DebugConfig, crate: str, fn: str) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    return cfg.runs_dir / ts / f"{crate}__{fn}"


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    crate, fn = _split_qualified(args.target)
    crate_cfg = crate_for(cfg.corpus, crate)

    if not args.skip_initial_rerun:
        print(f"[0/5] Running spec-determinism to refresh witness for {crate}::{fn}")
        rc = subprocess.run(
            ["spec-determinism-run", f"{crate}::{fn}", "-c", str(cfg.corpus.path)],
        ).returncode
        if rc != 0:
            print(f"      spec-determinism-run exited rc={rc}; aborting", file=sys.stderr)
            return rc

    print(f"[1/5] Loading witness for {crate}::{fn}")
    witness: Witness = load_witness(cfg.corpus, crate, fn)
    print(f"      {len(witness.assumes)} committed assumes, {witness.n_rounds} rounds")
    if not witness.has_gap():
        print("      (no gap to close — function is already tight)")
        return 0

    run_dir = _run_dir_for(cfg, crate, fn)
    print(f"[2/5] Building prompt → {run_dir}/prompt.md")
    spec_path = Path(crate_cfg.spec)
    prompt = build_prompt(witness, spec_path, spec_relpath=spec_path.name)

    print(f"[3/5] Waiting for LLM response ({args.llm})")
    if args.llm == "copilot":
        llm = CopilotLLMClient(model=args.model, reasoning_effort=args.effort)
    else:
        llm = ManualLLMClient()
    response = llm.query(prompt, run_dir)
    print(f"      got {len(response.raw)} chars, extracted {len(response.patch_text)} chars of patch")

    print(f"[4/5] Applying patch to {spec_path}")
    patch = apply_patch(spec_path, response.patch_text)
    try:
        print(f"[5/5] Verifying")
        report = verify(cfg.corpus, crate_cfg, fn, witness.assumes)
        r = report.rerun
        print(
            f"      spec-det rerun: {'PASS' if r.ok else 'FAIL'} "
            f"(rc={r.returncode}), closed={len(r.closed)}, added={len(r.added)}"
        )
    finally:
        if not args.keep:
            patch.revert()
            print(f"      reverted {spec_path}")
        else:
            print(f"      --keep: leaving patched file in place at {spec_path}")

    json_path, md_path = write_report(run_dir, witness, response, response.patch_text, report)
    print(f"Report: {md_path}")
    return 0 if report.rerun.ok else 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="spec-debug")
    p.add_argument("-c", "--config", default=str(default_config_path()),
                   help="spec-debug config file (default: %(default)s)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the debugging pipeline on one function")
    r.add_argument("target", help="<crate>::<function>, e.g. bitmap::new")
    r.add_argument("--skip-initial-rerun", action="store_true",
                   help="don't re-run spec-determinism before loading the witness")
    r.add_argument("--keep", action="store_true",
                   help="do NOT revert the patched .spec.rs after verification")
    r.add_argument("--llm", choices=["manual", "copilot"], default="copilot",
                   help="LLM backend (default: copilot, invokes `copilot -p`)")
    r.add_argument("--model", default=None,
                   help="pass --model to copilot CLI (e.g. gpt-5.2)")
    r.add_argument("--effort", default=None,
                   choices=["low", "medium", "high", "xhigh"],
                   help="pass --effort to copilot CLI")
    r.set_defaults(func=cmd_run)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
