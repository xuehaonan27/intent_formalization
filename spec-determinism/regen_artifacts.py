#!/usr/bin/env python3
"""Regenerate results/artifacts/<crate>__<fn>/{det_spec.json,template.rs}
from the current source + extractor. Uses per-crate `features` as the
active cfg feature set so cfg-gated variants/fields are filtered out.

If an existing det_spec.json is present, its equal_policy is preserved
(to keep zero-diff regression against the pre-refactor baseline).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from src.extract import extract_spec
from src.gen_det import build_det_check_spec, render_template
from src.equal_policy import EqualPolicy

from run_all import CRATES, artifact_key, ROOT


def regen_one(crate: str, fn: str) -> dict:
    cfg = CRATES[crate]
    with open(cfg["src"]) as f:
        src = f.read()
    type_sources = []
    if os.path.exists(cfg["spec"]):
        with open(cfg["spec"]) as f:
            type_sources.append(f.read())
    for extra in cfg.get("extra_type_sources", []):
        if os.path.exists(extra):
            with open(extra) as f:
                type_sources.append(f.read())

    active_features = set(cfg.get("features", []))
    spec = extract_spec(src, fn, type_sources=type_sources,
                        active_features=active_features)

    art_dir = ROOT / "results" / "artifacts" / artifact_key(crate, fn)
    art_dir.mkdir(parents=True, exist_ok=True)
    det_json = art_dir / "det_spec.json"

    # Preserve existing equal_policy if we've seen this artifact before.
    policy = None
    if det_json.exists():
        try:
            existing = json.loads(det_json.read_text())
            ep = existing.get("equal_policy")
            if ep is not None:
                policy = EqualPolicy.from_dict(ep)
        except Exception:
            policy = None

    check_name = cfg.get("check_overrides", {}).get(fn)
    det_spec = build_det_check_spec(spec, check_name=check_name,
                                     equal_policy=policy)

    det_json.write_text(det_spec.to_json())
    (art_dir / "template.rs").write_text(render_template(det_spec, []))
    return {"crate": crate, "fn": fn, "n_symbols": len(det_spec.symbols)}


def main():
    args = sys.argv[1:]
    if args:
        # regen_artifacts.py crate fn   OR   regen_artifacts.py crate
        crate = args[0]
        fns = [args[1]] if len(args) > 1 else CRATES[crate]["functions"]
        crates = [(crate, fn) for fn in fns]
    else:
        crates = [(c, fn) for c, cfg in CRATES.items() for fn in cfg["functions"]]

    for crate, fn in crates:
        try:
            r = regen_one(crate, fn)
            print(f"  ok  {crate}::{fn}  ({r['n_symbols']} symbols)")
        except Exception as e:
            print(f"  FAIL {crate}::{fn}  {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
