# Phase 2 Arc: View Registry → PR-G

> **Goal**: Phase 2 milestone summary for spec-determinism (axis-2
> false-positive reduction + axis-1 / axis-3 error reduction). Slides
> material.
> **Covers**: late April 2026 through 2026-05-12, from the `type_registry`
> SCC tooling through PR-G landing.
> **Out of scope**: Phase 1 (single-file Verus invoke, the prototype
> equal-fn, `EqualPolicy` defaults).

---

## 1. Problem statement

### 1.1 What we are building

Automatic **determinism checking** for every public function in a Verus
project — "given the same inputs, the function always produces
spec-equivalent outputs".

Input: Verus source + `requires/ensures` annotations
Output: a `status` per function — one of
`{ok, ok_with_witness, verus_error, runner_crash}`

```
ok               function is provably deterministic (z3 unsat, no
                 counterexample)
ok_with_witness  z3 finds a spec-level counterexample, but Verus still
                 accepts the equal-fn
verus_error      the generated equal-fn does not type-check under Verus
runner_crash     internal pipeline failure
```

Ideal distribution: **many `ok`, few `witness`, few `verus_error`**.

### 1.2 Three optimisation axes

| Axis | Meaning | Failure shape |
|---|---|---|
| **A-1** | equal-fn narrowing is too coarse | `verus_error`: z3 cannot narrow on the dimensions the spec mentions |
| **A-2** | equal-fn is too strict | `ok_with_witness` (false positive): two semantically-equivalent runs are treated as unequal |
| **A-3** | equal-fn has the wrong semantics | `verus_error`: `Err` payloads inside nested containers should collapse but do not |

Phase 1 baseline (commit `42c1248`, n=1647 across 7 projects):

```
ok               1455   ← push this up
ok_with_witness   376   ← A-2 battleground
verus_error       191   ← A-1 + A-3 battleground
runner_crash        1
```

### 1.3 Concrete examples per axis

**Framing — spec-determinism is an incompleteness detector, not a prover**

spec-determinism **auto-generates an `eq(r1, r2)` function for every target**
and asks Verus + z3 to check whether `eq(r1, r2)` holds under the function's
`ensures`.

