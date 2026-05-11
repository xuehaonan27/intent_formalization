"""L4 LLM-driven view synthesizer.

Generates ``impl View for T { type V = …; closed spec fn view(&self)
-> Self::V { … } }`` for types the cheap layers L1/L2/L3 couldn't
cover. Designed to be the offline lever that closes the ~290
"`ok_with_witness`" false positives in atmosphere/ironkv: 6/7 corpus
projects have zero raw ``impl View`` blocks because their View impls
live inside ``state_machine!`` / ``tokenized_state_machine!`` macros
that tree-sitter doesn't expand.

Architecture (parallel to :mod:`spec_determinism.policy_llm`):

* :class:`CopilotViewLLM` — thin wrapper over the ``copilot`` CLI
  (re-uses the same prompt-file / response-file dance as
  :mod:`policy_llm`). Replaceable with any other backend that exposes
  a ``query(prompt, run_dir) -> str``.
* :func:`build_view_prompt` — composes the prompt from a
  :class:`TypeDef` plus the already-resolved views of its field
  types.
* :func:`parse_view_response` — extracts the JSON block from the
  response.
* :func:`validate_view_decl` — tree-sitter syntactic check on the
  generated Verus text. We reject responses that don't parse as
  ``impl_item`` (so a hallucinated keyword never reaches gen_det).
* :class:`ViewCache` — on-disk cache under
  ``results-verusage/view_registry/<project>/<short>.json`` keyed by
  the type-def source hash. Subsequent runs with the same source
  reuse the cached synthesis.
* :func:`synthesize_view` — full single-type pipeline: cache hit?
  return; otherwise prompt → parse → validate → cache → return.
* :func:`prefill_project` — batch over a project's uncovered types,
  populating the cache.
* CLI: ``python -m spec_determinism.view.llm prefill --project X``.

The cache schema is stable so PR-D2 (gen_det integration) can read
this file shape without re-running the LLM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tree_sitter as ts
import tree_sitter_verus as tsv

from spec_determinism.extract.type_registry import (
    TypeDef,
    TypeExpr,
)
from spec_determinism.llm.copilot import CopilotCLI

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache schema constants
# ---------------------------------------------------------------------------

CACHE_SCHEMA_VERSION = 1
VIEW_SOURCE_TAG = "L4-llm"


# ---------------------------------------------------------------------------
# Copilot CLI backend
# ---------------------------------------------------------------------------


# Thin alias so call-sites can keep referring to a view-specific name; the
# subprocess logic lives in :mod:`spec_determinism.llm.copilot`.
CopilotViewLLM = CopilotCLI


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_PROMPT_HEADER = """\
You are helping a Verus-based determinism checker compute **semantic
equality** for a user-defined Rust type. The checker currently falls
back to *structural* `==` whenever it can't find a `View` impl,
producing spurious "two implementations differ" witnesses on fields
the spec author never meant to pin down (allocator addresses, ghost
indices, sequence ordering inside a Set, etc.).

Your job: emit a Verus `impl View for <T>` block that projects the
type to an abstract view capturing **only the dimensions the spec
actually constrains**. The checker will then compare `lhs.view() ==
rhs.view()` instead of structural `==`.
"""

_VIEW_SCHEMA_DOC = """\
## Output format (single fenced ```json block)

```json
{
  "viewed_type":  "<the Verus type expression for Self::V>",
  "view_decl":    "<the complete `impl View for <T>` block, source-form Verus>",
  "depends_on_views_of": ["<short type name>", ...],
  "rationale":    "<1-3 sentences explaining the projection choice>"
}
```

Required keys: `viewed_type`, `view_decl`, `rationale`. The
`depends_on_views_of` array lists short names of other user types
whose `.view()` you used inside `view_decl` (so a future pass can
synthesise them recursively). Omit or empty if none.

The `view_decl` must:
- be a single `impl<...> View for <T>{ ... }` item, valid Verus
  syntax (it will be parsed by tree-sitter-verus before caching);
- contain exactly one `type V = ...;` and one
  `closed spec fn view(&self) -> Self::V { ... }` (or
  `open spec fn`, your choice);
- preserve all generic parameters and where-clause bounds from the
  original type;
