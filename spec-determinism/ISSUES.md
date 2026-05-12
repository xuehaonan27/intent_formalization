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
`results-verusage/view_registry/nrkernel/_rejected.jsonl`. **Updated
2026-05-12 (PR-E):** the SCC framing was wrong — `{Directory,
NodeEntry, PTDir}` is **not** a cycle; `PTDir` is single-type
self-recursive (`entries: Seq<Option<PTDir>>`), and `Directory` /
`NodeEntry` are already covered. The real bug class is now caught
preventively by **M4** lint (`check_m4_self_recursion_bare_at` in
`view/llm.py`) + critic rule #9 + a new self-recursion alert in
`build_view_prompt`. The new prompt offers three legal shapes
(Options A/B/C documented in `docs/critic-criteria.md`); for PTDir
specifically, **Option C** (`type V = Self; view { *self }`) is
recommended because all fields are spec-friendly. LLM retry of PTDir
not yet performed; the static gate is in place.

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

## #7 — 14 broken L4-llm views quarantined (mass quarantine 2026-05-11)

Per COMPARE.md analysis, 14 L4-synthesised view entries correlated
with 74 verus_error regressions (66 `ok_w → verus_error` + 8 clean
`ok → verus_error`). All were `critic_verdict=accept` but had compile-
or proof-level defects. Quarantined to recover a clean A-2 diff.

Reproducer (already applied):

```sh
cd spec-determinism
for entry in \
  atmosphere/Kernel  atmosphere/SyscallReturnStruct  atmosphere/Endpoint \
  atmosphere/MapEntry  atmosphere/Registers \
  ironkv/EndPoint  ironkv/CSingleDelivery  ironkv/CSingleMessage \
  ironkv/CAckState  ironkv/CSendState  ironkv/ReceiveImplResult \
  ironkv/CPacket  ironkv/CKeyHashMap  ironkv/CMessage; do
    mv results-verusage/view_registry/$entry.json \
       results-verusage/view_registry/$entry.json.quarantine
done
```

| project | view | failure mode | reason |
|---|---|---|---|
| atmosphere | `Kernel`              | M1-cascade | `V` struct references `<PageAllocator as View>::V` / `<MemoryManager …>` / `<ProcessManager …>` — none of those have a View impl in the project nor in the registry |
| atmosphere | `SyscallReturnStruct` | M1-cascade | `V` fields use bare `RetValueType` and `Option<Pcid>` types — neither has a registered View, and as raw spec field types they aren't always spec-equal |
| atmosphere | `Endpoint`            | M1 + M2    | `self.queue_state@` ⇒ trait bound `EndpointState: View` not satisfied at this call site; `self.owning_threads@@` over-projects (`Set` has no `View::view`) |
| atmosphere | `MapEntry`            | M1-cascade | `V` references bare `PAddr` (not registered as View) — spec equality on `PAddr` is not the same as field-equal on the underlying `usize` |
| atmosphere | `Registers`           | M3         | `Registers` is `#[repr(C, align(8))]` — Verus often treats explicit-`repr` structs as external-body / opaque; field expressions are then disallowed in spec |
| ironkv | `EndPoint`               | M4 (semantic) | Body `self.id@` ⇒ `Seq<u8>`, but downstream proof code uses `AbstractEndPoint{id: …}` projections — the synthesiser picked the wrong `V` |
| ironkv | `CSingleDelivery`        | cascade    | `V` = `{… <CSendState as View>::V}` → fails once `EndPoint` / `CSendState` chain is quarantined |
| ironkv | `CSingleMessage`         | cascade    | `V` enum variant references `<EndPoint as View>::V`, `<CMessage as View>::V` |
| ironkv | `CAckState`              | cascade    | `Seq<<CSingleMessage as View>::V>` |
| ironkv | `CSendState`             | cascade    | `Map<AbstractEndPoint, <CAckState as View>::V>` |
| ironkv | `ReceiveImplResult`      | cascade    | variant `FreshPacket{<CPacket as View>::V}` |
| ironkv | `CPacket`                | cascade    | `{dst: <EndPoint as View>::V, msg: <CSingleMessage as View>::V}` |
| ironkv | `CKeyHashMap`            | M3         | `CKeyHashMap` wraps `collections::HashMap` and is marked `external_body`; `self.m@` ⇒ "field expression for an opaque datatype" |
| ironkv | `CMessage`               | cascade    | `Redirect{id: EndPoint}`, `Delegate{h: CKeyHashMap}` |

