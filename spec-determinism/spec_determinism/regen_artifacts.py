#!/usr/bin/env python3
"""Regenerate results/artifacts/<crate>__<fn>/{det_spec.json,template.rs}
from source + extractor, using the crate's active cfg feature set.

If an existing det_spec.json is present, its equal_policy is preserved
(to keep zero-diff regression against the pre-refactor baseline).
"""
import argparse
import json
import logging
from pathlib import Path

from spec_determinism.config import CorpusConfig, default_config_path, load_config
from spec_determinism.equal_policy import EqualPolicy
from spec_determinism.extract import extract_spec
from spec_determinism.gen_det import build_det_check_spec, render_template
from spec_determinism.types import TypeKind, TypeProjections
from spec_determinism.workspace import discover_workspace_rs_files, read_source


logger = logging.getLogger(__name__)


def artifact_key(crate: str, fn: str) -> str:
    return f"{crate}__{fn}"


def _collect_type_sources(corpus: CorpusConfig, cfg) -> list[str]:
    """Build the type-definition corpus for refine_types.

    Order (priority: earlier entries win on name collision inside refine_types):
      1. This crate's own .spec.rs (type view defs live here).
      2. cfg.extra_type_sources — explicit per-crate overrides.
      3. Every .rs under any Cargo workspace member rooted at `corpus.nanvix`.

    All file reads are cached, so calling this per artifact is cheap after
    the first pass.
    """
    seen: set[str] = set()
    out: list[str] = []

    def _push(path_str: str) -> None:
        p = str(Path(path_str).resolve())
        if p in seen:
            return
        if not Path(p).exists():
            return
        seen.add(p)
        out.append(read_source(p))

    if Path(cfg.spec).exists():
        _push(cfg.spec)
    for extra in cfg.extra_type_sources:
        _push(extra)
    for ws in discover_workspace_rs_files(corpus.nanvix):
        _push(str(ws))
    return out


def regen_one(
    corpus: CorpusConfig,
    crate: str,
    fn: str,
    *,
    use_llm_policy: bool = False,
    force_llm_policy: bool = False,
    use_llm_projections: bool = False,
    force_llm_projections: bool = False,
    llm_model: str | None = None,
    llm_run_root: Path | None = None,
) -> dict:
    cfg = corpus.crates[crate]
    with open(cfg.src) as f:
        src = f.read()
    type_sources = _collect_type_sources(corpus, cfg)

    active_features = set(cfg.features)
    spec = extract_spec(src, fn, type_sources=type_sources,
                        active_features=active_features)

    art_dir = corpus.artifacts_dir / artifact_key(crate, fn)
    art_dir.mkdir(parents=True, exist_ok=True)
    det_json = art_dir / "det_spec.json"

    policy: EqualPolicy | None = None
    stored_projections: dict[str, TypeProjections] = {}
    if det_json.exists():
        try:
            existing = json.loads(det_json.read_text())
            ep = existing.get("equal_policy")
            if ep is not None:
                policy = EqualPolicy.from_dict(ep)
            raw_projs = existing.get("type_projections") or {}
            stored_projections = {
                k: TypeProjections.from_dict(v) for k, v in raw_projs.items()
            }
        except Exception:
            policy = None
            stored_projections = {}

    # LLM policy hook: only overwrite when the stored policy is the
    # structural default (or missing entirely). Non-default stored policies
    # — whether from a human edit or a previous LLM run — are preserved
    # for reproducibility. Use --force-llm-policy to override.
    if use_llm_policy:
        should_call = force_llm_policy or policy is None or policy.is_default()
        if should_call:
            policy = _call_llm_policy(
                spec, crate, fn, art_dir, llm_run_root, llm_model
            )
        else:
            logger.info("skip LLM policy for %s::%s (existing policy source=%s)",
                        crate, fn, policy.source)

    check_name = cfg.check_overrides.get(fn)
    det_spec = build_det_check_spec(spec, check_name=check_name,
                                     equal_policy=policy)

    # Carry forward any previously-discovered projections.
    det_spec.type_projections = dict(stored_projections)

    if use_llm_projections:
        opaque_names = _opaque_type_names_needing_projections(
            det_spec, stored_projections, force=force_llm_projections,
        )
        if opaque_names:
            new_projs = _call_llm_projections(
                opaque_names, corpus, crate, fn, type_sources,
                art_dir, llm_run_root, llm_model,
            )
            det_spec.type_projections.update(new_projs)

    det_json.write_text(det_spec.to_json())
    (art_dir / "template.rs").write_text(render_template(det_spec, []))
    return {"crate": crate, "fn": fn, "n_symbols": len(det_spec.symbols)}


