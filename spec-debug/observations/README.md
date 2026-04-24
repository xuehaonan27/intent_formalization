# spec-debug v0 — First Observations

Three nanvix missing-ensures bugs run through the v0 pipeline
(`spec-debug run <crate::fn> --llm copilot`) with the generic prompt
template in [`spec_debug/prompt.py`](../spec_debug/prompt.py). Same
template, same GitHub Copilot CLI backend, no strategy layer. Raw
artifacts are preserved under [`observations/v0/<fn>/`](./v0/).

## Setup

- Verus: `v0.12.350-66-g171a06aae` (nanvix fork, 2026-04-04)
- spec-determinism @ `867ea6a` → witness source
- spec-debug v0 @ `c5fd0f0`
- LLM: `copilot -p` non-interactive, default model, default effort
- Target files patched (whole-file replacement, reverted after each run):
  - `nanvix/src/libs/bitmap/src/lib.spec.rs`
  - `nanvix/src/libs/slab/src/lib.spec.rs`
  - `nanvix/src/kernel/src/mm/kheap.spec.rs`

## Summary table

| # | Function | Witness | Patch size | Strategy | `closed / total` | `rounds` before → after | Verdict |
|---|---|---:|---:|---|---:|:---:|---|
| 1 | `bitmap::new` | 8 | 17 KB | Added helper spec fns `new_spec_ensures` / `new_args_valid`; never wired into `fn new`'s `ensures` | **0 / 8** | 20 → 20 | **No-op**; passes Verus compile |
| 2 | `slab::from_raw_parts` | 17 | 3.7 KB | Strengthened `SlabView::inv()` with a `forall i: allocated.contains(i) \|\| free.contains(i)` partition predicate | **1 / 17** | 67 → 99 | **Partial & wrong layer** |
| 3 | `kernel::from_raw_parts` | 9 | 13 KB | Added a brand-new `assume_specification[Kheap::from_raw_parts]` block with canonical `spec_from_raw_parts_err_reason()` | **9 / 9** | 65 → 0 | **Closes witness, but `rounds=0` is suspicious** — see §4 |

## Per-case observations

### 1. `bitmap::new` — the dangling-helper failure mode

Witness (8 committed assumes):

```
number_of_bits == 8
r1 is Ok
r1->Ok_0@.num_bits == 8
r1->Ok_0@.set_bits == Set::<int>::empty()
r2 is Err
r2->Err_0.code is OperationNotPermitted
r2->Err_0.reason == ""
!det_new_equal(r1, r2)
```

The gap is: on the same `number_of_bits = 8`, `r1` can be `Ok(bitmap)` and
`r2` can be `Err(OperationNotPermitted, "")`. The spec allows both.

Copilot's diff adds two helper spec fns to `BitmapView`:

```rust
pub open spec fn new_args_valid(number_of_bits: usize) -> bool {
    &&& number_of_bits > 0
    &&& (number_of_bits as int) < u32::MAX as int
    &&& number_of_bits % (u8::BITS as usize) == 0
}

pub open spec fn new_spec_ensures(number_of_bits: usize, r: Result<Bitmap, Error>) -> bool {
    ...
    // Strengthening: if the inputs are valid, the result must be Ok.
    &&& (Self::new_args_valid(number_of_bits) ==> r is Ok)
}
```

The strengthening idea (`valid inputs ⇒ r is Ok`) is actually correct for
this witness — but the ensures of `fn new` itself is never touched, so the
helper is **dead code**. spec-determinism rerun confirms: 0 of 8 assumes
closed.

**Failure mode name candidate: "dangling helper"** — reads like a
substantial fix, type-checks, adds zero semantic content. A metric based
only on "does Verus still compile?" or "did the patch touch a file?"
would pass this. Structural check needed: *are the new items referenced
from the target function's ensures?*

### 2. `slab::from_raw_parts` — fix at the wrong layer

Witness: `r1@.free_addrs == {}` vs `r2@.free_addrs == {0}` (etc.) — the
view's `free_addrs` / `allocated_addrs` are underspecified.

Copilot's patch is small and principled: it strengthens the struct's
`SlabView::inv()` by requiring every aligned slot in `[start_addr, end_addr)`
to be in `allocated_addrs ∪ free_addrs`.

