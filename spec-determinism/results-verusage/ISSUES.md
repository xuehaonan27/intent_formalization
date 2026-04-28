# Verusage Run — Outstanding Issues

Snapshot of every category of non-`deterministic` outcome observed in the
verusage batch (commit `eed6038`, 1647 targets across 9 projects). Each
entry records the symptom, root cause, intended fix, and what currently
blocks the fix.

Final batch totals:

| project | n | ok | witness | deterministic | verus_error |
|---|---:|---:|---:|---:|---:|
| anvil-controller | 0 | 0 | 0 | 0 | 0 |
| anvil-library | 1 | 0 | 0 | 0 | 1 |
| atmosphere | 1363 | 1082 | 289 | 793 | 280 |
| ironkv | 214 | 140 | 67 | 73 | 74 |
| memory-allocator | 16 | 15 | 9 | 6 | 1 |
| node-replication | 0 | 0 | 0 | 0 | 0 |
| nrkernel | 8 | 6 | 1 | 5 | 2 |
| storage | 43 | 0 | 0 | 0 | 43 |
| vest | 2 | 2 | 1 | 1 | 0 |
| **total** | **1647** | **1245** | **367** | **878** | **401** |

Issues are split into two top-level groups: **A. Witness-class** (the
schema search completed but a separating witness remained) and
**B. Verus-error class** (the synthesized determinism check failed to
type-check or verify before any search could run).

---

## A. Witness-class — 367 cases

### A-1. Real incompleteness with unreadable ghost witness — 29 (~8%)

**Symptom.** Postcondition genuinely admits multiple post-states; the
schema solver correctly produces a witness but the `assumes` list is
limited to primitive inputs. Ghost-typed post-state values appear only
in the final fall-through assertion `!det_X_equal(...)`.

**Examples.** `atmosphere::alloc_page_4k` (ensures only fixes the
symmetric difference of `free_pages_4k` / `allocated_pages_4k`),
`atmosphere::new_proc_with_endpoint` (frame condition `forall|p_ptr|
old(self).proc_dom().contains(p_ptr) ==> ...` excludes the freshly
allocated `page_ptr_1`, leaving five fields of the new proc
unconstrained), `ironkv::parse_command_line_configuration`
(disjunction over `Result` outcomes).

**Root cause.** `narrow.py` has no strategy for `Tracked<T>`,
`Ghost<T>`, or `PointsTo<V>`; these arrive at the dispatcher as
`TypeKind.UNKNOWN` with names like `Tracked<Map<...>>`, fall through
`narrow_unknown`, find no registered projections, and emit only a
warning. `narrow_map` *exists* but degrades to "length only" when the
key kind is not in `_INT_RANGE_KINDS`; `ProcPtr` / `ContainerPtr` /
`ThreadPtr` (newtypes around `usize`) are reported as `UNKNOWN`.

**Intended fix.**
1. Type extractor: recognize vstd `Tracked<T>`, `Ghost<T>`,
   `PointsTo<V>` (including fully-qualified paths) and emit dedicated
   `TypeKind.TRACKED` / `GHOST` / `POINTS_TO` with `type_args` populated.
2. `narrow.py`: add three projection-style strategies — `Tracked<T>`
   recurses on `t@`, `Ghost<T>` on `t@`, `PointsTo<V>` on
   `pt.is_init()`, `pt.value()`, and `pt.addr()`.
3. Type extractor: unwrap newtype-of-`usize` (e.g.,
   `pub struct ProcPtr(usize);`) to `TypeKind.USIZE` so `narrow_map`
   can bisect concrete keys instead of degrading.

**Blocker.** None — pure implementation work.

### A-2. Equal-fn over-comparison — ~280 of 338 suspect cases

**Symptom.** Ensures clause uniquely determines the public/observable
state via a `forall|i| self.@[i] = ...` view-style invariant, but a
witness still appears.

**Examples.** `set_ref_count`, `set_state`, `pop` — all have ensures
that pin every observable field through `self@`/`view()` yet still
report a separating witness.

**Root cause.** Synthesized equal-fn compares the concrete `self`
struct field by field. Private fields not mentioned in the ensures
(implementation details inside the view) become free under the
ensures and the equal-fn flags them as different.

**Intended fix.** View-aware equal-fn: when a type has a `view()` /
`@` projection, generate `a@ == b@` instead of structural field
equality.

