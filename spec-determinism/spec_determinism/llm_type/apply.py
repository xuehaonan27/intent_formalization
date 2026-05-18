"""Tier 1.5 — apply LLM-produced type patches to a ``FunctionSpec``.

A ``TypePatch`` is the structured form of one entry in the LLM's JSON
output. ``apply_patches`` converts each patch into a :class:`TypeInfo`
(via :func:`parse_type_str` for nested type expressions), inserts the
result into ``spec.type_defs``, and re-runs ``_substitute`` over every
reachable slot so dependent fields point at the new defs.

The applier is idempotent — applying the same patch twice produces the
same state. It also tolerates partial patches: if ``fields`` are omitted
on a struct, the struct gets ``fields=[]`` (the gen_det STRUCT branch
then routes through ``spec_view`` if available, or falls back to ``==``).

Soundness contract
------------------
Patches are *additive*: they only insert into ``type_defs``. They never
modify an entry that ``extract_spec`` already populated. If a patch tries
to overwrite an existing TypeInfo, the apply is rejected and reported in
the per-patch result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from spec_determinism.extract.types import (
    FieldInfo,
    FunctionSpec,
    TypeInfo,
    TypeKind,
    VariantInfo,
)

from .parse import parse_type_str


@dataclass
class TypePatch:
    """One LLM-proposed addition to ``spec.type_defs``."""
    name: str                                              # bare type name
    kind: str                                              # "struct" | "enum"
    type_params: list[str] = field(default_factory=list)   # e.g. ["V"]
    # struct: list[(field_name, type_str)]
    fields: list[tuple[str, str]] = field(default_factory=list)
    # enum: list[(variant_name, list_of_inner_type_strs)]
    variants: list[tuple[str, list[str]]] = field(default_factory=list)
    spec_view_type_str: Optional[str] = None
    # evidence
    source_rel_path: str = ""
    source_line: int = 0
    source_snippet: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "type_params": list(self.type_params),
            "fields": [
                {"name": fn, "type_str": ts} for fn, ts in self.fields
            ],
            "variants": [
                {"name": vn, "inner_types_str": list(its)}
                for vn, its in self.variants
            ],
            "spec_view": (
                {"type_str": self.spec_view_type_str}
                if self.spec_view_type_str else None
            ),
            "source_evidence": {
                "rel_path": self.source_rel_path,
                "line": self.source_line,
                "snippet": self.source_snippet,
            },
        }

    @staticmethod
    def from_dict(d: dict) -> "TypePatch":
        ev = d.get("source_evidence") or {}
        return TypePatch(
            name=d["name"],
            kind=d["kind"],
            type_params=list(d.get("type_params") or []),
            fields=[
                (f["name"], f["type_str"])
                for f in (d.get("fields") or [])
            ],
            variants=[
                (v["name"], list(v.get("inner_types_str") or []))
                for v in (d.get("variants") or [])
            ],
            spec_view_type_str=(
                (d.get("spec_view") or {}).get("type_str")
            ),
            source_rel_path=ev.get("rel_path", "") or d.get("source_rel_path", ""),
            source_line=int(ev.get("line", 0) or d.get("source_line", 0)),
            source_snippet=ev.get("snippet", "") or d.get("source_snippet", ""),
        )


@dataclass
class ApplyResult:
    """Per-patch outcome from :func:`apply_patches`."""
    name: str
    accepted: bool
    reason: str = ""             # populated when accepted=False


def _patch_to_typeinfo(p: TypePatch) -> TypeInfo:
    """Convert a TypePatch into a TypeInfo (raises ValueError on bad type_str)."""
    if p.kind == "struct":
        fields = []
        for fn, ts in p.fields:
            fields.append(FieldInfo(name=fn, type=parse_type_str(ts)))
        info = TypeInfo(kind=TypeKind.STRUCT, name=p.name, fields=fields)
    elif p.kind == "enum":
        variants = []
        for vn, inner_strs in p.variants:
            if not inner_strs:
                variants.append(VariantInfo(name=vn, inner=None))
                continue

            # Detect struct-like (named-field) variants: inner entries shaped
            # ``name: type``. Either every entry is named or none are; mixing
            # is a structural error. We tolerate both forms because the LLM
            # legitimately uses ``name: type`` for Rust struct-like variants
            # (``enum E { V { f: T, ... } }``).
            named_pairs: list[tuple[str, str]] = []
            tuple_strs: list[str] = []
            for entry in inner_strs:
                e = entry.strip()
                # naive split on first `:` not inside generics
                depth = 0
                cut = -1
                for i, ch in enumerate(e):
                    if ch == "<":
                        depth += 1
                    elif ch == ">":
                        depth -= 1
                    elif ch == ":" and depth == 0:
                        cut = i
                        break
                if cut >= 0 and e[:cut].strip().isidentifier():
                    named_pairs.append(
                        (e[:cut].strip(), e[cut + 1:].strip())
                    )
                else:
                    tuple_strs.append(e)

            if named_pairs and not tuple_strs:
                # struct-like variant → synthetic struct with named fields
                tuple_fields = [
                    FieldInfo(name=fn, type=parse_type_str(ts))
                    for fn, ts in named_pairs
                ]
                inner = TypeInfo(
                    kind=TypeKind.STRUCT,
                    name=f"{p.name}::{vn}",
                    fields=tuple_fields,
                )
                variants.append(VariantInfo(name=vn, inner=inner))
            elif tuple_strs and not named_pairs:
                if len(tuple_strs) == 1:
                    variants.append(
                        VariantInfo(name=vn, inner=parse_type_str(tuple_strs[0]))
                    )
                else:
                    tuple_fields = [
                        FieldInfo(name=str(i), type=parse_type_str(ts))
                        for i, ts in enumerate(tuple_strs)
                    ]
                    inner = TypeInfo(
                        kind=TypeKind.STRUCT,
                        name=f"({', '.join(tuple_strs)})",
                        fields=tuple_fields,
                    )
                    variants.append(VariantInfo(name=vn, inner=inner))
            else:
                raise ValueError(
                    f"enum variant {vn!r} of {p.name!r} mixes named and "
                    f"tuple inner entries: {inner_strs}"
                )
        info = TypeInfo(kind=TypeKind.ENUM, name=p.name, variants=variants)
    else:
        raise ValueError(f"TypePatch.kind must be 'struct' or 'enum', got {p.kind!r}")

    if p.spec_view_type_str:
        info.spec_view = parse_type_str(p.spec_view_type_str)
    return info


def _substitute(ti: TypeInfo, type_defs: dict[str, TypeInfo]) -> TypeInfo:
    """Mirror of extractor._substitute: replace UNKNOWN-kind references whose
    bare-name is now in ``type_defs`` with the resolved TypeInfo. Mutates
    nested slots in-place; returns top-level replacement when applicable."""
    bare = ti.name.split("<", 1)[0] if "<" in ti.name else ti.name
    if ti.kind == TypeKind.UNKNOWN and bare in type_defs:
        # Replace with the resolved def. Note: we keep the original name
        # (with type args, e.g. "HashMap<u8>") so downstream call sites
        # that re-stringify still see the instantiated form.
        resolved = type_defs[bare]
        if resolved.name == ti.name:
            return resolved
        # Shallow-copy and rename so other references to the same bare
        # name with different type args don't trample each other.
        copy = TypeInfo(
            kind=resolved.kind,
            name=ti.name,
            fields=list(resolved.fields),
            variants=list(resolved.variants),
            type_args=list(ti.type_args),
            spec_view=resolved.spec_view,
        )
        return copy

    ti.type_args = [_substitute(ta, type_defs) for ta in ti.type_args]
    for f in ti.fields:
        f.type = _substitute(f.type, type_defs)
    for v in ti.variants:
        if v.inner is not None:
            v.inner = _substitute(v.inner, type_defs)
    if ti.spec_view is not None:
        ti.spec_view = _substitute(ti.spec_view, type_defs)
    return ti


def apply_patches(
    spec: FunctionSpec,
    patches: list[TypePatch],
) -> list[ApplyResult]:
    """Apply each patch to ``spec.type_defs`` in-place. Returns per-patch
    outcomes; the caller decides what to do with rejections."""
    results: list[ApplyResult] = []

    for p in patches:
        bare = p.name.split("<", 1)[0]
        if bare in spec.type_defs and spec.type_defs[bare].kind != TypeKind.UNKNOWN:
            results.append(ApplyResult(
                name=p.name, accepted=False,
                reason=f"{bare!r} already in type_defs as "
                       f"kind={spec.type_defs[bare].kind.value} — refusing to overwrite",
            ))
            continue
        try:
            ti = _patch_to_typeinfo(p)
        except ValueError as e:
            results.append(ApplyResult(
                name=p.name, accepted=False,
                reason=f"type_str parse failed: {e}",
            ))
            continue
        spec.type_defs[bare] = ti
        results.append(ApplyResult(name=p.name, accepted=True))

    # Re-substitute reachable slots so dependent fields point at the new defs.
    for param in spec.params:
        param.type = _substitute(param.type, spec.type_defs)
    spec.return_type = _substitute(spec.return_type, spec.type_defs)
    for td in list(spec.type_defs.values()):
        _substitute(td, spec.type_defs)

    return results


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    from spec_determinism.extract.types import (
        Param, TypeInfo as TI, TypeKind as TK,
    )

    spec = FunctionSpec(
        name="f",
        params=[
            Param(name="h", type=TI(TK.UNKNOWN, "HashMap<u8>")),
            Param(name="m", type=TI(TK.UNKNOWN, "CSingleMessage")),
        ],
        return_type=TI(TK.UNIT, "()"),
        requires=[], ensures=[],
        type_defs={},
    )

    patches = [
        TypePatch(
            name="HashMap", kind="struct", type_params=["V"],
            fields=[("m", "u8")],
            spec_view_type_str="Map<EndPoint, V>",
            source_rel_path="src/host.rs", source_line=164,
            source_snippet="pub uninterp spec fn view(self) -> Map<EndPoint, V>;",
        ),
        TypePatch(
            name="CSingleMessage", kind="enum",
            variants=[
                ("Message", ["u64", "EndPoint", "CMessage"]),
                ("Ack", ["u64"]),
                ("InvalidMessage", []),
            ],
            source_rel_path="src/single_delivery.rs", source_line=1081,
            source_snippet="pub enum CSingleMessage {",
        ),
    ]
    results = apply_patches(spec, patches)

    ok = True
    if not all(r.accepted for r in results):
        print(f"FAIL: not all patches accepted: {results}")
        ok = False

    # type_defs now has both
    hm = spec.type_defs.get("HashMap")
    csm = spec.type_defs.get("CSingleMessage")
    if hm is None or hm.kind != TypeKind.STRUCT:
        print(f"FAIL: HashMap not added as struct: {hm}")
        ok = False
    if csm is None or csm.kind != TypeKind.ENUM:
        print(f"FAIL: CSingleMessage not added as enum: {csm}")
        ok = False

    # HashMap.spec_view is Map
    if hm and (hm.spec_view is None or hm.spec_view.kind != TypeKind.MAP):
        print(f"FAIL: HashMap.spec_view should be Map, got {hm.spec_view}")
        ok = False

    # CSingleMessage variants
    if csm and len(csm.variants) != 3:
        print(f"FAIL: CSingleMessage has {len(csm.variants)} variants, want 3")
        ok = False

    # Param[0].type was substituted: 'h: HashMap<u8>' should now point at
    # resolved STRUCT with the bare-name -> resolved-typeinfo lookup
    p0_type = spec.params[0].type
    if p0_type.kind != TypeKind.STRUCT:
        print(f"FAIL: param h.type should be STRUCT, got {p0_type.kind}")
        ok = False

    # Idempotent: applying again rejects (already in type_defs as STRUCT)
    results2 = apply_patches(spec, patches)
    if not all(not r.accepted for r in results2):
        print(f"FAIL: re-apply should reject all; got {results2}")
        ok = False

    # to_dict / from_dict round-trip (now matches LLM schema)
    p_dict = patches[0].to_dict()
    rt = TypePatch.from_dict(p_dict)
    if rt.name != patches[0].name or rt.fields != patches[0].fields:
        print(f"FAIL: round-trip from_dict differs: {rt}")
        ok = False
    if rt.spec_view_type_str != patches[0].spec_view_type_str:
        print(f"FAIL: round-trip spec_view_type_str differs")
        ok = False

    print("apply self-test:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
