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

---

## #9 — `PointsTo.value()` narrows are not guarded by `is_init()`

**Status:** closed (fix landed in `ff5eac2`, 2026-05-12). `narrow_points_to` now
probes `is_init=true` first and only recurses on `value()` when that branch
sticks; `schemas._emit` POINTS_TO branch wraps every `value()` schema with a
`(is_init(), __bool_true__)` sentinel guard that `_render_body` emits as
`assume((pt).is_init());` ahead of the value() assume. Selftest at
`narrow.py::_run_self_tests` (`replies=[True, False]`) verifies no `value`
nodes are recorded under is_init=false.

**Symptom.** PR-F added `PointsTo<V>` support in both equality and
narrowing. The narrowing strategy probes:

```rust
(pt).is_init()
(pt).value()
(pt).addr()
```

but `value()` is only meaningful when `pt.is_init()` holds. The schema
enumerator also emits `(var).value()` schemas unconditionally. This
means a witness branch can try to activate a `value()` assume without a
corresponding `is_init() == true` guard in the same activation chain.

**Root cause.** `narrow_points_to` records `is_init`, `value`, and
`addr` as sibling tree nodes. `schema_search/schemas.py` mirrors that
shape with independent schemas and no parent guard tying `value()` to
`is_init()`. The comment in `narrow.py` says the assume tree carries the
right polarity, but the current tree shape does not enforce that.

**Risk.** Depending on Verus' SMT encoding for `PointsTo.value()`, this
can produce invalid/unstable guarded templates, `search_error`, or
witnesses whose `value()` facts are not justified by `is_init()`.

**Fix idea.**

- Only narrow `value()` after `is_init() == true` is kept; skip value
  narrowing on false/unknown init branches.
- In schema enumeration, make `(var).value()` schemas carry a parent
  condition equivalent to `(var).is_init() == true`, or add a dedicated
  schema kind for guarded `PointsTo.value()`.
- Add a self-test where `is_init()==false` is the kept branch and assert
  no `.value()` assume is emitted.

Relevant files:

- `spec_determinism/extract/narrow.py::narrow_points_to`
- `spec_determinism/schema_search/schemas.py` `TypeKind.POINTS_TO`
  branch
- `spec_determinism/codegen/gen_det.py` `TypeKind.POINTS_TO` equality
  branch

## #10 — `Set<T>` element probing assumes integer elements

**Status:** closed (fix landed in `ba18ca8`, 2026-05-12). `narrow_set` now
returns early after the length narrow when `elem_ty.kind not in
_INT_RANGE_KINDS`, mirroring the existing `narrow_map` guard. Empty /
non-empty / length witnesses are preserved; element-content discovery is
skipped for non-integer sets. Selftests added in `narrow.py::_run_self_tests`:
`Set<Foo>` (must NOT record any `.contains(...)` / `::empty().insert(...)`)
plus a `Set<u32>` control to catch element-kind-vs-length regressions.

**Symptom.** `narrow_set` works for integer sets, but it does not check
the element kind before trying to discover concrete elements. For a
non-integer set such as `Set<Foo>`, it can emit assumptions like:

```rust
s.contains(-8)
s == Set::<Foo>::empty().insert(-8)
```

Both are ill-typed because `contains` / `insert` expect a `Foo`, not an
integer.

**Root cause.** `_bisect_set_element` calls `_int_range(elem_ty)` for
all element types. `_int_range` treats any non-unsigned kind as signed
and returns `[-8, 8]`, so unknown/user-defined element types are probed
with integer literals. `narrow_map` already has the required guard
(`if k_ty.kind not in _INT_RANGE_KINDS: return`); `narrow_set` does not.

**Risk.** Non-integer sets may produce type-invalid templates or sort
mismatches when schema search binds a Z3 constant of element sort `Foo`
to a Python integer. At best the witness becomes partial; at worst the
target reports `search_error`.

**Fix idea.**

- In `narrow_set`, after length narrowing, return early unless
  `elem_ty.kind in _INT_RANGE_KINDS`.
- Keep empty / non-empty / length witnesses for non-integer sets, but do
  not emit `contains(k)` or set-literal assumptions.
- Add a unit test for `Set<Foo>` asserting no `contains(-8)` or
  `.insert(-8)` assumptions are produced.
- Future extension: add type-specific finite-domain probing for bool,
  C-like enums, and small literal domains.

Relevant files:

- `spec_determinism/extract/narrow.py::narrow_set`
- `spec_determinism/extract/narrow.py::_bisect_set_element`
- `spec_determinism/schema_search/schemas.py` `TypeKind.SET` branch
- `spec_determinism/extract/predicates.py::SetContainsPred` and
  `SetLiteralPred`