- never reference identifiers that aren't already in scope at the
  type-def site (no fresh imports);
- use `Seq<X@>`, `Set<X@>`, `Map<K@, V@>`, `Option<X@>`, `X@`
  recursively for fields whose types have a view — `@` is sugar for
  `.view()` and works on any type with an `impl View`. For
  primitives (u8/usize/bool/&str/...) and unit `()`, the view is the
  value itself (DO NOT call `@` on a primitive — it won't compile).
- For raw pointer fields (`*mut T`, `*const T`), omit them from the
  view entirely (the checker treats raw pointers as
  allocator-opaque). For `Ghost<T>` / `Tracked<T>` ghost wrappers,
  project to the inner value's view: `self.<name>@@` (the first `@`
  unwraps Ghost, the second is the view of T).
- For variants of an enum, return a `Seq`/`int`/tagged-union view as
  appropriate — typically `pub enum <T>View { ... }` declared just
  above the `impl View` is acceptable IF you also include the enum
  declaration in `view_decl`.

Rules of thumb:
- A `Vec<X>` field that the spec only treats as an unordered
  multiset → view as `Set<X@>` or `Multiset<X@>`.
- A `Vec<X>` whose order matters → `Seq<X@>`.
- A `Map<K, V>` field always views to `Map<K@, V@>`.
- An allocator handle / opaque ID → omit from the view.
- A field that the ensures clause never inspects → omit.
"""

_FEW_SHOT = """\
## Example

### Type
```
pub struct Page {
    pub ptr: *mut u8,         // raw pointer — opaque
    pub size: usize,
    pub state: PageState,
    pub owner: Ghost<OwnerId>, // ghost wrapper
}
```

Already-resolved views of dependencies:
- `PageState`: identity view (it's a `#[derive(Eq)]` enum of unit
  variants — its structural equality is already semantic).
- `OwnerId`: identity view.

### Response

