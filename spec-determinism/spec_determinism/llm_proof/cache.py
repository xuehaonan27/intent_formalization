"""Persistent cache for LLM-authored Verus proof annotations.

The LLM proof loop (:mod:`spec_determinism.llm_proof.prover`) is
expensive — each call to the Copilot CLI takes 30-60 s, and the corpus
has hundreds of ``ok_inconclusive`` targets. Most reruns recompute the
same prompts and would benefit from a cache.

Cache key
---------
We key by **the inputs to the prompt**, not the prompt text itself:
that way upgrades to the prompt template don't invalidate cached
proofs. Specifically we hash:

  * ``det_spec.to_json()``   — function name, equal-fn def, det-check
    template, schema params. Captures the proof obligation exactly.
  * ``source.strip()``       — original Rust source, so a change to
    the function body / type definitions / ensures invalidates.

This is conservative (the cache treats two semantically-identical
sources as distinct) but trivially safe: a stale cached proof either
re-verifies cleanly under Verus or is reported as a stale-cache miss,
and we re-LLM.

Shape-level fallback (Pattern E)
--------------------------------
Two distinct (function name, source) pairs can have *identical* proof
obligations modulo type-parameter renaming. The canonical IronKV
example: ``delegation_map_v::impl1_insert::insert`` and
``delegation_map_v::impl3::set::insert`` both produce a
``det_insert_equal`` with body ``(r1 == r2) && (post1_self_ =~= post2_self_)``
and identical-shape ensures (strictly-sorted-vec insertion), so a
proof that works for one also works for the other.

To exploit this, every cached entry also stores a ``shape_key``: a
hash of (function name, normalised ``equal_fn_def``, normalised
``det_check_template``). On a cache miss-by-key we fall back to a
shape-key scan: if we find a prior ``verus_pass`` whose shape matches,
re-verify it against the current source. If Verus accepts, we promote
it to a real entry for the current artifact_key and skip the LLM.

This is sound because the proof-block has to pass Verus before we
trust it. The shape match is a heuristic for **prioritising** which
prior proof to try first, not for skipping verification.

Cache layout
------------
On disk::

    <cache_root>/<artifact_key>.json   # one file per target

``artifact_key`` defaults to ``f"{function}.{sha256[:16]}"`` and is
passed by the caller (``verusage_run`` provides it via
``run_single_file``). For ad-hoc / single-file callers we synthesise
one from ``det_spec.function``.

Cache schema (version 2)::

    {
      "cache_schema": 2,
      "cache_key":  "...sha256 hex...",
      "shape_key":  "...sha256 hex of normalised det_spec shape...",
      "function":   "set_owning_container",
      "file":       ".../remove_mapping_4k_helper2.rs",
      "status":     "verus_pass" | "verus_fail" | ...,
      "proof_block": "...",
      "helper_lemmas": "...",
      "rationale":  "...",
      "attempts":   N,
      "saved_at":   "2026-05-16T08:30:00Z",
      "verus_ms":   4321,
      "verus_stderr_tail": "..."
    }

The schema bump from v1 to v2 adds ``shape_key`` and ``helper_lemmas``.
Older v1 entries are still read; we recompute ``shape_key`` lazily on
first scan when it's missing.

Cache modes
-----------
``CacheMode`` enum controls behaviour:

  * ``USE`` (default) — read on hit, write at end. Hits skip LLM.
  * ``REFRESH``       — ignore prior hit, always re-LLM, overwrite.
  * ``BYPASS``        — ignore cache entirely; never read or write.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from spec_determinism.extract.types import DetCheckSpec

logger = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = 2


class CacheMode(Enum):
    USE = "use"          # read+write
    REFRESH = "refresh"  # ignore prior, write fresh
    BYPASS = "bypass"    # no read, no write

    @classmethod
    def parse(cls, s: str | None) -> "CacheMode":
        if not s:
            return cls.USE
        s = s.lower()
        for v in cls:
            if v.value == s:
                return v
        raise ValueError(f"unknown cache mode: {s!r} (allowed: use, refresh, bypass)")


@dataclass
class CachedProof:
    cache_key: str
    function: str
    file: str
    status: str
    proof_block: str
    rationale: str
    attempts: int
    saved_at: str
    verus_ms: int = 0
    verus_stderr_tail: str = ""
    cache_schema: int = CACHE_SCHEMA_VERSION
    # Pattern A: optional helper proof fns the LLM emitted to be injected
    # alongside (NOT inside) det_<f>. One Verus source string containing
    # zero or more ``proof fn lemma_*(...)`` defs.
    helper_lemmas: str = ""
    # Pattern E: hash of (function, equal_fn_def, det_check_template) used
    # for cross-target proof replay. Computed at save time; recomputed
    # lazily for v1 entries that pre-date this field.
    shape_key: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False, default=str)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_cache_key(det_spec: DetCheckSpec, source: str) -> str:
    """Stable hash of (det_spec JSON + normalised source).

    Source is whitespace-normalised at the line level (rstrip every line)
    so trailing whitespace edits don't blow the cache. This is conservative
    but matches the soundness model: any change Verus would notice changes
    the hash too.
    """
    src_norm = "\n".join(line.rstrip() for line in source.splitlines())
    h = hashlib.sha256()
    h.update(det_spec.to_json().encode("utf-8"))
    h.update(b"\n\0\n")  # separator
    h.update(src_norm.encode("utf-8"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Shape key (Pattern E).
# ---------------------------------------------------------------------------

# Strip whitespace + generic type parameter names + concrete numeric/length
# args. The shape is intentionally aggressive: it should match "morally the
# same" obligation across crates / impls.
_GENERIC_PARAM_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9_]*(?=\s*:\s*[A-Z])"   # `K: KeyTrait` -> K
)
_TYPE_ARG_RE = re.compile(r"<[^<>]*>")          # collapse generic instantiations


def _normalise_shape_text(s: str) -> str:
    """Aggressively normalise a Verus snippet for shape comparison.

    Collapses whitespace, strips line comments, and substitutes a small
    set of features that vary across crates without changing the proof
    obligation shape (e.g. ``post1_self_`` vs ``post1_state_``).
    """
    if not s:
        return ""
    # Drop ``//`` line comments.
    out = re.sub(r"//[^\n]*", "", s)
    # Generic-arg collapse (one pass — nested generics rarely matter for shape).
    out = _TYPE_ARG_RE.sub("<>", out)
    # Whitespace canonical form.
    out = re.sub(r"\s+", " ", out).strip()
    return out


def compute_shape_key(det_spec: DetCheckSpec) -> str:
    """Hash of (function name, normalised equal_fn_def, normalised template).

    The shape key matches two obligations that have identical proof
    structure even when their (function-qualifier, file, generics)
    differ. This is intentionally coarser than ``cache_key``: a shape
    hit must still re-verify against the new source before we trust it,
    which is enforced in the prover. Soundness rests on Verus, not on
    shape matching.
    """
    bits = (
        det_spec.function or "",
        _normalise_shape_text(det_spec.equal_fn_def),
        _normalise_shape_text(det_spec.det_check_template),
    )
    h = hashlib.sha256()
    for b in bits:
        h.update(b.encode("utf-8"))
        h.update(b"\n\0\n")
    return h.hexdigest()


_SAFE = re.compile(r"[^A-Za-z0-9_]")


def default_artifact_key(det_spec: DetCheckSpec, source: str) -> str:
    """Filesystem-safe identifier when the caller didn't supply one."""
    fn = _SAFE.sub("_", det_spec.function or "fn")
    return f"{fn}.{compute_cache_key(det_spec, source)[:16]}"


