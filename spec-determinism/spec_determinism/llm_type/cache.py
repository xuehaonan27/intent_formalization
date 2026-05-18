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
    one writer per (project_hash, type_name) pair."""

    def __init__(
        self,
        project_root: str,
        *,
        cache_root: str = DEFAULT_CACHE_ROOT,
        project_hash_override: Optional[str] = None,
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

    @property
    def project_hash(self) -> str:
        return self._hash

    def _path(self, type_name: str) -> str:
        # sanitise name for filesystem (no slashes, etc.)
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in type_name)
        return os.path.join(self.cache_dir, f"{safe}.json")

    def get(self, type_name: str) -> Optional[CacheEntry]:
        p = self._path(type_name)
        if not os.path.isfile(p):
            return None
        try:
            with open(p) as f:
                return CacheEntry.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def put(self, entry: CacheEntry) -> None:
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
        """Remove a cache entry. Returns True if a file was removed.

        Used by the Tier 1.5 shape-mismatch loop: when a previously-cached
        patch is shown (by the gen_det compile probe) to produce a bad
        ``(lhs)@`` access, the cached patch is invalidated so the next
        round's LLM call is not short-circuited by the same broken entry.
        """
        p = self._path(type_name)
        try:
            os.unlink(p)
            return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def list_entries(self) -> list[CacheEntry]:
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

    print("cache self-test:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
