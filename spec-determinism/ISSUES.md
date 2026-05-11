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

## #6 — `rerun_corpus.sh` flat `--out` overwrote 6 projects' results

**Symptom.** Corpus rerun `setsid bash scripts/auto_chain.sh`
(2026-05-11 15:22 → 17:07, all 7 projects, rc=0 in driver) produced
1649 artifact subdirs (all 7 prefixes present), but `SUMMARY.json` was
`{}` and `SUMMARY.md` showed 0 everywhere. `compare_runs.py` then
exited with code 2 (`empty candidate`).

Inspection of `results-verusage-viewreg/full_run.json` revealed
**only 1363 entries — all atmosphere**. The other 6 projects' status
records were silently lost.

**Root cause.** Two-part bug:

1. `spec_determinism/corpus/verusage_run.py` writes
   `<out_root>/full_run.json` and `<out_root>/artifacts/<key>/`
   **flat** at `out_root`, with no per-project nesting.
2. `scripts/rerun_corpus.sh` looped 7 projects all passing
   `--out "$OUT"` (`$OUT = results-verusage-viewreg/`). Each project's
   `full_run.json` clobbered the previous one. Atmosphere ran last
   (15:26 → 17:07), so only its data survived.

   The post-iteration `if [[ -f "$OUT/$proj/full_run.json" ]]` looked
   in the wrong path (per-project subdir didn't exist) and silently
   skipped the per-project status print in `_run_summary.log` —
   masking the problem.

3. `spec_determinism/corpus/verusage_summary.py::load_per_project`
   iterates `results_root.iterdir()` looking for
   `<dir>/full_run.json`. Without per-project subdirs it found only
   the flat `artifacts/` dir and returned `{}` — yielding the empty
   `SUMMARY.json`.

`compare_runs.py::load_run` shares the same per-project assumption.

**Fix.** `scripts/rerun_corpus.sh` now creates `$OUT/$proj/` and
passes `--out "$OUT/$proj"` to each `verusage_run` invocation. The
per-project status print path is updated to match. Also added an
optional `ONLY="proj1 proj2 ..."` env var to allow resuming a partial
rerun without redoing the long projects.

**Why not patch `verusage_run.py`?** That would have changed the API
for any other caller; `rerun_corpus.sh` was the only one with the
multi-project loop, and the per-project `--out` is the more common
convention (matches how baseline `results-verusage/` was produced).

**Salvage.** Atmosphere data at the top-level `full_run.json` and
1363 `atmosphere__*` artifact subdirs were moved into
`results-verusage-viewreg/atmosphere/`. Other 6 projects' artifacts
were stale (overwritten between runs) and were deleted; those 6 will
be rerun under the fix (~5 min total — much smaller than atmosphere
alone).

**Lesson.** Add a smoketest (or assertion) that
`load_per_project($OUT)` returns non-empty after `rerun_corpus.sh`
exits, before `compare_runs.py` is invoked. This is on the same wish
list as #5 (an `--use-view-registry` integration test).
