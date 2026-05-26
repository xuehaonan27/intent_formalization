"""Result classification for spec-determinism runs.

The high-level ``status`` field in a result records pipeline outcome
(``ok`` / ``verus_error`` / ``search_error`` / ...). When ``status == "ok"``
the determinism check itself ran successfully, but its semantic verdict
depends on what z3 returned at R0 (no schema narrowing applied):

  * ``r0_z3 == "unsat"`` — the spec is **complete**: it pins the
    function's behaviour to a single observable post-state. Optional
    narrowing may have committed assumes, but those are unused
    refinement attempts.

  * ``r0_z3 == "sat"`` — the spec is **incomplete**: z3 found two
    distinct post-states both satisfying the ensures. Narrowing then
    refined which fields are responsible. ``assumes`` is a *real*
    spec-incompleteness witness. May be intentional (spec uses
    ``|||`` to permit multiple posts) — see ``permitted`` flag.

  * ``r0_z3 == "unknown"`` — z3 surrendered (incomplete quantifiers,
    timeout, etc). Any ``assumes`` recorded by narrowing are unreliable
    because they were built on top of an undecided baseline. Reporting
    these as witnesses is a known false-positive class.

  * ``r0_z3 == ""`` — legacy run from before this field was persisted.
    Empirically (atmosphere/ironkv/memory-allocator replays, 2026-05-14)
    100 % of ``ok`` + ``assumes`` legacy results were R0=unknown, so we
    fall back to that classification.

When the LLM proof loop (:mod:`spec_determinism.llm_proof`) closes an
``unknown`` case by re-running Verus with an LLM-authored proof block,
the driver overwrites ``r0_z3`` with ``"unsat"`` and sets the result key
``llm_assisted=True``. The classifier then yields the dedicated
``complete_llm`` bucket so paper claims can distinguish baseline z3
proofs from LLM-assisted proofs.

This module returns one of:

  * ``"complete"``         — spec pins a unique post (R0=unsat,
                            baseline z3 alone)
  * ``"complete_llm"``     — same, after LLM-authored proof block
  * ``"incomplete"``       — spec admits multiple posts; real
                            nondeterminism witness (R0=sat)
  * ``"ok_inconclusive"``  — undecided (R0=unknown, including legacy)
  * ``"ok_unknown_kind"``  — status==ok but r0_z3 has an unexpected
                            value

Permitted-incompleteness detection
----------------------------------
Some Verus ensures intentionally permit multiple post-states. Two
detectors classify these so paper claims can distinguish spec-design-
intended non-determinism from accidental spec gaps:

  1. :func:`ensures_uses_permissive_or` — structural: ensures uses
     ``|||`` directly *or* via a transitively-referenced ``closed
     spec fn`` body (e.g., IronKV's ``next_delegate_postconditions``).
  2. :data:`REAL_SAT_MANUAL_FNS` + :func:`is_real_sat_manual_function`
     — curated allowlist of spec fns whose ensures permit multiple
     posts by leaving return components unconstrained (no ``|||``
     to detect structurally). Source:
     ``docs/ironkv-real-sat-cases-2026-05-19.en.md``.

Pipeline drivers set ``result["permitted"] = True`` if either detector
fires and ``result["permitted_reason"] in
{"permissive_or", "spec_underconstrained_manual"}``. ``classify_ok``
then promotes ``permitted + r0_z3=="unknown"`` to ``incomplete``
(rationale: spec analysis already established that the spec admits
multiple posts; z3 failing to produce a witness is not counter-
evidence).

Renamed 2026-05-19: old ``ok_proved``/``ok_proved_llm``/``ok_witness``
are now ``complete``/``complete_llm``/``incomplete`` respectively.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional


# Public bucket names — keep stable; tooling, summaries, slides reference them.
BUCKET_COMPLETE = "complete"
BUCKET_COMPLETE_LLM = "complete_llm"
BUCKET_INCOMPLETE = "incomplete"
BUCKET_INCONCLUSIVE = "ok_inconclusive"
BUCKET_UNKNOWN_KIND = "ok_unknown_kind"

# Backwards-compat aliases (still imported from a couple of call sites;
# emit the new strings but keep the old Python names working).
BUCKET_PROVED = BUCKET_COMPLETE
BUCKET_PROVED_LLM = BUCKET_COMPLETE_LLM
BUCKET_WITNESS = BUCKET_INCOMPLETE

OK_BUCKETS = (
    BUCKET_COMPLETE,
    BUCKET_COMPLETE_LLM,
    BUCKET_INCOMPLETE,
    BUCKET_INCONCLUSIVE,
    BUCKET_UNKNOWN_KIND,
)


def classify_ok(result: dict) -> str:
    """Classify an ``ok`` result by its R0 z3 verdict.

    Caller is expected to first check ``result.get("status") == "ok"``.

    Permitted-incompleteness promotion: when ``result["permitted"]`` is
    True (set by the pipeline based on ``ensures_uses_permissive_or`` or
    the curated manual REAL_SAT allowlist), an ``r0_z3 == "unknown"``
    verdict is promoted to ``incomplete`` instead of staying in
    ``ok_inconclusive``. Rationale: the spec analysis has already
    confirmed the spec admits multiple post-states — z3 failing to
    produce a witness is not evidence against that conclusion.
    """
    r0 = result.get("r0_z3", "")
    if r0 == "unsat":
        if result.get("llm_assisted"):
            return BUCKET_COMPLETE_LLM
        return BUCKET_COMPLETE
    if r0 == "sat":
        return BUCKET_INCOMPLETE
    if r0 == "unknown":
        if result.get("permitted"):
            return BUCKET_INCOMPLETE
        return BUCKET_INCONCLUSIVE
    if r0 == "":
        # Legacy run — assumes-bearing maps to inconclusive (empirical),
        # no-assumes maps to complete.
        return BUCKET_INCONCLUSIVE if result.get("assumes") else BUCKET_COMPLETE
    return BUCKET_UNKNOWN_KIND


# --------------------------------------------------------------------------
# Permitted-incompleteness detection (spec uses ``|||``)
# --------------------------------------------------------------------------
#
# Verus syntax: ``|||`` is the "spec OR" delimiter inside an
# expression-block ensures (each branch is a top-level disjunct over the
# post-state). When the top-level ensures uses ``|||`` directly *or* it
# calls a ``[pub] [open|closed] spec fn`` whose body uses ``|||``, the
# spec semantically permits multiple post-states — z3 returning sat/
# unknown is then a known-correct property, not a spec gap.

_PERMISSIVE_OR_RE = re.compile(r"\|\|\|")

# Match an unqualified Rust identifier in call position: ``foo(``.
# We use this to harvest candidate spec-fn names from an ensures text.
_CALLEE_RE = re.compile(r"\b([A-Za-z_][A-Za-z_0-9]*)\s*\(")


# Manual REAL_SAT allowlist: spec fns whose ensures permit multiple
# post-states by leaving return components unconstrained (rather than
# by using ``|||``). These are not detectable by the structural
# ``ensures_uses_permissive_or`` heuristic.
#
# Source: ``docs/ironkv-real-sat-cases-2026-05-19.en.md`` — 5 spec
# functions / 9 instances on the ironkv May-12 viewreg dataset.
# Convention: spec_underconstrained = the spec itself admits the
# nondeterminism (not a pipeline bug).
REAL_SAT_MANUAL_FNS: frozenset[str] = frozenset({
    # delegation_map_v: `ret.1` unconstrained when `ret.0 == true`
    "keys_in_index_range_agree",
    "values_agree",
    # single_delivery_model_v: spec uses set-equality; Vec order free
    "retransmit_un_acked_packets",
    "retransmit_un_acked_packets_for_dst",
    # net_sht_v: `InvalidMessage` branch entirely unconstrained
    "sht_demarshall_data_method",
})

# Project-path substrings used to scope the manual allowlist. Function
# names like ``values_agree`` are common; we only trust the allowlist
# when the source file lives under one of these projects.
_REAL_SAT_PROJECT_HINTS: tuple[str, ...] = ("ironkv",)


def is_real_sat_manual_function(
    function_name: str,
    file_path: str = "",
) -> bool:
    """True iff ``(function_name, file_path)`` is on the manual REAL_SAT
    allowlist.

    Both arguments must agree: the function name must be in
    ``REAL_SAT_MANUAL_FNS`` *and* the file path must contain one of the
    project hints in ``_REAL_SAT_PROJECT_HINTS``. The path scope avoids
    accidentally tagging same-named functions in unrelated projects.

    Pass ``file_path=""`` to opt out of the project-scope check (used
    only by self-tests).
    """
    if function_name not in REAL_SAT_MANUAL_FNS:
        return False
    if not file_path:
        return True
    fp = file_path.lower()
    return any(hint in fp for hint in _REAL_SAT_PROJECT_HINTS)

# Match a spec-fn header like ``pub closed spec fn foo(...) ...``.
# Capture group 1 is the name. We then brace-match to extract the body.
_SPEC_FN_HEADER_RE = re.compile(
    r"(?:pub(?:\([^)]*\))?\s+)?"
    r"(?:open\s+|closed\s+)?"
    r"(?:uninterp\s+)?"
    r"spec\s+fn\s+"
    r"([A-Za-z_][A-Za-z_0-9]*)"
)


def _spec_fn_body(source: str, name: str) -> Optional[str]:
    """Return the body text (between the first ``{`` and matching ``}``)
    of a ``spec fn <name>`` defined in *source*, or ``None`` if the
    function isn't defined / has no body / source is unbalanced."""
    for m in _SPEC_FN_HEADER_RE.finditer(source):
        if m.group(1) != name:
            continue
        # Find the opening brace for the body (skip the parameter list and
        # any ``-> RetType`` clause).
        i = m.end()
        depth_paren = 0
        body_open = -1
        while i < len(source):
            c = source[i]
            if c == "(":
                depth_paren += 1
            elif c == ")":
                depth_paren -= 1
            elif c == "{" and depth_paren == 0:
                body_open = i
                break
            elif c == ";" and depth_paren == 0:
                # uninterp spec fn / forward decl — no body.
                break
            i += 1
        if body_open < 0:
            continue
        # Brace-match the body.
        depth = 0
        for j in range(body_open, len(source)):
            if source[j] == "{":
                depth += 1
            elif source[j] == "}":
                depth -= 1
                if depth == 0:
                    return source[body_open + 1 : j]
        # Unbalanced — give up on this match.
    return None


