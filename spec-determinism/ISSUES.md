# spec-determinism — Known issues

Tracking real (not formatting / not stylistic) bugs found by the codex
critic or by manual audit during Phase 2 (A-2 view-aware equal-fn).
Each entry: **symptom / probable cause / fix idea**.

## #1 — `storage/CrcDigest`: over-projection with double `@`

**Symptom.** The synthesiser produced

```rust
closed spec fn view(&self) -> CrcDigestView {
    CrcDigestView { bytes_in_digest: self.bytes_in_digest@@ }
}
```

The critic correctly rejected: "after unwrapping `Ghost` with one `@`,
the stored spec sequence should be returned as `self.bytes_in_digest@`,
since the inner `u8` primitives cannot be `@`-projected."

**Probable cause.** The synthesiser treats `Ghost<Seq<Seq<u8>>>` as a
two-step unwrap because the type contains two layers of generic
brackets. It does not consistently apply the rule "primitive scalars
(`u8`, `usize`, …) do **not** take a `@`". The prompt header
(`view/llm.py::_BASE_PROMPT`) lists the rule under "primitive `@`
mistake" but the synthesiser still mis-fires when the primitive is
**nested** inside two `Seq<…>` layers.

**Fix idea.** Either

- (cheap) Add a concrete worked-example to the prompt showing
  `Ghost<Seq<Seq<u8>>>` → `Seq<Seq<u8>>` via one `@`, not two; OR
- (proper) Have the critic *propose* a corrected `view_decl` on
  reject (currently it only outputs `verdict`+`issues`) and feed it
  back into the cache. That converts an iteration into a single
  retry instead of a re-prefill.

**Status.** Recorded in
`results-verusage/view_registry/storage/_rejected.jsonl`. The next
`scripts/prefill_all.sh` run will retry this type from scratch.

## #2 — `nrkernel/PTDir`: inner-map elided

**Symptom.** Source has `entries: Seq<Option<PTDir>>`; the candidate
declared `entries: Seq<Option<PTDirView>>` in the view type but the
body was

```rust
PTDirView {
    region: self.region,
    entries: self.entries@,
    used_regions: self.used_regions,
}
```

Critic flagged: `self.entries@` produces `Seq<Option<PTDir>>`, not
`Seq<Option<PTDirView>>`; the inner element `View` is never applied.

**Probable cause.** The synthesiser knows the *declared* view type for
`PTDir` (it's writing it) but doesn't realise the body's nested-element
projection isn't automatic. Verus has no implicit "lift" from
`Seq<Option<T>>` to `Seq<Option<T::V>>`; you have to write it.

**Fix idea.**

- The correct view body would be
  ```rust
  entries: self.entries@.map_values(|o: Option<PTDir>|
      match o { None => None, Some(d) => Some(d@) }),
  ```
  or equivalently a `Seq::new(len, |i| …)` form.
- Add this exact "nested `Option<T>` inside `Seq`" pattern to the
  prompt header alongside the existing `Map.map_values` example.
- Critic could propose the fix automatically when it detects "viewed_type
  declares container of `<TypeName>View` but body shape doesn't visibly
  perform the lift".

**Status.** Recorded in
`results-verusage/view_registry/nrkernel/_rejected.jsonl`. Note this
type is part of the **mutually-recursive `{Directory, NodeEntry, PTDir}`
cycle** which PR-E (deferred SCC whole-component prompt) is intended to
address; until then, a single-type retry will keep failing for the same
structural reason.

## #3 — `nrkernel/LoadResult`: already-spec field re-projected

**Symptom.** Source:

```rust
pub enum LoadResult {
    Pagefault,
    Value(Seq<u8>),
}
```

The candidate:

```rust
LoadResult::Value(s) => LoadResultView::Value(s@),
```

Critic: "Value already carries spec type `Seq<u8>`; projecting it as
`s@` is likely a typecheck error".

**Probable cause.** The synthesiser couldn't tell from the prompt that
`Seq<u8>` is a Verus spec type. Its heuristic "every dependency field
gets a `@`" over-fires for things that are already spec. Note the
**prompt context** for this type was unusually small — only
`pub enum LoadResult { Pagefault, Value(Seq<u8>) }` was passed in,
without the import-resolved hint that `Seq<u8>` lives in `vstd::seq::*`.

**Fix idea.**

- Extend the `_BASE_PROMPT` rule list with: "if a field is already a
  spec type from `vstd::{seq, map, set, multiset}`, return it
  unchanged — do not append `@`".
- (Stronger) Have the type registry tag each field with
  `is_spec_type: bool` and pass that into the prompt context so the
  synthesiser cannot misclassify.

**Status.** Recorded in
`results-verusage/view_registry/nrkernel/_rejected.jsonl`.

## #4 — `storage/MaybeCorruptedBytes`: `arbitrary()` over-collapse

**Symptom.** The synthesiser produced

```rust
impl<S> View for MaybeCorruptedBytes<S> where S: PmCopy {
    type V = Seq<u8>;
    closed spec fn view(&self) -> Seq<u8> {
        arbitrary()
    }
}
```

The critic **accepted** this. It shouldn't have.

**Probable cause.** `arbitrary::<T>()` in vstd returns a fixed (but
unspecified) witness of `T`. Every call to `arbitrary::<Seq<u8>>()`
returns the **same** sequence. Therefore the view collapses every
value of `MaybeCorruptedBytes<S>` to one and the same `Seq<u8>`, which
means `equal_v(a, b)` is provably `true` for *all* `a, b`. The
function will then be marked deterministic regardless of whether it is.

**Fix idea.**

- Add to the critic prompt (`view/critic.py::_CRITIC_PROMPT_HEADER`)
  an explicit rule: "**Reject any view body whose RHS does not
  reference `self` at all**, including bodies of the form
  `arbitrary()`, `Seq::empty()`, or any constant-valued
  expression — they collapse all instances to equal."
- Add an AST-level lint inside `view/llm.py::_validate_view_decl`
  that rejects view bodies that don't read from `self`. This is a
  cheap mechanical guard that doesn't need an LLM round-trip.

**Status.** Currently cached as `accept`. To re-audit, delete the
file and re-prefill; the new critic rule above should catch it.

Found in audit round 2 (2026-05-11) — see
`results-verusage/view_registry/AUDIT_NOTES.md` "Round 2".

## #5 (reminder) — `--use-view-registry` had no integration test

Not a view-quality issue, but worth recording: the subpackage refactor
in `226d93f` broke 4 cross-subpackage relative imports (fixed in
`1751dc1`). These imports were inside `TYPE_CHECKING` blocks or
function-local imports that the existing selftests don't exercise.

**Fix idea.** Add a one-shot smoketest under `tests/` (or as a `make
check` target) that runs `verusage_run --use-view-registry` on a tiny
hand-rolled corpus (one project, one function) and asserts exit code
0. This would have caught the broken imports immediately.
