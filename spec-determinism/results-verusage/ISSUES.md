# Verusage Run — Outstanding Issues

Snapshot of every category of non-`deterministic` outcome observed in the
verusage batch. Each entry records the symptom, root cause, intended fix,
and what currently blocks the fix.

**Update 2026-05-08.** B-1 (`dd602c3`) and B-6 (`2f311af`) have shipped;
their entries are now annotated with the actual fix and outcome. B-5 was
investigated and reclassified as "non-target source contamination in the
inject pipeline" rather than a missing deref in equal-fn synthesis — see
its section for the corrected analysis. Numbers in the per-project table
below are the *original baseline* (commit `eed6038`); the `current` table
that follows shows the post-`42c1248` numbers.

Original baseline (1647 targets across 9 projects):

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

Current (after B-1 + B-6, commit `42c1248`):

| project | n | ok | ok-with-witness | verus_error |
|---|---:|---:|---:|---:|
| atmosphere | 1363 | 1262 | 289 | 100 |
| ironkv | 214 | 170 | 76 | 44 |
| memory-allocator | 16 | 15 | 9 | 1 |
| nrkernel | 8 | 6 | 1 | 2 |
| vest | 2 | 2 | 1 | 0 |
| storage | 43 | 0 | 0 | 43 |
| **total (covered projects)** | **1646** | **1455** | **376** | **190** |

Net change so far: **+210 ok, −210 verus_error**.

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

### B-1. `E0284`/`E0283` "type annotations needed" — 200 (173 atmo + 27 ironkv) — **fixed (`dd602c3`)**

**Symptom.** Synthesized determinism-check function fails Rust type
inference at the call site of the equal-fn:

```
det_len_equal::<???, ???>(r1, r2)
```

**Root cause.** Direct fallout from commit `168b071` (generic-lift
fix). That fix copies the entire enclosing `impl<T, const N: usize>`
generic list onto the synthesized equal-fn, but the equal-fn's
parameter list and return type may not textually reference any of
those generics — they become phantom and Rust cannot infer them.

**Fix.** `_prune_generics` in `gen_det.py` synthesizes a probe
`fn __probe<generics>(sig) where ... {}`, parses it with
tree-sitter-verus, walks the `type_parameters` and `where_clause`
subtrees, and:

  - keeps only the generics whose names appear textually inside
    the equal-fn parameters or return type;
  - applies a fixed-point closure over `where_predicate` nodes so a
    predicate that overlaps the kept set keeps the predicate AND
    pulls in its other referenced generics;
  - skips inner `type_parameters` subtrees so HRTB `for<'a>`
    binders do not leak as outer-scope references;
  - falls back to inputs unchanged on parse failure.

Wired into both the proof-fn template (`_build_template`) and the
spec-fn equal (`_build_equal_fn`); pruning runs after Self-
substitution so e.g. `Self → Foo<T>` correctly registers `T` as
referenced.

**Result.** atmosphere E0284 173 → 0; ironkv E0283 26 → 0;
"type annotations needed" 200 → 0. No regressions on
memory-allocator / nrkernel / vest. Total verus_error 400 → 203
after this fix alone.


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

### B-5. "Dereference this mutable reference …" — 18 (16 atmosphere + 2 ironkv)

**Symptom.** Verus rejects the comparison
```
error: Dereference this mutable reference to compare the value via Verus spec equality.
   |
   |    self == src,
   |    ^^^^
``
inside an injected source file.

**Initial hypothesis (wrong).** Equal-fn synthesis compares `&mut T`
parameters with `==` and forgets to deref.

**Actual root cause (verified 2026-04-29).** The error is **not in
spec-determinism's synthesized code**. It originates in *non-target*
functions that happen to live in the same source file as the target.
Two concrete examples:

  - `atmosphere/.../run_blocked_thread.rs:940` —
    ```
    #[verifier::external_body]
    pub fn set_self_fast(&mut self, src: &Registers)
        ensures self == src,
    ```
    Targets `len`, `get_head`, `get_container`, … fail because the
    injected file pulls in `set_self_fast`'s ensures clause and the
    current Verus version refuses the `&mut Self == &Self` comparison.

  - `ironkv/.../truncate.rs:311` — a `while` loop invariant
    `self == old(self),` written for a permissive Verus version, now
    rejected by the current toolchain.

The targets being checked (`len`, `to_vec`, `valid_physical_address`,
…) do not themselves contain the problematic comparison. They only
fail because the inject pipeline copies the entire surrounding source
into the temp crate.

**Why not "just deref in equal-fn".** The text inside the offending
ensures / invariant comes verbatim from the user's source, so adding
deref logic to equal-fn synthesis cannot reach it. This is also why
B-5 was originally tagged "trivial, < 1 hour" — the misdiagnosis hid
the real scope.

**Possible fixes (none implemented).**

  - **A. AST source-patch in inject pipeline.** Walk the injected
    source with tree-sitter, find `binary_expression` `==` nodes
    whose operands are `self` / `old(self)` / a `&mut`-typed local,
    and rewrite them to `*lhs == *rhs`. ~50-80 lines, low risk
    because spec equality on references and on derefs is equivalent
    in Verus. Estimated yield ≈ −18 verus errors.

  - **B. Minimal inject.** Restructure the inject pipeline so it
    drops every function in the source file *except* the target plus
    its closure of statically referenced spec definitions / type
    declarations. Larger change (dependency analysis, attribute
    handling, `#[verifier::external_body]` stubs) but eliminates
    whole classes of "neighbouring code is incompatible" failures.

  - **C. Block-list the affected source files.** Cheapest; sacrifices
    determinism coverage for the 18 affected targets.