def ensures_uses_permissive_or(
    ensures_texts: Iterable[str],
    source: str = "",
    *,
    max_depth: int = 4,
) -> bool:
    """Heuristic: ensures uses ``|||`` (direct or via a referenced spec fn).

    Returns ``True`` iff any of:

      1. The literal text of one of *ensures_texts* contains ``|||``.
      2. A ``[open|closed] spec fn`` referenced (transitively, up to
         *max_depth* hops) from the ensures is defined in *source* and
         its body contains ``|||``.

    Conservative on missing sources: when *source* is empty or the
    referenced spec fn isn't defined in *source*, the transitive
    check skips that callee (returns ``False`` for that branch).
    """
    joined = "\n".join(ensures_texts)
    if _PERMISSIVE_OR_RE.search(joined):
        return True
    if not source:
        return False

    seen: set[str] = set()
    queue: list[tuple[str, int]] = [
        (name, 0) for name in _CALLEE_RE.findall(joined)
    ]
    while queue:
        name, depth = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        if depth >= max_depth:
            continue
        body = _spec_fn_body(source, name)
        if body is None:
            continue
        if _PERMISSIVE_OR_RE.search(body):
            return True
        for callee in _CALLEE_RE.findall(body):
            if callee not in seen:
                queue.append((callee, depth + 1))
    return False