```json
{
  "viewed_type": "PageView",
  "view_decl": "pub struct PageView { pub size: usize, pub state: PageState, pub owner: OwnerId }\\n\\nimpl View for Page {\\n    type V = PageView;\\n    closed spec fn view(&self) -> PageView {\\n        PageView { size: self.size, state: self.state, owner: self.owner@ }\\n    }\\n}",
  "depends_on_views_of": [],
  "rationale": "Drop ptr (allocator-opaque), keep size/state which are spec-meaningful, project Ghost<OwnerId> to its inner identity view. PageState's structural eq is already semantic so we use it as-is."
}
```
"""


def _render_type_def(td: TypeDef, src_excerpt: str) -> str:
    """Pretty-print the type definition for inclusion in the prompt."""
    head = (f"kind={td.kind}  qualified_name={td.qualified_name}  "
            f"derives={td.derives or '[]'}  "
            f"cfg={td.cfg or '[]'}")
    body = src_excerpt.strip() if src_excerpt else "(source unavailable)"
    return f"{head}\n\n```\n{body}\n```"


def _render_deps(dep_views: dict[str, str]) -> str:
    """Render the already-resolved views map for the prompt."""
    if not dep_views:
        return "(no dependency views — all field types are primitives or unknown)"
    lines = []
    for name, info in dep_views.items():
        lines.append(f"- `{name}`: {info}")
    return "\n".join(lines)


def build_view_prompt(
    td: TypeDef,
    src_excerpt: str,
    dep_views: dict[str, str],
    project: str = "",
    extra_context: str = "",
) -> str:
    """Compose the full LLM prompt for one type."""
    parts = [
        _PROMPT_HEADER,
        "\n## Target type\n",
        (f"Project: `{project}`\n" if project else ""),
        _render_type_def(td, src_excerpt),
        "\n\n## Already-resolved views of dependency types\n\n",
        _render_deps(dep_views),
    ]
    if extra_context:
        parts.append("\n\n## Additional context\n\n")
        parts.append(extra_context)
    parts.append("\n\n")
    parts.append(_VIEW_SCHEMA_DOC)
    parts.append("\n")
    parts.append(_FEW_SHOT)
    parts.append(
        "\n## Your task\n\n"
        "Produce the JSON block described above for the target type.\n"
        "Output **nothing** outside the fenced ```json block.\n"
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Response parsing & validation
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)

_REQUIRED_KEYS = {"viewed_type", "view_decl", "rationale"}
_OPTIONAL_KEYS = {"depends_on_views_of"}
_ALLOWED_KEYS = _REQUIRED_KEYS | _OPTIONAL_KEYS


def parse_view_response(text: str) -> dict:
    """Extract the JSON object from the response."""
    m = _JSON_FENCE_RE.search(text)
    blob = m.group(1) if m else text.strip()
    try:
        d = json.loads(blob)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM response was not valid JSON:\n{text}") from e
    missing = _REQUIRED_KEYS - set(d.keys())
    if missing:
        raise ValueError(
            f"LLM response missing required keys: {sorted(missing)}\n{d}"
        )
    extra = set(d.keys()) - _ALLOWED_KEYS
    if extra:
        logger.warning("LLM view response has unknown keys (ignored): %s",
                       sorted(extra))
    return d


_lang = ts.Language(tsv.language())
_parser = ts.Parser(_lang)


def _find_impl_item(node: ts.Node) -> Optional[ts.Node]:
    """Depth-first walk for the first ``impl_item`` node in the tree.

    The Verus grammar wraps top-level items inside ``source_file →
    verus_block → declaration_with_attrs → impl_item``; we also accept
    a bare ``impl_item`` at the root.
    """
    if node.type == "impl_item":
        return node
    for ch in node.named_children:
        hit = _find_impl_item(ch)
        if hit is not None:
            return hit
    return None


def validate_view_decl(view_decl: str) -> tuple[bool, str]:
    """Tree-sitter syntactic validation.

    Returns ``(ok, message)``.  ``ok=True`` means the snippet parses
    cleanly and contains at least one ``impl_item``.  This is a
    cheap pre-flight before Verus does its own parse — we want to
    catch obviously broken responses without paying the
    ``verus --parse-only`` round-trip.
    """
    if not view_decl or not view_decl.strip():
        return False, "empty view_decl"
    # Wrap in a verus! { ... } block to satisfy the grammar entry rule.
    wrapped = "verus! {\n" + view_decl + "\n}"
    tree = _parser.parse(wrapped.encode("utf-8"))
    if tree.root_node.has_error:
        return False, "tree-sitter parse error in verus! { view_decl }"
    impl_node = _find_impl_item(tree.root_node)
    if impl_node is None:
        return False, "no `impl_item` found in view_decl"
    impl_text = wrapped[impl_node.start_byte:impl_node.end_byte]
    if " View for " not in impl_text and " View<" not in impl_text:
        return False, "impl_item is not an `impl View for …` block"
    return True, "ok"


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class CacheEntry:
    """One on-disk cache entry."""
    type_short: str
    qualified_name: str
    source_hash: str
    view_source: str
    viewed_type: str
    view_decl: str
    depends_on_views_of: list[str] = field(default_factory=list)
    rationale: str = ""
    schema_version: int = CACHE_SCHEMA_VERSION
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "type_short": self.type_short,
            "qualified_name": self.qualified_name,
            "source_hash": self.source_hash,
            "view_source": self.view_source,
            "viewed_type": self.viewed_type,
            "view_decl": self.view_decl,
            "depends_on_views_of": list(self.depends_on_views_of),
            "rationale": self.rationale,
            "raw_response": self.raw_response,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CacheEntry":
        return cls(
            schema_version=int(d.get("schema_version", 0)),
            type_short=d["type_short"],
            qualified_name=d.get("qualified_name", ""),
            source_hash=d["source_hash"],
            view_source=d.get("view_source", VIEW_SOURCE_TAG),
            viewed_type=d.get("viewed_type", ""),
            view_decl=d.get("view_decl", ""),
            depends_on_views_of=list(d.get("depends_on_views_of") or []),
            rationale=d.get("rationale", ""),
            raw_response=d.get("raw_response", ""),
        )


class ViewCache:
    """Per-project on-disk view cache.

    Layout: ``<root>/<short_name>.json`` — one file per type so a
    failed synthesis for one type doesn't poison the whole cache.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, short_name: str) -> Path:
        # ``/`` and `:` are illegal short names but defensive anyway.
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", short_name)
        return self.root / f"{safe}.json"

    def get(self, short_name: str, source_hash: str) -> Optional[CacheEntry]:
        p = self.path_for(short_name)
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            logger.warning("Corrupt cache entry %s — ignoring", p)
            return None
        entry = CacheEntry.from_dict(d)
        if entry.source_hash != source_hash:
            logger.info(
                "Cache miss for %s: source_hash changed (was %s, now %s)",
                short_name, entry.source_hash, source_hash,
            )
            return None
        return entry

    def get_any(self, short_name: str) -> Optional[CacheEntry]:
        """Hash-less lookup for the registry resolve path.

        Used at codegen time where we don't have ready access to the
        type's source bytes — we trust that the cache file's
        ``type_short`` is authoritative. Returns ``None`` if no file
        exists or the file is corrupt / wrong-shaped.
        """
        p = self.path_for(short_name)
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            return None
        try:
            entry = CacheEntry.from_dict(d)
        except Exception:
            return None
        if entry.type_short != short_name:
            return None
        return entry

    # ViewRegistry uses this short-circuit when looking up by short name
    # without re-hashing the type definition source.
    def _get_any_for_short(self, short_name: str) -> Optional[CacheEntry]:
        return self.get_any(short_name)

    def put(self, entry: CacheEntry) -> Path:
        p = self.path_for(entry.type_short)
        p.write_text(json.dumps(entry.to_dict(), indent=2) + "\n")
        return p

    def all_entries(self) -> list[CacheEntry]:
        entries: list[CacheEntry] = []
        for p in sorted(self.root.glob("*.json")):
            if p.name == "_resolver_audit.json":
                continue
            if p.name == "_prefill_summary.json":
                continue
            try:
                d = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            try:
                entries.append(CacheEntry.from_dict(d))
            except Exception:
                continue
        return entries


