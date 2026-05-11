# L4 view critique — acceptance criteria

This document defines what the view-synthesis pipeline considers a
**valid** `impl View` candidate, what it considers fixable, and what it
considers a hard reject.

It is intended for:

- humans calling `python -m spec_determinism.view.llm prefill` to know
  why an entry was rejected or revised;
- future authors of additional LLM callers (e.g. the deferred PR-E
  "SCC whole-component" prompt) so they can mirror the same rules.

## Layered checks

A candidate goes through three layers before it can be cached:

```
LLM JSON response
       │
       ▼
1. validate_view_decl()     -- tree-sitter parse + impl View wrapper
       │ pass ──►  fail → cache stub, status="validate_fail"
       ▼
2. check_view_body_uses_self()  -- static lint, no LLM
       │ pass ──►  fail → _rejected.jsonl, status="lint_reject"
       ▼
3. codex critic (CodexCritic.query / critique_view)
       │ accept | revise | error → cache + status="ok"
       │ reject ──► _rejected.jsonl, status="critic_reject"
       ▼
cached as L4-llm in <cache_root>/<project>/<Type>.json
```

The lint runs *before* the critic on purpose: it is mechanical, free,
and catches the most dangerous over-collapse class (`arbitrary()`) that
the critic has been observed to miss. The two layers are intentionally
overlapping for defense in depth.

## Verdicts

### `accept`

The view is good. Caches the entry with `critic_verdict = "accept"`
and `critic_issues = []`. The function `view()` returns
`<viewed_type>` and faithfully projects every spec-meaningful field.

### `revise`

The view compiles and preserves enough information, but there are
soft concerns worth recording. Examples seen in practice:

- "dependency `<Dep>` view is assumed but not provided in prompt
  context; verify that `<Dep> as View` actually exists";
- "field `f` is renamed in the view type — not wrong but
  inconsistent with the source name".

The cache entry is still written but `critic_verdict = "revise"` and
the strings populate `critic_issues`. The next prefill *does not*
re-query: revisions are advisory only.

### `reject` (or static lint fail)

The view will either fail Verus typecheck or silently collapse
information. The candidate is **not cached**; a JSON line is appended
to `<cache_root>/<project>/_rejected.jsonl` recording:

```json
{
  "type_short": "...",
  "qualified_name": "...",
  "source_hash": "...",
  "viewed_type": "...",
  "view_decl": "...",
  "issues": ["..."]
}
```

The next `prefill` run will retry the type from scratch.

### `error`

The critic itself failed (codex `--timeout` exceeded, JSON parse
failed, etc.). The entry is **cached normally** with
`critic_verdict = "error"` and the error string in `critic_issues`,
because withholding caches on critic-side outages would block progress
on every type. Such entries should be re-audited when the critic is
healthy.

## What gets rejected — concrete rules

The codex critic prompt (`view/critic.py::_CRITIC_PROMPT_HEADER`)
lists 8 rules. The static lint adds machine-checked enforcement of
rule 8.

| # | Rule | Where enforced | Example reject |
|---|---|---|---|
| 1 | **Lost information.** A field used in spec ensures is dropped. | critic | `ironkv/DuctTapeProfiler` (had `last_event` etc., view returned `()`) |
| 2 | **Wrong container shape.** `Vec<T>` as `Set<T@>` when spec uses `v[i]`. | critic | (none in corpus yet) |
| 3 | **Primitive `@`.** `5_usize@` or `self.byte_in_digest@@` (over-project). | critic | `storage/CrcDigest` (`@@` past Ghost into `u8`) |
| 4 | **type V mismatch.** `type V = X` but body returns `Y`. | critic | (none in corpus yet) |
| 5 | **Over-aggressive collapse to `()`.** Struct with real fields → unit. | critic | `ironkv/DuctTapeProfiler` |
| 6 | **Missing dep view.** Field of viewable type used as `self.field` instead of `self.field@`. | critic | `ironkv/AbstractHostState` (kept raw `Hashtable`) |
| 7 | **Wrong dep view.** `Seq<Option<T>>` declared as `Seq<Option<T::V>>` but body lacks the lift. | critic | `nrkernel/PTDir` |
| 8 | **Body does not read `self`.** `arbitrary()`, constant literal, `Seq::empty()`. | **static lint** + critic | `storage/MaybeCorruptedBytes` (`arbitrary()`) |