# --------------------------------------------------------------------------
# Closed-spec-fn opening (P0 unknowns -> unsat: closed spec fn opacity)
# --------------------------------------------------------------------------
#
# Many ``unknown`` det-check results trace back to ensures of the form
# ``self.foo_postconditions(...)`` where ``foo_postconditions`` is a
# ``pub closed spec fn`` whose body contains the key determinism facts
# (e.g., ``self.constants == pre.constants``). Because the function is
# *closed*, z3 sees only an uninterpreted predicate and cannot derive
# those facts.
#
# The fix: rewrite ``[pub] closed spec fn <name>`` to
# ``#[verifier::opaque] [pub] open spec fn <name>`` for spec fns
# transitively reachable from the target ensures, and emit
# ``reveal(<name>);`` at the top of the det-check proof body. ``open
# spec fn`` is a strict generalisation of ``closed``, so original
# proofs in the same file still hold; ``#[verifier::opaque]`` keeps the
# default opacity intact for any caller that doesn't ``reveal()``.

# Match the ``closed`` modifier on a spec fn header. Capture the
# leading visibility (pub / pub(crate) / blank) in group 1 and the
# function name in group 2. The replacement form is
# ``#[verifier::opaque]\n<vis>open spec fn <name>``.
#
# Note we don't allow ``closed`` to follow ``open`` (mutually exclusive
# in Verus syntax) so a single ``closed`` token is unambiguous.
_CLOSED_SPEC_FN_RE = re.compile(
    r"(?P<lead>(?:^|\n)[ \t]*)"
    r"(?P<vis>(?:pub(?:\([^)]*\))?\s+)?)"
    r"closed\s+spec\s+fn\s+"
    r"(?P<name>[A-Za-z_][A-Za-z_0-9]*)"
)