# ---------------------------------------------------------------------------
# End-to-end synthesis
# ---------------------------------------------------------------------------


def _extract_type_source(td: TypeDef) -> str:
    """Slice the type-def source text out of its file.

    Returns an empty string if the file is unreadable. We use
    ``tree_sitter`` to find the smallest enclosing item that starts at
    ``source_line`` — but for prompt purposes, a generous +/- window
    is fine.
    """
    if not td.source_file or not td.source_line:
        return ""
    try:
        lines = Path(td.source_file).read_text(errors="replace").splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    # Use a simple heuristic — start at source_line, scan forward
    # until brace depth returns to zero.
    start = max(td.source_line - 1, 0)
    depth = 0
    out = []
    started = False
    for i in range(start, min(len(lines), start + 200)):
        line = lines[i]
        out.append(line)
        for ch in line:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
        if started and depth == 0:
            break
        # Type alias / unit struct on a single line → look for `;`
        if not started and ";" in line:
            break
    return "\n".join(out)


def synthesize_view(
    td: TypeDef,
    *,
    dep_views: dict[str, str],
    cache: ViewCache,
    client: Optional[CopilotViewLLM] = None,
    run_root: Optional[Path] = None,
    project: str = "",
    extra_context: str = "",
    force: bool = False,
) -> Optional[CacheEntry]:
    """Synthesize a view for one type, with cache-hit short-circuit.

    Returns the cached/freshly-generated :class:`CacheEntry`, or
    ``None`` when synthesis or validation failed.
    """
    src_excerpt = _extract_type_source(td)
    src_hash = _source_hash(src_excerpt or td.qualified_name)

    if not force:
        hit = cache.get(td.name, src_hash)
        if hit is not None:
            logger.info("L4 cache hit for %s (hash=%s)", td.name, src_hash)
            return hit

    if client is None:
        client = CopilotViewLLM()
    if run_root is None:
        run_root = cache.root / "_llm_runs"
    run_dir = run_root / td.name
    prompt = build_view_prompt(td, src_excerpt, dep_views,
                               project=project,
                               extra_context=extra_context)
    logger.info("L4 LLM synth for %s …", td.name)
    try:
        raw = client.query(prompt, run_dir)
    except RuntimeError as e:
        logger.warning("L4 synth for %s: LLM query failed (%s)", td.name, e)
        return None
    try:
        d = parse_view_response(raw)
    except ValueError as e:
        logger.warning("L4 synth for %s: bad response (%s)", td.name, e)
        return None

    view_decl = d["view_decl"]
    ok, msg = validate_view_decl(view_decl)
    if not ok:
        logger.warning("L4 synth for %s: validation failed (%s)", td.name, msg)
        # Persist a stub so we don't re-query indefinitely; PR-D2 will
        # skip stubs (view_decl == "").
        entry = CacheEntry(
            type_short=td.name,
            qualified_name=td.qualified_name,
            source_hash=src_hash,
            view_source="L4-llm-invalid",
            viewed_type="",
            view_decl="",
            rationale=f"validation failed: {msg}",
            raw_response=raw,
        )
        cache.put(entry)
        return None

    entry = CacheEntry(
        type_short=td.name,
        qualified_name=td.qualified_name,
        source_hash=src_hash,
        view_source=VIEW_SOURCE_TAG,
        viewed_type=d["viewed_type"],
        view_decl=view_decl,
        depends_on_views_of=list(d.get("depends_on_views_of") or []),
        rationale=d.get("rationale", ""),
        raw_response=raw,
    )
    cache.put(entry)
    return entry


