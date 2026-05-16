"""Prompt construction for the LLM proof loop.

The prompt has four sections:

  1. **Task**: explain that the LLM is closing a z3 ``unknown`` on a
     synthetic determinism postcondition.
  2. **The function under analysis**: signature, requires, ensures,
     and the body of the synthetic ``det_<f>`` proof fn (so the LLM
     sees the *exact* postcondition it must discharge).
  3. **Output format**: ```verus block of statements + ```json rationale.
  4. **Allowlist** + few-shot examples derived from atmosphere's
     ``set_owning_container`` case study.

On retry (when a previous attempt failed Verus or violated the sandbox),
we append a 5th section with the prior attempt + the failure tail
(stderr / sandbox violations), so the LLM can self-correct.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from spec_determinism.extract.types import DetCheckSpec, FunctionSpec


_TASK_HEADER = """\
You are writing **Verus proof annotations** that help z3 discharge a
synthetic *determinism check* for a function. The pipeline runs `verus`,
extracts the resulting SMT2, and asks z3 whether the postcondition

    requires(<ensures>(r1)) && requires(<ensures>(r2))
        ==> det_<f>_equal(r1, r2)

is valid. z3 returned **`unknown`** at the file level — almost always a
quantifier-instantiation gap (the two `forall` quantifiers from the
ensures clauses have disjoint triggers, so z3 never lines them up).

Your job is to write a *small* block of Verus statements that, when
prepended to the body of the synthetic `det_<f>` proof fn, lets Verus
verify the postcondition. Verus will check every statement you write —
nothing in your block can be unsound.
"""


_FORMAT_DOC = """\
## Output format

Emit exactly two fenced blocks, in this order:

1. A ```verus fenced block whose body is the proof prelude. It will be
   inserted at the top of `proof fn det_<f>(...) { ... }`, before the
   schema-assume scaffolding that the pipeline appends. So you have:
     * `r1`, `r2` in scope (the two candidate results)
     * any inputs / `self` parameters in scope (consult the signature)
     * every requires / ensures from the original function as hypotheses
   You may write: `assert`, `assert ... by`, `assert forall|x| ... by`,
   `reveal(spec_fn)`, `broadcast use group_xyz`, calls to existing
   `lemma_*` functions, plain `let` / `if` / `match`, and inline
   `proof { ... }` blocks.
   Multi-statement is fine.

2. A ```json fenced block with `{"rationale": "<one or two sentences>"}`.

## Allowlist (mandatory — your output is rejected if you use any of these)

The following constructs make Verus accept the postcondition WITHOUT a
real proof, and will be rejected by the post-parse lex scanner:

  * `assume(P)` — adds P as an axiom. **Verus silently accepts
    `assume(false)`**, so this is the most dangerous failure mode.
    Use `assert(P)` (which Verus must verify) instead.
  * `admit()` — discharges any pending obligation.
  * `unimplemented!()` / `unreachable!()` — bypass verification.
  * `assume_specification` — declares an unverified extern spec.
  * `#[verifier::external_body]` / `#[verifier(external_body)]` —
    Verus skips body verification.
  * any new `fn` / `spec fn` / `proof fn` / `exec fn` definition.
  * any new `impl` / `trait` / `struct` / `enum` / `type` item.

Stick to *statements that live inside an existing proof body*.
"""


_FEW_SHOT = """\
## Example — closing a two-`forall` trigger gap (atmosphere `set_owning_container`)

The function maintains an `Array<Page, N>` whose only spec is a per-index
forall over its `.view()`:

```
ensures
    forall|i: int| 0 <= i < self_.len() ==>
        self_@[i] == old(self_)@[i] || (i == idx as int && self_@[i] == #[trigger] page),
```

z3 returned `unknown` because the two ensures-conjuncts (one for `r1`,
one for `r2`) have disjoint triggers — `self_@[i]` for each run binds
different array instances, so the `forall|i|` for run 1 doesn't fire on
the corresponding obligation for run 2. The repair, lex-clean:

```verus
// Pull both ensures into the proof context so triggers line up.
assert(forall|i: int| 0 <= i < r1.len() ==>
    r1@[i] == old(self_)@[i] || (i == idx as int && r1@[i] == page));
assert(forall|i: int| 0 <= i < r2.len() ==>
    r2@[i] == old(self_)@[i] || (i == idx as int && r2@[i] == page));

// Pointwise: for each i, r1@[i] and r2@[i] are forced equal.
assert forall|i: int| 0 <= i < r1.len() implies r1@[i] == r2@[i] by {
    if i == idx as int {
        // Both pick the second disjunct (== page).
    } else {
        // Both pick the first disjunct (== old(self_)@[i]).
    }
}

// Sequence extensionality lifts the pointwise equality to .view() ==.
assert(r1@ =~= r2@);
```