**Decision (2026-05-08).** Deferred. The 18 affected targets are
left as `verus_error` in the corpus until B-5 is revisited. When we
return to it, prefer option A unless the same week we are already
reworking inject for another reason (then bundle into option B).


### B-6. Field accesses corrupted by ensures rename — 13 (10 atmosphere E0609 + 3 ironkv E0599) — **fixed (`2f311af`)**

**Symptom.** Verus errors of the form
```
error[E0609]: no field `r1` on type `Node<T>`
   |
   |    &&& (r1 == self_.arr_seq@[index as int].r1)
                                                ^^ unknown field
```
and the symmetric "method `r1` not found".

**Initial hypothesis (wrong).** atmosphere's IPC `Node<T>` struct has
a real field named `r1` colliding with our synthesized return
variable.

**Actual root cause.** The original function was named with a
result-binding identifier (e.g., `next` in `fn get_next(...) ->
(next: SLLIndex)`) and its ensures referenced both the binding *and*
a struct field of the same spelling, e.g.
`next == self.arr_seq@[i].next`. Our pre-fix `_substitute_run` used
`re.sub(r'\bnext\b', 'r1', ...)`, which has no notion of context, so
the field access `.next` on the right was rewritten to `.r1`.
ironkv exposed the method-call variant
(`self@.len()` → `self_@.r1()`) when the binding was `len`.

**Fix.** Replaced the per-rename regex pipeline with an AST-aware
helper `_rename_idents_in_expr(text, name_map)` that:

  - wraps the ensures fragment in a probe `proof fn __probe()
    ensures EXPR, {}` and reuses the existing tree-sitter-verus
    parser (829/829 real ensures clauses parse cleanly);
  - walks `identifier` and `self` leaves only — `field_identifier`
    and `arrow_expression` field tags are different node types and
    are naturally skipped;
  - prunes `scoped_identifier` subtrees so `Foo::next` is left
    alone;
  - applies all collected edits in one pass over the byte buffer,
    avoiding cascading renames when one rename target appears in
    another's domain.

15 unit tests cover field access, paths, arrow-variant access,
quantifier inner expressions, view (`@`), nested fields, multi-name
maps, and empty inputs.

**Result.** atmosphere E0609 10 → 0; ironkv E0599 3 → 0; 0
behavioural changes elsewhere apart from the desired corrections (a
diff sweep across 2256 substitution outputs surfaced 4 differences,
all of them fixes for the same bug class).


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

Updated 2026-05-08 after the B-1, B-6, and B-5 investigations.

| # | item | status | impact | est. effort |
|---|---|---|---|---|
| ✅ | B-1 drop phantom generics from equal-fn | **shipped (`dd602c3`)** | −199 verus_err (atmosphere E0284 173, ironkv E0283 26, plus tail) | done |
| ✅ | B-6 AST-aware ensures rename | **shipped (`2f311af`)** | −13 verus_err (atmosphere E0609 10, ironkv E0599 3) | done |
| 1 | A-2 + B-3 view-aware equal-fn | open | ~−290 false witnesses, −13 verus_err | 1–2 days (policy design) |
| 2 | A-1 narrow strategies for Tracked/Ghost/PointsTo + newtype unwrap | open | makes the 29 real-incompleteness witnesses readable | ~1 day |
| 3 | B-4 E0308 type mismatch in equal-fn calls | open — needs case study | ~−32 verus_err | unknown |
| 4 | B-2 parser errors triage | open | up to −65 verus_err | unknown — depends on sub-cause split |
| 5 | A-3 nested-Err equivalence | open | ~−30 false witnesses | < 1 hour |
| 6 | A-4 lemma-as-axiom injection | open | ~−30 false witnesses | larger design |
| ⏸ | B-5 deref `&mut`/`&` (was 15, actually 18) | **deferred** — see B-5 section above; root cause is non-target source code copied into inject, not equal-fn synthesis | −18 verus_err | medium (option A: 50-80-line AST source-patch in inject pipeline) |
| ⏸ | B-7 storage `deps_hack` | deferred | −43 verus_err | high (vendor stub) |
| ⏸ | B-8 / B-9 / B-10 long tail | deferred | ~−25 verus_err total | varies; lowest priority |