def _opaque_type_names_needing_projections(
    det_spec,
    stored: dict[str, TypeProjections],
    *,
    force: bool,
) -> list[str]:
    """Collect distinct opaque-type names among det_spec.symbols whose
    projections have not yet been attempted (or all, if force)."""
    names: list[str] = []
    seen: set[str] = set()
    for sym in det_spec.symbols:
        t = sym.type
        if t.kind != TypeKind.UNKNOWN:
            continue
        if not t.name or t.name in seen:
            continue
        if not force and t.name in stored:
            continue
        seen.add(t.name)
        names.append(t.name)
    return names


def _call_llm_projections(
    opaque_type_names: list[str],
    corpus: CorpusConfig,
    crate: str,
    fn: str,
    type_sources: list[str],
    art_dir: Path,
    llm_run_root: Path | None,
    llm_model: str | None,
) -> dict[str, TypeProjections]:
    """Query LLM for opaque-type projections; log failures and return empty."""
    from spec_determinism.policy_llm import (
        CopilotPolicyLLM, generate_projections_with_llm,
    )
    run_dir = (llm_run_root or art_dir) / "llm_projections"
    blob = "\n".join(type_sources)
    try:
        client = CopilotPolicyLLM(model=llm_model)
        return generate_projections_with_llm(
            opaque_type_names, corpus.nanvix, run_dir, blob,
            crate_name=crate, client=client,
        )
    except Exception as e:
        logger.warning("LLM projection discovery failed for %s::%s: %s — "
                       "leaving opaque types as-is", crate, fn, e)
        return {}


def _call_llm_policy(
    fn_spec, crate: str, fn: str, art_dir: Path,
    llm_run_root: Path | None, llm_model: str | None,
) -> EqualPolicy:
    """Query LLM for EqualPolicy; log failures and fall back to default."""
    from spec_determinism.policy_llm import (
        CopilotPolicyLLM, generate_policy_with_llm,
    )
    # For the prompt we need the det_spec's symbol list; build once with
    # default policy to get symbols, then rebuild outside this function.
    tmp_det = build_det_check_spec(fn_spec, check_name=None, equal_policy=None)
    run_dir = (llm_run_root or art_dir) / "llm_policy"
    try:
        client = CopilotPolicyLLM(model=llm_model)
        return generate_policy_with_llm(
            fn_spec, tmp_det, run_dir, crate_name=crate, client=client
        )
    except Exception as e:
        logger.warning("LLM policy generation failed for %s::%s: %s — "
                       "falling back to default policy", crate, fn, e)
        return EqualPolicy()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", "-c", type=Path, default=None,
                    help="Path to corpus config TOML (default: configs/nanvix.toml)")
    ap.add_argument("targets", nargs="*",
                    help="Optional crate or crate::fn filter")
    ap.add_argument("--use-llm-policy", action="store_true",
                    help="Query an LLM to generate EqualPolicy for functions "
                         "whose stored policy is default/missing.")
    ap.add_argument("--force-llm-policy", action="store_true",
                    help="With --use-llm-policy, overwrite non-default stored "
                         "policies too (use sparingly — discards prior decisions).")
    ap.add_argument("--use-llm-projections", action="store_true",
                    help="Query an LLM to discover projection spec-fns for "
                         "opaque (unresolved) input/output types.")
    ap.add_argument("--force-llm-projections", action="store_true",
                    help="With --use-llm-projections, re-query even for types "
                         "with stored projections (status=ok/empty).")
    ap.add_argument("--llm-model", default=None,
                    help="Pass `--model <x>` to the Copilot CLI.")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

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
            r = regen_one(
                corpus, crate, fn,
                use_llm_policy=args.use_llm_policy,
                force_llm_policy=args.force_llm_policy,
                use_llm_projections=args.use_llm_projections,
                force_llm_projections=args.force_llm_projections,
                llm_model=args.llm_model,
            )
            print(f"  ok  {crate}::{fn}  ({r['n_symbols']} symbols)")
        except Exception as e:
            print(f"  FAIL {crate}::{fn}  {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
