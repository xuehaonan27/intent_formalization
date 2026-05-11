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

**Draft rule.**

```python
def check_view_field_targets_have_view(decl: str,
                                        registry_short_names: set[str],
                                        scanner: ImplScanner) -> Optional[str]:
    """Reject if the V-type or body references <X as View>::V or .@ on
    a type ``X`` that is neither (a) in the project's view_registry,
    (b) a vstd-known View (Vec, Box, Option, Result, primitive, etc.),
    (c) a Ghost/Tracked wrapper.
    """
    refs = re.findall(r"<(\w+) as View>::V", decl)
    fields = parse_self_field_projections(decl)  # tree-sitter
    for t in set(refs) | {f.field_type_head for f in fields}:
        if t in registry_short_names:        continue
        if t in VSTD_KNOWN_VIEW_HEADS:       continue
        if scanner.is_ghost_or_tracked(t):   continue
        return f"References `<{t} as View>::V` or `.@` but no View impl available."
    return None
```

Test fixtures: `atmosphere/Kernel`, `atmosphere/MapEntry`,
`atmosphere/SyscallReturnStruct` all reject.

### M2 — `field@@` over-projection past Ghost into Set/Map/etc.

**Symptom.** Body contains `self.<field>@@`. One `@` is fine when
`<field>` is `Ghost<T>` (peels Ghost), but the second `@` requires the
inner `T` to have `View::view`. `Set<…>` and `Map<…>` don't.

**Why critic misses it.** Already partly covered by rule 1 ("primitive
@-mistake") in the critic prompt, but the critic confuses "Ghost wraps
Set" with "Ghost wraps Vec" and accepts it anyway.

**Draft rule.**

```python
_DOUBLE_AT = re.compile(r"\bself\.\w+@@\B")

def check_no_double_at_on_set_or_map(decl: str, scanner: ImplScanner) -> Optional[str]:
    for m in _DOUBLE_AT.finditer(decl):
        field_name = re.match(r"self\.(\w+)@@", m.group(0)).group(1)
        ftype = scanner.field_type(field_name)
        if ftype is None: continue
        inner = strip_ghost_tracked(ftype)
        inner_head = inner.head if isinstance(inner, TypeExpr) else None
        if inner_head in {"Set", "Map"}:
            return f"`self.{field_name}@@` projects past Ghost into `{inner_head}`, which has no View::view."
    return None
```

Test fixture: `atmosphere/Endpoint` rejects on `self.owning_threads@@`.

### M3 — view body uses `self.<field>` on an `external_body` / opaque parent

**Symptom.** The parent type is marked `external_body` (or has
`#[repr(C)]` / similar that makes Verus treat it as opaque). Body
projects `self.m@` or similar, which Verus rejects as "field
expression for an opaque datatype".

**Why critic misses it.** Critic doesn't see the parent type's
annotations.

**Draft rule.**

```python
def check_parent_not_external_body(type_def: TypeDef) -> Optional[str]:
    if type_def.is_external_body or type_def.has_repr_c:
        return ("Parent type is external_body / repr(C); Verus treats "
                "its fields as opaque and forbids field expressions in "
                "spec functions. Use `arbitrary()` (rejected by rule 8) "
                "is not a workaround; this type should not have a "
                "synthesised view at all — drop it from the L4 work list.")
    return None
```

Test fixtures: `ironkv/CKeyHashMap`, `atmosphere/Registers` reject.

### Cascade closure

After rules M1/M2/M3 quarantine root-cause views, dependent views
(V-decls that reference the quarantined type's `View`) will fail to
compile in any target that needs them. Three options:

1. **(Recommended)** Add a `transitive_resolve()` pass to
   `view/registry.py` that, before injecting a cached view, walks
   `entry.depends_on_views_of` and only injects if all transitive deps
   are resolvable. If not, demote the view to "missing" (gen_det then
   falls back to per-field equal).
2. Eagerly quarantine the cascade closure each time a root is
   quarantined (what we did manually in #7).
3. Inject transitive views into the target's `injected.rs` so the
   compile is closed. Less surgical.

(1) is the cleanest long-term fix. (2) is what we currently do.

### Acceptance test for the new rules

When implementing, the unit-test fixtures should be the 14 quarantined
view JSONs — for each, the relevant lint rule must produce a
non-None reject reason. This guarantees the regression does not recur
when those types' source bytes change and the cache is rebuilt.
