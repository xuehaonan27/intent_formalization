"""Tier 1.5 — per-project type-completion cache.

Cache key is ``(project_hash, type_name)`` where ``project_hash`` is the
sha256 of sorted concatenated contents of ``<project>/src/**/*.rs`` plus
``<project>/Cargo.toml``. This means a benign cargo dep bump that doesn't
touch source won't invalidate cached patches, but any source change does.

Layout::

    ~/.cache/spec_determinism/type_completion/<project_hash>/
      _meta.json                       # project_root, files included
      HashMap.json                     # one cache entry per type
      StrictlyOrderedVec.json
      CSingleMessage.json

Each entry is a :class:`TypePatch.to_dict` payload plus a few accounting
fields (``cached_at_ms``, ``llm_round_count``, ``validator_verdict``).

Dual-layer (live + pinned)
==========================

When ``pinned_cache_dir`` is supplied, the cache becomes a two-layer
read-through:

* Reads (:meth:`get`, :meth:`get_with_source`) check **live first**,
  then fall back to ``pinned_cache_dir``.
* Writes (:meth:`put`, :meth:`put_rejected`) only touch the live layer.
* :meth:`delete` records an in-memory tombstone for the type name and
  removes any live entry; pinned files on disk are never modified. The
  tombstone is per-instance, so the next ``TypeCompletionCache`` for the
  same project starts clean.

This is the recommended setup for A/B tests: pin a known-good snapshot
(e.g. ``verusage/cache_snapshots/<project>/``) and let the live layer
absorb anything the LLM has to fill in this run, without polluting the
snapshot.

The pinned ``_meta.json`` carries the source hash captured at snapshot
time. :attr:`pinned_hash`, :attr:`current_source_hash`, and
:attr:`pinned_hash_matches` expose the comparison; a mismatch means the
project source has drifted since the pin and the snapshot is best-effort
warm-start, not byte-identical guarantee.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from .apply import TypePatch


DEFAULT_CACHE_ROOT = os.path.expanduser("~/.cache/spec_determinism/type_completion")


def _iter_project_files(project_root: str) -> list[str]:
    out = []
    for dirpath, _, fnames in os.walk(project_root):
        # skip target/, .git/, etc.
        rel = os.path.relpath(dirpath, project_root)
        skip = any(
            part in {"target", ".git", "node_modules", ".venv", "__pycache__"}
            for part in rel.split(os.sep)
        )
        if skip:
            continue
        for fn in fnames:
            if fn.endswith(".rs") or fn == "Cargo.toml":
                out.append(os.path.join(dirpath, fn))
    out.sort()
    return out


def project_hash(project_root: str) -> str:
    """SHA-256 of sorted concat of ``<project>/**/*.rs`` + Cargo.toml."""
    h = hashlib.sha256()
    files = _iter_project_files(project_root)
    for f in files:
        rel = os.path.relpath(f, project_root)
        h.update(rel.encode())
        h.update(b"\0")
        try:
            with open(f, "rb") as fp:
                h.update(fp.read())
        except OSError:
            pass
        h.update(b"\0\0")
    return h.hexdigest()


@dataclass
class CacheEntry:
    patch: TypePatch
    cached_at_ms: int
    llm_round_count: int = 0
    validator_verdict: str = "accepted"     # 'accepted' | 'rejected'
    reject_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "patch": self.patch.to_dict(),
            "cached_at_ms": self.cached_at_ms,
            "llm_round_count": self.llm_round_count,
            "validator_verdict": self.validator_verdict,
            "reject_reason": self.reject_reason,
        }

    @staticmethod
    def from_dict(d: dict) -> "CacheEntry":
        return CacheEntry(
            patch=TypePatch.from_dict(d["patch"]),
            cached_at_ms=int(d.get("cached_at_ms", 0)),
            llm_round_count=int(d.get("llm_round_count", 0)),
            validator_verdict=d.get("validator_verdict", "accepted"),
            reject_reason=d.get("reject_reason", ""),
        )


class TypeCompletionCache:
    """File-backed per-project cache. Thread-safe enough for our use:
    one writer per (project_hash, type_name) pair.

    With ``pinned_cache_dir`` set, the cache becomes a read-through dual
    layer: writes touch only the live directory; reads check live first
    then fall back to the pinned snapshot. See module docstring."""

    def __init__(
        self,
        project_root: str,
        *,
        cache_root: str = DEFAULT_CACHE_ROOT,
        project_hash_override: Optional[str] = None,
        pinned_cache_dir: Optional[str] = None,
    ):
        self.project_root = project_root
        self.cache_root = cache_root
        self._hash = project_hash_override or project_hash(project_root)
        self.cache_dir = os.path.join(self.cache_root, self._hash)
        os.makedirs(self.cache_dir, exist_ok=True)
        meta_path = os.path.join(self.cache_dir, "_meta.json")
        if not os.path.isfile(meta_path):
            with open(meta_path, "w") as f:
                json.dump({
                    "project_root": project_root,
                    "project_hash": self._hash,
                    "first_seen_ms": int(time.time() * 1000),
                }, f, indent=2)

        # Pinned (read-only) layer — optional.
        self.pinned_cache_dir: Optional[str] = (
            pinned_cache_dir if pinned_cache_dir and os.path.isdir(pinned_cache_dir)
            else None
        )
        self._pinned_meta: dict = {}
        if self.pinned_cache_dir:
            pm = os.path.join(self.pinned_cache_dir, "_meta.json")
            if os.path.isfile(pm):
                try:
                    with open(pm) as f:
                        self._pinned_meta = json.load(f)
                except (json.JSONDecodeError, OSError):
                    self._pinned_meta = {}

        # Per-instance tombstones: names invalidated by :meth:`delete` so
        # subsequent reads in the same run don't resurrect a stale pinned
        # entry. Cleared on instance destruction (per-target lifecycle).
        self._invalidated: set[str] = set()

    @property
    def project_hash(self) -> str:
        return self._hash

    @property
    def current_source_hash(self) -> str:
        """Alias for :attr:`project_hash` — readability for A/B reporting."""
        return self._hash

    @property
    def pinned_hash(self) -> Optional[str]:
        """Source hash recorded in the pinned snapshot's ``_meta.json``."""
        h = self._pinned_meta.get("project_hash")
        return h if isinstance(h, str) and h else None

    @property
    def pinned_hash_matches(self) -> Optional[bool]:
        """``True`` if pinned hash == current source hash; ``None`` if no
        pinned cache or no recorded hash."""
        ph = self.pinned_hash
        if ph is None:
            return None
        return ph == self._hash

    def _path(self, type_name: str) -> str:
        # sanitise name for filesystem (no slashes, etc.)
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in type_name)
        return os.path.join(self.cache_dir, f"{safe}.json")

    def _pinned_path(self, type_name: str) -> Optional[str]:
        if not self.pinned_cache_dir:
            return None
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in type_name)
        return os.path.join(self.pinned_cache_dir, f"{safe}.json")

    def get_with_source(
        self, type_name: str
    ) -> tuple[Optional[CacheEntry], str]:
        """Return ``(entry, source)`` where ``source`` is one of
        ``"live"``, ``"pinned"``, or ``"miss"``.

        Live takes precedence. A tombstone (recorded via :meth:`delete`)
        forces a miss regardless of pinned content.
        """
        if type_name in self._invalidated:
            return None, "miss"
        live_p = self._path(type_name)
        if os.path.isfile(live_p):
            try:
                with open(live_p) as f:
                    return CacheEntry.from_dict(json.load(f)), "live"
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        pinned_p = self._pinned_path(type_name)
        if pinned_p and os.path.isfile(pinned_p):
            try:
                with open(pinned_p) as f:
                    return CacheEntry.from_dict(json.load(f)), "pinned"
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        return None, "miss"

    def get(self, type_name: str) -> Optional[CacheEntry]:
        entry, _ = self.get_with_source(type_name)
        return entry

    def put(self, entry: CacheEntry) -> None:
        # Writes always go to the live layer; clear any tombstone so the
        # newly-written entry is visible to subsequent reads.
        self._invalidated.discard(entry.patch.name)
        p = self._path(entry.patch.name)
        tmp = p + ".tmp"
        with open(tmp, "w") as f:
            json.dump(entry.to_dict(), f, indent=2)
        os.replace(tmp, p)

    def put_rejected(self, type_name: str, reason: str) -> None:
        """Record a *negative* cache entry so we don't keep retrying the LLM
        on a type it can't resolve. The caller still owns the decision of
        whether to short-circuit on rejection or retry — :meth:`get` returns
        the entry regardless of verdict."""
        # Use the minimal patch payload — type name only — since by definition
        # we have nothing else to record.
        patch = TypePatch(name=type_name, kind="struct")
        self.put(CacheEntry(
            patch=patch,
            cached_at_ms=int(time.time() * 1000),
            validator_verdict="rejected",
            reject_reason=reason,
        ))

    def delete(self, type_name: str) -> bool:
        """Invalidate a cache entry. Returns True if any state changed.

        Used by the Tier 1.5 shape-mismatch loop: when a previously-cached
        patch is shown (by the gen_det compile probe) to produce a bad
        ``(lhs)@`` access, the cached patch is invalidated so the next
        round's LLM call is not short-circuited by the same broken entry.

        Removes any live file AND records a per-instance tombstone so a
        pinned entry with the same name will not resurface for the rest of
        this cache's lifetime. Pinned files on disk are never modified.
        """
        changed = False
        p = self._path(type_name)
        try:
            os.unlink(p)
            changed = True
        except FileNotFoundError:
            pass
        except OSError:
            pass
        # Always tombstone — pinned might have the entry even if live didn't.
        if type_name not in self._invalidated:
            self._invalidated.add(type_name)
            changed = True
        return changed

    def list_entries(self) -> list[CacheEntry]:
        """Live entries only (pinned is read-through, list it via
        :meth:`list_pinned_entries`)."""
        out = []
        for fn in sorted(os.listdir(self.cache_dir)):
            if fn == "_meta.json" or not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.cache_dir, fn)) as f:
                    out.append(CacheEntry.from_dict(json.load(f)))
            except (json.JSONDecodeError, KeyError, OSError):
                continue
        return out

    def list_pinned_entries(self) -> list[CacheEntry]:
        if not self.pinned_cache_dir:
            return []
        out = []
        for fn in sorted(os.listdir(self.pinned_cache_dir)):
            if fn == "_meta.json" or not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.pinned_cache_dir, fn)) as f:
                    out.append(CacheEntry.from_dict(json.load(f)))
            except (json.JSONDecodeError, KeyError, OSError):
                continue
        return out


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    import tempfile, textwrap

    ok = True
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as cache:
        # Build a fake project
        os.makedirs(os.path.join(proj, "src"))
        with open(os.path.join(proj, "src", "lib.rs"), "w") as f:
            f.write("pub struct Foo {}\n")
        with open(os.path.join(proj, "Cargo.toml"), "w") as f:
            f.write("[package]\nname='x'\n")

        h1 = project_hash(proj)
        h2 = project_hash(proj)
        if h1 != h2:
            print(f"FAIL: project_hash not stable: {h1} vs {h2}")
            ok = False

        c = TypeCompletionCache(proj, cache_root=cache)

        # miss
        if c.get("HashMap") is not None:
            print("FAIL: get on empty cache should be None")
            ok = False

        # put + get
        p = TypePatch(
            name="HashMap", kind="struct",
            fields=[("m", "u8")],
            source_rel_path="src/lib.rs", source_line=1,
            source_snippet="pub struct Foo {}",
        )
        c.put(CacheEntry(patch=p, cached_at_ms=123, llm_round_count=2))
        got = c.get("HashMap")
        if got is None or got.patch.name != "HashMap" or got.llm_round_count != 2:
            print(f"FAIL: round-trip lost data: {got}")
            ok = False

        # rejected entry
        c.put_rejected("Mystery", "evidence not found")
        rj = c.get("Mystery")
        if rj is None or rj.validator_verdict != "rejected":
            print(f"FAIL: rejected entry missing or wrong verdict: {rj}")
            ok = False

        # list
        entries = c.list_entries()
        if len(entries) != 2:
            print(f"FAIL: list_entries should have 2, got {len(entries)}")
            ok = False

        # source change → new hash
        with open(os.path.join(proj, "src", "lib.rs"), "a") as f:
            f.write("// touched\n")
        h3 = project_hash(proj)
        if h3 == h1:
            print(f"FAIL: project_hash unchanged after edit")
            ok = False

    # ------- pinned (read-only) layer --------------------------------
    with tempfile.TemporaryDirectory() as proj, \
         tempfile.TemporaryDirectory() as live, \
         tempfile.TemporaryDirectory() as pinned:
        os.makedirs(os.path.join(proj, "src"))
        with open(os.path.join(proj, "src", "lib.rs"), "w") as f:
            f.write("pub struct Foo {}\n")
        with open(os.path.join(proj, "Cargo.toml"), "w") as f:
            f.write("[package]\nname='x'\n")
        src_hash = project_hash(proj)

        # Seed the pinned directory with an entry + matching _meta.
        with open(os.path.join(pinned, "_meta.json"), "w") as f:
            json.dump({"project_root": proj, "project_hash": src_hash,
                       "first_seen_ms": 1}, f)
        p_pinned = TypePatch(
            name="HashMap", kind="struct",
            fields=[("k", "u8"), ("v", "u8")],
            source_rel_path="src/lib.rs", source_line=1,
            source_snippet="(pinned snapshot)",
        )
        with open(os.path.join(pinned, "HashMap.json"), "w") as f:
            json.dump(CacheEntry(patch=p_pinned, cached_at_ms=1).to_dict(), f)

        # Snapshot pinned directory contents for tamper check.
        def _snap(d):
            return {fn: open(os.path.join(d, fn), "rb").read()
                    for fn in sorted(os.listdir(d))}
        pinned_before = _snap(pinned)

        c = TypeCompletionCache(proj, cache_root=live, pinned_cache_dir=pinned)

        # Hash match reported correctly.
        if c.pinned_hash != src_hash:
            print(f"FAIL: pinned_hash mismatch: {c.pinned_hash} vs {src_hash}")
            ok = False
        if c.pinned_hash_matches is not True:
            print(f"FAIL: pinned_hash_matches: {c.pinned_hash_matches}")
            ok = False

        # Read-through: pinned entry visible via get/get_with_source.
        got = c.get("HashMap")
        if got is None or got.patch.name != "HashMap":
            print(f"FAIL: pinned fallback failed: {got}"); ok = False
        e, src = c.get_with_source("HashMap")
        if e is None or src != "pinned":
            print(f"FAIL: get_with_source pinned: {src}"); ok = False

        # Live precedence: writing live HashMap shadows pinned.
        p_live = TypePatch(
            name="HashMap", kind="struct",
            fields=[("only", "u8")],
            source_rel_path="src/lib.rs", source_line=1,
            source_snippet="(live)",
        )
        c.put(CacheEntry(patch=p_live, cached_at_ms=2))
        e, src = c.get_with_source("HashMap")
        if e is None or src != "live" or e.patch.fields != [("only", "u8")]:
            print(f"FAIL: live should shadow pinned: src={src} fields={e.patch.fields if e else None}")
            ok = False

        # delete() invalidates BOTH live + pinned for this session.
        c.delete("HashMap")
        e, src = c.get_with_source("HashMap")
        if e is not None or src != "miss":
            print(f"FAIL: delete should tombstone pinned: src={src}"); ok = False

        # Pinned directory on disk is byte-identical (read-only invariant).
        pinned_after = _snap(pinned)
        if pinned_before != pinned_after:
            print(f"FAIL: pinned dir was modified")
            ok = False

        # New instance starts clean (tombstones don't leak across instances).
        c2 = TypeCompletionCache(proj, cache_root=live, pinned_cache_dir=pinned)
        e, src = c2.get_with_source("HashMap")
        # Live HashMap was unlinked by delete on c, so c2 should see pinned again.
        if e is None or src != "pinned":
            print(f"FAIL: new instance should re-see pinned: src={src}"); ok = False

        # put() clears tombstone (live write wins immediately).
        c.put(CacheEntry(patch=p_live, cached_at_ms=3))
        e, src = c.get_with_source("HashMap")
        if e is None or src != "live":
            print(f"FAIL: put should clear tombstone: src={src}"); ok = False

        # pinned_hash_matches=False when source drifts.
        with open(os.path.join(proj, "src", "lib.rs"), "a") as f:
            f.write("// touched\n")
        c3 = TypeCompletionCache(proj, cache_root=live, pinned_cache_dir=pinned)
        if c3.pinned_hash_matches is not False:
            print(f"FAIL: pinned_hash_matches should be False after drift: "
                  f"{c3.pinned_hash_matches}")
            ok = False
        # Drifted pinned is still served (read-only warm-start).
        e, src = c3.get_with_source("HashMap")
        if e is None or src not in ("live", "pinned"):
            print(f"FAIL: drifted pinned should still serve: src={src}")
            ok = False

        # No pinned dir → graceful no-op.
        c4 = TypeCompletionCache(proj, cache_root=live, pinned_cache_dir=None)
        if c4.pinned_hash is not None or c4.pinned_hash_matches is not None:
            print(f"FAIL: no pinned should report None")
            ok = False
        if c4.list_pinned_entries() != []:
            print(f"FAIL: no pinned should list []")
            ok = False

    print("cache self-test:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