def cache_path(cache_dir: Path, artifact_key: str) -> Path:
    """Resolve where a per-target cache entry lives."""
    safe = _SAFE.sub("_", artifact_key)
    return cache_dir / f"{safe}.json"


def load(cache_dir: Path | None, artifact_key: str) -> Optional[CachedProof]:
    if cache_dir is None:
        return None
    p = cache_path(cache_dir, artifact_key)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
    except Exception as e:
        logger.warning("llm_proof cache: failed to parse %s: %s", p, e)
        return None
    # Accept forward-compatible schemas; warn if older/newer.
    v = raw.get("cache_schema", 1)
    if v != CACHE_SCHEMA_VERSION:
        logger.info("llm_proof cache: schema v%d found, expected v%d (%s)",
                    v, CACHE_SCHEMA_VERSION, p)
    # Strip extra keys; only feed the known ones to the dataclass.
    fields = {f for f in CachedProof.__dataclass_fields__}
    return CachedProof(**{k: v for k, v in raw.items() if k in fields})


# ---------------------------------------------------------------------------
# Shape-level lookup (Pattern E).
# ---------------------------------------------------------------------------


@dataclass
class ShapeHit:
    """A cache entry returned via shape-key fallback."""
    entry: CachedProof
    path: Path
    confidence: str  # "exact" if shape_key match; otherwise human-readable


