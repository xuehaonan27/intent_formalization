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
    FieldDecl,
    TypeDef,
    TypeExpr,
    VariantDecl,
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

## Self-recursive types  (PR-E)

A type `T` is **self-recursive** when one of its fields (or one of its
enum-variant fields) — directly or through a container — references
`T` itself. Examples:

- `pub struct PTDir { entries: Seq<Option<PTDir>>, ... }`   // tree
- `pub struct Node  { children: Vec<Node>, ... }`           // n-ary tree
- `pub enum List<T> { Cons(T, Box<List<T>>), Nil }`         // linked list

The `@` operator does **NOT** auto-descend through container
generics. `self.entries@` on a `Seq<Option<T>>` field yields
`Seq<Option<T>>` (identity), **not** `Seq<Option<TView>>`. So the
bare-`@` pattern that works for non-recursive fields silently
type-mismatches on a self-recursive container. You have three legal
shapes — pick the cheapest that compiles:

### Option C — identity view (`type V = Self`)  *preferred*

Use when **every** field is already spec-friendly: each field type
either is a Verus primitive (`int`/`nat`/`bool`/`usize`/`char`/...),
a vstd spec container (`Seq`/`Set`/`Map`/`Multiset`) **all the way
down**, or has identity `View::V` (V = T). Then:

```rust
impl View for T {
    type V = T;
    closed spec fn view(&self) -> T { *self }
}
```

This is identical to spec-level structural compare — no abstraction
loss, no extra schemas, no SMT trigger noise.

### Option B — V mirrors concrete inner

Use when some fields are `Ghost<X>`/`Tracked<X>` ghost wrappers but
the surviving fields are all spec-friendly. V looks like the concrete
type with ghost wrappers stripped (and ghost-only fields elided).
**Recursive fields keep `T` (NOT `<T>View`)** inside their container,
and the body copies them through unchanged:

```rust
pub struct TView { region: MemRegion, entries: Seq<Option<T>>, ... }
impl View for T {
    type V = TView;
    closed spec fn view(&self) -> TView {
        TView { region: self.region, entries: self.entries, ... }
    }
}
```

### Option A — recursive lift  *most expensive — avoid if possible*

Use **only** when the inner type's view genuinely abstracts away
information (its `V` is a smaller / different shape than `T`).
V replaces `T` with `<T>View` inside the container, and the body
**must** lift explicitly with `Seq::new` / `Map::new` / `match`:

```rust
pub struct TView { ..., entries: Seq<Option<TView>>, ... }
impl View for T {
    type V = TView;
    closed spec fn view(&self) -> TView {
        TView {
            ...,
            entries: Seq::new(
                self.entries.len(),
                |i: int| match self.entries[i] {
                    Some(d) => Some(d@),
                    None => None,
                },
            ),
        }
    }
}
```

⚠ **Cost note.** Each container layer over `Self` inside V multiplies
schema-search work (one extra dimension to enumerate per layer), and
SMT extensionality on the recursive `view()` function adds trigger
pressure. Always prefer **C** (or **B**) over **A** when both
compile.
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

## Example: self-recursive  (preferred Option C path)

### Type
```
pub struct Tree {
    pub value: i64,
    pub children: Seq<Tree>,
}
```

Already-resolved views of dependencies:
- `i64`: primitive (no `View::view`).
- `Seq<T>`: identity view (vstd container — `type V = Seq<T>`).

### Response

```json
{
  "viewed_type": "Tree",
  "view_decl": "impl View for Tree {\\n    type V = Tree;\\n    closed spec fn view(&self) -> Tree { *self }\\n}",
  "depends_on_views_of": [],
  "rationale": "Tree is self-recursive via Seq<Tree>. Every field (i64 primitive, Seq<Tree> vstd-identity) is already spec-friendly, so identity view (Option C) is the cheapest correct choice. Writing a separate TreeView with Seq<TreeView> would force an explicit Seq::new lift (Option A) that costs schema search and SMT triggers without buying any abstraction."
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
    # PR-E — surface self-recursion early. The LLM has been observed
    # to default to ``self.<field>@`` on container-wrapped self fields,
    # which silently mis-types against a ``Seq<Option<TView>>`` V
    # declaration (cf. ``check_m4_self_recursion_bare_at`` for the
    # post-hoc lint).
    if _is_self_recursive(td):
        rec_fields = sorted(_self_recursive_fields(td).keys())
        parts.append(
            "\n\n## ⚠ Self-recursion alert\n\n"
            f"This type is **self-recursive** via field(s): "
            f"`{', '.join(rec_fields)}`. **Re-read the "
            f"\"Self-recursive types\" section above before answering.** "
            "The most common failure mode is declaring V as "
            f"`Seq<Option<{td.name}View>>` (or similar) but assigning "
            f"`self.<field>@` to it: `@` does not auto-descend through "
            "containers. Prefer **Option C** (`type V = "
            f"{td.name};` with body `*self`) when every field is "
            "spec-friendly. Use **Option A** (`Seq::new`/`map_values` "
            "lift) only when the inner type's `View::V` is genuinely "
            "smaller than the inner type."
        )
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


_VIEW_FN_BODY_RE = re.compile(
    r"fn\s+view\s*\(\s*&?\s*self\b[^)]*\)\s*->\s*[^{]+\{",
)


