"""
Equal-fn policy: how to compare two outputs of a function for "equivalent
enough for determinism". The strict default is field-by-field structural
equality, but for specifications we usually want coarser notions:

* All ``Err`` values are equivalent — the spec rarely pins down which
  concrete error is returned, so two ``Err``s (regardless of code/reason)
  should count as "same outcome".
* Some ``Ok`` values carry opaque payloads (e.g. an allocator returns an
  index / address whose exact value is an implementation detail).
* Struct fields that are opaque state (e.g. an internal cache) should be
  ignored when deciding whether two post-states are equivalent.

The policy object lets us express these rules declaratively. It is consumed
by ``gen_det.build_equal_expr`` / ``_build_equal_fn`` to emit the
``spec fn det_<fn>_equal(...) -> bool`` body.

The generated equal fn is inlined into the same Verus proof file as the
det-check template (no separate review file), so a developer can inspect
and tweak it by reading the rendered proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EqualPolicy:
    """Declarative rules for how to emit per-function structural equality.

    Fields:
        errs_equivalent: if True (default), any two ``Err`` values are
            considered equal — only ``Ok`` is compared down to inner fields.
        opaque_ok: if True, any two ``Ok`` values are considered equal —
            useful when the Ok payload is an opaque handle / index (e.g.
            allocator returning an address).
        ignore_fields: set of struct/view field names to omit from the
            comparison. Applied by *unqualified* field name.
        opaque_types: set of type *names* treated as opaque — any value
            of such a type compares equal. Match is on ``TypeInfo.name``.
        custom_body: if non-empty, use this verbatim as the body of the
            generated equal fn (after the signature). Takes priority over
            all other rules. Typically written by a human reviewer or by
            an LLM hook for cases the heuristics can't cover.
    """
    errs_equivalent: bool = True
    opaque_ok: bool = False
    ignore_fields: set[str] = field(default_factory=set)
    opaque_types: set[str] = field(default_factory=set)
    custom_body: str | None = None

    def to_dict(self) -> dict:
        return {
            "errs_equivalent": self.errs_equivalent,
            "opaque_ok": self.opaque_ok,
            "ignore_fields": sorted(self.ignore_fields),
            "opaque_types": sorted(self.opaque_types),
            "custom_body": self.custom_body,
        }

    @staticmethod
    def from_dict(d: dict | None) -> "EqualPolicy":
        if not d:
            return EqualPolicy()
        return EqualPolicy(
            errs_equivalent=bool(d.get("errs_equivalent", True)),
            opaque_ok=bool(d.get("opaque_ok", False)),
            ignore_fields=set(d.get("ignore_fields") or []),
            opaque_types=set(d.get("opaque_types") or []),
            custom_body=d.get("custom_body"),
        )


def default_policy() -> EqualPolicy:
    """Project-wide default: all Errs are equivalent; Ok is compared strictly."""
    return EqualPolicy(errs_equivalent=True)