def find_by_shape(
    cache_dir: Path | None,
    shape_key: str,
    *,
    function: str = "",
    require_pass: bool = True,
) -> Optional[ShapeHit]:
    """Scan ``cache_dir`` for the best entry whose shape matches.

    Returns the most-recent ``verus_pass`` entry whose ``shape_key``
    matches. For v1 entries (no embedded shape_key) we skip — the caller
    only benefits from passes the prover has just refreshed.

    ``function`` (optional) narrows the search to entries with the same
    bare function name as a final safety check. The shape_key already
    embeds this, but the explicit filter makes corrupted entries
    survivable.
    """
    if cache_dir is None or not shape_key:
        return None
    if not cache_dir.exists():
        return None

    best: Optional[CachedProof] = None
    best_path: Optional[Path] = None
    best_saved_at: str = ""

    for p in sorted(cache_dir.glob("*.json")):
        try:
            raw = json.loads(p.read_text())
        except Exception:
            continue
        if raw.get("shape_key") != shape_key:
            continue
        if function and raw.get("function") != function:
            continue
        status = raw.get("status", "")
        if require_pass and status != "verus_pass":
            continue
        saved_at = raw.get("saved_at", "")
        if saved_at < best_saved_at:
            continue
        fields = {f for f in CachedProof.__dataclass_fields__}
        best = CachedProof(**{k: v for k, v in raw.items() if k in fields})
        best_path = p
        best_saved_at = saved_at

    if best is None or best_path is None:
        return None
    return ShapeHit(entry=best, path=best_path, confidence="exact")


def save(cache_dir: Path | None, entry: CachedProof) -> None:
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_path(cache_dir, default_safe_name(entry))
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(entry.to_json())
    os.replace(tmp, p)
    logger.debug("llm_proof cache: wrote %s (%s)", p, entry.status)


