"""Prompt builder for v0.1 — policy-aware.

Upgrade over v0: surface the `equal_fn` as the *contract* that "same
output" is measured by, split the witness's committed assumes into
driving vs collateral (per the `EqualPolicy` of the function), and
include a short layer directive to discourage dangling helpers and
parallel `assume_specification` blocks.
"""
from __future__ import annotations

from pathlib import Path

from .gap import Witness, classify_assumes


PROMPT_TEMPLATE = """# Task: close a spec-nondeterminism gap

You are editing a Verus specification file. A determinism checker has
found an input for which two spec-allowed outputs differ. Strengthen the
spec so that the spec-allowed output is uniquely determined (up to the
equivalence relation below), without over-constraining it.

## Function under spec
`{qualified_name}`

## Current `{spec_relpath}`
```rust
{spec_text}
```

## Determinism check context
The checker expands the spec with this template (ASSUMES is where the
witness below lives):

```rust
{det_template}
```

## Equivalence relation — the contract for "same output"
Two outputs count as the same *iff* the following `spec fn` returns
`true`. **This is the only definition of equality the checker uses.**
Any field / variant / payload **not mentioned** by this function is
already considered irrelevant and does NOT need to be pinned by your
fix. Any field that **is** mentioned must be determined by the `ensures`.

```rust
{equal_fn}
```

Equality policy for this function: `errs_equivalent={errs_equivalent}`,
`opaque_ok={opaque_ok}`.
- `errs_equivalent=True`  → ANY two `Err(_)` values compare equal; Err
  internals are already collapsed away.
- `opaque_ok=True`        → ANY two `Ok(_)` values compare equal (the
  returned address/handle is opaque); only post-state fields matter.

## Gap summary (derived from the witness)
{gap_summary}

### Driving assumptions — what actually makes `!equal` true
These are the assumes that flow into the equivalence relation above.
Your fix must rule out this combination.

```text
{driving_block}
```

### Input narrowing — concrete inputs the checker found
```text
{input_block}
```

### Collateral assumes — same SMT model but policy-ignored
The search loop committed these too (they were consistent with the
model), but they do NOT flow into the equal fn under the current policy.
**Do not pin these values** — doing so would over-specify.

```text
{collateral_block}
```

## What to return

Return a single fenced ```rust block containing the **full replacement
contents** of `{spec_relpath}`. Do not include any other prose.

### Layering rules (important)
- Strengthen the `ensures` of `fn {function}` **in place**.
- Do not add helper `spec fn`s unless you actually reference them from
  `ensures` of `fn {function}`. Unreferenced helpers are dead code.
- Do not add a new `assume_specification` block for a function whose
  contract is declared inline on its `impl` — edit the inline `ensures`
  instead. Parallel contracts shadow each other and do not fix the gap.
- Do not change function signatures.
- Do not add constraints on fields that the equal fn above does not
  compare — such constraints are over-specification.
- Your new `ensures` must still be satisfied by a reasonable
  implementation (e.g. don't force `r is Ok` unconditionally if the
  function legitimately returns errors on bad input).
"""


def _fmt_block(lines: list[str]) -> str:
    return "\n".join(lines) if lines else "(none)"


def build_prompt(witness: Witness, spec_path: Path, spec_relpath: str | None = None) -> str:
    spec_text = spec_path.read_text()
    template = witness.det_check_template or "// <det template unavailable>"
    equal_fn = witness.equal_fn_def or "// <equal-fn definition unavailable>"
    policy = witness.equal_policy or {}
    classified = classify_assumes(witness.assumes, policy)

    driving_lines = classified.discriminant + classified.driving_ok + classified.driving_err + classified.result_assertion
    collateral_lines = classified.collateral_ok + classified.collateral_err

    return PROMPT_TEMPLATE.format(
        qualified_name=witness.qualified_name,
        spec_relpath=spec_relpath or str(spec_path),
        spec_text=spec_text,
        det_template=template,
        equal_fn=equal_fn,
        errs_equivalent=policy.get("errs_equivalent", True),
        opaque_ok=policy.get("opaque_ok", False),
        gap_summary=classified.gap_summary,
        driving_block=_fmt_block(driving_lines),
        input_block=_fmt_block(classified.input_narrowing),
        collateral_block=_fmt_block(collateral_lines),
        function=witness.function,
    )
