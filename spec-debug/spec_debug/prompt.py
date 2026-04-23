"""Prompt builder for v0.

Bare-minimum template: we hand the LLM (1) the whole .spec.rs, (2) the
det-check template from spec-determinism, (3) the committed assumes
witness. Task: propose an edit to the spec that closes the gap.

No strategy, no structural hints. We want to see what the LLM does without
guidance before adding any.
"""
from __future__ import annotations

from pathlib import Path

from .gap import Witness


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

The equivalence relation used to decide "same output":

```rust
{equal_fn}
```

## Witness (committed assumes that demonstrate nondeterminism)
The checker found the following `assume`s consistent with the spec; the
last assume `!{equal_fn_name}(r1, r2)` asserts the two outputs differ.

```text
{assumes}
```

## What to return

Return a single fenced ```rust block containing the **full replacement
contents** of `{spec_relpath}`. Do not include any other prose.

Constraints:
- Keep all existing items; only strengthen the `ensures` of
  `{function}` (or add whatever minimal new helper items are needed).
- Do not change function signatures.
- Your fix must still be satisfied by a reasonable implementation.
"""


def build_prompt(witness: Witness, spec_path: Path, spec_relpath: str | None = None) -> str:
    spec_text = spec_path.read_text()
    template = witness.det_check_template or "// <det template unavailable>"
    equal_fn = witness.equal_fn_def or "// <equal-fn definition unavailable>"
    equal_fn_name = witness.equal_fn_name or f"det_{witness.function}_equal"
    assumes_block = "\n".join(witness.assumes) if witness.assumes else "(no committed assumes)"

    return PROMPT_TEMPLATE.format(
        qualified_name=witness.qualified_name,
        spec_relpath=spec_relpath or str(spec_path),
        spec_text=spec_text,
        det_template=template,
        equal_fn=equal_fn,
        equal_fn_name=equal_fn_name,
        function=witness.function,
        assumes=assumes_block,
    )
