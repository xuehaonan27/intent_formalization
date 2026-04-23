#!/usr/bin/env python3
"""Regenerate results/artifacts/<crate>__<fn>/{det_spec.json,template.rs}
from source + extractor, using the crate's active cfg feature set.

If an existing det_spec.json is present, its equal_policy is preserved
(to keep zero-diff regression against the pre-refactor baseline).
"""
import argparse
import json
from pathlib import Path

from spec_determinism.config import CorpusConfig, default_config_path, load_config
from spec_determinism.equal_policy import EqualPolicy
from spec_determinism.extract import extract_spec
from spec_determinism.gen_det import build_det_check_spec, render_template


def artifact_key(crate: str, fn: str) -> str:
    return f"{crate}__{fn}"


def regen_one(corpus: CorpusConfig, crate: str, fn: str) -> dict:
    cfg = corpus.crates[crate]
    with open(cfg.src) as f:
        src = f.read()
    type_sources: list[str] = []
    if Path(cfg.spec).exists():
        with open(cfg.spec) as f:
            type_sources.append(f.read())
    for extra in cfg.extra_type_sources:
        if Path(extra).exists():
            with open(extra) as f:
                type_sources.append(f.read())

    active_features = set(cfg.features)
    spec = extract_spec(src, fn, type_sources=type_sources,
                        active_features=active_features)

    art_dir = corpus.artifacts_dir / artifact_key(crate, fn)
    art_dir.mkdir(parents=True, exist_ok=True)
    det_json = art_dir / "det_spec.json"

    policy = None
    if det_json.exists():
        try:
            existing = json.loads(det_json.read_text())
            ep = existing.get("equal_policy")
            if ep is not None:
                policy = EqualPolicy.from_dict(ep)
        except Exception:
            policy = None

    check_name = cfg.check_overrides.get(fn)
    det_spec = build_det_check_spec(spec, check_name=check_name,
                                     equal_policy=policy)

    det_json.write_text(det_spec.to_json())
    (art_dir / "template.rs").write_text(render_template(det_spec, []))
    return {"crate": crate, "fn": fn, "n_symbols": len(det_spec.symbols)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", "-c", type=Path, default=None,
                    help="Path to corpus config TOML (default: configs/nanvix.toml)")
    ap.add_argument("targets", nargs="*",
                    help="Optional crate or crate::fn filter")
    args = ap.parse_args()

    corpus = load_config(args.config or default_config_path())

    if args.targets:
        pairs: list[tuple[str, str]] = []
        for t in args.targets:
            if "::" in t:
                c, f = t.split("::", 1)
                pairs.append((c, f))
            else:
                pairs.extend((t, fn) for fn in corpus.crates[t].functions)
    else:
        pairs = [(c, fn) for c, cc in corpus.crates.items() for fn in cc.functions]

    for crate, fn in pairs:
        try:
            r = regen_one(corpus, crate, fn)
            print(f"  ok  {crate}::{fn}  ({r['n_symbols']} symbols)")
        except Exception as e:
            print(f"  FAIL {crate}::{fn}  {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