For rule 8, the **only legitimate exception** is `type V = ();` with
body `()` — a deliberate "this type carries no spec content" collapse
for raw-pointer / extern-fn-pointer wrappers. The static lint
(`check_view_body_uses_self`) skips that case automatically.

## What gets accepted with `revise` (not rejected)

- The candidate references a dependency view (`<Dep as View>::V`,
  `self.field@`) for a type whose own view isn't yet in the prefill's
  resolved-dep map. Critic flags as uncertain because it cannot
  confirm `Dep` actually has a view, but does **not** reject — the
  dep may be resolvable at codegen time. This is the dominant `revise`
  cause; see `nrkernel/Directory`, `atmosphere/PageAllocator`.
- Field names in the view struct differ from the source struct.

## What is intentionally **not** checked

- We do not run `verus --parse-only` over the candidate as part of
  prefill. Verus will catch any remaining errors at corpus-rerun time
  (`scripts/rerun_corpus.sh`).
- We do not currently check whether all dependency views recursively
  exist. PR-E (deferred) will introduce a "whole SCC" prompt for
  mutually-recursive types.
- We do not check that the `viewed_type` is a closed spec type. A
  malformed `viewed_type` would surface at codegen time via a verus
  error and would be triaged via `COMPARE.md` regression rows.

## Adding a new check

1. If it's mechanical (string match, AST walk, type-name check), add a
   new function next to `check_view_body_uses_self` in
   `spec_determinism/view/llm.py` and call it after
   `validate_view_decl`.
2. If it requires semantic judgment, add a numbered rule to
   `_CRITIC_PROMPT_HEADER` in `spec_determinism/view/critic.py`.