## #11 — `verusage_run --use-view-registry` default L4 cache path is wrong

**Status:** closed (fix landed in `0309567`, 2026-05-12). Canonical L4 path
now resolves from `Path(__file__).resolve().parents[2]` (the repo root,
`spec-determinism/`) instead of `.parent.parent` (the package dir,
`spec_determinism/`). Added an explicit WARNING log when
`--use-view-registry` is set but no cache is attached, listing every
checked path. Verified on this checkout: canonical resolves to
`spec-determinism/results-verusage/view_registry/atmosphere` (28 entries).

**Symptom.** Direct CLI usage of

```sh
python -m spec_determinism.corpus.verusage_run \
  --project ironkv --roots ... --out results-verusage-viewreg/ironkv \
  --use-view-registry
```

does not automatically attach the canonical L4 cache at
`results-verusage/view_registry/<project>`. The batch script avoids this
only because it passes `--view-cache-dir "$cache"` explicitly.

**Root cause.** The "canonical" path in `verusage_run.py` is computed
relative to the Python package directory:

```python
Path(__file__).resolve().parent.parent / "results-verusage" / "view_registry" / project
```

For this repository that resolves to
`spec_determinism/results-verusage/view_registry/<project>`, but the real
cache lives at repo root:
`spec-determinism/results-verusage/view_registry/<project>`.

**Risk.** A user can believe they are running with L4 cached views while
actually getting only L1/L2/L3 resolution and structural fallback. This
silently changes A-2 numbers and makes one-off reproductions disagree
with `scripts/rerun_corpus.sh`.

**Fix idea.**

- Compute the repo root as `Path(__file__).resolve().parents[2]` (or use
  a shared config/root helper) before appending `results-verusage/...`.
- Log a clear warning when `--use-view-registry` is set but no L4 cache
  is attached.
- Add a smoketest that creates a fake repo-root
  `results-verusage/view_registry/<project>` and checks that
  `verusage_run` attaches it without `--view-cache-dir`.

Relevant file:

- `spec_determinism/corpus/verusage_run.py`

## #12 — L4 view cache lookup ignores `source_hash` at codegen time

**Status:** open / design debt (found in code review 2026-05-12).

**Symptom.** `ViewCache.get(short_name, source_hash)` validates that a
cached L4 view was generated for the current type source, but the
codegen-time resolver cannot supply a hash and instead calls
`_get_any_for_short(short_name)`. That accepts any active cache file
whose `type_short` matches.

**Root cause.** `ViewRegistry.resolve(TypeExpr)` only receives a
type-expression head, not the `TypeDef` / source bytes for that head.
The implementation therefore does a permissive short-name lookup.

**Risk.**

- If a type changes after prefill, a stale `impl View` may still be
  injected.
- If two modules define the same short type name, the resolver may pick
  the wrong cache entry.
- The failure can be obvious (`verus_error`) or subtle if the stale view
  still compiles but no longer matches intended spec equality.

**Fix idea.**

- Thread enough type-definition metadata into `ViewRegistry.resolve` to
  compute/check the source hash for L4 hits.
- At minimum, reject cache entries whose `qualified_name` does not match
  the resolved `TypeDef` when that information is available.
- Log stale/mismatched hash misses as explicit L4 cache misses rather
  than silently accepting by short name.
- Add tests for "same short name, different qualified_name" and "source
  hash changed" cache entries.

Relevant files:

- `spec_determinism/view/registry.py::_resolve_l4`
- `spec_determinism/view/llm.py::ViewCache.get_any`
- `spec_determinism/view/llm.py::synthesize_view`

## #13 — verusage single-file targets are keyed only by function name

**Status:** open (found in code review 2026-05-12).

**Symptom.** `discover_exec_fns` returns a de-duplicated list of function
names, and `extract_spec(source, fn_name)` selects the first function
with that name. In a file with multiple impl blocks that each define
common method names such as `new`, `get`, `len`, or `clone`, later
methods are skipped or accidentally bound to the first same-named
function.

**Root cause.** The target identity is only `fn_name`; it does not
include an impl/type path, byte range, or fully qualified method path.
`_artifact_key` similarly uses only project + relative path + function
name, so same-file duplicate names would collide.

**Risk.** The verusage corpus may undercount targets, analyze the wrong
method body/spec, or overwrite artifacts for same-name methods. This is
especially likely in trait-heavy single-file corpora.

**Fix idea.**

- Change discovery to return a richer target descriptor:
  `(file_path, fn_name, byte_range, impl_self_type, optional module path)`.
- Teach `extract_spec` to accept a byte range or function node identity
  instead of only a name.