def default_safe_name(entry: CachedProof) -> str:
    """Same shape as default_artifact_key but computed from a CachedProof.

    Used by save() so callers can build a CachedProof first and let the
    cache decide its on-disk name from the stored ``cache_key``.
    """
    fn = _SAFE.sub("_", entry.function or "fn")
    return f"{fn}.{entry.cache_key[:16]}"


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _self_test() -> None:
    import tempfile
    from spec_determinism.extract.types import DetCheckSpec

    ds = DetCheckSpec(
        function="f",
        det_check_template="proof fn det_f() { {ASSUMES} }",
        symbols=[],
        equal_fn_def="spec fn det_f_equal(r1: int, r2: int) -> bool { r1 == r2 }",
        equal_fn_name="det_f_equal",
        equal_arg_pairs=[{"lhs": "r1", "rhs": "r2"}],
        check_fn_name="det_f",
    )
    src = "fn f() {}"
    k1 = compute_cache_key(ds, src)
    k2 = compute_cache_key(ds, src + "\n")
    assert k1 == k2, "trailing newline must not change the key"
    k3 = compute_cache_key(ds, "fn f() { let _ = 0; }")
    assert k1 != k3, "body change must change the key"

    # Shape key normalisation.
    shape1 = compute_shape_key(ds)
    ds_b = DetCheckSpec(
        function="f",
        det_check_template="proof fn det_f() {\n    {ASSUMES} }",  # extra whitespace
        symbols=[],
        equal_fn_def="spec fn det_f_equal(r1: int, r2: int) -> bool { r1 == r2 }",
        equal_fn_name="det_f_equal",
        equal_arg_pairs=[{"lhs": "r1", "rhs": "r2"}],
        check_fn_name="det_f",
    )
    shape2 = compute_shape_key(ds_b)
    assert shape1 == shape2, "shape key should be whitespace-invariant"

    # Different function name => different shape.
    ds_g = DetCheckSpec(
        function="g",
        det_check_template=ds.det_check_template,
        symbols=[],
        equal_fn_def=ds.equal_fn_def,
        equal_fn_name=ds.equal_fn_name,
        equal_arg_pairs=ds.equal_arg_pairs,
        check_fn_name="det_g",
    )
    assert compute_shape_key(ds_g) != shape1, "different fn names should diverge"

    # Generic instantiation should be erased from shape.
    ds_typed = DetCheckSpec(
        function="f",
        det_check_template=ds.det_check_template,
        symbols=[],
        equal_fn_def="spec fn det_f_equal<K: KeyTrait>(r1: Vec<K>, r2: Vec<K>) -> bool { r1 == r2 }",
        equal_fn_name=ds.equal_fn_name,
        equal_arg_pairs=ds.equal_arg_pairs,
        check_fn_name="det_f",
    )
    shape3 = compute_shape_key(ds_typed)
    ds_int = DetCheckSpec(
        function="f",
        det_check_template=ds.det_check_template,
        symbols=[],
        equal_fn_def="spec fn det_f_equal<T: KeyTrait>(r1: Vec<T>, r2: Vec<T>) -> bool { r1 == r2 }",
        equal_fn_name=ds.equal_fn_name,
        equal_arg_pairs=ds.equal_arg_pairs,
        check_fn_name="det_f",
    )
    assert compute_shape_key(ds_int) == shape3, "different generic param letters should match"

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        # miss
        assert load(d, "x") is None
        # round-trip
        e = CachedProof(
            cache_key=k1, function="f", file="x.rs",
            status="verus_pass", proof_block="assert(true);",
            rationale="", attempts=1,
            saved_at=utc_now_iso(),
            shape_key=shape1,
        )
        save(d, e)
        e2 = load(d, default_safe_name(e))
        assert e2 is not None
        assert e2.proof_block == "assert(true);"
        assert e2.status == "verus_pass"
        assert e2.shape_key == shape1

        # Shape lookup for an unrelated artifact_key but same shape.
        ds_other = DetCheckSpec(
            function="f",
            det_check_template=ds.det_check_template,
            symbols=[],
            equal_fn_def=ds.equal_fn_def,  # same shape
            equal_fn_name=ds.equal_fn_name,
            equal_arg_pairs=ds.equal_arg_pairs,
            check_fn_name="det_f",
        )
        hit = find_by_shape(d, compute_shape_key(ds_other), function="f")
        assert hit is not None, "shape fallback should find the saved pass"
        assert hit.entry.cache_key == k1
        assert hit.confidence == "exact"

        # No false positives across function names.
        hit_g = find_by_shape(d, compute_shape_key(ds_g), function="g")
        assert hit_g is None

        # Negative entries shouldn't surface from shape lookup by default.
        neg = CachedProof(
            cache_key=k3, function="f", file="y.rs",
            status="verus_fail", proof_block="assert(false);",
            rationale="", attempts=2,
            saved_at=utc_now_iso(),
            shape_key=shape1,
        )
        save(d, neg)
        hit2 = find_by_shape(d, shape1, function="f")
        assert hit2 is not None and hit2.entry.status == "verus_pass"

        # mode parse
        assert CacheMode.parse(None) is CacheMode.USE
        assert CacheMode.parse("use") is CacheMode.USE
        assert CacheMode.parse("refresh") is CacheMode.REFRESH
        assert CacheMode.parse("bypass") is CacheMode.BYPASS
        try:
            CacheMode.parse("nope")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
    print("cache self-test: PASS")


if __name__ == "__main__":
    _self_test()
