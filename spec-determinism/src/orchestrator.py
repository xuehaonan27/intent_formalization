"""
spec-determinism — Orchestrator

Drives the full pipeline: extract → gen_det → verify → binary_search → witness → report
"""

import argparse
import logging
import sys
from pathlib import Path

from .types import FunctionSpec, Witness
from .extract import extract_spec, Unsupported as ExtractUnsupported
from .gen_det import generate_det_check
from .verify import VerusRunner
from .binary_search import binary_search
from .report import complete_witness, write_reports, generate_trace_report

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
    llm_client=None,
) -> list[Witness]:
    """
    Run the full spec-determinism pipeline.

    Args:
        crate_dir: Path to the crate root (for cargo verus)
        crate_name: Crate/package name (e.g. "bitmap")
        proof_file: Path to .proof.rs file for injection
        verus_path: Path to directory containing verus binary
        source_files: List of .rs files to search for specs and type defs
        functions: List of function names to check
        features: Cargo features to enable
        output_dir: Where to write reports
        timeout: Verus timeout per call (seconds)
        llm_client: Optional LLM client for fallbacks

    Returns:
        List of Witness results
    """
    # Read all source files
    sources = []
    for f in source_files:
        sources.append(Path(f).read_text())

    combined_source = "\n".join(sources)

    # Set up Verus runner
    runner = VerusRunner(
        crate_dir=crate_dir,
        crate_name=crate_name,
        proof_file=proof_file,
        verus_path=verus_path,
        features=features,
        timeout=timeout,
    )

    results = []

    for fn_name in functions:
        logger.info(f"=== Processing {fn_name} ===")

        # Step 1: Extract spec
        try:
            spec = extract_spec(combined_source, fn_name, sources)
        except ExtractUnsupported as e:
            logger.warning(f"Parser failed for {fn_name}: {e}")
            if llm_client:
                logger.info("Falling back to LLM for extraction")
                from .llm_fallback import LLMFallback
                fb = LLMFallback(llm_client)
                # TODO: integrate LLM extraction result into FunctionSpec
                logger.error("LLM extraction not yet integrated")
                continue
            else:
                logger.error(f"Skipping {fn_name}: no parser support and no LLM")
                continue

        logger.info(
            f"Extracted: {spec.name}, "
            f"{len(spec.params)} params, "
            f"return={spec.return_type.name}, "
            f"{len(spec.requires)} requires, "
            f"{len(spec.ensures)} ensures"
        )

        # Steps 2-4: Gen det check + verify + binary search
        witness = binary_search(spec, runner, llm_client)

        # Step 5: Complete witness
        witness = complete_witness(spec, witness, llm_client)

        results.append(witness)

        # Progress
        status = "deterministic" if not witness.assumes else f"GAP: {witness.gap_type}"
        logger.info(f"{fn_name}: {status} ({runner.call_count} total Verus calls)")

    # Step 6: Report
    write_reports(results, output_dir)

    # Summary
    det_count = sum(1 for w in results if not w.assumes)
    gap_count = sum(1 for w in results if w.assumes)
    logger.info(f"\n=== Summary ===")
    logger.info(f"Functions checked: {len(results)}")
    logger.info(f"Deterministic: {det_count}")
    logger.info(f"Gaps found: {gap_count}")
    logger.info(f"Total Verus calls: {runner.call_count}")
    logger.info(f"Reports: {output_dir}/")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="spec-determinism: Detect spec incompleteness via nondeterminism checking"
    )
    parser.add_argument("--crate-dir", required=True, help="Path to crate root")
    parser.add_argument("--crate-name", required=True, help="Crate/package name")
    parser.add_argument("--proof-file", required=True, help="Path to .proof.rs file")
    parser.add_argument("--verus-path", required=True, help="Path to verus binary dir")
    parser.add_argument("--source", nargs="+", required=True, help="Source .rs files")
    parser.add_argument("--functions", nargs="+", required=True, help="Functions to check")
    parser.add_argument("--features", nargs="*", help="Cargo features")
    parser.add_argument("--output", default="./det_output", help="Output directory")
    parser.add_argument("--timeout", type=int, default=120, help="Verus timeout (seconds)")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM fallback")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    llm_client = None
    if args.use_llm:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
            from utils.llm import LLMClient
            llm_client = LLMClient()
            logger.info("LLM fallback enabled")
        except ImportError:
            logger.warning("Could not import LLMClient — running without LLM fallback")

    run_pipeline(
        crate_dir=args.crate_dir,
        crate_name=args.crate_name,
        proof_file=args.proof_file,
        verus_path=args.verus_path,
        source_files=args.source,
        functions=args.functions,
        features=args.features,
        output_dir=args.output,
        timeout=args.timeout,
        llm_client=llm_client,
    )


if __name__ == "__main__":
    main()