- Include the impl/type qualifier or byte offset in `_artifact_key`.
- Add a fixture with two impls both defining `fn new(...) ensures ...`
  and assert both targets are discovered and extracted separately.

Relevant files:

- `spec_determinism/verus/single_file.py::discover_exec_fns`
- `spec_determinism/extract/extractor.py::extract_spec`
- `spec_determinism/corpus/verusage_run.py::_artifact_key`


## #14 — `tuple_type` / `array_type` punted to UNKNOWN by the extractor

**Status:** closed by 377af18 (tuple) + ee57c7d (array) on 2026-05-12.

**Symptom.** Functions whose params / returns contain tuples or fixed-size
arrays produced uselessly weak witnesses. The headline case is
`memory-allocator::next_run(self: &CommitMask, idx: usize) -> (usize, usize)`
where `CommitMask = { mask: [usize; 8] }`. Pre-fix witness:

```
assumes: idx == 0; !det_next_run_equal(r1, r2)
```

The only schemas emitted were `g_idx_eq` / `g_idx_rng` (for the lone
scalar input) and `g_neq_tuple` (distinctness). `self` was a STRUCT and
`narrow_struct` recursed into `self_.mask`, but `[usize; 8]` was UNKNOWN
and the recursion dead-ended. `r1` / `r2` were UNKNOWN as
`(usize, usize)` and never decomposed. So the witness asserted "two
runs differ" without instantiating *which* state or *which* values.

**Root cause.** `extract/extractor.py::_parse_type_node` enumerated
`primitive_type` / `unit_type` / `type_identifier` / `generic_type` /
`scoped_type_identifier` / `reference_type` and punted everything else
to `TypeInfo(kind=UNKNOWN, name=…)`. tree-sitter-verus emits dedicated
`tuple_type` and `array_type` nodes that were silently dropped to the
fallback.

`type_registry.py` already models tuples (`TypeExpr(kind="tuple", args=[…])`)
because the view subsystem needs it — but the extract pipeline never
imported it, so the global type tree's tuple awareness was unused on
the witness side.

**Fix.**

1. *Tuple* (377af18): added a `tuple_type` branch that produces
   `TypeInfo(kind=STRUCT, name="(T1, T2, …)", fields=[FieldInfo("0", T1),
   FieldInfo("1", T2), …])`. Rust/Verus's positional `t.0` / `t.1`
   syntax matches `narrow_struct`'s `f"{accessor}.{fld.name}"`
   construction exactly, so the existing struct strategy, the STRUCT
   branch of `schemas._emit`, and gen_det's STRUCT equality builder
   all decompose tuples correctly with zero downstream changes. Empty
   tuples `()` continue to map to `TypeKind.UNIT`.

2. *Array* (ee57c7d): added an `array_type` branch that produces
   `TypeInfo(kind=SEQ, name="[T; N]", type_args=[T])`. Verus accepts
   `arr.len()` / `arr[i]` directly in spec contexts (verified against
   verusage `memory-allocator/commit_mask/*.rs`, which uses
   `self.mask[i]` freely in ensures / invariant / forall), and these
   match `narrow_seq`'s accessors. tree-sitter's `integer_literal`
   size child is intentionally dropped — schema search rediscovers the
   static size N via the length probe (`arr.len() == 8` sticks; the
   smaller probes fail).

**Validation.** After both commits, `memory-allocator::next_run` runs
with 29 schemas (was 3) and 108 rounds (was 8), yielding 15 strong
assumes:

```
self_.mask.len() == 8
self_.mask[0..7] == 0          # full bitmap state pinned
idx == 0
r1.0 == 0; r1.1 == 0           # r1 = (0, 0)
r2.0 == 0; r2.1 == 1           # r2 = (0, 1)
!det_next_run_equal(r1, r2)
```

i.e. on `next_run(CommitMask{mask:[0;8]}, 0)` the spec admits both
`(0, 0)` and `(0, 1)` — a textbook nondeterminism, with both the
state and both return tuples concretely instantiated.

Full memory-allocator re-run after the fix: 15 ok / 1 verus_error
(unchanged from baseline; the pre-existing `Ghost<PageId>`
param-name extraction bug at `calculate_page_block_at`, unrelated).

**Selftests.** `python -m spec_determinism.extract.narrow test` —
added a tuple-as-STRUCT case (`r1.0` and `r1.1` recursion) and an
array-as-SEQ case (`self_.mask.len()` + `self_.mask[0]` recursion);
both pass.

Relevant files:

- `spec_determinism/extract/extractor.py::_parse_type_node`
- `spec_determinism/extract/narrow.py` (selftests only)
- `docs/incompleteness-examples.md` (example 1 witness regenerated)