```json
{"rationale": "Force both `forall|i|` to be instantiated by re-asserting them, do a case split on i==idx, then close with Seq::ext_equal (`=~=`)."}
```

Notice: every `assert` is something Verus must verify; nothing is
asserted on faith.
"""


_RETRY_HEADER = """\
## Previous attempt FAILED

Your previous proof block did not let Verus accept the postcondition.
Use the error tail below to figure out which case / trigger / lemma you
need to add, and emit a corrected block.
"""


@dataclass
class PromptInputs:
    """Inputs needed to build a proof prompt.

    Required: ``det_spec`` (always available) and ``det_body`` (the
    rendered synthetic proof fn — already contains the postcondition the
    LLM must prove). Everything else is optional human-readable context.
    """

    det_spec: DetCheckSpec
    det_body: str                  # the rendered `proof fn det_<f>(...) { ... }`
    fn_spec: Optional[FunctionSpec] = None    # for nicer signature/requires/ensures headers
    source_excerpt: str = ""       # the original .rs file (or a window of it)
    crate_name: str = ""

    # Retry-only fields.
    prior_proof_block: Optional[str] = None
    prior_failure_kind: Optional[str] = None       # "verus" | "sandbox"
    prior_failure_detail: Optional[str] = None     # stderr tail or violation list

    # Optional caps to control prompt size for very large files.
    max_source_chars: int = 8000


def _ensures_block(fn_spec: Optional[FunctionSpec]) -> str:
    if fn_spec is None or not fn_spec.ensures:
        return "(see the synthetic proof fn below)"
    return "\n".join(f"  - {e}" for e in fn_spec.ensures)


def _requires_block(fn_spec: Optional[FunctionSpec]) -> str:
    if fn_spec is None or not fn_spec.requires:
        return "(see the synthetic proof fn below)"
    return "\n".join(f"  - {r}" for r in fn_spec.requires)


def _signature_line(det_spec: DetCheckSpec, fn_spec: Optional[FunctionSpec]) -> str:
    if fn_spec is None:
        return f"fn {det_spec.function}(...) -> ..."
    parts: list[str] = []
    for p in fn_spec.params:
        pfx = "&mut " if p.is_mut_ref else ("&" if p.is_ref else "")
        nm = "self" if p.is_self else p.name
        parts.append(f"{nm}: {pfx}{p.type.name}")
    return f"fn {fn_spec.name}({', '.join(parts)}) -> {fn_spec.return_type.name}"


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n/* … truncated … */\n\n" + text[-half:]


def build_proof_prompt(inputs: PromptInputs) -> str:
    """Compose the full prompt text to send to the LLM."""
    sections: list[str] = [_TASK_HEADER]

    sections.append("## Function under analysis\n")
    if inputs.crate_name:
        sections.append(f"Crate: `{inputs.crate_name}`\n")
    sections.append(f"Signature:\n```\n{_signature_line(inputs.det_spec, inputs.fn_spec)}\n```\n")
    sections.append(f"Requires clauses:\n{_requires_block(inputs.fn_spec)}\n")
    sections.append(f"Ensures clauses:\n{_ensures_block(inputs.fn_spec)}\n")

    sections.append(
        "## Synthetic determinism proof fn (your prelude goes at the top "
        "of this body)\n"
    )
    sections.append(f"```verus\n{inputs.det_body}\n```\n")

    if inputs.source_excerpt:
        sections.append(
            "## Surrounding source (for lemma names, broadcast groups, helper "
            "spec fns you can reveal/call)\n"
        )
        sections.append(
            f"```verus\n{_clip(inputs.source_excerpt, inputs.max_source_chars)}\n```\n"
        )

    sections.append(_FORMAT_DOC)
    sections.append(_FEW_SHOT)

    if inputs.prior_proof_block is not None and inputs.prior_failure_kind:
        sections.append(_RETRY_HEADER)
        sections.append("### Prior proof block\n")
        sections.append(f"```verus\n{inputs.prior_proof_block}\n```\n")
        sections.append(f"### Failure ({inputs.prior_failure_kind})\n")
        sections.append(f"```\n{inputs.prior_failure_detail or '(no detail)'}\n```\n")

    sections.append(
        "## Your reply\n\n"
        "Emit exactly the two fenced blocks (```verus + ```json). "
        "Do not output anything else.\n"
    )

    return "\n".join(sections)