**Blocker.** Policy design. Need to decide: default-on, opt-in per
type, or driven by a `#[verifier(view)]` / similar attribute?
Default-on is appealing but risks under-checking when the user does
care about a private field difference.

### A-3. Equality policy too strict on nested `Result` / `Option` — ~30

**Symptom.** Ensures treats "any `Err`" as acceptable (e.g.,
`res.is_err() ==> ...`), but the equal-fn structurally compares the
inner `Err` payloads.

**Root cause.** `equal_policy.errs_equivalent=True` only collapses
the top-level `Result` constructor; nested `Result<T, E>` inside
container types still uses structural equality.

**Intended fix.** Recurse `errs_equivalent` into nested `Result`
positions during equal-fn synthesis.

**Blocker.** Trivial implementation. Care needed not to flatten
cases where the user *does* care which `Err` was returned.

### A-4. Spec carried by lemmas, not ensures — ~30

**Symptom.** Ensures clause is intentionally weak; the real behavioral
specification lives in companion `proof fn lemma_*` statements that
the caller invokes.

**Root cause.** The schema search injects only the function's own
`requires` and `ensures`. Companion lemmas (and module-level
invariants) are out of scope.

**Intended fix.** Either (a) inject relevant invariant lemmas as
axioms, or (b) use an LLM hook to extract additional ensures from
nearby lemmas.

**Blocker.** Lemmas have applicability conditions that are not
trivially syntactic; injecting unconditionally would unsoundly
strengthen ensures. Needs a deliberate design pass.

### A-5. Witness summary

| sub-class | count | repair scope |
|---|---:|---|
| A-1 real, unreadable ghost | 29 | narrow strategies + extractor |
| A-2 view over-comparison | ~280 | equal-fn policy redesign |
| A-3 nested-Err strictness | ~30 | equal-fn small fix |
| A-4 lemma-shaped spec | ~30 | larger design |

---

## B. Verus-error class — 401 cases

### B-1. `E0284`/`E0283` "type annotations needed" — 199 (173 atmo + 26 ironkv)

**Symptom.** Synthesized determinism-check function fails Rust type
inference at the call site of the equal-fn:

```
det_len_equal::<???, ???>(r1, r2)
```

**Root cause.** Direct fallout from commit `168b071` (generic-lift
fix). The fix copies the entire enclosing `impl<T, const N: usize>`
generic list onto the synthesized equal-fn, but the equal-fn's
parameter list and return type may not textually reference any of
those generics — they become phantom and Rust cannot infer them.

**Intended fix.** Drop unused generics: retain only the generic
parameters whose names appear textually inside the equal-fn signature
(parameters or return); prune `where` clauses that reference only
dropped generics.

**Blocker.** None — straightforward textual filter on the lifted
generics. Highest-ROI fix in the table.

### B-2. Parser errors in injected.rs — ~65 (38+11+10+4+1+1)

**Symptom.** A grab-bag of "expected one of …", "expected `,`", and
"expected `!` or `::`" errors emitted by rustc on the synthesized
file before Verus even runs.

**Root cause.** Multiple sub-causes, not yet individually triaged:
malformed ensures concatenation (missing separators), bad type
annotation positions, possible mishandling of macro-style ensures.

**Intended fix.** Sample one representative per error message,
identify each sub-cause, fix in synthesis.

**Blocker.** Diagnosis work — no single root cause yet.

### B-3. `field expression for an opaque datatype` — 13 ironkv

**Symptom.** Equal-fn body reads `.field` on a Verus-opaque type,
which Verus rejects.

**Root cause.** Same shape as A-2: structural field equality is
generated even for opaque types. memory-allocator was patched
indirectly when we reverted the `pub open spec fn` change in
`eed6038`, but the underlying issue (no view-aware fallback) remains
in ironkv.

**Intended fix.** Same as A-2 — when the type is opaque (or has a
public `view()`), compare via `a@ == b@`.

**Blocker.** Same as A-2 — needs an opacity / view-eligibility
policy. Detecting opacity may need to read `#[verifier::opaque]`
attribute or fall back to "if type has a public `view`, use it".

### B-4. `E0308 mismatched types` — 27 (23+4)

**Symptom.** Argument types at the equal-fn call site do not match
its declared parameter types.

**Root cause.** Most likely a downstream effect of B-1 — once Rust
gives up on inferring the phantom generics, it falls back to default
types that disagree with the signature.

