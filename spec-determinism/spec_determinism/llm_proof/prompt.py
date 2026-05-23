"""Prompt construction for the LLM proof loop.

The prompt has four sections:

  1. **Task**: explain that the LLM is closing a z3 ``unknown`` on a
     synthetic determinism postcondition.
  2. **The function under analysis**: signature, requires, ensures,
     and the body of the synthetic ``det_<f>`` proof fn (so the LLM
     sees the *exact* postcondition it must discharge).
  3. **Output format**: ```verus block of statements + optional
     ```verus_lemmas block (Pattern A helper proof fn declarations) +
     ```json rationale.
  4. **Allowlist** + few-shot examples derived from atmosphere's
     ``set_owning_container`` case study + Pattern C hints listing
     any relational spec fns reachable from the ensures.

On retry (when a previous attempt failed Verus or violated the sandbox),
we append a 5th section with the prior attempt + the failure tail
(stderr / sandbox violations), so the LLM can self-correct.
"""
from __future__ import annotations

import re
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
ensures clauses have disjoint triggers, so z3 never lines them up), or
a missing functional-uniqueness lemma for some relational spec fn that
the ensures references.

Your job is to write a *small* block of Verus statements that, when
prepended to the body of the synthetic `det_<f>` proof fn, lets Verus
verify the postcondition. Verus will check every statement you write —
nothing in your block can be unsound.

You **may** also emit module-scope helper lemmas in a separate block
(see "Output format" below). This is useful when the proof needs a
non-trivial functional-uniqueness lemma — e.g. "given two outputs both
satisfying a relational spec fn, they are equal" — that is too long
to inline.
"""


_FORMAT_DOC = """\
## Output format

Emit (in order):

1. **Optional**: a ```verus_lemmas fenced block containing one or more
   module-scope `proof fn lemma_<name>(...)` declarations that will be
   spliced into the file next to `det_<f>`. Use this when you need a
   lemma — for example a functional-uniqueness lemma — that is too
   large to inline into the prelude. Constraints:
     * Each declaration MUST start with `proof fn lemma_` and a
       descriptive name (e.g. `lemma_sorted_insert_unique_pos`).
     * Same allowlist as the prelude — no `assume` / `admit` / etc.
     * Lemma bodies may use `assert`, `assert ... by`, `reveal`,
       `broadcast use`, lemma calls, plain control flow, and
       `assert forall ... by { ... }`.
   When you don't need a helper, omit this block entirely.

2. A ```verus fenced block whose body is the proof prelude. It will be
   inserted at the top of `proof fn det_<f>(...) { ... }`, before the
   schema-assume scaffolding that the pipeline appends. So you have:
     * `r1`, `r2` in scope (the two candidate results)
     * any inputs / `self` parameters in scope (consult the signature)
     * every requires / ensures from the original function as hypotheses
     * any lemma you declared in the `verus_lemmas` block is callable
       by name.
   You may write: `assert`, `assert ... by`, `assert forall|x| ... by`,
   `reveal(spec_fn)`, `broadcast use group_xyz`, calls to existing
   `lemma_*` functions, plain `let` / `if` / `match`, and inline
   `proof { ... }` blocks.
   Multi-statement is fine.