**Key invariant**: the equal-fn is **fully determined by the return type**
(plus configurable policies, e.g. PR-G's errs-equivalent). It **never** adapts
to whatever the `ensures` happens to say. So the verdict means:

| verdict | meaning |
|---|---|
| `ok` | the `ensures` is tight enough to imply spec-level determinism |
| `ok_with_witness` | the `ensures` is too loose — the tool produced a spec-meaningful counterexample (→ user should tighten) |
| `verus_error` / `runner_crash` | **the tool is broken** for this target, verdict carries no signal |

The goal of PR-F / PR-G is **not** "make more functions look complete". It is:

1. Promote "tool broken" states (`verus_error`) into "tool works + real signal" (`ok` / `ok_with_witness`)
2. Where the `ensures` happens to be tight, let z3 chain through to `ok`
3. Turn spurious witnesses (caused by byte-level noise — the A-2 axis) into meaningful witnesses or `ok`

The six examples below illustrate the three kinds of flip.

#### A-1 example 1 — `Ghost<Seq<u32>>` output (atmosphere shape)

```rust
// source
fn build_log() -> (r: Ghost<Seq<u32>>)
    ensures r@.len() == 5
```

The `ensures` **deliberately pins only the length, not the contents** — this
is the common shape in real atmosphere code.

| | generated equal-fn (**type-determined**) | Verus + z3 reasoning | verdict |
|---|---|---|---|
| pre-PR-F | `r1 == r2` (Ghost not recognised → UNKNOWN fallback) | Verus rejects structural `==` on the Ghost wrapper (or z3 treats Ghost as an opaque sort and produces a vacuous SAT) | **verus_error** — tool broken, verdict carries **no spec signal** |
| post-PR-F | `((r1)@ == (r2)@)` (GHOST branch: strip the wrapper) | Verus accepts (`Seq` is a spec type); z3 narrow adds `_leneq` / `_lenrng`; `ensures` gives `r1@.len()==5` and `r2@.len()==5` but elements are free → z3 finds a legitimate witness `r1@=seq![0;5]`, `r2@=seq![1;5]` | **ok_with_witness** — tool works, verdict is a **real signal**: the spec doesn't pin element values, the user should add `forall\|i\| r@[i] == …` |

**The PR-F win here**: the verdict flips from "tool broken" to "tool working +
genuine incompleteness signal". If the user later tightens `ensures` to
`r@ == state.log@`, the verdict will further flip to `ok` (z3 chains via
transitivity) — but that's the user's job, not PR-F's.

#### A-1 example 2 — `Tracked<PointsTo<u32>>` output (storage shape)

```rust
// source
fn split_cell(pt: Tracked<PointsTo<u32>>) -> (r: Tracked<PointsTo<u32>>)
    ensures r@.is_init() == pt@.is_init(),
            r@.addr() == pt@.addr()
```

| | generated equal-fn | outcome |
|---|---|---|
| pre-PR-F | `r1 == r2` — `Tracked` is an `external_body` newtype, structural `==` is unprovable in Verus spec mode | **verus_error** |
| post-PR-F | `(r1)@.is_init() == (r2)@.is_init() && (r1)@.addr() == (r2)@.addr() && ((r1)@.is_init() ==> (r1)@.value() == (r2)@.value())` | **ok** |

#### A-2 example 1 — struct field is `Vec<u8>`

```rust
// source
pub struct AbstractEndPoint { pub id: Vec<u8> }

fn make_endpoint(bytes: Vec<u8>) -> (r: AbstractEndPoint)
    ensures r.id@ == bytes@
```

| | generated equal-fn | z3 counterexample | outcome |
|---|---|---|---|
| no view-registry | `r1 == r2` — `Vec` structural `==` compares ptr/capacity/len; z3 can produce "two Vecs with the same logical bytes but different `cap`" | `r1.cap=8, r2.cap=16, contents equal to bytes@` | **ok_with_witness** (false positive) |
| L4-synth view | `r1.view() == r2.view()` where `view()` projects to `Seq<u8>` | (unsat — `Seq` is a mathematical sequence) | **ok** |

#### A-2 example 2 — enum + self-recursive struct

```rust
// source
pub enum NodeEntry { Leaf(usize), Subdir(Box<PTDir>) }
pub struct PTDir { pub entries: Seq<Option<PTDir>> }

fn modify_tree(t: PTDir, k: usize) -> (r: PTDir)
    ensures r.entries.len() == t.entries.len()
```

| | generated equal-fn | outcome |
|---|---|---|
| no view-registry | recurses into `Subdir`'s `Box<PTDir>` — Verus spec mode cannot deref `Box`, falls back to `==` on the box pointer | **ok_with_witness** (pointer-identity false positive) |
| L4-synth view + PR-E M4 lint | LLM picks Option C: `type V = Self` for `PTDir` → `r1.view() == r2.view()` degenerates to `r1 == r2` but **at the spec layer** (box noise stripped) | **ok** |

#### A-3 example 1 — `Seq<Result<u32, MyErr>>` output

```rust
// source
fn batch_lookup(keys: Vec<u32>) -> (r: Seq<Result<u32, MyErr>>)
    ensures r.len() == keys.len()

// assume the policy says errs_equivalent=True (all Err variants are equivalent)
```

| | generated equal-fn | z3 input | outcome |
|---|---|---|---|
| pre-PR-G | `r1 == r2` — `Seq` was in the primitive `==` list | `r1 = [Err(Foo("a"))]`, `r2 = [Err(Foo("b"))]` — different payloads | `r1 == r2` is false → **verus_error** (policy never fires) |
| post-PR-G | `r1.len() == r2.len() && forall\|i: int\| 0 <= i < r1.len() ==> ((r1[i] is Ok) == (r2[i] is Ok)) && ((r1[i] is Ok) ==> (r1[i]->Ok_0 == r2[i]->Ok_0))` | same | both elements have `Err` discriminator, Ok branch is vacuous → **ok** |

#### A-3 example 2 — `Map<Key, Result<Val, Err>>` field

```rust
// source
pub struct ResultCache { pub entries: Map<Key, Result<Val, CacheErr>> }

fn populate(keys: Set<Key>) -> (r: ResultCache)
    ensures r.entries.dom() == keys
```

| | generated equal-fn fragment | outcome |
|---|---|---|
| pre-PR-G | `r1.entries == r2.entries` — `Map` fell through to UNKNOWN's `==` fallback | two `Err` payloads differ → false → **verus_error** |
| post-PR-G | `r1.entries.dom() == r2.entries.dom() && forall\|k: Key\| r1.entries.dom().contains(k) ==> ((r1.entries[k] is Ok) == (r2.entries[k] is Ok)) && ((r1.entries[k] is Ok) ==> (...))` | `dom()` pinned by ensures, Err branch collapses → **ok** |

---

## 2. The approach: View Registry

### 2.1 Core idea

In Verus, `impl View for T` is a trait that projects a runtime struct
to a spec struct. If every type has a `View`, the generated equal-fn
can use:

```rust
fn equal_fn(r1: T, r2: T) -> bool {
    r1.view() == r2.view()    // compare at spec level — bypass Vec/byte-level noise
}
```

Z3 reasons only at the spec level → fewer witnesses (A-2) and more
narrow-able dimensions (A-1).

### 2.2 Where do Views come from — the 4-layer resolver (L1–L4)

| Layer | Source | Examples |
|---|---|---|
| **L1** | Verus prelude (hand-coded) | `Vec → Seq`, `HashMap → Map` |
| **L2** | Type alias unfolding | `Pcid = usize` → transparent |
| **L3** | Existing `impl View for T` in the project sources | scan atmosphere's ~50 pre-existing impls |
| **L4** | **LLM-synthesised** (Copilot CLI) | types nobody wrote a View for — let the model draft one |

L1+L2+L3 are mechanical; L4 is the new thing, off-loading the
"remaining work" of spec engineering onto a model.

---

## 3. Build sequence (commit timeline)

```
view/ subpackage scaffolding         8dc1c20  2026-04-30
L3 scan                              5ea750b  → per-project audit
L1+L2+L3 resolver                    b65d37f  PR-B
gen_det threading registry           5a67804  PR-C
L4 LLM synth (offline)               f094843  PR-D1
L4 cache wired into gen_det          1f7a245  PR-D2
cross-subpackage refactor            226d93f  → 1751dc1 fixed import bug
LLM backend extracted                ab5f5d6  → shared with codegen/policy_llm
codex critic pass                    f47125f  → post-synth check
prefill batch driver                 aaa4059
critic_reject status code            aa0744e
wait-for-prefill chain               7531eeb  scripts/auto_chain.sh
M1/M2/M3 lint sketch                 ad691cd  static lint: "view body must reference self"
quarantined 14 broken views          a71ff15  + M1/M2/M3 detector specs
PR-D4 final                          4cd29b4  11 wins / 0 regress / -10 witness
PR-D5: M1/M2/M3 impl                 e61a504  retroactive scan → +4 quarantines
PR-E: M4 + self-recursive prompt     513d8d9
PR-F + PR-G                          4eb7376  Tracked/Ghost/PointsTo + nested Err
```

---

## 4. The four most recent PRs (Phase 2 close-out)

### 4.1 PR-D5 — M1/M2/M3 lint implementation

**Problem**: L4 LLM-synth views occasionally have **silent** bugs —
e.g. `field@` projecting through a type with no `View` impl. Verus
either rejects later or, worse, silently accepts a bad spec.

**Fix**: three tree-sitter static lints, applied at L4 cache time:

| Rule | What it rejects |
|---|---|
| **M1** | `field@` or `<Inner as View>::V` on a type with **no registered View** |
| **M2** | `field@@` over-projecting past `Ghost<…>` into `Set`/`Map`/etc. |
| **M3** | view body uses `self.<field>` while parent is `external_body` / opaque |

**Key deviations discovered during implementation**:

- M2 only fires on `FnSpec`-headed inner types; other cases turned out
  to be legitimate recursion
- M3 has a "unit-V" exemption (`type V = ()`)
- M1 honours `impl<G>` generic params — `T@` on a generic `T` is fine

**Retroactive scan**: ran the lints against **all** cached views,
including ones that had not been quarantined → caught 4 hidden bugs
of the same shape, added them to quarantine. Defence in depth.

---

### 4.2 PR-E — M4 lint + recursive-view prompt guidance

**Pivot**: the original PR-E plan was "whole-SCC prompts" (feed an
entire strongly-connected component of types to the LLM at once).
After running `discover_sccs.py` across all 9 verusage projects, only
**one** non-trivial multi-type SCC exists (`{Directory, NodeEntry}`
in nrkernel) and both are already L4-cached. The plan had no real
target → pivot to the remaining problem.

**New target**: self-recursion, where a type contains itself
(possibly wrapped) in its own fields. Canonical bug: PTDir

```rust
pub struct PTDir { pub entries: Seq<Option<PTDir>>, ... }
```

The LLM tends to write:

```rust
type V = PTDirView { entries: Seq<Option<PTDir>>, ... }     // element is the original type!
fn view(&self) { entries: self.entries@, ... }
```

But `<Seq<Option<T>> as View>::V = Seq<Option<T>>` is identity —
the inner View is **never applied**, the equal-fn collapses to
trivially-true, and the determinism check returns false-`ok` for
every PTDir-returning function. Silent.

**M4 lint** catches this class — the V declaration uses `T@`-lifted
inner types, but the body emits bare `self.f@`. `lint_view_decl`
priority becomes **M3 > M2 > M4 > M1**.

**Prompt rework**: `view/llm.py`'s `_VIEW_SCHEMA_DOC` gained an
~80-line "Self-recursive types" section laying out three legitimate
strategies:

- **Option A**: full recursive lift (`type V = MyView { entries:
   Seq<Option<MyView>> }`) — most expensive
- **Option B**: V mirrors concrete inner with spec-side type — medium
- **Option C**: `type V = Self` (leaf-reuse, when no projection makes
   sense) — cheapest

Additionally, `build_view_prompt` detects self-recursion and **injects
a callout block** naming the offending fields before the schema doc,
so the LLM is told explicitly rather than being expected to read it
out of the generic instructions. `_FEW_SHOT` was extended with a
`Tree` (Option C) example.

---

### 4.3 PR-F — A-1: Tracked / Ghost / PointsTo

**Problem**: in Verus, `Tracked<T>`, `Ghost<T>`, and `PointsTo<V>`
are common permission / ghost wrappers. The extractor was storing all
three as `TypeKind.UNKNOWN`, with two consequences:

1. **Schema enumeration**: 0 schemas emitted (no narrow entry points
   for z3)
2. **Equal-fn**: fell back to `r1 == r2`, which is structurally
   correct but invisible to z3
3. **Narrow strategies**: routed through `narrow_unknown`, partial
   witnesses

Worse: fully-qualified paths like `vstd::pcell::Tracked<T>` had a
**tree-sitter parsing bug** — the name node was
`scoped_type_identifier`, not `type_identifier`, so the extractor
took the whole text `vstd::pcell::Tracked<T>` as the type name and
never matched the generics table.

**Fix** (4 files):

| File | Changes |
|---|---|
| `extract/types.py` | New `TypeKind.TRACKED / GHOST / POINTS_TO` |
| `extract/extractor.py` | `_KNOWN_GENERICS` += 3 entries; `_parse_type_node` accepts `scoped_type_identifier` and strips the `vstd::pcell::` scope before lookup |
| `extract/narrow.py` | `narrow_tracked_or_ghost` (project via `@`, recurse on inner); `narrow_points_to` (probe `is_init()` / `value()` / `addr()`) |
| `codegen/gen_det.py build_equal_expr` | TRACKED/GHOST → `({lhs})@` recurses on inner; POINTS_TO → conjunction of the three probes |
| `schema_search/schemas.py _emit` | Emit schemas for the three new kinds, otherwise narrow's assumes hit `pass_untranslatable` |

**Insight 1: compositionality**.
PR-F's `({lhs})@` recurses into the inner `EventResults` (UNKNOWN+View),
which automatically meets PR-D2's `.view()` projection. Two
independently-shipped PRs compose to a clean one-liner:

```rust
spec fn equal(r1: Ghost<EventResults>, r2: Ghost<EventResults>) -> bool {
    ((((r1)@).view() == ((r2)@).view()))     // PR-F outer @, PR-D2 inner .view()
}
```

**Insight 2: schemas and narrows must evolve together**.
Narrow writes `(g)@.recvs.len() == k`. If `_emit` did not emit a
schema for `(g)@.recvs.len()`, the search layer treats the assume as
`pass_untranslatable`, the narrow aborts on that dimension, and the
witness stays partial. **Updating one without the other is silently
broken.**

---

### 4.4 PR-G — A-3: nested-Err policy lift

**Problem**: `EqualPolicy.errs_equivalent=True` collapses all `Err`
variants of `Result<T, Err>` to a single equivalence class — but
only at the **outermost** Result.

```rust
// ❌ broken case
fn foo() -> Seq<Result<u32, MyErr>>;

// auto-generated equal-fn:
fn equal(r1, r2) -> bool { r1 == r2 }    // Seq was in the primitive-== list
// → two sequences with structurally-different Err payloads compare false,
//   policy never fires.
```

Root cause: `TypeKind.SEQ` was in `build_equal_expr`'s primitive-`==`
allowlist. `TypeKind.MAP` fell through to the UNKNOWN `==` fallback
with the same effect.

**Fix** (one file, `gen_det.py`):

```python
# 1. New _contains_result(ty)  —  recurse over type_args + fields,
#    guard cycles via id() visited set.
# 2. New _container_needs_elementwise(ty, policy)  —  true only when
#    policy collapses Err AND the element contains Result.
# 3. TypeKind.SEQ removed from primitive == list:
#    elementwise needed  → forall|i: int| 0 <= i < len ==> elem_eq
#    otherwise           → fall back to ==
# 4. Same for TypeKind.MAP:
#    dom == + forall|k: K| dom.contains(k) ==> val_eq
# 5. TypeKind.SET left as raw == (no positional indexing; lifting
#    requires a custom set-equivalence relation — recorded as a
#    known limitation in the branch comment).
```

---

## 5. Engineering practices that carried us through

### 5.1 Quarantine system

A `.quarantine` filename suffix marks a known-bad cache entry — it
stays on disk but is skipped by the loader. L4 prefill also writes
failed cases to `_rejected.jsonl` (durable log, retryable on next
run).

`view/llm.py --include-quarantined` is the opt-in for retries.

### 5.2 Critic pass

Before an L4 view is cached, it goes through a **codex critic** —
an independent LLM call with its own prompt:

```
"Here is a candidate view. Verdict: accept / revise / reject?"
```

- `accept`  → cache it
- `revise`  → forward the critic's notes back to the original
              synthesiser for a retry
- `reject`  → write to `_rejected.jsonl`

The acceptance criteria live in `docs/critic-criteria.md`, are
quoted in the critic's prompt, and serve as a contract for future
LLM callers and reviewers.

### 5.3 Lint pipeline evolution

```
PR-D5  → M1 (field@ on type with no View)
         M2 (Ghost-piercing into Set/Map)
         M3 (self.field on external_body parent)
PR-E   → M4 (bare self.f@ on a self-recursive type)

priority: M3 > M2 > M4 > M1
```

Each rule has acceptance fixtures = the quarantined view that
motivated it (must reject) + 4 known-good winning views (must
accept) as controls.

### 5.4 Compare framework

`scripts/compare_runs.py` produces a per-project transition table
between two runs:

```
fixed         witness → ok            (true win)
witness → verus_error                  (view compiles but blocks Verus;
                                        not a clean win)
regressed     ok → verus_error        (must be ≈ 0 to ship)
```

`scripts/auto_chain.sh` wires "wait for prefill → rerun → compare"
into one driver.

---

## 6. Numbers

### 6.1 Baseline (`42c1248`, snapshot 2026-04-29)

```
n=1647  ok=1455  witness=376  verus_error=191  runner_crash=1
```

### 6.2 Post-quarantine + PR-D5 + PR-E (`33bd09a`, 2026-05-11)

```
ok=1456 (+1)   witness=366 (-10)   verus_error=190 (-1)
```

**11 true wins** (one quarantine cascade clobbered the 11th, so net 10
witnesses cleared + 0 regressions).

### 6.3 Post-PR-F + PR-G (`4eb7376`, atmosphere rerun in flight)

Prediction: the A-1 (~29) + A-3 (~30) cohorts should drop
`verus_error` to the ~130 region. Atmosphere progress 944/1363 (69%)
at the time of writing, ETA ~30 minutes.

**Per-target cost +62%** (4.89 s → 7.93 s/target — more schemas means
larger SMT files). This is the expected tradeoff for finer narrowing.

---

## 7. Key technical take-aways

1. **L4 LLM-synth + critic + lint** is the right factoring:
   generation is one process, verification is a separate process
   with its own prompt and its own code-side rules.
   **Retroactive scanning** is defence in depth — every time a new
   bug class is discovered, scan **all** historical cache for the
   same shape.

2. **Schemas, narrows, and the equal-fn must evolve together**.
   PR-F could not ship as a series of partial PRs — schema without
   narrow gives unused dimensions; narrow without schema gives
   `pass_untranslatable`; equal-fn without either gives "z3 sees
   only `r1 == r2`".

3. **Quarantine, do not delete**. Bad views stay on disk with a
   suffix → auditable, retryable, comparable. `_rejected.jsonl`
   makes "failure" a first-class data product.

4. **Compose by recursion** gives clean abstraction boundaries.
   PR-F's `({lhs})@` neither knows nor cares what the inner type is;
   PR-D2's `.view()` is independent of the wrapper. They compose in
   atmosphere and ironkv with **zero shared code**, producing
   `((r1)@).view()` automatically. Two PRs ship in isolation, meet
   in production.

5. **Predict → quarantine → re-run** is debuggable.
   PR-D4-final predicted "11 wins / 0 regression / -10 witnesses".
   Reality: "10 wins / 0 regression / -10 witnesses" (one win lost
   to a cascade quarantine). Small error → calibration trustable
   → next prediction can take more risk.

---

## 8. Open items / what's next

- 🟡 **Integration smoketest** (`ISSUES.md #5`) — single-target
  end-to-end run wired into `make check`. Would have caught the
  `1751dc1` cross-subpackage import regression immediately rather
  than after a manual rerun.
- 🟡 **`results-verusage/view_registry/` version-control decision** —
  git vs DVC vs S3. Currently untracked (112 active entries + 23
  quarantine markers + per-project audit JSONs + rejected logs).
- ⏳ **Newtype-of-`usize` unwrap** (e.g. `struct ProcPtr(pub usize);`)
  — deferred A-1 follow-up. Needs cross-file type resolution.
- ⏳ **After atmosphere finishes**, write the final `COMPARE.md` and
  push the numbers into `STATUS.md`.
- ⏳ **Retry the four `_rejected.jsonl` types**: `CrcDigest`, `PTDir`,
  `LoadResult`, `MaybeCorruptedBytes`. The combined M1-M4 + critic
  is now strict enough to retry safely.

---

## 9. One-paragraph abstract

> Phase 2 added a **layered view resolver** (mechanical L1-L3 +
> LLM-synth L4) to spec-determinism, and constrained the
> LLM-introduced uncertainty through four static lint rules, a
> codex-based critic, a quarantine system, and durable rejection
> logs. Without altering the baseline tool-chain, 376 witnesses fell
> to 366 (10 true wins, 0 regressions). After PR-F + PR-G, the 191
> `verus_error` is expected to fall by ~50 more, closing the
> remaining A-1 (Tracked/Ghost/PointsTo) and A-3 (nested-Err) cohorts.