def reachable_spec_fns(
    ensures_texts: Iterable[str],
    source: str,
    *,
    max_depth: int = 4,
) -> set[str]:
    """Return the set of ``spec fn`` names transitively reachable from
    the ensures texts, restricted to those *defined in* ``source``
    (i.e., ``_spec_fn_body`` returns a body).

    Used by the det-check pipeline to know which closed spec fns to
    open + reveal."""
    joined = "\n".join(ensures_texts)
    seen: set[str] = set()
    reachable: set[str] = set()
    queue: list[tuple[str, int]] = [
        (name, 0) for name in _CALLEE_RE.findall(joined)
    ]
    while queue:
        name, depth = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        if depth >= max_depth:
            continue
        body = _spec_fn_body(source, name)
        if body is None:
            continue
        reachable.add(name)
        for callee in _CALLEE_RE.findall(body):
            if callee not in seen:
                queue.append((callee, depth + 1))
    return reachable


def closed_spec_fns_in(source: str, names: Iterable[str]) -> set[str]:
    """Return the subset of ``names`` that are declared as ``closed
    spec fn`` in ``source`` (so are candidates for the ``closed → opaque
    open`` rewrite)."""
    names = set(names)
    found: set[str] = set()
    for m in _CLOSED_SPEC_FN_RE.finditer(source):
        if m.group("name") in names:
            found.add(m.group("name"))
    return found


# Match an ``impl [<Generics>] <Type> [for <Trait>] { ... }`` header.
# When the "for" clause is present, the *Self* type is the LHS-of-for
# (the implementing type); the RHS is the trait we're implementing.
# When absent, Self IS the first type token (inherent impl).
# We capture the impl-header span up to the opening brace and post-process
# in Python to locate Self vs trait.
_IMPL_HEADER_RE = re.compile(
    r"\bimpl\b"                                # impl keyword
    r"(?:\s*<(?P<generics>[^>]*)>)?"           # optional generics
    r"\s+"
    r"(?P<rest>[^{]+?)"                        # everything up to the brace
    r"\s*\{"
)


def _impl_generic_param_names(generics_text: str) -> set[str]:
    """Extract the BARE generic-parameter names from an ``impl<...>`` clause.

    ``<T, const N: usize, U: Foo>`` -> ``{"T", "N", "U"}``. Lifetimes
    are skipped. Only the identifier preceding ``:`` / ``=`` / ``,`` is
    captured.
    """
    if not generics_text:
        return set()
    out: set[str] = set()
    for part in generics_text.split(","):
        s = part.strip()
        if not s or s.startswith("'"):
            continue
        if s.startswith("const "):
            s = s[len("const "):]
        m = re.match(r"([A-Za-z_][A-Za-z_0-9]*)", s)
        if m:
            out.add(m.group(1))
    return out


