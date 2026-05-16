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

Cache layout
------------
On disk::

    <cache_root>/<artifact_key>.json   # one file per target

``artifact_key`` defaults to ``f"{function}.{sha256[:16]}"`` and is
passed by the caller (``verusage_run`` provides it via
``run_single_file``). For ad-hoc / single-file callers we synthesise
one from ``det_spec.function``.

Cache schema (version 1)::

    {
      "cache_schema": 1,
      "cache_key": "...sha256 hex...",
      "function": "set_owning_container",
      "file": ".../remove_mapping_4k_helper2.rs",
      "status": "verus_pass" | "verus_fail" | "sandbox_reject"
                | "parse_failure" | "llm_failure" | "init",
      "proof_block": "...",         # winning block if status=verus_pass,
                                    # otherwise the last attempted block
      "rationale": "...",
      "attempts": N,
      "saved_at": "2026-05-16T08:30:00Z",
      "verus_ms": 4321,             # total Verus time of the winning attempt
      "verus_stderr_tail": "..."    # only set when status != verus_pass
    }

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

CACHE_SCHEMA_VERSION = 1


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
        )
        save(d, e)
        e2 = load(d, default_safe_name(e))
        assert e2 is not None
        assert e2.proof_block == "assert(true);"
        assert e2.status == "verus_pass"
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