Outcome: this closes **1 of 17** assumes (just
`r2->Ok_0@.free_addrs.contains(0)`) and increases search rounds from
**67 → 99**. The underlying gap (`free_addrs` and `allocated_addrs`
aren't pinned by the ensures) is untouched; the invariant change merely
rules out one specific witness configuration.

**Failure mode name candidate: "wrong layer"** — a structurally valid
edit in the wrong place. The missing content belongs in `fn
from_raw_parts`'s `ensures` (relating post-state to inputs), but Copilot
moved it into the struct's invariant.

### 3. `kernel::from_raw_parts` — closed, but `rounds=0` is suspicious

Witness shows two differing `Err.reason` strings for the same input
(`addr=0, size=0`): `""` vs `"string 1"`.

Copilot's patch introduces a **new** `assume_specification` block for
`Kheap::from_raw_parts` in `kheap.spec.rs`. Two concerns:

1. The **original ensures lives inline on the `impl Kheap` in
   `kheap.rs`** (lines 122–151), not in `kheap.spec.rs`. It constrains
   `Err.code` but not `Err.reason`, which is what created the gap in
   the first place. Copilot chose to add a parallel
   `assume_specification` that *does* pin `reason`, effectively
   shadowing / duplicating the inline contract.

2. **`rounds=0`** in the rerun — normal runs for this function take
   ~65 rounds. Zero rounds means spec-determinism may have short-
   circuited (e.g. no schemas emitted, or the check trivially passed
   because the assume_specification rewrote the symbol resolution in
   an unexpected way). Possible interpretations:
   - **(a) Genuine**: the new spec is tight enough that the checker
     proved determinism with no assumptions needed. Under this view,
     `closed=9` is a real success.
   - **(b) Bypass**: the `assume_specification` block changed what
     symbol the checker instruments, so it never actually re-checked
     the same function. Under this view, `closed=9` is vacuous.

   The current pipeline doesn't distinguish these. Comparing
   `n_schemas` before/after (519 → ?) or re-running the checker with
   the *original* inline ensures removed would help.

**Open follow-up**: add a sanity diff of the *structural shape* of
what's being checked (function name, schema count, param count) before
trusting `closed=N`.

## Cross-case patterns

1. **One prompt → three different edit layers.** Bitmap got a new
   helper spec fn. Slab got a struct invariant. Kernel got a new
   top-level `assume_specification`. Nothing in the prompt directed
   Copilot to the ensures of the target function — and the two failures
   (#1, #2) correlate with Copilot picking a layer *other than* the
   ensures.

2. **`closed` is a necessary but not sufficient signal.** Case #3 shows
   that a high `closed` number can come from a structurally dubious
   edit. Case #1 shows that `closed=0` is a very clean "no fix"
   signal. Between them, `closed` alone doesn't rank candidates
   meaningfully.

3. **"Passes `verus`" is a very weak filter.** All three patches
   compile. Only one actually closed witnesses meaningfully, and even
   that one has shape concerns.

4. **Same-prompt LLM output is long-tailed.** Bitmap: 17 KB mostly
   restated existing items; Slab: 3.7 KB focused edit; Kernel: 13 KB
   with full spec block. Response size doesn't predict fix quality in
   an obvious way (smallest closed the least; biggest did nothing;
   medium-sized closed everything).

## 5. Policy lens — which witness assumes actually drive `!equal`

`spec-determinism` attaches an `EqualPolicy` to each determinism-
checked function (persisted in `det_spec.json`). The same witness
assumes can mean very different things depending on the policy:

| knob | default | effect when True |
|---|---|---|
| `errs_equivalent` | **True** | `equal_fn` does NOT inspect `Err(_)` — any two `Err`s compare equal regardless of `.code` / `.reason`. |
| `opaque_ok` | **False** | When True, `equal_fn` does NOT inspect `Ok(_)` — any two `Ok`s compare equal; only post-state `&mut self` view fields matter. |

Across our 15 nanvix artifacts:
- `opaque_ok=True` (4): `bitmap::alloc`, `bitmap::alloc_range`,
  `slab::allocate`, `kernel::allocate`. All allocator-style returning
  a handle.
- `errs_equivalent=False` (1): **only** `kernel::from_raw_parts`.
- Neither flag is ever set by code; both are manual edits preserved
  across `spec-determinism-regen`.

### 5.1 `bitmap::new` — most of the witness is collateral

Default policy `(errs_equivalent=True, opaque_ok=False)` generates:

```rust
spec fn det_new_equal(r1, r2) -> bool {
    (r1 is Ok) == (r2 is Ok)
 && (r1 is Ok) ==> ((r1->Ok_0)@ == (r2->Ok_0)@)
}
```

Mapped against the 8-assume witness:

| Assume | Role |
|---|---|
| `number_of_bits == 8` | input narrowing |
| `r1 is Ok` | **driving** (discriminant) |
| `r2 is Err` | **driving** (discriminant) |
| `r1->Ok_0@.num_bits == 8` | collateral — Ok branch not taken once r2 is Err |
| `r1->Ok_0@.set_bits == ...` | collateral, same reason |
| `r2->Err_0.code is OperationNotPermitted` | **collateral** — Err branch erased by `errs_equivalent=True` |
| `r2->Err_0.reason == ""` | **collateral**, same reason |
| `!det_new_equal(r1, r2)` | assertion |

**The gap is just `r1 is Ok && r2 is Err`.** Everything else is
search-loop residue. Case #1's Copilot patch pinned validity-⇒-Ok in a
helper, which is actually the right direction — it just wasn't wired
into `fn new`'s `ensures`.

### 5.2 `kernel::from_raw_parts` — the `reason` assume is genuinely driving

With `errs_equivalent=False`, the generated `equal_fn` expands into a
~400-line body: for every variant `V` of `ErrorCode` it emits
`(r1.code is V) == (r2.code is V)`, plus `r1.reason == r2.reason`.

```rust
spec fn det_from_raw_parts_equal(r1, r2) -> bool {
    (r1 is Ok) == (r2 is Ok)
 && (r1 is Ok) ==> ((r1->Ok_0)@ == (r2->Ok_0)@)
 && (r1 is Err) ==> (
        /* ~120 variant-discriminant pairs */
     && (r1->Err_0.reason == r2->Err_0.reason)
   )
}
```

Mapped against the 9-assume witness (both `r1 is Err && r2 is Err`,
same `.code`, differing `.reason`):

| Assume | Role |
|---|---|
| `addr == 0`, `size == 0` | input narrowing |
| `r1 is Err`, `r2 is Err` | discriminant (aligned — not the driver) |
| `r1.code is InvalidArgument`, `r2.code is InvalidArgument` | **driving** (enter Err branch, code must agree — and it does) |
| `r1.reason == ""` | **driving** — the real driver |
| `r2.reason == "string 1"` | **driving** — the real driver |
| `!det_..._equal(r1, r2)` | assertion |

**Rehabilitation of case #3**: Copilot's decision to pin
`Err.reason` to a canonical string was directionally correct — the
policy **requires** Err content to agree, so the gap really is in
`reason`. The remaining concern is orthogonal: the patch introduced a
parallel `assume_specification` block shadowing the inline `impl
Kheap` contract, and `rounds=0` afterwards could indicate either a
genuinely tight spec or an instrumentation bypass.

### 5.3 `slab::from_raw_parts` — gap shape is about Ok-view fields

Same default policy as bitmap, but the witness has both results as
`Ok(_)` with differing `@.free_addrs` / `@.allocated_addrs` sets. So
the driver is in the Ok branch's `view == view` comparison — i.e.,
ensures must pin these sets as functions of `(start_addr, size)`.
Copilot's strengthening of `SlabView::inv()` was at the wrong layer
(invariant restricts the *type's legal states*, not the *function's
output*).

### 5.4 Implications for prompting

- Pass the LLM **the rendered `equal_fn_def`**, not just the policy flags.
- **Split witness assumes** into driving / input / collateral before
  displaying them. Telling the LLM "these assumes are policy-ignored;
  don't pin them" removes the main source of over-specification noise
  from cases like bitmap::new.
- Add a **layer directive** to the prompt: "strengthen `ensures` of
  `fn <name>` in place; helpers must be referenced; do not add parallel
  `assume_specification` blocks." This directly targets the three
  observed failure modes.

All three changes are pure prompt-engineering against data already
emitted by `spec-determinism`; no extraction changes needed. Landed in
`spec-debug/spec_debug/prompt.py` and `gap.classify_assumes` as of
v0.1.

### 5.5 Open question on `errs_equivalent=False` for kernel::from_raw_parts

The policy forces callers to distinguish every distinct
`Error::reason` string. Realistic callers of `Kheap::from_raw_parts`
probably branch on `.code` alone (e.g., retry on `OutOfMemory`, give up
on `InvalidArgument`) — the reason is diagnostic text. If so, this
policy entry is over-specification and flipping it to True would make
case #3's witness vacuous by construction. Worth asking the nanvix
author before we treat case #3 as a "real" incompleteness bug.

## What v0 rules out / in

These observations already rule out several metric designs:

- ❌ **`verify_pass` as a scorer** — passes all three cases with
  wildly different quality.
- ❌ **Patch size / minimality as a primary signal** — smallest patch
  (slab) is the most misdirected.
- ❌ **`closed` count as a sole signal** — kernel looks perfect but
  shape-wise may be vacuous.

They point towards needing:

- ✅ **Structural check: is the edit actually referenced from the
  target function's ensures?** Catches the "dangling helper" (#1)
  failure mode directly.
- ✅ **Layer check: which AST node type received the edit?**
  (ensures vs. struct `inv` vs. new `assume_specification`.)
  Different layers have different validity implications.
- ✅ **Symbol-stability check: before/after patch, is the checker
  instrumenting the same function with roughly the same schema
  count?** Catches the case-#3 style "did we bypass the check?"
  concern.
- ✅ **Witness-closure has to be combined with structure** — the
  ranking signal is `(closed_count, structural_validity_flags)`.

## Open questions for next step

1. Is case #3's `rounds=0` a genuine tight spec, or an instrumentation
   bypass? Need a structural diff of what the checker sees.
2. Would a prompt that explicitly says *"strengthen the ensures of `fn
   <name>` in-place; do not add helpers unless they are called from
   ensures; do not add `assume_specification` blocks for functions
   whose spec lives inline"* move all three into the same edit layer?
3. Is the `(closed_count, structural_flags)` two-axis score enough, or
   do we need a third axis for referential density / input-vs-literal
   content?
4. When Copilot is re-invoked on the same prompt, how stable is its
   output? (v0 only ran each case once.) Stability matters if we plan
   to use "which of N candidates dominate" as part of the ranking.

---

Raw artifacts for each case live in [`v0/<function>/`](./v0/)
(`prompt.md`, `response.md`, `patch.spec.rs`, `report.json`,
`report.md`).