def _impl_self_type(rest: str) -> Optional[str]:
    """Given the text between ``impl`` (incl. its generics) and the
    opening ``{``, return the bare Self-type identifier of the impl.

    Inherent impl ``impl Foo<K> { ... }``      -> ``"Foo"``
    Trait impl    ``impl Trait for Foo<K> {}`` -> ``"Foo"``
    """
    s = rest.strip()
    # ``for`` keyword at a word boundary marks a trait impl. Use rsplit
    # so we don't get confused by an earlier ``for`` inside a generic.
    m = re.search(r"\bfor\b", s)
    if m:
        s = s[m.end():].strip()
    # First identifier token in s is the Self type (possibly followed by
    # generic args / trait bounds / lifetime, all of which we strip).
    m2 = re.match(r"([A-Za-z_][A-Za-z_0-9]*)", s)
    return m2.group(1) if m2 else None


def _has_external_body_attr_before(source: str, pos: int) -> bool:
    """Return True if the closest preceding non-whitespace tokens before
    ``pos`` contain ``#[verifier::external_body]``. We scan up to ~160
    chars back (enough to skip another attribute or two)."""
    start = max(0, pos - 160)
    window = source[start:pos]
    # Walk backwards through attribute/whitespace lines. If we hit a
    # non-attribute, non-whitespace token, stop — the attribute (if any)
    # belongs to something else.
    lines = window.splitlines()
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#["):
            if "external_body" in stripped:
                return True
            continue
        # Hit a non-attr token before finding external_body.
        return False
    return False


def _has_opaque_attr_before(source: str, decl_start: int) -> bool:
    """Return True iff a ``#[verifier::opaque]`` attribute is present
    in the attribute-block immediately preceding ``decl_start``.

    Walks back over consecutive attribute lines (and blank lines)
    until a non-attribute line is reached, then returns True if any
    of those attribute lines contain ``opaque``.
    """
    window = source[max(0, decl_start - 240) : decl_start]
    lines = window.splitlines()
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#["):
            if "opaque" in stripped:
                return True
            continue
        return False
    return False


def closed_spec_fn_qualified_names(
    source: str,
    names: Iterable[str],
) -> dict[str, str]:
    """For each name in ``names`` that is declared as a ``closed spec fn``
    in ``source``, return the qualified path Verus needs to ``reveal`` it.

    Free fns (declared at module scope) map to their bare name.
    Impl-method spec fns (declared inside ``impl <Type> {...}``) map
    to ``"<Type>::<name>"``. ``impl Trait for Type`` correctly maps to
    ``<Type>::<name>`` (not ``<Trait>::<name>``).

    Skips declarations annotated with ``#[verifier::external_body]`` —
    their bodies are deliberately opaque (e.g., ``unimplemented!()``)
    and Verus rejects ``#[verifier::opaque]`` on them.

    Also skips declarations with no ``{ body }`` (forward decls / trait
    method signatures inside a ``trait`` block).

    A spec fn is considered to live inside an impl block iff the
    nearest enclosing ``{...}`` opened by an ``impl ... { ... }`` header
    surrounds it (by brace depth).
    """
    names = set(names)
    if not names:
        return {}

    # Pre-compute impl-block ranges: (open_brace_idx, close_brace_idx, self_type)
    impl_blocks: list[tuple[int, int, str]] = []
    # Spans of "skipped" impl blocks (blanket impls where the Self type
    # IS a generic parameter): we drop any closed spec fn declared in
    # one of these spans entirely, since ``T::name`` is not legal at
    # module scope and a bare ``name`` would also resolve incorrectly.
    skipped_impl_spans: list[tuple[int, int]] = []
    for m in _IMPL_HEADER_RE.finditer(source):
        self_ty = _impl_self_type(m.group("rest"))
        if self_ty is None:
            continue
        # Brace-match to find the matching close.
        open_idx = m.end() - 1
        depth = 0
        close_idx = -1
        for j in range(open_idx, len(source)):
            if source[j] == "{":
                depth += 1
            elif source[j] == "}":
                depth -= 1
                if depth == 0:
                    close_idx = j
                    break
        if close_idx <= 0:
            continue
        # Blanket impl ``impl<T: Foo> Bar for T``: the Self type IS a
        # generic parameter. We cannot emit ``T::name`` in a reveal
        # because ``T`` is not in scope at the det-check call site,
        # and the bare ``name`` would resolve incorrectly (or not at
        # all). Record the block's span so we can drop decls inside.
        impl_generics = _impl_generic_param_names(m.group("generics") or "")
        if self_ty in impl_generics:
            skipped_impl_spans.append((open_idx, close_idx))
            continue
        impl_blocks.append((open_idx, close_idx, self_ty))

    def _is_in_skipped_impl(pos: int) -> bool:
        return any(o < pos < c for (o, c) in skipped_impl_spans)

    def _enclosing_impl_type(pos: int) -> Optional[str]:
        candidates = [
            (open_, close_, ty)
            for (open_, close_, ty) in impl_blocks
            if open_ < pos < close_
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[1] - x[0])
        return candidates[0][2]

    out: dict[str, str] = {}
    for m in _CLOSED_SPEC_FN_RE.finditer(source):
        name = m.group("name")
        if name not in names or name in out:
            continue
        # Skip declarations inside blanket impls (``impl<T: Foo> Bar for T``):
        # neither ``T::name`` nor bare ``name`` resolve correctly at the
        # det-check call site.
        if _is_in_skipped_impl(m.start("name")):
            continue
        # Skip if marked external_body — has no real Verus-visible body.
        if _has_external_body_attr_before(source, m.start()):
            continue
        # Skip if there's no body block (forward decl in a trait).
        if _spec_fn_body(source, name) is None:
            continue
        ty = _enclosing_impl_type(m.start("name"))
        out[name] = f"{ty}::{name}" if ty else name
    return out