3. A ```json fenced block with `{"rationale": "<one or two sentences>"}`.

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

Additional rule for the prelude block (the inline `verus` block):
  * No new `fn` / `spec fn` / `proof fn` / `exec fn` definitions inside
    the prelude — stick to *statements that live inside an existing
    proof body*. If you need a helper proof fn, put it in the
    `verus_lemmas` block.

For the optional `verus_lemmas` block:
  * Only `proof fn lemma_<name>(...)` declarations. No exec / spec /
    open / closed fn declarations. No `struct` / `enum` / `trait` /
    `impl` / `type` items.
"""


_FEW_SHOT = """\
## Example 1 — closing a two-`forall` trigger gap (atmosphere `set_owning_container`)

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

## Example 2 — closing a relational spec fn via a helper functional-uniqueness lemma

Suppose the ensures references a `closed spec fn step(pre: S, post: S, in: I, out: O) -> bool`
that pins `(post, out)` *implicitly* given `(pre, in)`. The pipeline already
reveals the body of `step`, so the LLM sees its definition. The proof prelude
alone is too verbose; instead emit a module-scope lemma:

```verus_lemmas
proof fn lemma_step_functional(pre: S, in_: I, post1: S, out1: O, post2: S, out2: O)
    requires
        step(pre, post1, in_, out1),
        step(pre, post2, in_, out2),
    ensures
        post1 == post2,
        out1 == out2,
{
    reveal(step);
    // ... case-split / forall instantiation here, every step asserted ...
}
```

```verus
// Apply the helper, then case-split on the discriminator the spec actually pinned.
lemma_step_functional(*old(self), input, r1.0, r1.1, r2.0, r2.1);
assert(r1 == r2);
```

```json
{"rationale": "Step is functional in (pre, input). Derive the per-component equalities from one lemma call."}
```

Notice: every `assert` is something Verus must verify; the helper
lemma's body is also fully checked. Nothing is asserted on faith.
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


# ---------------------------------------------------------------------------
# Pattern C: scan reachable spec fns from ensures for relational shapes.
# ---------------------------------------------------------------------------
# Heuristic for "relational" spec fn: signature has *more than one* "result-
# carrying" parameter — typically a state pair `pre, post` and/or an output
# `out`. We look for spec fns whose ensures clause (or reveal target) appears
# in the det_spec.opened_closed_specs / source_excerpt, and pick out
# signatures that look like `fn name(pre: S, post: S, in: I, out: O) -> bool`.
# This is a hint, not a guarantee — the LLM is free to ignore.

_REL_SPEC_FN_RE = re.compile(
    r"(?P<vis>pub\s+)?(?:open\s+|closed\s+)?spec(?:\(\s*checked\s*\))?\s+fn\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?:<[^>]*>)?\s*"
    r"\((?P<params>[^)]*)\)\s*"
    r"->\s*bool",
    re.DOTALL,
)


def _scan_relational_specs(source: str) -> list[tuple[str, str]]:
    """Return a list of ``(name, signature_snippet)`` for relational spec fns.

    A spec fn is considered "relational" when its parameter list contains
    at least one identifier matching the heuristic markers ``pre`` / ``post`` /
    ``s1`` / ``s2`` / ``out`` / ``output``, or when it has 3+ non-self params
    (the typical state-machine step signature ``step(pre, post, in, out)``).
    Empty result is fine — the section is omitted from the prompt then.
    """
    if not source:
        return []
    seen: set[str] = set()
    hints: list[tuple[str, str]] = []
    for m in _REL_SPEC_FN_RE.finditer(source):
        name = m.group("name")
        if name in seen:
            continue
        params = m.group("params") or ""
        param_list = [p.strip() for p in params.split(",") if p.strip()]
        param_names = [p.split(":", 1)[0].strip() for p in param_list]
        markers = {"pre", "post", "s1", "s2", "out", "output", "post1", "post2"}
        is_rel = bool(set(param_names) & markers) or len(param_list) >= 3
        if not is_rel:
            continue
        # One-line summary: `name(params)`
        sig = f"{name}({params.strip()})"
        hints.append((name, sig))
        seen.add(name)
        if len(hints) >= 8:
            break
    return hints


def _relational_specs_section(source: str) -> str:
    """Build the Pattern C "suggested helper lemmas" section, or empty."""
    rel = _scan_relational_specs(source)
    if not rel:
        return ""
    lines = [
        "## Suggested helper lemmas (Pattern C — relational spec fns detected)\n",
        "The function's reachable spec fns include the relational signatures",
        "below. Each one is *likely* functional in the (state-in, input) side —",
        "i.e. if both `(post1, out1)` and `(post2, out2)` satisfy the relation",
        "given the same input, then they are equal. If z3 can't directly close",
        "the obligation, consider emitting a helper lemma like:",
        "",
        "```",
        "proof fn lemma_<name>_functional(...args...)",
        "    requires <name>(args, post1, out1), <name>(args, post2, out2)",
        "    ensures post1 == post2 && out1 == out2",
        "{ /* case-split on the discriminator, reveal closed fns, etc. */ }",
        "```",
        "",
        "Detected relational spec fns:",
    ]
    for name, sig in rel:
        lines.append(f"  - `{sig}`")
    lines.append("")
    return "\n".join(lines)


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

    rel_section = _relational_specs_section(inputs.source_excerpt)
    if rel_section:
        sections.append(rel_section)

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
        "Emit the ```verus + (optional ```verus_lemmas) + ```json fenced blocks. "
        "Do not output anything else.\n"
    )

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> None:
    # Pattern C relational scanner: state-machine step fn matches.
    src = """
verus! {
pub closed spec fn host_step(pre: HostState, post: HostState,
                              input: Packet, out: bool) -> bool {
    true
}

pub open spec fn is_empty(s: Seq<int>) -> bool { s.len() == 0 }

pub closed spec(checked) fn next_get_request(
    pre: HostState, post: HostState, pkt: Packet
) -> bool { true }
}
"""
    rel = _scan_relational_specs(src)
    names = [n for n, _ in rel]
    assert "host_step" in names, names
    assert "next_get_request" in names, names
    assert "is_empty" not in names, "is_empty is not relational"

    sec = _relational_specs_section(src)
    assert "host_step(" in sec, sec
    assert "lemma_<name>_functional" in sec

    # No source -> no section
    assert _relational_specs_section("") == ""

    # Build_proof_prompt ends with the "Your reply" footer & contains
    # the Pattern A description.
    from spec_determinism.extract.types import DetCheckSpec
    ds = DetCheckSpec(
        function="foo",
        det_check_template="proof fn det_foo() {}",
        symbols=[],
        equal_fn_def="spec fn det_foo_equal(r1: int, r2: int) -> bool { r1 == r2 }",
        equal_fn_name="det_foo_equal",
    )
    prompt = build_proof_prompt(PromptInputs(
        det_spec=ds, det_body="proof fn det_foo() {}", source_excerpt=src,
    ))
    assert "verus_lemmas" in prompt, "Pattern A docs missing"
    assert "Suggested helper lemmas" in prompt, "Pattern C section missing"
    assert "Your reply" in prompt

    print("prompt self-test: PASS")


if __name__ == "__main__":
    _self_test()
