"""
spec-determinism — Orchestrator / minimal CLI entry point.

This is a thin, working wrapper around the current pipeline:

    extract_spec  →  build_det_check_spec  →  binary_search  →  report

It is intentionally minimal. The project's main batch driver is
`test_all.py` at the repo root; prefer that for running the full
nanvix matrix. Use this orchestrator when you want a single-function,
ad-hoc run from the shell.
"""

import argparse
import logging
import sys
from pathlib import Path

from .types import Witness
from .extract import extract_spec, Unsupported as ExtractUnsupported
from .gen_det import build_det_check_spec
from .equal_policy import EqualPolicy
from .verify import VerusRunner
from .binary_search import binary_search
from .backend import DetBackend
from .report import complete_witness, write_reports

logger = logging.getLogger(__name__)


def run_pipeline(
    crate_dir: str,
    crate_name: str,
    proof_file: str,
    verus_path: str,
    source_files: list[str],
    functions: list[str],
    features: list[str] | None = None,
    output_dir: str = "./det_output",
    timeout: int = 120,
    runner: DetBackend | None = None,
    equal_policy: EqualPolicy | None = None,
) -> list[Witness]:
    """Run the full spec-determinism pipeline on a list of functions.

    Args:
        crate_dir:     Crate root (for `cargo verus`).
        crate_name:    Crate/package name (e.g. "bitmap").
        proof_file:    .proof.rs file into which det-check proof fns
                       are injected.
        verus_path:    Directory containing the `verus` binary.
        source_files:  .rs files to search for specs and type defs.
        functions:     Function names to check.
        features:      Cargo features to enable.
        output_dir:    Where markdown/JSON reports are written.
        timeout:       Verus per-call timeout (seconds).
        runner:        Optional pre-built DetBackend. If None, a
                       VerusRunner is constructed from the above args.
        equal_policy:  Optional EqualPolicy; defaults to `EqualPolicy()`.

    Returns:
        Witness for each requested function (including failures).
    """
    type_sources = [Path(f).read_text() for f in source_files]
    combined_source = "\n".join(type_sources)

    if runner is None:
        runner = VerusRunner(
            crate_dir=crate_dir,
            crate_name=crate_name,
            proof_file=proof_file,
            verus_path=verus_path,
            features=features,
            timeout=timeout,
        )

    policy = equal_policy or EqualPolicy()

    results: list[Witness] = []

    for fn_name in functions:
        logger.info(f"=== Processing {fn_name} ===")

        try:
            spec = extract_spec(combined_source, fn_name, type_sources=type_sources)
        except ExtractUnsupported as e:
            logger.error(f"Skipping {fn_name}: extract failed: {e}")
            results.append(Witness(function=fn_name, gap_type="extract_failed",
                                   gap_description=str(e)))
            continue

        logger.info(
            f"Extracted: {spec.name}, {len(spec.params)} params, "
            f"return={spec.return_type.name}, "
            f"{len(spec.requires)} requires, {len(spec.ensures)} ensures"
        )

        try:
            det_spec = build_det_check_spec(spec, equal_policy=policy)
        except Exception as e:
            logger.error(f"Skipping {fn_name}: gen_det failed: {e}")
            results.append(Witness(function=fn_name, gap_type="gen_det_failed",
                                   gap_description=str(e)))
            continue

        witness = binary_search(det_spec, runner)
        witness = complete_witness(spec, witness)
        results.append(witness)

        status = "deterministic" if not witness.assumes else f"GAP: {witness.gap_type or 'nondet'}"
        calls = getattr(runner, "call_count", None)
        calls_str = f" ({calls} total backend calls)" if calls is not None else ""
        logger.info(f"{fn_name}: {status}{calls_str}")

    write_reports(results, output_dir)

    det_count = sum(1 for w in results if not w.assumes)
    gap_count = len(results) - det_count
    logger.info("=== Summary ===")
    logger.info(f"Functions checked: {len(results)}  "
                f"deterministic={det_count}  gaps={gap_count}")
    logger.info(f"Reports: {output_dir}/")

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.orchestrator",
        description="spec-determinism: detect spec nondeterminism for Verus fns",
    )
    parser.add_argument("--crate-dir", required=True, help="Path to crate root")
    parser.add_argument("--crate-name", required=True, help="Crate/package name")
    parser.add_argument("--proof-file", required=True, help="Path to .proof.rs file")
    parser.add_argument("--verus-path", required=True,
                        help="Path to directory containing the verus binary")
    parser.add_argument("--source", nargs="+", required=True,
                        help="Source .rs files to search for specs and types")
    parser.add_argument("--functions", nargs="+", required=True,
                        help="Function names to check")
    parser.add_argument("--features", nargs="*", help="Cargo features")
    parser.add_argument("--output", default="./det_output", help="Output directory")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Verus timeout per call (seconds)")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    results = run_pipeline(
        crate_dir=args.crate_dir,
        crate_name=args.crate_name,
        proof_file=args.proof_file,
        verus_path=args.verus_path,
        source_files=args.source,
        functions=args.functions,
        features=args.features,
        output_dir=args.output,
        timeout=args.timeout,
    )

    # Non-zero exit if any function failed pre-search (template / extract error).
    hard_fail = any(
        w.gap_type in ("extract_failed", "gen_det_failed") for w in results
    )
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