def rewrite_closed_to_opaque(
    source: str,
    names: Iterable[str],
) -> str:
    """Inject ``#[verifier::opaque]`` on top of each ``[pub] closed
    spec fn <name>`` declaration in ``names``. Returns the modified
    source text.

    Critically, we **do not** rewrite ``closed`` to ``open``. Verus
    requires ``open spec fn`` to be ``pub`` (otherwise: "function is
    marked `open` but not marked `pub`"), but ``pub open spec fn``
    requires the body to be well-formed at every external call site
    — which fails when the body references module-private fields
    (e.g. ``self.delegation_map`` on a struct whose fields are
    pkg-private). Verus does, however, accept
    ``#[verifier::opaque] pub closed spec fn``: the body is closed
    by default (preserving the visibility invariant) but can be
    revealed inside our injected det-check proof with
    ``reveal(<qualified_name>);``.

    Idempotent: skips declarations already preceded by an
    ``#[verifier::opaque]`` attribute (the regex match still fires,
    but ``_already_has_opaque_attr_before`` returns True). Idempotent
    by inspection of the immediate preceding attribute line(s).

    Skips declarations annotated with ``#[verifier::external_body]``
    — Verus rejects ``#[verifier::opaque]`` on those. Also skips
    declarations with no ``{ body }`` (forward decls in trait blocks
    — also rejected by ``#[verifier::opaque]``).

    The injected ``#[verifier::opaque]`` attribute is placed on its
    own line preceding the original modifier, matching the ironkv
    convention (see e.g.
    ``host_impl_v__impl2__real_init_impl.rs:1110``).
    """
    names = set(names)
    if not names:
        return source

    def _sub(m: "re.Match[str]") -> str:
        if m.group("name") not in names:
            return m.group(0)
        # Skip external_body decls (Verus rejects opaque on them).
        if _has_external_body_attr_before(source, m.start()):
            return m.group(0)
        # Skip if already annotated opaque (idempotency).
        if _has_opaque_attr_before(source, m.start()):
            return m.group(0)
        # Skip bodyless forward decls.
        if _spec_fn_body(source, m.group("name")) is None:
            return m.group(0)
        lead = m.group("lead")
        vis = m.group("vis")
        name = m.group("name")
        prefix_newline = "\n" if lead.startswith("\n") else ""
        prefix_indent = lead.lstrip("\n")
        return (
            f"{prefix_newline}{prefix_indent}#[verifier::opaque]"
            f"\n{prefix_indent}{vis}closed spec fn {name}"
        )

    return _CLOSED_SPEC_FN_RE.sub(_sub, source)


