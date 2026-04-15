"""
Module 5: witness — Witness Completion & Formatting
Module 6: reporter — Output & Reporting

Combined for now since they're tightly coupled.
"""

import json
import logging
from pathlib import Path

from .types import (
    TypeKind, TypeInfo, FunctionSpec, Assume,
    ConcreteValue, Witness,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Witness completion
# ---------------------------------------------------------------------------

def complete_witness(
    spec: FunctionSpec,
    witness: Witness,
    llm_client=None,
) -> Witness:
    """
    Fill in any missing fields from the binary search result.
    
    Uses constraint propagation first, LLM fallback for gap classification.
    """
    # Build concrete values from assumes
    inputs = _extract_concrete_values(witness.assumes, "input", spec)
    output1 = _extract_concrete_values(witness.assumes, "output1", spec)
    output2 = _extract_concrete_values(witness.assumes, "output2", spec)

    witness.inputs = inputs
    witness.output1 = output1
    witness.output2 = output2

    # Gap classification via LLM (the one place LLM adds real value)
    if llm_client and witness.assumes:
        witness.gap_type, witness.gap_description = _classify_gap(
            spec, witness, llm_client
        )

    return witness


def _extract_concrete_values(
    assumes: list[Assume],
    category: str,
    spec: FunctionSpec,
) -> dict[str, ConcreteValue]:
    """Extract concrete values from assume constraints."""
    values = {}
    for assume in assumes:
        # Parse simple equality: var == value
        parts = assume.expression.split("==")
        if len(parts) == 2:
            var = parts[0].strip()
            val = parts[1].strip()
            values[var] = ConcreteValue(
                var_name=var,
                type_name="",  # would need type resolution
                raw=val,
            )
    return values


def _classify_gap(spec: FunctionSpec, witness: Witness, llm_client) -> tuple[str, str]:
    """Use LLM to classify the gap type and generate description."""
    assumes_str = "\n".join(f"  {a.expression}" for a in witness.assumes)
    prompt = (
        f"A Verus function `{spec.name}` has a specification that is nondeterministic.\n"
        f"The concrete witness:\n{assumes_str}\n\n"
        f"Classify this gap as one of: liveness, error_wildcard, frame_condition, "
        f"design_choice, type_abstraction, totality, other.\n"
        f"Give a one-line description of the gap.\n"
        f"Format: TYPE: description"
    )
    try:
        response = llm_client.chat(
            system_prompt="You are a formal verification expert.",
            user_prompt=prompt,
        )
        text = response.content.strip()
        if ":" in text:
            gap_type, gap_desc = text.split(":", 1)
            return gap_type.strip().lower(), gap_desc.strip()
        return "other", text
    except Exception as e:
        logger.warning(f"LLM gap classification failed: {e}")
        return "unknown", ""


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def generate_trace_report(results: list[Witness]) -> str:
    """Generate markdown trace report."""
    lines = ["# Determinism Check — Binary Search Traces\n"]

    for w in results:
        lines.append(f"## Function: `{w.function}`\n")

        if not w.trace:
            lines.append("No trace recorded.\n")
            continue

        # Check if deterministic (R0 passed)
        if w.trace and w.trace[0].get("result") == "pass":
            lines.append("✅ Spec is deterministic. No nondeterminism detected.\n")
            continue

        lines.append("| Round | Phase | Active assumes | New constraint | Result |")
        lines.append("|-------|-------|---------------|---------------|--------|")

        for step in w.trace:
            r = step["round"]
            phase = step["phase"]
            assumes = ", ".join(step["assumes"]) if step["assumes"] else "(none)"
            new = step.get("new_assume", "—") or "—"
            result = "❌ FAIL" if step["result"] == "fail" else "✅ PASS"
            lines.append(f"| R{r} | {phase} | `{assumes}` | `{new}` | {result} |")

        lines.append("")

        if w.gap_type:
            lines.append(f"**Gap type:** {w.gap_type}")
        if w.gap_description:
            lines.append(f"**Description:** {w.gap_description}")
        lines.append("")

    return "\n".join(lines)


def generate_witness_report(results: list[Witness]) -> str:
    """Generate markdown witness report with all fields concrete."""
    lines = ["# Determinism Check — Complete Witnesses\n"]

    for w in results:
        if not w.assumes:
            continue

        lines.append(f"## Function: `{w.function}`\n")
        lines.append("```")

        if w.inputs:
            lines.append("INPUT:")
            for var, val in w.inputs.items():
                lines.append(f"  {var} = {val.raw}")

        if w.output1:
            lines.append("\nOUTPUT 1 (y1):")
            for var, val in w.output1.items():
                lines.append(f"  {var} = {val.raw}")

        if w.output2:
            lines.append("\nOUTPUT 2 (y2):")
            for var, val in w.output2.items():
                lines.append(f"  {var} = {val.raw}")

        lines.append("```\n")

        if w.gap_type:
            lines.append(f"**Gap:** {w.gap_type} — {w.gap_description}\n")

    return "\n".join(lines)


def generate_summary_json(results: list[Witness]) -> str:
    """Generate machine-readable JSON summary."""
    summary = []
    for w in results:
        entry = {
            "function": w.function,
            "deterministic": len(w.assumes) == 0,
            "gap_type": w.gap_type,
            "gap_description": w.gap_description,
            "num_rounds": len(w.trace),
            "assumes": [a.expression for a in w.assumes],
        }
        summary.append(entry)
    return json.dumps(summary, indent=2)


def write_reports(results: list[Witness], output_dir: str):
    """Write all report files."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "traces.md").write_text(generate_trace_report(results))
    (out / "witnesses.md").write_text(generate_witness_report(results))
    (out / "summary.json").write_text(generate_summary_json(results))

    logger.info(f"Reports written to {output_dir}")