3. If the rule is both mechanical *and* important enough that the
   critic has been seen to miss it, add it in both places (see rule
   8 — that's the precedent).

## File reference

| File | Role |
|---|---|
| `spec_determinism/view/llm.py::validate_view_decl` | tree-sitter parse |
| `spec_determinism/view/llm.py::check_view_body_uses_self` | static lint (rule 8) |
| `spec_determinism/view/critic.py::CodexCritic` | codex backend |
| `spec_determinism/view/critic.py::critique_view` | run + persist |
| `spec_determinism/view/critic.py::_CRITIC_PROMPT_HEADER` | prompt rules |
| `spec_determinism/view/critic.py::parse_critic_response` | JSON parser |
| `spec_determinism/view/critic.py::append_rejected` | `_rejected.jsonl` writer |

## Lint rule drafts (post-quarantine 2026-05-11)

After the rerun-against-`results-verusage-viewreg` produced 73
verus_error regressions, 14 cached views had to be quarantined (see
`ISSUES.md` #7). Critic + existing lints did not catch any of them.
Three mechanical lint rules would have rejected most root causes
*before* expensive verus runs:

### M1 — `field@` / `<Inner as View>::V` on a type with no registered View

**Symptom.** Body or `V` struct references `<Inner as View>::V`, or
the body contains `self.<field>@` where `<field>` has a type that
is not in `{Vec<…>, Ghost<…>, Tracked<…>, primitive, vstd-known-View}`
and is not present in the project's view registry.

**Why critic misses it.** The critic only sees the synthesised
body, not the registry. It cannot verify that `<PageAllocator as View>::V`
actually resolves.

**Detector sketch.**

```python
# spec_determinism/view/llm.py

# Heads that vstd / std unconditionally implement View for. The
# resolver also picks these up at L1/L2; we hard-code them to avoid
# a circular dep on the registry.
VSTD_VIEW_HEADS: frozenset[str] = frozenset({
    "Vec", "Box", "Rc", "Arc", "Option", "Result", "Set", "Map",
    "Seq", "Multiset", "Ghost", "Tracked", "FnSpec",
    # primitives — Verus auto-derives View for these
    "u8","u16","u32","u64","u128","usize",
    "i8","i16","i32","i64","i128","isize",
    "bool","char","str",
})

def check_view_field_targets_have_view(
    decl: str,
    *,
    parent_type: TypeDef,           # impl_scanner.get_type(short_name)
    cache: ViewCache,               # for is_quarantined() + active sibling views
    registry_short_names: set[str], # ViewRegistry.short_names()
    scanner: ImplScanner,
) -> Optional[str]:
    """Lint M1 (see docs/critic-criteria.md).

    Inputs are all read-only; the function is pure.

    Returns ``None`` on accept, a reject reason string on reject.
    """
    refs: set[str] = set()

    # --- Step 1 — gather <X as View>::V references via tree-sitter.
    # In the Verus grammar a `<X as View>::V` is parsed as
    #   qualified_type_path → type_path { type ; trait_path } → "::" V
    # but tsv exposes it as a generic type_arguments / scoped_identifier
    # subtree. Robust matcher: walk every "scoped_type_identifier" node
    # whose suffix is "V" and whose qualifier text contains " as View".
    wrapped = "verus! {\n" + decl + "\n}"
    tree = _parser.parse(wrapped.encode("utf-8"))
    cursor = tree.walk()
    def walk(node):
        if node.type in ("qualified_type", "scoped_type_identifier",
                         "qualified_identifier"):
            txt = wrapped[node.start_byte:node.end_byte]
            m = re.match(r"<\s*(\w+)\s+as\s+View\s*>", txt)
            if m: refs.add(m.group(1))
        for ch in node.named_children: walk(ch)
    walk(tree.root_node)

    # --- Step 2 — gather self.<field>@ projections from the view body.
    # We do NOT walk the V-struct (those references are caught above).
    body = _extract_view_fn_body(decl) or ""
    body_tree = _parser.parse(("verus! { fn _v() { " + body + " } }").encode())
    self_at_fields: set[str] = set()
    def walk_body(node):
        # tsv emits `field_expression` for self.x and `unary_expression`
        # (op="@") for x@. Catch the field name when @ is applied.
        if node.type == "unary_expression" and \
           node.child_by_field_name("operator") is not None and \
           wrapped_text(node).endswith("@"):
            inner = node.child_by_field_name("argument")
            if inner is not None and inner.type == "field_expression" \
               and wrapped_text(inner.child_by_field_name("value")) == "self":
                fname = wrapped_text(inner.child_by_field_name("field"))
                self_at_fields.add(fname)
        for ch in node.named_children: walk_body(ch)
    walk_body(body_tree.root_node)

    # --- Step 3 — resolve each field's declared type head via impl_scanner.
    field_heads: set[str] = set()
    for fname in self_at_fields:
        ftype = scanner.field_type(parent_type.qualified_name, fname)
        if ftype is None:
            # impl_scanner couldn't find the field — bail out to a permissive
            # reject (with field name in message) so the critic can ask the
            # synthesiser to justify it.
            return (f"`self.{fname}@` references unknown field on "
                    f"`{parent_type.name}`. impl_scanner missed it; the "
                    f"synthesiser may have hallucinated a field.")
        inner = _strip_ghost_tracked(ftype)
        field_heads.add(inner.head)

    # --- Step 4 — every referenced head must be View-resolvable.
    candidate_heads = refs | field_heads
    available = (registry_short_names
                 | VSTD_VIEW_HEADS
                 | scanner.known_view_impls(parent_type.crate))
    for h in candidate_heads:
        if h in available: continue
        if cache.is_quarantined(h):
            # Belt + suspenders: a previously-quarantined dep is the same
            # as missing.
            return (f"`<{h} as View>::V` or `self.<…>@` references "
                    f"`{h}`, which is quarantined. Re-attempting this "
                    f"view would cascade-break.")
        return (f"View target `{h}` has no registered View impl "
                f"(not in {sorted(available)[:5]}…). Either "
                f"(a) restructure the V-type to avoid the dep, "
                f"(b) quarantine `{parent_type.name}` until `{h}` has a "
                f"view, or (c) add a manual `impl View for {h}` to the "
                f"project source.")
    return None
```

**Helper to wire up.** Patch `synthesize_view` to call this between
`check_view_body_uses_self` (rule 8) and the codex critic:

```python
m1_reject = check_view_field_targets_have_view(
    view_decl, parent_type=td, cache=cache,
    registry_short_names=set(view_registry.short_names()),
    scanner=impl_scanner,
)
if m1_reject:
    status_out["status"] = "lint_reject"
    append_rejected(cache.root, td.name, m1_reject, view_decl,
                    rule="M1-field-view-target")
    return None
```

**Acceptance fixtures (must reject all):**

| view | head that triggers reject |
|---|---|
| `atmosphere/Kernel`              | `PageAllocator` / `MemoryManager` / `ProcessManager` |
| `atmosphere/MapEntry`            | `PAddr` |
| `atmosphere/SyscallReturnStruct` | `RetValueType` (or `Pcid`) |
| `atmosphere/Endpoint`            | `EndpointState` (also a target of M2 below) |

**False-positive guard.** Be sure to also accept the 11 winning views
(see COMPARE.md "Case studies"): they only reference Vec/Seq/Array
heads which are in `VSTD_VIEW_HEADS`. Unit-test must include
`memory-allocator/CommitMask`, `atmosphere/PageMap`,
`ironkv/Constants`, `nrkernel/ArchExec` as `expect=None`.

### M2 — `field@@` over-projection past Ghost into Set/Map/etc.

**Symptom.** Body contains `self.<field>@@`. One `@` is fine when
`<field>` is `Ghost<T>` (peels Ghost), but the second `@` requires the
inner `T` to have `View::view`. `Set<…>` and `Map<…>` don't.

**Why critic misses it.** Already partly covered by rule 1 ("primitive
@-mistake") in the critic prompt, but the critic confuses "Ghost wraps
Set" with "Ghost wraps Vec" and accepts it anyway.

**Detector sketch.**

```python
# spec_determinism/view/llm.py

# Heads whose values are NOT View-projectable even when wrapped in
# Ghost / Tracked. Adding @@ here is guaranteed-wrong.
NON_VIEWABLE_INNER_HEADS: frozenset[str] = frozenset({
    "Set", "Map", "Multiset", "FnSpec", "Seq",  # Seq has identity view, no @
    "int", "nat",                                  # ghost ints; @ is noop
})

# Regex is sufficient because @@ is unambiguous in the verus grammar
# (no overload / no operator method named `@@`).
_DOUBLE_AT_RE = re.compile(r"\bself\.(\w+)\s*@\s*@")

def check_no_double_at_past_ghost(
    decl: str,
    *,
    parent_type: TypeDef,
    scanner: ImplScanner,
) -> Optional[str]:
    """Lint M2 (see docs/critic-criteria.md).

    For each `self.<field>@@` in the body, check whether the inner
    type after peeling Ghost / Tracked has a registered View.
    """
    body = _extract_view_fn_body(decl) or ""
    for m in _DOUBLE_AT_RE.finditer(body):
        fname = m.group(1)
        ftype = scanner.field_type(parent_type.qualified_name, fname)
        if ftype is None:
            return (f"`self.{fname}@@` references unknown field on "
                    f"`{parent_type.name}`.")
        if ftype.head not in ("Ghost", "Tracked"):
            return (f"`self.{fname}@@` applied to a non-Ghost / non-Tracked "
                    f"field (type `{ftype.head}`). Use a single `@` "
                    f"or drop the projection entirely.")
        inner = ftype.generic_args[0] if ftype.generic_args else None
        if inner is None: continue
        if inner.head in NON_VIEWABLE_INNER_HEADS:
            return (f"`self.{fname}@@` projects past Ghost<{inner.head}<…>>; "
                    f"`{inner.head}` has no `View::view`. Use a single "
                    f"`@` to unwrap Ghost, then the resulting `{inner.head}` "
                    f"already lives in spec land.")
    return None
```

**Wiring.** Same insertion point as M1. M2 should run *before* M1 so
its more specific message takes precedence when both fire.

**Acceptance fixtures:**

| view | field that triggers reject |
|---|---|
| `atmosphere/Endpoint` | `self.owning_threads@@` (Ghost\<Set\<…\>\>) |

**False-positive guard.** Other instances of `Ghost<Map<…>>`
legitimately need `@@` only when the map's value type itself has a
View. None of the winning views use `@@`; unit-test pulls the entire
130-entry cache and asserts only Endpoint rejects.

### M3 — view body uses `self.<field>` on an `external_body` / opaque parent

**Symptom.** The parent type is marked `external_body` (or has
`#[repr(C)]` / similar that makes Verus treat it as opaque). Body
projects `self.m@` or similar, which Verus rejects as "field
expression for an opaque datatype".

**Why critic misses it.** Critic doesn't see the parent type's
annotations.

**Detector sketch.**

```python
# spec_determinism/view/impl_scanner.py — extend TypeDef
#
#   @dataclass
#   class TypeDef:
#       name: str
#       qualified_name: str
#       kind: str                # "struct" | "enum" | "union" | "alias"
#       fields: list[Field]
#       variants: list[Variant]
#       source_file: Path
#       source_line: int
#       # NEW
#       attrs: list[str] = field(default_factory=list)  # raw textual attrs
#       is_external_body: bool = False
#       is_external_type_specification: bool = False
#       repr_kind: Optional[str] = None  # "C", "transparent", None, …
#
# Populated by parse_type_def() which already walks the
# `attribute_item` / `outer_attribute` siblings of the struct_item /
# enum_item tree-sitter nodes. Pseudocode:

def _attrs_for(node: ts.Node, src: bytes) -> list[str]:
    out = []
    sib = node.prev_named_sibling
    while sib is not None and sib.type in ("attribute_item",
                                            "outer_attribute"):
        out.append(src[sib.start_byte:sib.end_byte].decode())
        sib = sib.prev_named_sibling
    return list(reversed(out))

def _classify_attrs(attrs: list[str]) -> tuple[bool, bool, Optional[str]]:
    is_ext_body = any("external_body" in a for a in attrs)
    is_ext_spec = any("external_type_specification" in a for a in attrs)
    repr_kind = None
    for a in attrs:
        m = re.search(r"#\[\s*repr\s*\(\s*([A-Za-z0-9_, ]+?)\s*\)", a)
        if m:
            # "C", "C, align(8)" → "C"
            repr_kind = m.group(1).split(",", 1)[0].strip()
            break
    return is_ext_body, is_ext_spec, repr_kind

# spec_determinism/view/llm.py

def check_parent_not_external_body(
    *,
    parent_type: TypeDef,
) -> Optional[str]:
    """Lint M3 (see docs/critic-criteria.md).

    Pure parent-type predicate; does not even look at view_decl.
    """
    if parent_type.is_external_body:
        return (f"`{parent_type.name}` is marked `#[verifier::external_body]` "
                f"— Verus treats its fields as opaque and forbids field "
                f"expressions in spec functions. Drop `{parent_type.name}` "
                f"from the L4 work list (or rewrite via an "
                f"`external_type_specification` shim).")
    if parent_type.repr_kind == "C":
        return (f"`{parent_type.name}` is `#[repr(C)]` — typically used for "
                f"FFI / hardware-layout structs that Verus opaque-models. "
                f"Field projections in spec are likely to fail. Audit "
                f"manually; if Verus does accept field access, mark this "
                f"type explicitly viewable and bypass the lint.")
    return None
```

**Wiring.** Insert M3 *first* of the three (it's the cheapest — a
single attr check, no parsing). If M3 rejects, the synthesiser doesn't
even need to be invoked for this type at all; the right action is to
add the type to a project-level skip list:

```python
# In synthesize_view, right after _extract_type_source:
m3_reject = check_parent_not_external_body(parent_type=td)
if m3_reject:
    status_out["status"] = "lint_reject"
    append_rejected(cache.root, td.name, m3_reject, view_decl="",
                    rule="M3-parent-opaque")
    return None
```

**Acceptance fixtures:**

| view | parent attribute |
|---|---|
| `ironkv/CKeyHashMap` | `#[verifier::external_body]` |
| `atmosphere/Registers` | `#[repr(C, align(8))]` |

**False-positive guard.** `#[repr(transparent)]` newtypes ARE
spec-projectable; the `repr_kind == "C"` clause skips them. Also,
`atmosphere/Endpoint` has `#[repr(C, align(8))]` per the source diff
above but its breakage is M1/M2, not M3 — so M3 alone would not
reject it, but M3+M1 together would (and we want both to fire so the
critic feedback is rich).

Wait — that contradicts the goal of running M3 first. Reconcile:
either drop the `repr_kind == "C"` clause (only flag
`external_body`), or keep it as a "warn but continue" rather than a
reject. **Recommended:** demote `repr_kind == "C"` to a warning that
appends a `note` to the rejected.jsonl entry but lets synth proceed,
so that M1/M2 can still produce the more actionable reject reason.
`external_body` stays as a hard reject because it really is
impossible.

### Cascade closure

After rules M1/M2/M3 quarantine root-cause views, dependent views
(V-decls that reference the quarantined type's `View`) will fail to
compile in any target that needs them. Three options:

1. **(Recommended)** Add a `transitive_resolve()` pass to
   `view/registry.py` that, before injecting a cached view, walks
   `entry.depends_on_views_of` and only injects if all transitive deps
   are resolvable. If not, demote the view to "missing" (gen_det then
   falls back to per-field equal). Sketch:

   ```python
   # spec_determinism/view/registry.py — inside _l4_resolution_from_entry
   def _all_deps_resolvable(self, entry, visiting=None) -> bool:
       visiting = visiting or set()
       for dep in (entry.depends_on_views_of or []):
           if dep in visiting: continue  # cycle break
           visiting.add(dep)
           # vstd / primitive: always OK
           if dep in VSTD_VIEW_HEADS:                continue
           # impl-scanner sees an `impl View` in source: OK
           if self.l3_has(dep):                       continue
           # cache has an active (non-quarantined) entry: recurse
           inner = self.llm_cache.get_any(dep) if self.llm_cache else None
           if inner is None:                          return False
           if not self._all_deps_resolvable(inner, visiting): return False
       return True
   # in _l4_resolution_from_entry, gate the resolution:
   if not self._all_deps_resolvable(entry): return None
   ```

2. Eagerly quarantine the cascade closure each time a root is
   quarantined (what we did manually in #7). Implemented as a CLI
   helper:

   ```sh
   python -m spec_determinism.view.llm quarantine \
       --cache-dir results-verusage/view_registry/ironkv \
       --short EndPoint --close-cascade
   ```
   where `--close-cascade` walks every cache entry with `EndPoint` in
   `depends_on_views_of` and quarantines them too, transitively.

3. Inject transitive views into the target's `injected.rs` so the
   compile is closed. Less surgical.

(1) is the cleanest long-term fix. (2) is what we currently do.

### Acceptance test for the new rules

When implementing, the unit-test fixtures should be the 14 quarantined
view JSONs — for each, the relevant lint rule must produce a
non-None reject reason. Plus the 11 winning views as
`expect=None` controls.

Test harness sketch (drop into `view/llm.py::_run_self_tests`):

```python
QUARANTINE_FIXTURES = [
    # (proj, name, rule_that_must_reject)
    ("atmosphere","Kernel",              "M1"),
    ("atmosphere","SyscallReturnStruct", "M1"),
    ("atmosphere","Endpoint",            "M2"),  # M1 also OK, M2 preferred
    ("atmosphere","MapEntry",            "M1"),
    ("atmosphere","Registers",           "M3"),
    ("ironkv","EndPoint",                "M1"),  # M4 too but unimpl
    ("ironkv","CKeyHashMap",             "M3"),
    # cascade group — rejected by transitive resolve once M1/M2/M3
    # quarantine the roots; we test the resolve gate separately.
    *(("ironkv", n, "cascade") for n in (
        "CSingleDelivery","CSingleMessage","CAckState","CSendState",
        "ReceiveImplResult","CPacket","CMessage",
    )),
]
GOOD_FIXTURES = [
    ("memory-allocator","CommitMask"),
    ("atmosphere","PageMap"),
    ("ironkv","Constants"),
    ("nrkernel","ArchExec"),
]
```

This guarantees the regression does not recur when those types'
source bytes change and the cache is rebuilt.

### Quarantine sticky-marker (implemented 2026-05-11)

`ViewCache.is_quarantined(short)` checks for a sibling
`<short>.json.quarantine` file, and `prefill_project` skips those
types by default (override with `--include-quarantined`). This means
the quarantines from ISSUES.md #7 survive future `prefill_all.sh`
runs — the LLM will not silently re-synthesise the same broken
shape on the next batch. To intentionally retry a quarantine
(e.g. after a project-source change), delete the `.quarantine` file
or pass `--include-quarantined`.

---

## PR-D5 — M1/M2/M3 lint impl + retroactive scan (2026-05-11)

The lints sketched above are now implemented in `view/llm.py` and
wired into both `synthesize_view` (pre-cache) and a new `lint-scan`
CLI sub-command (retroactive). Self-tests cover M1/M2/M3 and the
priority aggregator; `python -m spec_determinism.view.llm test`
exits 0.

The detectors took **two intentional deviations** from the sketches
above. Both were forced by the retroactive scan on PR-D4's
post-quarantine corpus, which surfaced false positives a more naive
implementation would emit:

### Deviation 1 — M2's "non-viewable inner heads" is just `{FnSpec}`

The sketch listed `{Set, Map, Multiset, FnSpec, Seq, int, nat}`. In
practice **Set / Seq / Map / Multiset have identity `View` impls in
vstd** (they are spec-only types; `@` is a noop). atmosphere /
`Container` uses `Ghost<Set<…>>@@` and `Ghost<Seq<…>>@@` in its
real cached view and verifies cleanly. `int@` and `nat@` are
similarly noops. Narrowing the set to `{FnSpec}` retains a
meaningful M2 (a `Ghost<FnSpec<…>>@@` is still a type error: Fn
traits have no projectable View) without producing the Container
false positive.

### Deviation 2 — M3 has a "unit-V" exemption

`#[verifier::external_body]` parents can legitimately collapse their
view to the unit type via:
```rust
impl View for Foo { type V = (); fn view(&self) -> () { () } }
```
This is the same escape hatch documented for `check_view_body_uses_self`
(`legitimate unit collapse`). M3 now consults `_is_unit_v(view_decl)`
and accepts these silently; the only remaining hard reject is
`external_body` + non-trivial body (the
`ironkv/HashMap`, `storage/ExternalDigest`, and the four pre-existing
M3-quarantined cases all match this shape).

### Deviation 3 — M1 honours impl-generic params

`_extract_impl_generics(view_decl)` parses the leading `impl<...>`
block and returns the set of generic param names (lifetimes and
`const` params are dropped). Those names are treated as
already-viewable by M1: the synthesiser is relying on the impl's
trait bounds, and Verus will catch any missing `View` bound at
parse time. This pin lets `ironkv/KeyIterator`
(`impl<K: KeyTrait + VerusClone + View> View for KeyIterator<K>`)
and `storage/WriteRestrictedPersistentMemoryRegion`
(`impl<Perm, PMRegion>`) pass cleanly.

### Other implementation refinements

* `VSTD_VIEW_HEADS` was extended with `String` (vstd has
  `impl View for String { type V = Seq<char>; }`) and `spec_fn`
  (the spec function type has identity View).
* For `self.<field>@`, when the field's type expression has
  `kind == "fn"` (i.e. `spec_fn(...)`) the head check is skipped —
  Verus accepts identity views on spec functions.
* `known_view_heads` is now built by *probing* every parsed short
  name through `ViewRegistry.resolve` rather than unioning name
  sets. This single change subsumes L1 prelude rules, L2 alias
  chains, L3 raw `impl View` blocks, and L4 active cache entries —
  and crucially does NOT include parsed types that lack any View
  impl. Earlier drafts that unioned `types_by_short.keys()` made
  the M1 rule toothless; earlier-still drafts that omitted aliases
  flagged `ironkv/AckList` / `ironkv/SendState` as
  unresolvable when they are actually `type X = Seq<...>;` and
  `type X = Map<...>;` aliases.

### Retroactive scan outcome (per project, post-FP-iteration)

| project | active scanned | active reject | quarantined (incl.) | reject (incl.) |
|---|---:|---:|---:|---:|
| anvil-library | 2 | 0 | 0 | 0 |
| atmosphere | 23 | 0 | 5 | 1 (M1) |
| ironkv | 28 | 0 | 12 | 11 (M1=9, M3=2) |
| memory-allocator | 6 | 0 | 0 | 0 |
| nrkernel | 36 | 0 | 0 | 0 |
| storage | 17 | 0 | 2 | 2 (M3=2) |
| vest | 0 | 0 | 0 | 0 |

* Active-cache lint emits **0 rejections** across all 7 projects,
  confirming the lints don't fire on the PR-D4-blessed corpus.
* When quarantined entries are included (`--include-quarantined`),
  the lints recapture every M1/M3-classifiable quarantine — that's
  the regression-pin against future cache rebuilds.

### 4 retroactive findings → 4 new quarantines

The retroactive scan found 4 cached views that PR-D4 left in active
cache but that the lints (correctly) reject:

| project | type | rule | reason |
|---|---|---|---|
| ironkv | HashMap | M3 | external_body parent; inherent `uninterp spec fn view` in source already provides a (different) View, so the L4 cache entry conflicts |
| ironkv | ReceiveResult | M1 | cascade: references `<CPacket as View>::V`, CPacket already quarantined |
| ironkv | CTombstoneTable | M1 | cascade: references `<HashMap as View>::V`, HashMap freshly quarantined above |
| storage | ExternalDigest | M3 | external_body parent; body projects `<Digest as View>::V` |

These views did not cause PR-D4 regressions (their target rows show
no verus_error delta), so quarantining them is a cleanup — they were
dead-weight cache entries that would have surfaced as silent regressions
the moment any new target tried to use them. Total quarantine count:
14 (original PR-D4) + 4 = **18**.

### CLI

```
python -m spec_determinism.view.llm lint-scan \
  --cache-dir results-verusage/view_registry/<project> \
  --root /path/to/verusage/source-projects/<project> \
  --project <project> \
  [--include-quarantined] \
  [--show-decl]
```
Writes `<cache-dir>/_lint_scan.json`. Exits 1 if any rejection
fires, 0 otherwise.