# ----------------------------- self-tests --------------------------------

def _selftest_classify() -> None:
    cases = [
        ({"status": "ok", "r0_z3": "unsat"}, BUCKET_COMPLETE),
        ({"status": "ok", "r0_z3": "unsat", "llm_assisted": True}, BUCKET_COMPLETE_LLM),
        ({"status": "ok", "r0_z3": "sat"}, BUCKET_INCOMPLETE),
        ({"status": "ok", "r0_z3": "unknown"}, BUCKET_INCONCLUSIVE),
        # permitted promotes unknown → incomplete
        ({"status": "ok", "r0_z3": "unknown", "permitted": True}, BUCKET_INCOMPLETE),
        # permitted does NOT affect unsat (still complete)
        ({"status": "ok", "r0_z3": "unsat", "permitted": True}, BUCKET_COMPLETE),
        ({"status": "ok", "r0_z3": "", "assumes": ["x"]}, BUCKET_INCONCLUSIVE),
        ({"status": "ok", "r0_z3": ""}, BUCKET_COMPLETE),
        ({"status": "ok", "r0_z3": "bogus"}, BUCKET_UNKNOWN_KIND),
    ]
    for r, want in cases:
        got = classify_ok(r)
        assert got == want, f"classify({r}) -> {got}, want {want}"


def _selftest_real_sat_manual() -> None:
    # On the allowlist + ironkv path → True.
    assert is_real_sat_manual_function(
        "values_agree",
        "/abs/verusage/source-projects/ironkv/verified/x.rs",
    ) is True
    # On the allowlist but unrelated project → False (project guard).
    assert is_real_sat_manual_function(
        "values_agree",
        "/abs/verusage/source-projects/atmosphere/verified/x.rs",
    ) is False
    # Not on the allowlist → False regardless of path.
    assert is_real_sat_manual_function(
        "some_other_fn",
        "/abs/ironkv/x.rs",
    ) is False
    # Empty path opts out of project guard (self-tests only).
    assert is_real_sat_manual_function("keys_in_index_range_agree", "") is True
    assert is_real_sat_manual_function("nonsense", "") is False


def _selftest_permitted_or() -> None:
    # Direct ||| in ensures.
    assert ensures_uses_permissive_or(["a ||| b"]) is True
    # No ||| anywhere.
    assert ensures_uses_permissive_or(["a && b"]) is False
    # || (boolean OR, not Verus spec-OR) does NOT trigger.
    assert ensures_uses_permissive_or(["a || b"]) is False

    # Transitive via single-hop closed spec fn.
    source = """
        pub closed spec fn p(x: T) -> bool {
            ||| a(x) ||| b(x)
        }
    """
    assert ensures_uses_permissive_or(["self.p(x)"], source) is True

    # Transitive over two hops.
    source2 = """
        pub closed spec fn p(x: T) -> bool { q(x) }
        pub open spec fn q(x: T) -> bool { ||| a(x) ||| b(x) }
    """
    assert ensures_uses_permissive_or(["self.p(x)"], source2) is True

    # uninterp spec fn — has no body, must not crash.
    source3 = "pub uninterp spec fn p(x: T) -> bool;\n"
    assert ensures_uses_permissive_or(["self.p(x)"], source3) is False

    # max_depth bound respected (no |||).
    source4 = """
        pub closed spec fn p(x: T) -> bool { q(x) }
        pub closed spec fn q(x: T) -> bool { r(x) }
        pub closed spec fn r(x: T) -> bool { s(x) }
        pub closed spec fn s(x: T) -> bool { true && false }
    """
    assert ensures_uses_permissive_or(["self.p(x)"], source4) is False

    # Conservative: missing source returns False even with callee.
    assert ensures_uses_permissive_or(["self.p(x)"], "") is False