# ---------------------------------------------------------------------------
# Project prefill
# ---------------------------------------------------------------------------


def _uncovered_types(view_registry) -> list[TypeDef]:
    """Return the list of TypeDefs the L1/L2/L3 resolver leaves uncovered.

    Uses :class:`ViewRegistry.resolve` on a synthesised leaf TypeExpr
    per short name, picking the first definition in the bucket.
    """
    out: list[TypeDef] = []
    seen: set[str] = set()
    for short, defs in view_registry.types_by_short.items():
        if short in seen:
            continue
        seen.add(short)
        # Pick the most informative definition: prefer non-alias over alias.
        td = next((d for d in defs if d.kind != "alias"), defs[0])
        # Skip aliases entirely — L2 handles them transitively.
        if td.kind == "alias":
            continue
        # Build a leaf TypeExpr for resolve().
        e = TypeExpr(kind="leaf", head=short, raw=short)
        res = view_registry.resolve(e)
        if not res.is_resolved:
            out.append(td)
    return out


def prefill_project(
    project_root: Path,
    *,
    view_registry,
    cache: ViewCache,
    client: Optional[CopilotViewLLM] = None,
    project_name: str = "",
    only: Optional[set[str]] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """Batch-synthesize views for every uncovered type in the project.

    Parameters
    ----------
    only :
        If provided, restrict synthesis to these short names.
    limit :
        Hard cap on number of synth calls (for cost control).
    dry_run :
        If True, just emit the plan (skip LLM calls).
    force :
        If True, ignore cache hits and re-query.

    Returns a summary dict suitable for JSON dumping.
    """
    uncovered = _uncovered_types(view_registry)
    if only is not None:
        uncovered = [td for td in uncovered if td.name in only]
    if limit is not None:
        uncovered = uncovered[:limit]

    summary = {
        "project": project_name,
        "total_uncovered": len(uncovered),
        "results": [],
    }

    for td in uncovered:
        dep_views = _dep_views_for(td, view_registry)
        record = {
            "type_short": td.name,
            "qualified_name": td.qualified_name,
            "kind": td.kind,
            "n_fields": len(td.fields),
            "n_variants": len(td.variants),
            "source_file": td.source_file,
            "source_line": td.source_line,
            "deps": list(dep_views.keys()),
        }
        if dry_run:
            record["action"] = "dry-run"
        else:
            entry = synthesize_view(
                td, dep_views=dep_views, cache=cache,
                client=client,
                project=project_name,
                force=force,
            )
            if entry is None:
                record["action"] = "failed"
            elif entry.view_source == VIEW_SOURCE_TAG and entry.view_decl:
                record["action"] = "ok"
                record["viewed_type"] = entry.viewed_type
            else:
                record["action"] = "invalid"
        summary["results"].append(record)

    # Persist summary alongside the cache.
    (cache.root / "_prefill_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    return summary


def _dep_views_for(td: TypeDef, view_registry) -> dict[str, str]:
    """Resolve the views of every short type referenced by ``td``.

    Returns a ``{short_name: "<layer> → <viewed_type>"}`` map for
    inclusion in the prompt. Only includes types the cheap layers can
    already resolve (so the LLM can lean on them); if a dependency is
    itself uncovered we still include it so the LLM can flag the
    transitive need.
    """
    out: dict[str, str] = {}
    seen: set[str] = set()
    refs: list[str] = []

    for fld in td.fields:
        refs.extend(fld.type_refs or [])
    for v in td.variants:
        for fld in v.fields:
            refs.extend(fld.type_refs or [])

    for r in refs:
        if r in seen:
            continue
        seen.add(r)
        if r not in view_registry.types_by_short:
            continue
        e = TypeExpr(kind="leaf", head=r, raw=r)
        res = view_registry.resolve(e)
        if res.is_resolved:
            out[r] = f"{res.layer} → {res.view_type_text}  ({res.rationale})"
        else:
            out[r] = f"uncovered ({res.rationale})"
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("prefill",
                        help="Batch-synthesize views for a project's "
                             "L1/L2/L3-uncovered types.")
    pf.add_argument("--project", required=True,
                    help="Project name (used in prompt + summary header).")
    pf.add_argument("--root", required=True, type=Path,
                    help="Project source root (passed to ViewRegistry.from_project).")
    pf.add_argument("--cache-dir", required=True, type=Path,
                    help="Cache directory (e.g. "
                         "results-verusage/view_registry/<project>).")
    pf.add_argument("--model", default=None)
    pf.add_argument("--effort", default=None,
                    help="Copilot reasoning effort (low/medium/high).")
    pf.add_argument("--timeout", type=int, default=600)
    pf.add_argument("--only", default=None,
                    help="Comma-separated short names to restrict to.")
    pf.add_argument("--limit", type=int, default=None)
    pf.add_argument("--dry-run", action="store_true")
    pf.add_argument("--force", action="store_true",
                    help="Ignore cache hits, re-query the LLM.")

    insp = sub.add_parser("inspect",
                          help="Print cache contents for a project.")
    insp.add_argument("--cache-dir", required=True, type=Path)
    insp.add_argument("--show-decl", action="store_true",
                      help="Print full view_decl text (otherwise just summary).")

    ts_test = sub.add_parser("test",
                             help="Run module self-tests "
                                  "(no network calls).")

    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    if args.cmd == "test":
        return _run_self_tests()

    if args.cmd == "inspect":
        cache = ViewCache(args.cache_dir)
        entries = cache.all_entries()
        if not entries:
            print(f"(empty cache at {args.cache_dir})")
            return 0
        for e in entries:
            print(f"\n=== {e.type_short}  ({e.view_source}) ===")
            print(f"viewed_type: {e.viewed_type}")
            print(f"depends_on_views_of: {e.depends_on_views_of}")
            print(f"rationale: {e.rationale}")
            if args.show_decl:
                print("\nview_decl:")
                print(e.view_decl)
        print(f"\n[{len(entries)} entries]")
        return 0

    if args.cmd == "prefill":
        from spec_determinism.view.registry import ViewRegistry
        reg = ViewRegistry.from_project(args.root)
        cache = ViewCache(args.cache_dir)
        client = CopilotViewLLM(
            model=args.model,
            reasoning_effort=args.effort,
            timeout=args.timeout,
        )
        only = (set(s.strip() for s in args.only.split(","))
                if args.only else None)
        summary = prefill_project(
            args.root,
            view_registry=reg,
            cache=cache,
            client=client,
            project_name=args.project,
            only=only,
            limit=args.limit,
            dry_run=args.dry_run,
            force=args.force,
        )
        n_ok = sum(1 for r in summary["results"] if r["action"] == "ok")
        n_fail = sum(1 for r in summary["results"] if r["action"] == "failed")
        n_invalid = sum(1 for r in summary["results"]
                        if r["action"] == "invalid")
        n_dry = sum(1 for r in summary["results"] if r["action"] == "dry-run")
        print(f"prefill {args.project}: total={summary['total_uncovered']}  "
              f"ok={n_ok}  fail={n_fail}  invalid={n_invalid}  "
              f"dry-run={n_dry}")
        return 0

    return 1


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------


def _run_self_tests() -> int:
    """Lightweight in-process tests (no LLM calls)."""
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- parse_view_response: valid fenced JSON
    raw = """\
some preamble
```json
{
  "viewed_type": "PageView",
  "view_decl": "impl View for Page { type V = PageView; closed spec fn view(&self) -> PageView { PageView { id: self.id } } }",
  "rationale": "test"
}
```
trailing text
"""
    d = parse_view_response(raw)
    check(d["viewed_type"] == "PageView", "parse: viewed_type")
    check("rationale" in d, "parse: rationale")

    # --- parse_view_response: missing required key
    raw_bad = '```json\n{"viewed_type": "X", "rationale": "y"}\n```'
    try:
        parse_view_response(raw_bad)
        failures.append("parse: should have rejected missing view_decl")
    except ValueError:
        pass

    # --- validate_view_decl: well-formed impl
    good = (
        "impl View for Page {\n"
        "    type V = PageView;\n"
        "    closed spec fn view(&self) -> PageView {\n"
        "        PageView { id: self.id }\n"
        "    }\n"
        "}"
    )
    ok, msg = validate_view_decl(good)
    check(ok, f"validate good: {msg}")

    # --- validate_view_decl: missing `View for`
    not_view = (
        "impl Page {\n"
        "    fn hello(&self) {}\n"
        "}"
    )
    ok, msg = validate_view_decl(not_view)
    check(not ok, f"validate non-View: should have failed but got: {msg}")

    # --- validate_view_decl: tree-sitter parse error
    broken = "impl View for Page { type V = ; closed spec fn"
    ok, msg = validate_view_decl(broken)
    check(not ok, "validate broken: should have failed")

    # --- validate_view_decl: empty
    ok, msg = validate_view_decl("")
    check(not ok, "validate empty: should have failed")

    # --- _source_hash: stable
    h1 = _source_hash("pub struct Foo { x: usize }")
    h2 = _source_hash("pub struct Foo { x: usize }")
    h3 = _source_hash("pub struct Foo { y: usize }")
    check(h1 == h2, "_source_hash deterministic")
    check(h1 != h3, "_source_hash differs on different input")

    # --- ViewCache round-trip
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        c = ViewCache(Path(tmp))
        e = CacheEntry(
            type_short="Foo",
            qualified_name="m::Foo",
            source_hash="abc123",
            view_source=VIEW_SOURCE_TAG,
            viewed_type="FooView",
            view_decl="impl View for Foo { type V = FooView; "
                      "closed spec fn view(&self) -> FooView "
                      "{ FooView {} } }",
            rationale="r",
        )
        p = c.put(e)
        check(p.exists(), "cache: file written")
        loaded = c.get("Foo", "abc123")
        check(loaded is not None, "cache: hit on matching hash")
        check(loaded.viewed_type == "FooView", "cache: round-trip viewed_type")
        loaded_miss = c.get("Foo", "different-hash")
        check(loaded_miss is None, "cache: miss on hash mismatch")
        loaded_absent = c.get("DoesNotExist", "any")
        check(loaded_absent is None, "cache: miss when file absent")

        all_e = c.all_entries()
        check(len(all_e) == 1, f"cache: all_entries len {len(all_e)}")

    # --- _find_impl_item: locates inside verus_block wrapper
    src = "verus! {\n" + good + "\n}"
    tree = _parser.parse(src.encode("utf-8"))
    impl = _find_impl_item(tree.root_node)
    check(impl is not None, "find_impl_item: located")
    check(impl.type == "impl_item", "find_impl_item: correct type")

    # --- build_view_prompt: does not crash on a minimal TypeDef
    td = TypeDef(
        name="Page",
        qualified_name="m::Page",
        kind="struct",
        source_file="",
        source_line=0,
    )
    p = build_view_prompt(
        td, "pub struct Page { pub id: usize }", {"usize": "primitive"},
        project="test",
    )
    check("Target type" in p, "prompt: has target section")
    check("Page" in p, "prompt: mentions type")
    check("primitive" in p, "prompt: includes dep")

    # --- CacheEntry round-trip via to_dict / from_dict
    e2 = CacheEntry.from_dict(e.to_dict())
    check(e2.type_short == e.type_short, "CacheEntry: round-trip name")
    check(e2.depends_on_views_of == e.depends_on_views_of,
          "CacheEntry: round-trip deps")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("All self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