**Three intrinsic root causes**, plus cascade closure:

- **M1 (5 views)**: synthesiser inferred a `<Inner as View>::V` field
  type whose `Inner` has no `View` impl. Cross-check against
  `impl_scanner` + L4 cache should reject.
- **M2 (1 view, `Endpoint`)**: extra `@` after Ghost unwrap when the
  inner type is `Set`. Same family as #1 (CrcDigest) but at field
  level. Tree-sitter regex `\w+@@` would have caught it.
- **M3 (2 views)**: parent type or inner container is `external_body`
  or `repr(C)`. `impl_scanner` knows this; the synthesiser ignored it.
- **M4 (1 view, `EndPoint`)**: V-type semantically inconsistent with
  downstream proof's expected view. Hardest to detect statically;
  would need either a project convention table or a verus dry-run.
- **Cascade (7 views, all ironkv)**: V depends transitively on a
  broken view. After the root is quarantined, the dependent V-decls
  can no longer compile (gen_det does not auto-inject transitive view
  declarations). Quarantine eagerly to keep the cascade closed.

**Lessons.** Critic + lint pipeline did not catch any of these. See
docs/critic-criteria.md "Lint rule drafts (post-quarantine)" for
draft static checks corresponding to M1/M2/M3.

---

## #8 — 4 additional broken L4-llm views found by PR-D5 retroactive scan (2026-05-11)

**Status:** quarantined (commit pending).

The M1/M2/M3 lints from PR-D5 ran retroactively over PR-D4's
post-quarantine cache and surfaced 4 cached views that PR-D4 had
left active but that the lints (correctly) reject. These views did
not cause PR-D4 regressions — their target rows show no
verus_error delta — so they were dead-weight cache entries that
would have surfaced as silent regressions the moment any new
target referenced them. Quarantining is preventive cleanup.

| project | type | rule | reason |
|---|---|---|---|
| ironkv | HashMap | M3 | `#[verifier::external_body]` parent + non-trivial body. Source already has an inherent `pub uninterp spec fn view(self) -> Map<AbstractEndPoint, V>;` (different V-type from the L4 cache), and impl_scanner doesn't see inherent uninterp views — so the L4 cache silently competed with a hand-written authoritative view. |
| ironkv | ReceiveResult | M1 | cascade: body uses `<CPacket as View>::V`, but CPacket is in the original PR-D4 quarantine set. Was always failing to inject. |
| ironkv | CTombstoneTable | M1 | cascade: body uses `<HashMap as View>::V`; HashMap was freshly quarantined above. |
| storage | ExternalDigest | M3 | `#[verifier::external_body]` parent + body projects `<Digest as View>::V` through the opaque boundary. |

**Mass-quarantine command (executed):**
```sh
cd /home/chentianyu/intent_formalization/spec-determinism
for q in \
  "ironkv/HashMap" \
  "ironkv/ReceiveResult" \
  "ironkv/CTombstoneTable" \
  "storage/ExternalDigest"; do
  mv "results-verusage/view_registry/${q}.json" \
     "results-verusage/view_registry/${q}.json.quarantine"
done
```

**Total quarantine count after #8:** 14 (PR-D4 #7) + 4 = 18.

**Verification:** `python -m spec_determinism.view.llm lint-scan
--cache-dir results-verusage/view_registry/<proj> --root … --project
<proj>` now emits 0 rejections on the active cache across all 7
projects. With `--include-quarantined` the rules still trip every
M1/M3-classifiable quarantine (regression pin against future cache
rebuilds).