def _selftest_reachable_and_rewrite() -> None:
    # reachable_spec_fns: single-hop reaches p, two-hop reaches p+q.
    source = """
        pub closed spec fn p(x: T) -> bool { q(x) && r(x) }
        pub open spec fn q(x: T) -> bool { true }
        pub closed spec fn r(x: T) -> bool { s(x) }
        pub open spec fn s(x: T) -> bool { true }
        pub closed spec fn unrelated(x: T) -> bool { true }
    """
    reach = reachable_spec_fns(["self.p(x)"], source, max_depth=4)
    assert reach == {"p", "q", "r", "s"}, reach
    assert "unrelated" not in reach

    # closed_spec_fn_qualified_names: free fns map to bare names.
    qual = closed_spec_fn_qualified_names(source, reach)
    assert qual == {"p": "p", "r": "r"}, qual

    # rewrite_closed_to_opaque: rewrites the closed fns we asked for.
    rewritten = rewrite_closed_to_opaque(source, set(qual.keys()))
    assert "#[verifier::opaque]" in rewritten
    # The decl stays ``pub closed spec fn``; only the attr is added.
    assert "pub closed spec fn p" in rewritten
    assert "pub closed spec fn r" in rewritten
    # ``q`` was already open; left alone (no attr injected).
    assert rewritten.count("#[verifier::opaque]") == 2
    # ``unrelated`` is still closed and unannotated.
    assert "closed spec fn unrelated" in rewritten

    # Idempotent: re-applying does nothing extra.
    rewritten2 = rewrite_closed_to_opaque(rewritten, set(qual.keys()))
    assert rewritten2 == rewritten

    # Empty names set is a no-op.
    assert rewrite_closed_to_opaque(source, set()) == source

    # Pub-modifier is preserved (needed for ``pub closed`` to compile
    # AND for ``reveal()`` to find the qualified path).
    src_pub_crate = "    pub(crate) closed spec fn foo(x: T) -> bool { true }\n"
    out = rewrite_closed_to_opaque(src_pub_crate, {"foo"})
    assert "pub(crate) closed spec fn foo" in out
    assert "#[verifier::opaque]" in out

    # Impl-method closed spec fns get the Type::name qualified path.
    src_impl = """
        struct Foo {}
        impl Foo {
            pub closed spec fn bar(&self) -> bool { true }
        }
        pub closed spec fn free_fn(x: T) -> bool { true }
    """
    qual2 = closed_spec_fn_qualified_names(src_impl, {"bar", "free_fn"})
    assert qual2 == {"bar": "Foo::bar", "free_fn": "free_fn"}, qual2

    # Generic impl with bare type token.
    src_generic = """
        impl<K: Trait> StrictlyOrderedMap<K> {
            pub closed spec fn valid(&self) -> bool { true }
        }
    """
    qual3 = closed_spec_fn_qualified_names(src_generic, {"valid"})
    assert qual3 == {"valid": "StrictlyOrderedMap::valid"}, qual3

    # impl ... for Trait syntax: capture the SELF type, not the trait.
    src_trait_impl = """
        impl View for HostState {
            closed spec fn view(&self) -> AbstractHostState { todo!() }
        }
    """
    qual4 = closed_spec_fn_qualified_names(src_trait_impl, {"view"})
    assert qual4 == {"view": "HostState::view"}, qual4

    # external_body and bodyless decls are skipped.
    src_external = """
        #[verifier::external_body]
        pub closed spec fn opaque_fn(x: T) -> bool {
            unimplemented!()
        }
        pub trait MyTrait {
            closed spec fn no_body(&self) -> bool;
        }
        pub closed spec fn real_fn(x: T) -> bool { true }
    """
    qual5 = closed_spec_fn_qualified_names(
        src_external, {"opaque_fn", "no_body", "real_fn"}
    )
    assert qual5 == {"real_fn": "real_fn"}, qual5

    # Rewrite respects the same filter: external_body / no-body decls
    # are not rewritten.
    out5 = rewrite_closed_to_opaque(
        src_external, {"opaque_fn", "no_body", "real_fn"}
    )
    assert "closed spec fn opaque_fn" in out5
    assert "closed spec fn no_body" in out5
    assert "pub closed spec fn real_fn" in out5
    assert "#[verifier::opaque]" in out5


def _selftest() -> None:
    _selftest_classify()
    _selftest_real_sat_manual()
    _selftest_permitted_or()
    _selftest_reachable_and_rewrite()
    print("classify self-tests PASS")


if __name__ == "__main__":
    _selftest()
