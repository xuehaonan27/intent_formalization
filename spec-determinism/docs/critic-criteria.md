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