def _extract_view_fn_body(view_decl: str) -> Optional[str]:
    """Return the textual body of ``spec fn view(&self) -> ... { … }``.

    Returns ``None`` if no ``fn view`` is found.
    """
    m = _VIEW_FN_BODY_RE.search(view_decl)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    for i in range(start, len(view_decl)):
        c = view_decl[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return view_decl[start + 1:i]
    return None


def _normalize_unit_type(t: str) -> bool:
    """True iff ``t`` denotes the unit type.

    Accepts ``()``, ``Self::V`` won't match — caller should pass the
    *normalized* viewed type. Whitespace and ``type V = ();`` tail are
    tolerated.
    """
    s = (t or "").strip().rstrip(";").strip()
    return s in ("()", "Unit")


def check_view_body_uses_self(view_decl: str, viewed_type: str) -> tuple[bool, str]:
    """Reject view bodies whose RHS does not reference ``self``.

    A view body that doesn't read from ``self`` collapses every value of
    the type to the same spec witness — e.g. ``arbitrary()``, a constant
    struct literal, or ``Seq::empty()``. The resulting
    ``equal_v(a, b)`` is then provably ``true`` for *every* pair ``a, b``,
    silently masking real non-determinism.

    The only legitimate exception is ``type V = ();`` with body ``()`` —
    a deliberate "this type carries no spec content" collapse (used for
    raw-pointer / extern-fn-pointer wrappers). We let that through.

    Returns ``(ok, message)``. ``ok=False`` means the view should be
    treated as a hard reject (do not cache, route to ``_rejected.jsonl``).
    """
    body = _extract_view_fn_body(view_decl)
    if body is None:
        return True, "no view fn body found (skipped)"
    # Strip line and block comments before scanning.
    body_stripped = re.sub(r"//[^\n]*", "", body)
    body_stripped = re.sub(r"/\*.*?\*/", "", body_stripped, flags=re.S)
    if re.search(r"\bself\b", body_stripped):
        return True, "ok"
    if _normalize_unit_type(viewed_type):
        return True, "ok (legitimate unit collapse)"
    return (
        False,
        "view body does not reference `self`; this collapses every "
        "instance to the same spec value (e.g. `arbitrary()` returns a "
        "fixed witness), silently making equal_v(a, b) provably true",
    )


# ---------------------------------------------------------------------------
# PR-D5 — M1 / M2 / M3 static lints
#
# Detector sketches live in docs/critic-criteria.md (commit 33bd09a). The
# acceptance test for every rule is the 14-quarantine fixture set from
# ISSUES.md #7 plus the 4 winning views as negative controls.
# ---------------------------------------------------------------------------

# Heads that vstd / std unconditionally implement View for. The L1 resolver
# also picks these up at prelude time; we hard-code them here to avoid
# importing ``view.prelude`` (would create a cycle with ``view.registry``).
VSTD_VIEW_HEADS: frozenset[str] = frozenset({
    # vstd containers / wrappers
    "Vec", "Box", "Rc", "Arc", "Option", "Result",
    "Seq", "Set", "Map", "Multiset", "FnSpec",
    "Ghost", "Tracked",
    # primitives — Verus auto-derives View
    "u8", "u16", "u32", "u64", "u128", "usize",
    "i8", "i16", "i32", "i64", "i128", "isize",
    "bool", "char", "str", "int", "nat",
    # vstd containers that view to themselves
    "Array", "PrimitiveBytes",
    # vstd has `impl View for String { type V = Seq<char>; }`
    "String",
    # spec_fn(...) is a spec-only type; identity View applies.
    "spec_fn",
    # spec library widgets that have an identity View
    "()",
})

# Heads whose value is NOT projectable via `@` even when wrapped in Ghost
# or Tracked. Applying `@@` to a `Ghost<X>` where X is one of these is
# always wrong.
#
# IMPORTANT: ``Set``/``Seq``/``Map``/``Multiset`` are **identity-View**
# in vstd (they're spec-only collections), so ``Ghost<Set<…>>@@`` peels
# Ghost then returns Set unchanged — atmosphere/Container relies on
# this pattern in its real view_decl and verifies cleanly. They were
# initially listed as non-viewable in PR-D5's first draft; the
# retroactive scan caught the false positive on Container before any
# real bug used this rule. The list below is now narrowed to the heads
# that genuinely have no projectable View at all.
NON_VIEWABLE_INNER_HEADS: frozenset[str] = frozenset({
    # `FnSpec` is the trait, not the spec function type — projecting
    # an Fn through `@` is a type error.
    "FnSpec",
})


def _strip_ghost_tracked(te) -> "tuple[object, list[str]]":
    """Peel outer ``Ghost<…>`` / ``Tracked<…>`` wrappers off a TypeExpr.

    Returns ``(inner_typeexpr, list_of_wrappers_peeled)``. The wrappers
    list is in outside-in order — ``Tracked<Ghost<Set<X>>>`` peels to
    ``(Set<X>, ["Tracked", "Ghost"])``.
    """
    wraps: list[str] = []
    cur = te
    # Guard: only `generic` TypeExpr with exactly 1 arg counts as a wrap.
    while (cur is not None
           and getattr(cur, "kind", None) == "generic"
           and getattr(cur, "head", None) in ("Ghost", "Tracked")
           and len(getattr(cur, "args", []) or []) == 1):
        wraps.append(cur.head)
        cur = cur.args[0]
    return cur, wraps


def _field_type(td: "TypeDef", name: str):
    """Find a struct field by name (or tuple position).

    Searches:
    * top-level ``td.fields`` (struct / tuple-struct / union);
    * every enum variant's fields (matches the first hit by name).

    Returns the field's ``TypeExpr`` if available, else ``None``.
    """
    for f in td.fields or []:
        if f.name == name:
            return f.type_expr
    for v in td.variants or []:
        for f in v.fields or []:
            if f.name == name:
                return f.type_expr
    return None


# ``#[repr(C)]`` / ``#[repr(C, align(N))]`` discovered in the body excerpt.
# Used by M3 as a soft warning (Verus often opaque-models repr(C) structs).
# ``#[repr(transparent)]`` newtypes are explicitly NOT flagged: they are
# spec-projectable.
_REPR_RE = re.compile(
    r"#\[\s*repr\s*\(\s*(?P<arg>[A-Za-z0-9_,\s\(\)]+?)\s*\)\s*\]"
)


def _repr_kind_of_source(src_excerpt: str) -> Optional[str]:
    """Return the head repr kind ('C' / 'transparent' / 'packed' / …)
    or ``None`` if the type has no ``#[repr(...)]`` attribute.

    Only the FIRST `#[repr(...)]` is consulted; multi-repr is rare.
    """
    m = _REPR_RE.search(src_excerpt or "")
    if not m:
        return None
    arg = m.group("arg")
    # Split off the first head before any "," — keeps "C" out of
    # "C, align(8)".
    return arg.split(",", 1)[0].strip()


# Matches the generics list on the leading `impl<...>` of a view_decl.
# View bodies always come from `impl[<G...>] View for X { ... }` so we
# scan the FIRST `impl<...>` occurrence. The generics list itself may
# contain nested `<>` (bounds like `Foo<Bar>`), so we balance brackets.
_IMPL_HEAD_RE = re.compile(r"\bimpl\b\s*<")


def _extract_impl_generics(view_decl: str) -> set[str]:
    """Return the set of generic-parameter names declared on the
    outermost ``impl<...>`` block of a view_decl.

    For ``impl<K: KeyTrait + VerusClone + View> View for KeyIterator<K>``
    this returns ``{"K"}``. Lifetimes (``'a``) are skipped. Returns an
    empty set if the impl block has no generics (or if the decl is a
    bare ``pub struct …``).

    These names are treated by ``check_m1_view_targets_have_view`` as
    already-viewable: the synthesiser is trusting the impl's trait
    bounds, and Verus will catch any missing ``View`` bound at parse
    time.
    """
    if not view_decl:
        return set()
    m = _IMPL_HEAD_RE.search(view_decl)
    if not m:
        return set()
    start = m.end()  # position just past the `<`
    depth = 1
    i = start
    n = len(view_decl)
    while i < n and depth > 0:
        c = view_decl[i]
        if c == "<":
            depth += 1
        elif c == ">":
            depth -= 1
        i += 1
    if depth != 0:
        return set()
    inner = view_decl[start : i - 1]
    out: set[str] = set()
    # Split on top-level commas (depth-aware to avoid commas inside
    # nested bounds like ``Foo<A, B>``).
    parts: list[str] = []
    buf: list[str] = []
    d = 0
    for c in inner:
        if c == "<":
            d += 1
        elif c == ">":
            d -= 1
        if c == "," and d == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
    if buf:
        parts.append("".join(buf))
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # `'lifetime` or `const N: usize` — skip.
        if p.startswith("'"):
            continue
        if p.startswith("const "):
            continue
        # Take the identifier before the first ':' (bound) / '=' (default).
        for sep in (":", "="):
            idx = p.find(sep)
            if idx != -1:
                p = p[:idx]
                break
        name = p.strip()
        if name and (name[0].isalpha() or name[0] == "_"):
            out.add(name)
    return out


# Matches `type V = (...);` on the impl block — used by M3's unit-V
# exemption. Only the FIRST `type V = ...;` is considered (view impls
# only declare V once).
_TYPE_V_RE = re.compile(r"\btype\s+V\s*=\s*(?P<rhs>[^;]+?)\s*;")


def _view_v_type(view_decl: str) -> Optional[str]:
    """Return the textual right-hand side of ``type V = …;`` or
    ``None`` if the decl has no such declaration (e.g. it's only the
    V-struct definition without the impl block, in which case M3 is
    not applicable anyway).
    """
    m = _TYPE_V_RE.search(view_decl or "")
    if not m:
        return None
    return m.group("rhs").strip()


def _is_unit_v(view_decl: str) -> bool:
    """True iff the view's V-type is the unit type ``()``.

    Recognises the "legitimate unit collapse" pattern documented in
    ``docs/critic-criteria.md`` (the same exception that
    ``check_view_body_uses_self`` already allows): when V is ``()`` the
    view discards all spec content; this is the canonical way to mark
    an external_body / FFI type as "no spec story" without bothering
    the verifier.
    """
    v = _view_v_type(view_decl)
    return v == "()"


# ---------------------------------------------------------------------------
# M3 — parent is `external_body` / `#[repr(C)]` opaque
# ---------------------------------------------------------------------------


def check_m3_parent_not_opaque(
    td: "TypeDef",
    *,
    src_excerpt: str = "",
    view_decl: str = "",
) -> Optional[str]:
    """M3: reject when the parent type is opaque to Verus.

    * Hard reject on ``#[verifier::external_body]`` — Verus refuses
      ``self.field`` projections inside spec functions on such types.
    * Unit-V exemption: an external_body parent with ``type V = ();``
      and a unit body is the documented "legitimate unit collapse"
      escape hatch (cf. ``check_view_body_uses_self`` and
      ``docs/critic-criteria.md``). Accept these silently.
    * Soft reject (None — let M1/M2 produce a more actionable message)
      on ``#[repr(C)]``; this is often used for FFI / hardware-layout
      structs that Verus opaque-models, but the failure mode is the
      same as M1 (field type has no View) so M1 wins.
    * No flag on ``#[repr(transparent)]``: newtype wrappers are
      spec-projectable.
    """
    if getattr(td, "is_external_body", False):
        if _is_unit_v(view_decl):
            return None
        return (
            f"M3: `{td.name}` is `#[verifier::external_body]` — Verus "
            f"treats its fields as opaque and forbids field "
            f"expressions in spec functions. Either drop `{td.name}` "
            f"from the L4 work list, rewrite via an "
            f"`external_type_specification` shim, or collapse the "
            f"view body to `type V = (); fn view -> () {{ () }}`."
        )
    # repr(C) is intentionally NOT a hard reject here; M1/M2 handle the
    # concrete failure mode (no view on the inner type).
    return None


# ---------------------------------------------------------------------------
# M2 — `self.field@@` projects past Ghost into Set/Map/Multiset/etc.
# ---------------------------------------------------------------------------

# ``@@`` is unambiguous in the Verus grammar (no overload, no operator
# method named ``@@``), so regex over the body is precise enough.
_DOUBLE_AT_RE = re.compile(r"\bself\.([A-Za-z_][A-Za-z0-9_]*)\s*@\s*@")


def check_m2_no_double_at_past_ghost(
    view_decl: str,
    *,
    td: "TypeDef",
) -> Optional[str]:
    """M2: reject ``self.<field>@@`` when the inner type has no View.

    Sequence: peel outer Ghost/Tracked, look at the *inner* head; if
    it's in NON_VIEWABLE_INNER_HEADS, the second ``@`` is a type
    error. We also reject when the field itself is not Ghost/Tracked
    (``@@`` only makes sense as "peel Ghost, then view").
    """
    body = _extract_view_fn_body(view_decl) or ""
    # Strip comments so a stray "@@" in a comment doesn't false-fire.
    body_stripped = re.sub(r"//[^\n]*", "", body)
    body_stripped = re.sub(r"/\*.*?\*/", "", body_stripped, flags=re.S)

    for m in _DOUBLE_AT_RE.finditer(body_stripped):
        fname = m.group(1)
        ftype = _field_type(td, fname)
        if ftype is None:
            return (
                f"M2: `self.{fname}@@` references field `{fname}` not "
                f"found on `{td.name}`. Either the synthesiser "
                f"hallucinated a field or impl_scanner missed it."
            )
        head = getattr(ftype, "head", None)
        if head not in ("Ghost", "Tracked"):
            return (
                f"M2: `self.{fname}@@` applied to a `{head}` field "
                f"(not `Ghost<…>` / `Tracked<…>`). Double-`@` only "
                f"makes sense as 'peel Ghost, then view'; use a single "
                f"`@` here."
            )
        # Peel Ghost/Tracked and inspect the inner head.
        inner, _wraps = _strip_ghost_tracked(ftype)
        inner_head = getattr(inner, "head", None) if inner is not None else None
        if inner_head in NON_VIEWABLE_INNER_HEADS:
            return (
                f"M2: `self.{fname}@@` projects past `{head}` into "
                f"`{inner_head}`, which has no `View::view`. Use a "
                f"single `@` to unwrap `{head}`; the resulting "
                f"`{inner_head}` already lives in spec land."
            )
    return None


# ---------------------------------------------------------------------------
# M1 — view body / V-struct references a head with no resolvable View
# ---------------------------------------------------------------------------

# Regex fallbacks for type references — robust to whitespace and
# nesting. The view_decl is small (< 2 KB) so a few passes are cheap.
_AS_VIEW_RE = re.compile(
    r"<\s*(?P<head>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s*<[^<>]*>)?"           # optional generic args on the head
    r"\s+as\s+View\s*>\s*::\s*V"
)
_SELF_FIELD_AT_RE = re.compile(
    r"\bself\.(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s*@(?!\s*@)"
)


def check_m1_view_targets_have_view(
    view_decl: str,
    *,
    td: "TypeDef",
    known_view_heads: set[str],
    cache: Optional["ViewCache"] = None,
) -> Optional[str]:
    """M1: reject if the view body / V-struct references a type whose
    View is not in the registry.

    Inputs
    ------
    view_decl :
        Full ``impl View for X { type V = …; spec fn view(&self) -> … }``
        block source.
    td :
        Parent ``TypeDef``; used to look up field types referenced via
        ``self.<field>@``.
    known_view_heads :
        Union of (a) every short name with a registered ``impl View``
        in the project scan, (b) every short name with an active
        (non-quarantined) cached L4 entry. Caller is responsible for
        merging.
    cache :
        Optional ``ViewCache``; when provided, ``cache.is_quarantined``
        is consulted to upgrade an otherwise-tolerable miss into an
        explicit "cascade" reject.

    Returns ``None`` on accept, a reject reason on reject.
    """
    refs: set[str] = set()
    body = _extract_view_fn_body(view_decl) or ""
    body_stripped = re.sub(r"//[^\n]*", "", body)
    body_stripped = re.sub(r"/\*.*?\*/", "", body_stripped, flags=re.S)
    decl_stripped = re.sub(r"//[^\n]*", "", view_decl)
    decl_stripped = re.sub(r"/\*.*?\*/", "", decl_stripped, flags=re.S)

    # Generic params on the impl block are assumed to satisfy any View
    # bound the synthesiser intends; Verus will reject at parse time
    # if the bound is actually missing.
    impl_generics = _extract_impl_generics(decl_stripped)

    # --- Step 1 — gather <X as View>::V refs across the entire decl.
    for m in _AS_VIEW_RE.finditer(decl_stripped):
        refs.add(m.group("head"))

    # --- Step 2 — gather self.<field>@ projections.
    # We resolve the field type's head through impl_scanner.field_type;
    # if Ghost / Tracked, peel one level and take the inner head.
    seen_fields: set[str] = set()
    for m in _SELF_FIELD_AT_RE.finditer(body_stripped):
        fname = m.group("field")
        if fname in seen_fields:
            continue
        seen_fields.add(fname)
        ftype = _field_type(td, fname)
        if ftype is None:
            # Field is not in our TypeDef — conservative reject; the
            # synthesiser may have hallucinated.
            return (
                f"M1: `self.{fname}@` references unknown field on "
                f"`{td.name}`. The synthesiser may have hallucinated; "
                f"reject conservatively."
            )
        # Peel one Ghost/Tracked layer (one `@` peels Ghost), then take
        # the head.
        head = getattr(ftype, "head", None)
        if head in ("Ghost", "Tracked"):
            inner, _ = _strip_ghost_tracked(ftype)
            head = getattr(inner, "head", None) if inner is not None else None
        # `spec_fn(int) -> bool` parses with kind="fn"; treat it as
        # already-viewable (spec functions are spec-only).
        if head is None:
            kind = getattr(ftype, "kind", None)
            if kind == "fn":
                continue
        if head:
            refs.add(head)

    # --- Step 3 — every referenced head must be View-resolvable.
    for h in sorted(refs):
        if h in VSTD_VIEW_HEADS:
            continue
        if h in impl_generics:
            continue
        if h in known_view_heads:
            continue
        if cache is not None and cache.is_quarantined(h):
            return (
                f"M1: references `{h}` (via `<{h} as View>::V` or "
                f"`self.<…>@`), which is currently quarantined. "
                f"Re-attempting this view would cascade-break."
            )
        return (
            f"M1: references `{h}` (via `<{h} as View>::V` or "
            f"`self.<…>@`), but no View impl is registered for `{h}` "
            f"(not in VSTD_VIEW_HEADS, not a generic parameter of "
            f"this impl, not in project view registry). "
            f"Either restructure to avoid the dependency, add a "
            f"manual `impl View for {h}`, or quarantine `{td.name}` "
            f"until `{h}` is covered."
        )
    return None


# ---------------------------------------------------------------------------
# M4 — self-recursive type projected by bare `@` on a container field
#
# Pattern caught:
#
#   pub struct PTDirView { ..., entries: Seq<Option<PTDirView>>, ... }
#   impl View for PTDir {
#       spec fn view(&self) -> PTDirView {
#           PTDirView { ..., entries: self.entries@, ... }  // type mismatch
#       }
#   }
#
# `@` does NOT auto-descend through container generics: `self.entries`
# has type ``Seq<Option<PTDir>>`` and `self.entries@` returns
# ``Seq<Option<PTDir>>`` (identity), NOT ``Seq<Option<PTDirView>>``.
# So the assignment in the V-struct typechecks only when V's recursive
# field keeps the concrete ``PTDir`` head (Options B/C) — or the body
# uses an explicit ``Seq::new`` / ``map_values`` lift (Option A).
# ---------------------------------------------------------------------------


def _self_recursive_fields(td: "TypeDef") -> dict[str, "object"]:
    """Return ``{display_name: type_expr}`` for fields whose type
    transitively references ``td.name``.

    Display names are bare field names for struct fields, and
    ``Variant:field`` for variant fields (kept distinct so a struct
    can't shadow a variant field's diagnostic).
    """
    out: dict[str, object] = {}
    for f in td.fields:
        if td.name in (f.type_refs or []):
            out[f.name] = f.type_expr
    for v in td.variants:
        for f in v.fields:
            if td.name in (f.type_refs or []):
                out[f"{v.name}:{f.name}"] = f.type_expr
    return out


def _is_self_recursive(td: "TypeDef") -> bool:
    """True iff ``td`` has at least one field (struct or variant) whose
    parsed ``type_refs`` mention ``td.name``."""
    return bool(_self_recursive_fields(td))


# Matches a (sub-)field declaration in either a V struct or the parent
# struct: ``name: <type>,``. We use the surrounding decl text to filter
# down to V-struct decls (see M4 detector below).
_V_FIELD_DECL_RE = re.compile(
    r"\b(?:pub\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<rhs>[^,\n}]+)"
)


def check_m4_self_recursion_bare_at(
    view_decl: str,
    *,
    td: "TypeDef",
) -> Optional[str]:
    """M4: when ``td`` is self-recursive, reject bare ``self.<field>@``
    projections on container-wrapped self fields whose V-side type
    mentions the V head (e.g. ``<T>View``).

    Accepts:

    * non-self-recursive types (no-op);
    * self-recursive types whose V-side field keeps the concrete head
      (Option B — body's bare ``@`` is identity-correct);
    * self-recursive types with ``type V = Self`` / ``type V = T``
      (Option C — body uses ``*self`` and no bare ``@``);
    * self-recursive types using explicit ``Seq::new`` / ``map_values``
      lift inside the body for the recursive field (Option A — no
      bare ``self.<field>@`` on that field).

    Rejects:

    * the LLM's most common self-recursion bug — declaring V as
      ``Seq<Option<TView>>`` but assigning ``self.entries@`` to it.
      The mismatch is a guaranteed typecheck failure; we catch it
      pre-critic so it never reaches the cache.
    """
    self_rec = _self_recursive_fields(td)
    if not self_rec:
        return None

    body = _extract_view_fn_body(view_decl) or ""
    body_stripped = re.sub(r"//[^\n]*", "", body)
    body_stripped = re.sub(r"/\*.*?\*/", "", body_stripped, flags=re.S)
    decl_stripped = re.sub(r"//[^\n]*", "", view_decl)
    decl_stripped = re.sub(r"/\*.*?\*/", "", decl_stripped, flags=re.S)

    # The V-type head, e.g. ``PTDirView`` for ``type V = PTDirView;``.
    # If absent we can't compute the M4 pattern.
    v_text = _view_v_type(view_decl) or ""
    v_head = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", v_text)
    if not v_head:
        return None
    v_head_name = v_head.group(1)
    # Identity-V (`type V = Self` or `type V = T`) is sound by
    # construction — body uses ``*self`` and there's no bare ``@`` to
    # mismatch on. Skip immediately.
    if v_head_name in ("Self", td.name):
        return None

    # Which fields does the body bare-@-project?
    bare_at_fields: set[str] = set()
    for m in _SELF_FIELD_AT_RE.finditer(body_stripped):
        bare_at_fields.add(m.group("field"))

    # Reduce keys to bare-field-names for cross-matching with the body
    # (variants share field names across arms; we only care about the
    # simple identifier).
    self_rec_names = {
        (k.split(":", 1)[1] if ":" in k else k) for k in self_rec
    }

    if not (bare_at_fields & self_rec_names):
        # No bare-@ on a self-recursive field → no M4 issue, regardless
        # of V's shape.
        return None

    # Decide whether V's field declaration for any of the implicated
    # field names mentions ``v_head_name`` (the V head — i.e. wraps the
    # recursive position in ``<T>View``).
    #
    # Heuristic: scan all ``name: <type>,`` occurrences in decl_stripped
    # (we don't try to demarcate the V-struct from the impl block — if
    # the V head appears anywhere in a field RHS for a self-rec field
    # name, the bug pattern is present). To avoid false-positive on the
    # parent's own field decl ``entries: Seq<Option<PTDir>>``, we
    # restrict the match to RHS-es that contain ``v_head_name`` as a
    # whole word (the parent's RHS uses ``td.name``, not the V head).
    rec_at = bare_at_fields & self_rec_names
    for m in _V_FIELD_DECL_RE.finditer(decl_stripped):
        fname = m.group("name")
        rhs = m.group("rhs").strip()
        if fname not in rec_at:
            continue
        if not re.search(rf"\b{re.escape(v_head_name)}\b", rhs):
            continue
        # Found the bug.
        return (
            f"M4: `{td.name}` is self-recursive (field `{fname}` "
            f"transitively contains `{td.name}`) and V declares "
            f"`{fname}: {rhs}` — wrapping the recursive position in "
            f"`{v_head_name}` — but the body uses bare "
            f"`self.{fname}@`. `@` does not descend through containers "
            f"like `Seq` / `Option` / `Vec`: `self.{fname}@` yields the "
            f"concrete container of `{td.name}` (identity), not "
            f"`{rhs}`. Fix options: "
            f"(C, preferred) `type V = {td.name};` with body `*self`; "
            f"(B) drop `{v_head_name}` from the recursive position in V "
            f"(keep `{td.name}`) and assign `self.{fname}` directly; "
            f"(A) write an explicit "
            f"`Seq::new(self.{fname}.len(), |i| match self.{fname}[i] "
            f"{{ Some(d) => Some(d@), None => None }})` lift — but A "
            f"only buys abstraction when the inner type's `View::V` "
            f"differs from itself; otherwise A is strictly more "
            f"expensive than C/B."
        )
    return None



def lint_view_decl(
    view_decl: str,
    *,
    td: "TypeDef",
    src_excerpt: str = "",
    known_view_heads: Optional[set[str]] = None,
    cache: Optional["ViewCache"] = None,
) -> Optional[tuple[str, str]]:
    """Run M3 → M2 → M4 → M1 in order; return ``(rule, reason)`` on
    first rejection or ``None`` on accept.

    The ordering is intentional:

    * **M3** is cheapest (attribute predicate); rejects external_body
      types before parsing the body at all.
    * **M2** is the most specific (double-``@`` on ``Ghost<NonView>``);
      fires on a strict subset of the cases where M1 would also fire.
    * **M4** is shape-specific to self-recursive types; catches the
      bare-``@``-on-container-of-Self bug that M1 cannot see (the head
      ``T`` is in ``known_view_heads`` so M1 silently accepts).
    * **M1** is the broad catch-all (any missing View head).

    When ``known_view_heads`` is ``None`` (e.g. retroactive scan over
    cached entries with no registry handy), M1 is skipped — only
    M3 / M2 / M4 run. M4 needs no registry: it derives everything
    from ``td.fields[].type_refs`` plus the decl text.
    """
    msg = check_m3_parent_not_opaque(
        td, src_excerpt=src_excerpt, view_decl=view_decl,
    )
    if msg:
        return ("M3", msg)
    msg = check_m2_no_double_at_past_ghost(view_decl, td=td)
    if msg:
        return ("M2", msg)
    msg = check_m4_self_recursion_bare_at(view_decl, td=td)
    if msg:
        return ("M4", msg)
    if known_view_heads is not None:
        msg = check_m1_view_targets_have_view(
            view_decl, td=td,
            known_view_heads=known_view_heads, cache=cache,
        )
        if msg:
            return ("M1", msg)
    return None


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
    # Critic fields (PR-D2.5). Optional — entries written before the
    # critic step landed have ``critic_verdict == ""`` and the registry
    # treats them as unchecked.
    critic_verdict: str = ""
    critic_issues: list[str] = field(default_factory=list)

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
            "critic_verdict": self.critic_verdict,
            "critic_issues": list(self.critic_issues),
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
            critic_verdict=str(d.get("critic_verdict", "") or ""),
            critic_issues=list(d.get("critic_issues") or []),
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

    def is_quarantined(self, short_name: str) -> bool:
        """Return True iff ``<short>.json.quarantine`` exists.

        A quarantined entry means a human (or audit script) has decided
        the previously-synthesised view for ``short_name`` was unsound
        and must not be re-synthesised on the next prefill run. The
        prefill driver consults this and skips quarantined types unless
        ``--include-quarantined`` is passed.

        Quarantine is intentionally a separate sticky file on disk
        rather than a flag inside the regular cache JSON, so that
        accidental deletion of the cache (e.g. ``rm *.json``) does
        not also delete the quarantine record.
        """
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", short_name)
        return (self.root / f"{safe}.json.quarantine").is_file()

    def quarantined_names(self) -> list[str]:
        """List short names with an active ``.json.quarantine`` marker."""
        out: list[str] = []
        for p in sorted(self.root.glob("*.json.quarantine")):
            # path_for() sanitises ``[^A-Za-z0-9_]+`` → ``_``; we cannot
            # reverse that transform, so we report the on-disk stem as
            # authoritative. Callers compare against td.name which is
            # already sanitised at synth time.
            out.append(p.name[: -len(".json.quarantine")])
        return out

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
    critic: Optional["CodexCritic"] = None,
    enable_critic: bool = True,
    status_out: Optional[dict] = None,
    known_view_heads: Optional[set[str]] = None,
) -> Optional[CacheEntry]:
    """Synthesize a view for one type, with cache-hit short-circuit.

    Returns the cached/freshly-generated :class:`CacheEntry`, or
    ``None`` when synthesis or validation failed or the critic
    rejected the candidate.

    If ``status_out`` is provided, the function writes a single key
    ``"status"`` into it on entry, ranging over::

        "cache_hit"      cache hit, no LLM call
        "ok"             fresh synth, accepted (critic accept/revise/error)
        "llm_fail"       copilot.query raised RuntimeError
        "parse_fail"     could not parse JSON from response
        "validate_fail"  tree-sitter parse of view_decl failed
        "lint_reject"    view body fails the static "must reference self" check
        "lint_m1_reject" view references a type with no registered View
        "lint_m2_reject" view applies `@@` over Ghost<NonView>
        "lint_m3_reject" parent type is `external_body` / opaque to Verus
        "lint_m4_reject" self-recursive type uses bare `@` on container of Self
        "critic_reject"  critic rejected the candidate

    ``known_view_heads`` (PR-D5) — set of short type names that have a
    registered View impl in the project (L3 scan + active L4 cache
    entries). Passed through to the M1 detector. ``None`` skips M1.
    """
    from spec_determinism.view.critic import (
        CodexCritic, critique_view, append_rejected,
    )

    def _set(s: str) -> None:
        if status_out is not None:
            status_out["status"] = s

    src_excerpt = _extract_type_source(td)
    src_hash = _source_hash(src_excerpt or td.qualified_name)

    if not force:
        hit = cache.get(td.name, src_hash)
        if hit is not None:
            logger.info("L4 cache hit for %s (hash=%s)", td.name, src_hash)
            _set("cache_hit")
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
        _set("llm_fail")
        return None
    try:
        d = parse_view_response(raw)
    except ValueError as e:
        logger.warning("L4 synth for %s: bad response (%s)", td.name, e)
        _set("parse_fail")
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
        _set("validate_fail")
        return None

    viewed_type = d["viewed_type"]
    rationale = d.get("rationale", "")

    # Static lint: a view body whose RHS does not reference `self` is
    # almost certainly an over-collapse (arbitrary() / constant literal /
    # Seq::empty()). We catch this *before* the codex critic round-trip
    # because (a) the critic has been observed to miss this class of bug
    # (see ISSUES.md #4) and (b) it costs ~0 to check, vs. a codex call.
    ok, msg = check_view_body_uses_self(view_decl, viewed_type)
    if not ok:
        logger.warning(
            "L4 synth for %s: static lint rejected (%s); "
            "appending to _rejected.jsonl and NOT caching",
            td.name, msg,
        )
        append_rejected(
            cache.root,
            type_short=td.name,
            qualified_name=td.qualified_name,
            issues=[f"static lint: {msg}"],
            viewed_type=viewed_type,
            view_decl=view_decl,
            source_hash=src_hash,
        )
        _set("lint_reject")
        return None

    # PR-D5 — M1 / M2 / M3 lints. Reject the candidate without caching
    # if any of the three fires. Status is "lint_m{1,2,3}_reject" so
    # downstream summaries can distinguish.
    m_hit = lint_view_decl(
        view_decl,
        td=td,
        src_excerpt=src_excerpt,
        known_view_heads=known_view_heads,
        cache=cache,
    )
    if m_hit is not None:
        rule, reason = m_hit
        logger.warning(
            "L4 synth for %s: %s rejected (%s); "
            "appending to _rejected.jsonl and NOT caching",
            td.name, rule, reason,
        )
        append_rejected(
            cache.root,
            type_short=td.name,
            qualified_name=td.qualified_name,
            issues=[f"{rule} lint: {reason}"],
            viewed_type=viewed_type,
            view_decl=view_decl,
            source_hash=src_hash,
        )
        _set(f"lint_{rule.lower()}_reject")
        return None

    critic_verdict = ""
    critic_issues: list[str] = []
    if enable_critic:
        if critic is None:
            critic = CodexCritic()
        cr = critique_view(
            type_short=td.name,
            qualified_name=td.qualified_name,
            type_source=src_excerpt,
            viewed_type=viewed_type,
            view_decl=view_decl,
            dep_views=dep_views,
            rationale=rationale,
            project=project,
            run_dir=run_dir,
            critic=critic,
        )
        critic_verdict = cr.verdict
        critic_issues = list(cr.issues)
        if cr.verdict == "reject":
            logger.warning(
                "L4 synth for %s: critic rejected (%d issues); "
                "appending to _rejected.jsonl and NOT caching",
                td.name, len(cr.issues),
            )
            append_rejected(
                cache.root,
                type_short=td.name,
                qualified_name=td.qualified_name,
                issues=cr.issues,
                viewed_type=viewed_type,
                view_decl=view_decl,
                source_hash=src_hash,
            )
            _set("critic_reject")
            return None

    entry = CacheEntry(
        type_short=td.name,
        qualified_name=td.qualified_name,
        source_hash=src_hash,
        view_source=VIEW_SOURCE_TAG,
        viewed_type=viewed_type,
        view_decl=view_decl,
        depends_on_views_of=list(d.get("depends_on_views_of") or []),
        rationale=rationale,
        raw_response=raw,
        critic_verdict=critic_verdict,
        critic_issues=critic_issues,
    )
    cache.put(entry)
    _set("ok")
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
    enable_critic: bool = True,
    critic_model: Optional[str] = None,
    critic_timeout: int = 180,
    include_quarantined: bool = False,
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
    include_quarantined :
        If True, ignore the ``.json.quarantine`` skip-list and
        re-attempt synthesis for those types too. Default is False so
        that a quarantine decision sticks across runs.

    Returns a summary dict suitable for JSON dumping.
    """
    uncovered = _uncovered_types(view_registry)
    if only is not None:
        uncovered = [td for td in uncovered if td.name in only]

    quarantined: list[str] = []
    if not include_quarantined:
        quarantined = [td.name for td in uncovered if cache.is_quarantined(td.name)]
        if quarantined:
            logger.info(
                "Skipping %d quarantined type(s): %s",
                len(quarantined), ", ".join(quarantined),
            )
        uncovered = [td for td in uncovered if not cache.is_quarantined(td.name)]

    if limit is not None:
        uncovered = uncovered[:limit]

    critic_obj = None
    if enable_critic and not dry_run:
        from spec_determinism.view.critic import CodexCritic
        critic_obj = CodexCritic(model=critic_model, timeout=critic_timeout)

    summary = {
        "project": project_name,
        "total_uncovered": len(uncovered),
        "skipped_quarantined": quarantined,
        "enable_critic": enable_critic,
        "results": [],
    }

    # PR-D5 — assemble the set of short names that have a resolvable
    # View, used by the M1 detector. We probe ``view_registry.resolve``
    # on every parsed short name in the project — that single API
    # already unifies L1 prelude rules, L2 alias chains, L3 raw
    # ``impl View`` blocks, and L4 cached entries. A name is "known
    # viewable" iff a leaf TypeExpr for it resolves.
    #
    # Earlier drafts unioned ``types_by_short.keys()`` directly, which
    # was too lenient (the M1 rule became toothless: atmosphere/Endpoint
    # references ``<EndpointState as View>::V``; EndpointState had no
    # View impl yet was accepted because it was a parsed struct). The
    # earlier-than-that draft used only ``scan.views.keys()`` plus
    # active cache, which was too strict: it dropped type aliases like
    # ironkv's ``pub type AckList<MT> = Seq<SingleMessage<MT>>;`` even
    # though they resolve through L1 + L2.
    known_view_heads: set[str] = set(view_registry.scan.views.keys())
    try:
        for e in cache.all_entries():
            if e.view_decl:
                known_view_heads.add(e.type_short)
    except Exception:
        pass
    for short in view_registry.types_by_short.keys():
        if short in known_view_heads:
            continue
        probe = TypeExpr(kind="leaf", head=short, raw=short)
        try:
            res = view_registry.resolve(probe)
            if res.is_resolved:
                known_view_heads.add(short)
        except Exception:
            pass

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
            status: dict = {}
            entry = synthesize_view(
                td, dep_views=dep_views, cache=cache,
                client=client,
                project=project_name,
                force=force,
                critic=critic_obj,
                enable_critic=enable_critic,
                status_out=status,
                known_view_heads=known_view_heads,
            )
            record["status"] = status.get("status", "?")
            if entry is None:
                # Map fine-grained status into a coarse action label for
                # back-compat with downstream summaries.
                if record["status"] == "critic_reject":
                    record["action"] = "critic_reject"
                elif record["status"] in ("lint_reject", "lint_m1_reject",
                                          "lint_m2_reject", "lint_m3_reject",
                                          "lint_m4_reject"):
                    record["action"] = "lint_reject"
                elif record["status"] == "validate_fail":
                    record["action"] = "invalid"
                else:
                    record["action"] = "failed"
            elif entry.view_source == VIEW_SOURCE_TAG and entry.view_decl:
                record["action"] = "ok"
                record["viewed_type"] = entry.viewed_type
                record["critic_verdict"] = entry.critic_verdict
                if entry.critic_issues:
                    record["critic_issues"] = list(entry.critic_issues)
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
# PR-D5 retroactive lint scan (CLI command)
# ---------------------------------------------------------------------------


def _cmd_lint_scan(args) -> int:
    """Run M1/M2/M3 against every cached view in ``--cache-dir``.

    For each active entry (i.e. ``*.json``), reconstruct a minimal
    ``TypeDef`` from the cache record + (if ``--root`` is supplied) the
    project's type registry, and pass it through ``lint_view_decl``.

    Prints a per-rejection block:
        - cache entry path
        - rule (M1 / M2 / M3)
        - reason
        - (optional) view_decl

    Exits with 0 if no rejections, 1 otherwise (so the scan can be
    wired into CI later).
    """
    cache = ViewCache(args.cache_dir)
    entries = list(cache.all_entries())
    quarantined_count = 0
    if args.include_quarantined:
        for qname in cache.quarantined_names():
            qpath = args.cache_dir / f"{qname}.json.quarantine"
            try:
                d = json.loads(qpath.read_text())
                entries.append(CacheEntry.from_dict(d))
                quarantined_count += 1
            except Exception as e:
                logger.warning("Could not load %s: %s", qpath, e)

    # Optional registry — needed for M1 (known_view_heads) and for
    # well-typed TypeDef recovery (so we can resolve field types).
    types_by_short: dict[str, list[TypeDef]] = {}
    known_view_heads: Optional[set[str]] = None
    if args.root is not None:
        from spec_determinism.view.registry import ViewRegistry
        reg = ViewRegistry.from_project(args.root)
        types_by_short = reg.types_by_short
        # Same semantics as ``prefill_project``: probe ``reg.resolve``
        # on every parsed short name so the set covers L1/L2/L3/L4
        # uniformly.
        known_view_heads = set(reg.scan.views.keys())
        for e in cache.all_entries():
            if e.view_decl:
                known_view_heads.add(e.type_short)
        for short in reg.types_by_short.keys():
            if short in known_view_heads:
                continue
            probe = TypeExpr(kind="leaf", head=short, raw=short)
            try:
                res = reg.resolve(probe)
                if res.is_resolved:
                    known_view_heads.add(short)
            except Exception:
                pass

    n_total = 0
    n_reject = 0
    by_rule: dict[str, int] = {}
    rejections: list[dict] = []

    for e in entries:
        if not e.view_decl:
            continue
        n_total += 1
        # Reconstruct a TypeDef. Prefer the project registry; fall back
        # to a stub. The stub lacks field types, which means M1 will
        # be unable to peel ghost wrappers — that's a known limitation.
        td = None
        if types_by_short:
            defs = types_by_short.get(e.type_short, [])
            td = next((d for d in defs if d.kind != "alias"), None)
        if td is None:
            td = TypeDef(name=e.type_short,
                         qualified_name=e.qualified_name,
                         kind="struct",
                         source_file="", source_line=0)

        # The cache holds the view_decl text but not the original
        # type source excerpt; the only is_external_body signal we
        # have is the TypeDef we recovered from the registry.
        hit = lint_view_decl(
            e.view_decl,
            td=td,
            src_excerpt="",
            known_view_heads=known_view_heads,
            cache=cache,
        )
        if hit is None:
            continue
        rule, reason = hit
        n_reject += 1
        by_rule[rule] = by_rule.get(rule, 0) + 1
        rejections.append({
            "type_short": e.type_short,
            "qualified_name": e.qualified_name,
            "rule": rule,
            "reason": reason,
        })
        marker = " [QUARANTINED]" if cache.is_quarantined(e.type_short) else ""
        print(f"\n=== {e.type_short}{marker}  ({rule}) ===")
        print(f"qualified_name: {e.qualified_name}")
        print(f"reason: {reason}")
        if args.show_decl:
            print("\nview_decl:")
            print(e.view_decl)

    qbits = (f" (incl. {quarantined_count} quarantined)"
             if args.include_quarantined else "")
    by = ", ".join(f"{k}={v}" for k, v in sorted(by_rule.items()))
    print(f"\n[lint-scan] project={args.project or '?'}  "
          f"scanned={n_total}{qbits}  "
          f"reject={n_reject}  "
          f"by_rule=[{by}]")

    # Persist a JSON report next to the cache for diff'ing.
    report = {
        "project": args.project,
        "scanned": n_total,
        "rejected": n_reject,
        "by_rule": by_rule,
        "rejections": rejections,
    }
    out_path = args.cache_dir / "_lint_scan.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"[lint-scan] report written: {out_path}")

    return 1 if n_reject > 0 else 0




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
    pf.add_argument("--no-critic", dest="critic", action="store_false",
                    default=True,
                    help="Skip the codex critic pass after each synth.")
    pf.add_argument("--critic-model", default=None,
                    help="Codex model for the critic (default: codex default).")
    pf.add_argument("--critic-timeout", type=int, default=180,
                    help="Per-call codex timeout in seconds (default 180).")
    pf.add_argument("--include-quarantined", action="store_true",
                    help="Re-attempt synthesis for types with a "
                         "<name>.json.quarantine marker (default: skip).")

    insp = sub.add_parser("inspect",
                          help="Print cache contents for a project.")
    insp.add_argument("--cache-dir", required=True, type=Path)
    insp.add_argument("--show-decl", action="store_true",
                      help="Print full view_decl text (otherwise just summary).")

    ls = sub.add_parser("lint-scan",
                        help="PR-D5 retroactive scan: run M1/M2/M3 on "
                             "every active cache entry; print any "
                             "rejection that would have been emitted "
                             "had the lint existed at synth time.")
    ls.add_argument("--cache-dir", required=True, type=Path,
                    help="Cache directory.")
    ls.add_argument("--root", default=None, type=Path,
                    help="Project source root. When omitted, M1 is "
                         "skipped (no known_view_heads to compare).")
    ls.add_argument("--project", default="",
                    help="Project name (header only).")
    ls.add_argument("--include-quarantined", action="store_true",
                    help="Also scan .json.quarantine entries (e.g. to "
                         "confirm they all still trip the lint).")
    ls.add_argument("--show-decl", action="store_true",
                    help="Print the view_decl alongside each rejection.")

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

    if args.cmd == "lint-scan":
        return _cmd_lint_scan(args)

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
            enable_critic=args.critic,
            critic_model=args.critic_model,
            critic_timeout=args.critic_timeout,
            include_quarantined=args.include_quarantined,
        )
        n_ok = sum(1 for r in summary["results"] if r["action"] == "ok")
        n_reject = sum(1 for r in summary["results"]
                       if r["action"] == "critic_reject")
        n_lint = sum(1 for r in summary["results"]
                     if r["action"] == "lint_reject")
        n_fail = sum(1 for r in summary["results"] if r["action"] == "failed")
        n_invalid = sum(1 for r in summary["results"]
                        if r["action"] == "invalid")
        n_dry = sum(1 for r in summary["results"] if r["action"] == "dry-run")
        n_revise = sum(1 for r in summary["results"]
                       if r.get("critic_verdict") == "revise")
        n_critic_err = sum(1 for r in summary["results"]
                           if r.get("critic_verdict") == "error")
        n_quar = len(summary.get("skipped_quarantined") or [])
        print(f"prefill {args.project}: total={summary['total_uncovered']}  "
              f"ok={n_ok}  reject={n_reject}  lint_reject={n_lint}  "
              f"fail={n_fail}  invalid={n_invalid}  dry-run={n_dry}  "
              f"quarantined-skipped={n_quar}  "
              f"critic[revise={n_revise} err={n_critic_err}]")
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

    # --- check_view_body_uses_self: body references self
    good_self = (
        "impl View for Page {\n"
        "    type V = PageView;\n"
        "    closed spec fn view(&self) -> PageView {\n"
        "        PageView { id: self.id, name: self.name@ }\n"
        "    }\n"
        "}"
    )
    ok, msg = check_view_body_uses_self(good_self, "PageView")
    check(ok, f"self-ref: body with self.* should pass: {msg}")

    # --- check_view_body_uses_self: arbitrary() bug (the
    #     storage/MaybeCorruptedBytes case)
    arbitrary_body = (
        "impl<S> View for MaybeCorruptedBytes<S> where S: PmCopy {\n"
        "    type V = Seq<u8>;\n"
        "    closed spec fn view(&self) -> Seq<u8> {\n"
        "        arbitrary()\n"
        "    }\n"
        "}"
    )
    ok, msg = check_view_body_uses_self(arbitrary_body, "Seq<u8>")
    check(not ok, f"self-ref: arbitrary() should be rejected, got: {msg}")
    check("does not reference `self`" in msg, "self-ref: helpful message")

    # --- check_view_body_uses_self: legitimate unit collapse — body has
    #     no `self` but viewed_type is `()` (the NetClientCPointers and
    #     memory-allocator/Node case)
    unit_collapse = (
        "impl View for OpaqueFnPtrs {\n"
        "    type V = ();\n"
        "    closed spec fn view(&self) -> () {\n"
        "        ()\n"
        "    }\n"
        "}"
    )
    ok, msg = check_view_body_uses_self(unit_collapse, "()")
    check(ok, f"self-ref: legitimate () collapse should pass: {msg}")

    # --- check_view_body_uses_self: constant struct literal (subtler
    #     over-collapse — viewed_type is non-unit but body never reads self)
    const_struct = (
        "impl View for X {\n"
        "    type V = XView;\n"
        "    closed spec fn view(&self) -> XView {\n"
        "        XView { id: 0, name: Seq::empty() }\n"
        "    }\n"
        "}"
    )
    ok, msg = check_view_body_uses_self(const_struct, "XView")
    check(not ok, f"self-ref: constant literal should be rejected, got: {msg}")

    # --- check_view_body_uses_self: comment containing the word "self"
    #     does not count as a reference
    only_in_comment = (
        "impl View for X {\n"
        "    type V = Seq<u8>;\n"
        "    closed spec fn view(&self) -> Seq<u8> {\n"
        "        // self is allocator-opaque\n"
        "        Seq::empty()\n"
        "    }\n"
        "}"
    )
    ok, msg = check_view_body_uses_self(only_in_comment, "Seq<u8>")
    check(not ok, f"self-ref: `self` in comment should not count, got: {msg}")

    # --- check_view_body_uses_self: no view fn at all → skip
    no_view_fn = "impl View for X { type V = (); }"
    ok, msg = check_view_body_uses_self(no_view_fn, "()")
    check(ok, "self-ref: no view fn → skip")

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

        # quarantine: rename .json → .json.quarantine, verify lookup
        # tools all reflect the new state
        check(not c.is_quarantined("Foo"),
              "quarantine: Foo not yet quarantined")
        check(c.quarantined_names() == [],
              "quarantine: list empty before any rename")
        p.rename(p.with_suffix(".json.quarantine"))
        check(c.is_quarantined("Foo"),
              "quarantine: is_quarantined reflects .quarantine file")
        check(c.quarantined_names() == ["Foo"],
              "quarantine: listed by short name")
        # active cache lookup still misses (file at <name>.json gone)
        check(c.get("Foo", "abc123") is None,
              "quarantine: get() still misses after rename")
        check(c.get_any("Foo") is None,
              "quarantine: get_any() still misses after rename")
        # all_entries should now show 0 since the .json is gone
        check(len(c.all_entries()) == 0,
              "quarantine: all_entries excludes quarantined files")

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

    # ------------------------------------------------------------------
    # PR-D5 — M1 / M2 / M3 detector unit tests
    # ------------------------------------------------------------------

    # --- helpers --------------------------------------------------------
    def _te_leaf(h):
        return TypeExpr(kind="leaf", head=h, raw=h)
    def _te_gen(h, *args):
        return TypeExpr(kind="generic", head=h, args=list(args), raw=h)
    def _fd(name, te):
        return FieldDecl(name=name, type_text=te.raw, type_refs=[],
                         is_pub=False, span=(0, 0), type_expr=te)
    def _struct(name, *fields, **kw):
        return TypeDef(
            name=name, qualified_name=name, kind="struct",
            fields=list(fields), source_file="", source_line=0,
            **kw,
        )

    # --- M3 — external_body parent ------------------------------------
    td_ext = _struct("CKeyHashMap", _fd("m", _te_gen("HashMap")),
                     is_external_body=True)
    out = check_m3_parent_not_opaque(td_ext)
    check(out is not None and out.startswith("M3:"),
          f"M3: external_body should reject (got {out!r})")

    td_plain = _struct("Foo", _fd("x", _te_leaf("u64")))
    out = check_m3_parent_not_opaque(td_plain)
    check(out is None, f"M3: plain struct should accept (got {out!r})")

    # repr(C) is intentionally NOT a hard reject — M1/M2 carry the
    # message instead.
    td_reprc = _struct("Registers", _fd("rax", _te_leaf("u64")))
    out = check_m3_parent_not_opaque(td_reprc,
                                     src_excerpt="#[repr(C, align(8))]\npub struct Registers { rax: u64 }")
    check(out is None, "M3: repr(C) is a soft warning, not a hard reject")

    # --- M2 — `self.f@@` past Ghost ------------------------------------
    # PR-D5 fix iteration: Set/Seq/Map/Multiset HAVE identity Views in
    # vstd, so `Ghost<Set<…>>@@` is fine (Container relies on this).
    # The retained M2 contract: `Ghost<FnSpec>@@` is still a type error
    # (Fn traits have no `View::view`).
    td_endpoint = _struct(
        "EndpointStub",
        _fd("predicate",
            _te_gen("Ghost", _te_leaf("FnSpec"))),
    )
    decl_bad = (
        "impl View for EndpointStub {\n"
        "    type V = EndpointStubView;\n"
        "    closed spec fn view(&self) -> EndpointStubView {\n"
        "        EndpointStubView { p: self.predicate@@ }\n"
        "    }\n"
        "}"
    )
    out = check_m2_no_double_at_past_ghost(decl_bad, td=td_endpoint)
    check(out is not None and out.startswith("M2:"),
          f"M2: Ghost<FnSpec>@@ should reject (got {out!r})")

    # Ghost<Set<…>>@@ is the legitimate atmosphere/Container pattern —
    # Set has an identity View in vstd, so `@@` peels Ghost then
    # identity-views. Must ACCEPT (regression pin for the FP that
    # PR-D5 first-draft caught).
    td_container = _struct(
        "Container",
        _fd("subtree_set",
            _te_gen("Ghost", _te_gen("Set", _te_leaf("ContainerPtr")))),
        _fd("uppertree_seq",
            _te_gen("Ghost", _te_gen("Seq", _te_leaf("ContainerPtr")))),
    )
    decl_container = (
        "impl View for Container {\n"
        "    type V = ContainerView;\n"
        "    closed spec fn view(&self) -> ContainerView {\n"
        "        ContainerView {\n"
        "            subtree_set: self.subtree_set@@,\n"
        "            uppertree_seq: self.uppertree_seq@@,\n"
        "        }\n"
        "    }\n"
        "}"
    )
    out = check_m2_no_double_at_past_ghost(decl_container, td=td_container)
    check(out is None,
          f"M2: Ghost<Set<…>>@@ should ACCEPT (Set has identity View; "
          f"got {out!r})")

    # Ghost<Vec<u8>> field → @@ is fine (Vec has View)
    td_ok = _struct(
        "Wrap",
        _fd("g", _te_gen("Ghost", _te_gen("Vec", _te_leaf("u8")))),
    )
    decl_ok = (
        "impl View for Wrap {\n"
        "    type V = WrapView;\n"
        "    closed spec fn view(&self) -> WrapView {\n"
        "        WrapView { g: self.g@@ }\n"
        "    }\n"
        "}"
    )
    out = check_m2_no_double_at_past_ghost(decl_ok, td=td_ok)
    check(out is None,
          f"M2: Ghost<Vec<u8>>@@ should accept (got {out!r})")

    # Plain Vec<u8> with @@ → reject (not Ghost/Tracked).
    td_vec = _struct("V", _fd("bytes", _te_gen("Vec", _te_leaf("u8"))))
    decl_atat_on_vec = (
        "impl View for V {\n"
        "    type V = Seq<u8>;\n"
        "    closed spec fn view(&self) -> Seq<u8> { self.bytes@@ }\n"
        "}"
    )
    out = check_m2_no_double_at_past_ghost(decl_atat_on_vec, td=td_vec)
    check(out is not None and "not `Ghost" in out,
          f"M2: Vec@@ should reject as non-Ghost (got {out!r})")

    # No `@@` anywhere → accept regardless of field shape.
    decl_single_at = (
        "impl View for V {\n"
        "    type V = Seq<u8>;\n"
        "    closed spec fn view(&self) -> Seq<u8> { self.bytes@ }\n"
        "}"
    )
    out = check_m2_no_double_at_past_ghost(decl_single_at, td=td_vec)
    check(out is None, "M2: single @ should accept")

    # Comment-only `@@` doesn't count.
    decl_comment = (
        "impl View for V {\n"
        "    type V = Seq<u8>;\n"
        "    closed spec fn view(&self) -> Seq<u8> {\n"
        "        // we are NOT using self.x@@ here\n"
        "        self.bytes@\n"
        "    }\n"
        "}"
    )
    out = check_m2_no_double_at_past_ghost(decl_comment, td=td_vec)
    check(out is None, "M2: @@ inside comment must not fire")

    # --- M1 — referenced head has no View ------------------------------
    # `<PageAllocator as View>::V` is not in known_view_heads.
    td_kernel = _struct(
        "Kernel",
        _fd("alloc", _te_leaf("PageAllocator")),
    )
    decl_kernel = (
        "impl View for Kernel {\n"
        "    type V = KernelView;\n"
        "    closed spec fn view(&self) -> KernelView {\n"
        "        KernelView { alloc: <PageAllocator as View>::V::default() }\n"
        "    }\n"
        "}"
    )
    out = check_m1_view_targets_have_view(
        decl_kernel, td=td_kernel,
        known_view_heads={"Kernel", "Endpoint"},  # PageAllocator absent
    )
    check(out is not None and "PageAllocator" in out,
          f"M1: missing PageAllocator should reject (got {out!r})")

    # With PageAllocator in the set → accept.
    out = check_m1_view_targets_have_view(
        decl_kernel, td=td_kernel,
        known_view_heads={"Kernel", "PageAllocator"},
    )
    check(out is None,
          f"M1: known head should accept (got {out!r})")

    # `self.field@` head check — when the field's head has a View, accept.
    decl_self_at = (
        "impl View for Kernel {\n"
        "    type V = Seq<PageAllocator>;\n"
        "    closed spec fn view(&self) -> Seq<PageAllocator> { self.alloc@ }\n"
        "}"
    )
    out = check_m1_view_targets_have_view(
        decl_self_at, td=td_kernel,
        known_view_heads={"PageAllocator"},
    )
    check(out is None, "M1: self.alloc@ with PageAllocator known → accept")

    out = check_m1_view_targets_have_view(
        decl_self_at, td=td_kernel,
        known_view_heads=set(),
    )
    check(out is not None and "PageAllocator" in out,
          f"M1: self.alloc@ missing PageAllocator → reject (got {out!r})")

    # vstd heads pass without registration.
    td_winner = _struct(
        "CommitMask", _fd("mask", _te_gen("Vec", _te_leaf("u64"))),
    )
    decl_winner = (
        "impl View for CommitMask {\n"
        "    type V = Seq<u64>;\n"
        "    closed spec fn view(&self) -> Seq<u64> { self.mask@ }\n"
        "}"
    )
    out = check_m1_view_targets_have_view(
        decl_winner, td=td_winner, known_view_heads=set(),
    )
    check(out is None, "M1: Vec<u64> via VSTD_VIEW_HEADS → accept")

    # Quarantine cascade — head is in `cache.is_quarantined`.
    with tempfile.TemporaryDirectory() as tmp:
        c_q = ViewCache(Path(tmp))
        (Path(tmp) / "EndPoint.json.quarantine").write_text("{}")
        td_csm = _struct(
            "CSingleMessage",
            _fd("dst", _te_leaf("EndPoint")),
        )
        decl_csm = (
            "impl View for CSingleMessage {\n"
            "    type V = CSingleMessageView;\n"
            "    closed spec fn view(&self) -> CSingleMessageView {\n"
            "        CSingleMessageView { dst: <EndPoint as View>::V::default() }\n"
            "    }\n"
            "}"
        )
        out = check_m1_view_targets_have_view(
            decl_csm, td=td_csm, known_view_heads=set(), cache=c_q,
        )
        check(out is not None and "quarantined" in out,
              f"M1: cascade through quarantine should reject (got {out!r})")

    # Hallucinated field reference → reject.
    td_no_field = _struct("Foo", _fd("real", _te_leaf("u64")))
    decl_hallucinated = (
        "impl View for Foo {\n"
        "    type V = Seq<u64>;\n"
        "    closed spec fn view(&self) -> Seq<u64> { self.imaginary@ }\n"
        "}"
    )
    out = check_m1_view_targets_have_view(
        decl_hallucinated, td=td_no_field,
        known_view_heads=set(),
    )
    check(out is not None and "imaginary" in out,
          f"M1: hallucinated field should reject (got {out!r})")

    # --- lint_view_decl aggregator order: M3 > M2 > M1 -----------------
    # An external_body parent with a broken body should report M3 first.
    td_both = _struct(
        "Bad",
        _fd("g", _te_gen("Ghost", _te_leaf("FnSpec"))),
        is_external_body=True,
    )
    decl_both = (
        "impl View for Bad {\n"
        "    type V = BadView;\n"
        "    closed spec fn view(&self) -> BadView {\n"
        "        BadView { g: self.g@@ }\n"
        "    }\n"
        "}"
    )
    hit = lint_view_decl(decl_both, td=td_both, known_view_heads=set())
    check(hit is not None and hit[0] == "M3",
          f"lint: M3 has priority (got {hit!r})")

    # M2 fires before M1 when M3 doesn't.
    hit = lint_view_decl(decl_bad, td=td_endpoint, known_view_heads=set())
    check(hit is not None and hit[0] == "M2",
          f"lint: M2 fires before M1 (got {hit!r})")

    # Winning view from PR-D4 case studies must pass all three.
    hit = lint_view_decl(decl_winner, td=td_winner, known_view_heads=set())
    check(hit is None,
          f"lint: PR-D4 winner CommitMask should pass all 3 (got {hit!r})")

    # --- PR-D5 retroactive scan: FP regression-pins -------------------
    # (a) M3 unit-V exemption: external_body + `type V = ()` + body `()`
    # is the documented "legitimate unit collapse" pattern
    # (ironkv/NetClientCPointers, nrkernel/Token).
    td_ffi = _struct("NetClientCPointers", is_external_body=True)
    decl_unit_collapse = (
        "impl View for NetClientCPointers {\n"
        "    type V = ();\n"
        "    closed spec fn view(&self) -> () { () }\n"
        "}"
    )
    out = check_m3_parent_not_opaque(
        td_ffi, view_decl=decl_unit_collapse,
    )
    check(out is None,
          f"M3: unit-V collapse on external_body should ACCEPT (got {out!r})")
    hit = lint_view_decl(
        decl_unit_collapse, td=td_ffi, known_view_heads=set(),
    )
    check(hit is None,
          f"lint: unit-V collapse should pass all 3 rules (got {hit!r})")

    # (b) M1 impl-generics: a generic param like `K: View` introduced
    # in the `impl<K: …View>` header is treated as already-viewable.
    # Regression pin for ironkv/KeyIterator.
    td_keyiter = _struct(
        "KeyIterator", _fd("k", _te_gen("Option", _te_leaf("K"))),
    )
    decl_keyiter = (
        "impl<K: KeyTrait + VerusClone + View> View for KeyIterator<K> {\n"
        "    type V = Option<<K as View>::V>;\n"
        "    closed spec fn view(&self) -> Self::V { self.k@ }\n"
        "}"
    )
    out = check_m1_view_targets_have_view(
        decl_keyiter, td=td_keyiter, known_view_heads=set(),
    )
    check(out is None,
          f"M1: impl-generic K should be treated as known (got {out!r})")
    # Also tests `_extract_impl_generics` directly.
    gens = _extract_impl_generics(decl_keyiter)
    check(gens == {"K"},
          f"_extract_impl_generics: KeyIterator → {{K}} (got {gens!r})")
    # Multi-param impl block (WriteRestrictedPersistentMemoryRegion).
    td_wrpr = _struct(
        "WriteRestrictedPersistentMemoryRegion",
        _fd("pm_region", _te_leaf("PMRegion")),
    )
    decl_wrpr = (
        "impl<Perm, PMRegion> View for "
        "WriteRestrictedPersistentMemoryRegion<Perm, PMRegion>\n"
        "    where\n"
        "        Perm: CheckPermission<Seq<u8>>,\n"
        "        PMRegion: PersistentMemoryRegion,\n"
        "{\n"
        "    type V = PersistentMemoryRegionView;\n"
        "    closed spec fn view(&self) -> Self::V { self.pm_region@ }\n"
        "}"
    )
    out = check_m1_view_targets_have_view(
        decl_wrpr, td=td_wrpr, known_view_heads=set(),
    )
    check(out is None,
          f"M1: impl<Perm, PMRegion> with `self.pm_region@` should ACCEPT "
          f"(got {out!r})")

    # (c) String field via `self.message@` — String has built-in View
    # in vstd (regression pin for ironkv/IronfleetIOError).
    td_ioerr = _struct(
        "IronfleetIOError", _fd("message", _te_leaf("String")),
    )
    decl_ioerr = (
        "impl View for IronfleetIOError {\n"
        "    type V = IronfleetIOErrorView;\n"
        "    closed spec fn view(&self) -> IronfleetIOErrorView {\n"
        "        IronfleetIOErrorView { message: self.message@ }\n"
        "    }\n"
        "}"
    )
    out = check_m1_view_targets_have_view(
        decl_ioerr, td=td_ioerr, known_view_heads=set(),
    )
    check(out is None,
          f"M1: `self.message@` on `String` field should ACCEPT "
          f"(got {out!r})")

    # (d) `Ghost<spec_fn(int) -> bool>` field via `self.fn_@` — spec_fn
    # has identity View (regression pin for
    # storage/WritablePersistentMemorySubregion).
    td_subreg = _struct(
        "WritablePersistentMemorySubregion",
        _fd("is_writable_absolute_addr_fn_",
            _te_gen("Ghost",
                    TypeExpr(kind="fn", head="spec_fn", args=[],
                             raw="spec_fn(int) -> bool"))),
    )
    decl_subreg = (
        "impl View for WritablePersistentMemorySubregion {\n"
        "    type V = WritablePersistentMemorySubregionView;\n"
        "    open spec fn view(&self) -> WritablePersistentMemorySubregionView {\n"
        "        WritablePersistentMemorySubregionView {\n"
        "            is_writable_absolute_addr_fn_: "
        "self.is_writable_absolute_addr_fn_@,\n"
        "        }\n"
        "    }\n"
        "}"
    )
    out = check_m1_view_targets_have_view(
        decl_subreg, td=td_subreg, known_view_heads=set(),
    )
    check(out is None,
          f"M1: `Ghost<spec_fn(...)>` field via `@` should ACCEPT "
          f"(got {out!r})")

    # (e) `_extract_impl_generics` edge cases.
    check(_extract_impl_generics("") == set(),
          "_extract_impl_generics: empty input → empty set")
    check(_extract_impl_generics("pub struct Foo { x: u32 }") == set(),
          "_extract_impl_generics: bare struct (no impl) → empty set")
    check(_extract_impl_generics("impl View for Foo { }") == set(),
          "_extract_impl_generics: impl with no <...> → empty set")
    # Lifetimes and const params are filtered out.
    gens2 = _extract_impl_generics(
        "impl<'a, const N: usize, T: View> View for Foo<'a, N, T> { }"
    )
    check(gens2 == {"T"},
          f"_extract_impl_generics: lifetimes/consts filtered "
          f"(got {gens2!r})")

    # (f) `_view_v_type` / `_is_unit_v` smoke tests.
    check(_view_v_type(decl_unit_collapse) == "()",
          "_view_v_type: unit-V decl extracts ()")
    check(_is_unit_v(decl_unit_collapse) is True,
          "_is_unit_v: unit-V decl")
    check(_is_unit_v(decl_winner) is False,
          "_is_unit_v: CommitMask is NOT unit-V")

    # ------------------------------------------------------------------
    # PR-E — M4 (self-recursive view) detector unit tests
    # ------------------------------------------------------------------

    def _fd_refs(name, te, refs):
        return FieldDecl(name=name, type_text=te.raw, type_refs=list(refs),
                         is_pub=False, span=(0, 0), type_expr=te)

    # PTDir-shaped fixture: `entries: Seq<Option<PTDir>>` self-references PTDir.
    td_ptdir = _struct(
        "PTDir",
        _fd_refs("region", _te_leaf("MemRegion"), ["MemRegion"]),
        _fd_refs("entries",
                 _te_gen("Seq", _te_gen("Option", _te_leaf("PTDir"))),
                 ["Seq", "Option", "PTDir"]),
        _fd_refs("used_regions", _te_gen("Set", _te_leaf("MemRegion")),
                 ["Set", "MemRegion"]),
    )

    check(_is_self_recursive(td_ptdir) is True,
          "_is_self_recursive: PTDir is self-recursive via entries")
    rec = _self_recursive_fields(td_ptdir)
    check(set(rec.keys()) == {"entries"},
          f"_self_recursive_fields: PTDir → {{entries}} (got {sorted(rec)!r})")

    # Non-recursive baseline.
    td_page = _struct("Page", _fd("size", _te_leaf("usize")))
    check(_is_self_recursive(td_page) is False,
          "_is_self_recursive: Page is NOT self-recursive")
    check(_self_recursive_fields(td_page) == {},
          "_self_recursive_fields: Page → {}")

    # --- M4 rejection: Option A bug (the historical PTDir failure).
    # V declares Seq<Option<PTDirView>> but body assigns self.entries@.
    decl_ptdir_buggy = (
        "pub struct PTDirView {\n"
        "    pub region: MemRegion,\n"
        "    pub entries: Seq<Option<PTDirView>>,\n"
        "    pub used_regions: Set<MemRegion>,\n"
        "}\n\n"
        "impl View for PTDir {\n"
        "    type V = PTDirView;\n"
        "    closed spec fn view(&self) -> PTDirView {\n"
        "        PTDirView {\n"
        "            region: self.region,\n"
        "            entries: self.entries@,\n"
        "            used_regions: self.used_regions,\n"
        "        }\n"
        "    }\n"
        "}"
    )
    out = check_m4_self_recursion_bare_at(decl_ptdir_buggy, td=td_ptdir)
    check(out is not None and out.startswith("M4:") and "PTDirView" in out,
          f"M4: PTDir Seq<Option<TView>> + self.entries@ should REJECT (got {out!r})")
    # Aggregator: M4 should fire (M3/M2 don't apply, M1 sees PTDir as known head).
    hit = lint_view_decl(
        decl_ptdir_buggy, td=td_ptdir, known_view_heads={"PTDir"},
    )
    check(hit is not None and hit[0] == "M4",
          f"lint_view_decl: PTDir buggy → M4 (got {hit!r})")

    # --- M4 acceptance: Option C — identity view.
    decl_ptdir_c = (
        "impl View for PTDir {\n"
        "    type V = PTDir;\n"
        "    closed spec fn view(&self) -> PTDir { *self }\n"
        "}"
    )
    out = check_m4_self_recursion_bare_at(decl_ptdir_c, td=td_ptdir)
    check(out is None,
          f"M4: PTDir Option C (type V = PTDir, *self) should ACCEPT (got {out!r})")
    hit = lint_view_decl(
        decl_ptdir_c, td=td_ptdir, known_view_heads={"PTDir"},
    )
    check(hit is None,
          f"lint_view_decl: PTDir Option C passes all rules (got {hit!r})")

    # --- M4 acceptance: Option B — V keeps concrete PTDir in container.
    decl_ptdir_b = (
        "pub struct PTDirView {\n"
        "    pub region: MemRegion,\n"
        "    pub entries: Seq<Option<PTDir>>,\n"
        "    pub used_regions: Set<MemRegion>,\n"
        "}\n\n"
        "impl View for PTDir {\n"
        "    type V = PTDirView;\n"
        "    closed spec fn view(&self) -> PTDirView {\n"
        "        PTDirView {\n"
        "            region: self.region,\n"
        "            entries: self.entries,\n"
        "            used_regions: self.used_regions,\n"
        "        }\n"
        "    }\n"
        "}"
    )
    out = check_m4_self_recursion_bare_at(decl_ptdir_b, td=td_ptdir)
    check(out is None,
          f"M4: PTDir Option B (V wraps Seq<Option<PTDir>>, body uses self.entries) "
          f"should ACCEPT (got {out!r})")

    # --- M4 acceptance: Option A done correctly — Seq::new lift, no bare @.
    decl_ptdir_a = (
        "pub struct PTDirView {\n"
        "    pub region: MemRegion,\n"
        "    pub entries: Seq<Option<PTDirView>>,\n"
        "    pub used_regions: Set<MemRegion>,\n"
        "}\n\n"
        "impl View for PTDir {\n"
        "    type V = PTDirView;\n"
        "    closed spec fn view(&self) -> PTDirView {\n"
        "        PTDirView {\n"
        "            region: self.region,\n"
        "            entries: Seq::new(\n"
        "                self.entries.len(),\n"
        "                |i: int| match self.entries[i] {\n"
        "                    Some(d) => Some(d@),\n"
        "                    None => None,\n"
        "                },\n"
        "            ),\n"
        "            used_regions: self.used_regions,\n"
        "        }\n"
        "    }\n"
        "}"
    )
    out = check_m4_self_recursion_bare_at(decl_ptdir_a, td=td_ptdir)
    check(out is None,
          f"M4: PTDir Option A (explicit Seq::new lift, no bare entries@) "
          f"should ACCEPT (got {out!r})")

    # --- M4 short-circuit: non-self-recursive types are skipped.
    decl_page_at = (
        "pub struct PageView { pub size: usize }\n"
        "impl View for Page {\n"
        "    type V = PageView;\n"
        "    closed spec fn view(&self) -> PageView {\n"
        "        PageView { size: self.size }\n"
        "    }\n"
        "}"
    )
    out = check_m4_self_recursion_bare_at(decl_page_at, td=td_page)
    check(out is None,
          f"M4: non-recursive Page should be skipped (got {out!r})")

    # --- M4 priority: aggregator runs M3 > M2 > M4 > M1.
    # A self-recursive external_body type with the M4 bug should report M3 first.
    td_ptdir_ext = _struct(
        "PTDir",
        _fd_refs("entries",
                 _te_gen("Seq", _te_gen("Option", _te_leaf("PTDir"))),
                 ["Seq", "Option", "PTDir"]),
        is_external_body=True,
    )
    hit = lint_view_decl(
        decl_ptdir_buggy, td=td_ptdir_ext, known_view_heads={"PTDir"},
    )
    check(hit is not None and hit[0] == "M3",
          f"lint: M3 still wins over M4 on external_body (got {hit!r})")

    # M4 wins over M1 when M3/M2 don't fire.
    hit = lint_view_decl(
        decl_ptdir_buggy, td=td_ptdir, known_view_heads=set(),
    )
    check(hit is not None and hit[0] == "M4",
          f"lint: M4 fires before M1 when both could (got {hit!r})")

    # --- CacheEntry round-trip via to_dict / from_dict
    e2 = CacheEntry.from_dict(e.to_dict())
    check(e2.type_short == e.type_short, "CacheEntry: round-trip name")
    check(e2.depends_on_views_of == e.depends_on_views_of,
          "CacheEntry: round-trip deps")

    # --- E2E: synthesize_view lint→retry path with a stub LLM
    class _StubLLM(CopilotViewLLM):
        def __init__(self, response: str):
            self._response = response
        def query(self, prompt: str, run_dir: Path) -> str:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "response.md").write_text(self._response)
            return self._response

    _bad = (
        '```json\n{"viewed_type": "Seq<u8>", '
        '"view_decl": "impl<S> View for X<S> { type V = Seq<u8>; '
        'closed spec fn view(&self) -> Seq<u8> { arbitrary() } }", '
        '"depends_on_views_of": [], "rationale": "r"}\n```'
    )
    _good = (
        '```json\n{"viewed_type": "Seq<u8>", '
        '"view_decl": "impl<S> View for X<S> { type V = Seq<u8>; '
        'closed spec fn view(&self) -> Seq<u8> { self.bytes@ } }", '
        '"depends_on_views_of": [], "rationale": "r"}\n```'
    )
    _td_e2e = TypeDef(
        name="X", qualified_name="X", kind="struct",
        source_file="", source_line=0,
    )

    with tempfile.TemporaryDirectory() as tmp:
        cache_root = Path(tmp) / "view_registry" / "p"
        c2 = ViewCache(cache_root)

        # 1. arbitrary() → lint_reject, no cache, _rejected.jsonl has 1 row
        st = {}
        entry = synthesize_view(
            _td_e2e, dep_views={}, cache=c2,
            client=_StubLLM(_bad), project="p",
            enable_critic=False, status_out=st,
        )
        check(entry is None, "e2e: arbitrary() returns None")
        check(st.get("status") == "lint_reject",
              f"e2e: status=lint_reject (got {st.get('status')})")
        rej = cache_root / "_rejected.jsonl"
        check(rej.exists(), "e2e: _rejected.jsonl written on lint reject")
        check(not (cache_root / "X.json").exists(),
              "e2e: no cache file on lint reject")

        # 2. retry path: good body now → ok, cache file present
        st = {}
        entry = synthesize_view(
            _td_e2e, dep_views={}, cache=c2,
            client=_StubLLM(_good), project="p",
            enable_critic=False, status_out=st,
        )
        check(entry is not None, "e2e: retry produces entry")
        check(st.get("status") == "ok", f"e2e: retry status=ok (got {st.get('status')})")
        check((cache_root / "X.json").exists(), "e2e: cache written on retry")

        # 3. third call hits cache, bypasses both LLM and lint
        st = {}
        synthesize_view(
            _td_e2e, dep_views={}, cache=c2,
            client=_StubLLM(_bad),  # would re-trip lint if not hit
            project="p", enable_critic=False, status_out=st,
        )
        check(st.get("status") == "cache_hit",
              f"e2e: cache_hit on 3rd call (got {st.get('status')})")

        # 4. force=True bypasses cache, lint re-rejects, existing good cache
        #    preserved
        st = {}
        entry = synthesize_view(
            _td_e2e, dep_views={}, cache=c2,
            client=_StubLLM(_bad), project="p",
            enable_critic=False, force=True, status_out=st,
        )
        check(entry is None, "e2e: force+bad → None")
        check(st.get("status") == "lint_reject",
              f"e2e: force+bad status=lint_reject (got {st.get('status')})")
        check((cache_root / "X.json").exists(),
              "e2e: existing good cache preserved across force-reject")
        n_lines = len(rej.read_text().strip().split("\n"))
        check(n_lines == 2, f"e2e: _rejected.jsonl now has 2 lines (got {n_lines})")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("All self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