**Intended fix.** Re-run after B-1 to confirm; remaining cases get
individual diagnosis.

**Blocker.** Depends on B-1.

### B-5. "Dereference this mutable reference …" — 15 (13+2)

**Symptom.** Equal-fn compares values of type `&mut T` (or `&T`)
with `==`; Verus requires `*x == *y` for these.

**Root cause.** equal-fn synthesis does not deref reference-typed
parameters before comparing.

**Intended fix.** When emitting structural equality for `&T` /
`&mut T` arguments, deref both sides.

**Blocker.** Trivial.

### B-6. `no field r1 on type Node<T>` (`E0609`) — 10 atmosphere

**Symptom.** atmosphere's IPC `Node<T>` struct has a real field
named `r1` (an x86-64 register-name reuse). Our synthesized
return-value variable `r1` shadows / collides with code that reads
`node.r1`.

**Intended fix.** Rename synthesized return variables to a
collision-resistant name (e.g., `__det_r1`, `__det_r2`). Sweep all
emitter sites.

**Blocker.** Trivial.

### B-7. `unresolved import deps_hack` / `cannot find type Self` — 29 storage

**Symptom.** Every storage target fails to compile because it
imports `deps_hack`, an external linker shim provided by storage's
build.rs.

**Root cause.** Our verusage runner compiles each function's
extracted file in isolation; it does not vendor or stub
`deps_hack`.

**Intended fix.** Either vendor a stub for `deps_hack`, or carve
the storage project out of the verusage corpus.

**Blocker.** Low ROI — storage is one project of nine and the work
to stub `deps_hack` may be substantial. Recommend skipping unless
storage becomes a priority.

### B-8. "function pointer types" not supported — 9 ironkv

**Symptom.** Verus rejects `fn(...)` pointer types.

**Root cause.** Verus tool limitation, not a bug in
spec-determinism.

**Intended fix.** Skip these targets at extraction time.

**Blocker.** None — apply a precondition filter.

### B-9. `rlimit` exceeded — 7 atmosphere

**Symptom.** Verus z3 query exceeds the configured resource limit.

**Intended fix.** Re-run failures with a higher rlimit, or reduce
schema complexity for these specific targets.

**Blocker.** None; deferred until higher-ROI items are done.

### B-10. `repr(transparent)` zero-sized field error — 2 nrkernel

**Symptom.** Extractor produces a struct that Verus rejects because
of a `repr(transparent)` field with a private, externally-defined
inner type.

**Root cause.** Extractor copies the type definition without
preserving the necessary `external_body` annotations.

**Intended fix.** Mark the offending struct as `external_body` (or
skip extraction) when the original definition has a private inner
type.

**Blocker.** Small but needs reproducer triage.

---

## C. Project-level non-issues

- **anvil-controller, node-replication** — n=0 by design. Both are
  TLA-style temporal-logic proof libraries containing only
  `proof fn lemma_*<T>(...)` and `fn main() {}`. No `exec fn` exists
  for spec-determinism to analyze.

- **anvil-library** — n=1 / err=1 due to a vstd version mismatch
  (`lemma_seq_properties` was renamed `group_seq_properties` in
  newer vstd). This is a corpus-vs-stdlib drift, not a tool bug.

---

## Priority and ROI

| # | item | impact | est. effort |
|---|---|---|---|
| 1 | B-1 drop phantom generics from equal-fn | −199 verus_err (and likely most of B-4's 27) | < 1 hour |
| 2 | A-2 + B-3 view-aware equal-fn | ~−290 false witnesses, −13 verus_err | 1–2 days (policy design) |
| 3 | A-1 narrow strategies for Tracked/Ghost/PointsTo + newtype unwrap | makes the 29 real-incompleteness witnesses readable | ~1 day |
| 4 | B-5 deref `&mut`/`&` in equal-fn | −15 verus_err | < 1 hour |
| 5 | B-6 rename synthesized `r1`/`r2` | −10 verus_err | < 1 hour |
| 6 | B-2 parser errors triage | up to −65 verus_err | unknown — depends on sub-cause split |
| 7 | A-3 nested-Err equivalence | ~−30 false witnesses | < 1 hour |
| 8 | A-4 lemma-as-axiom injection | ~−30 false witnesses | larger design |
| 9 | B-8 / B-9 / B-10 / B-7 (long tail) | ~−50 verus_err total | varies; lowest priority |
