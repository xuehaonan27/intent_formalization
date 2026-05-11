# L4 view-cache — audit notes

Spot-audit of cached `impl View` entries produced by the Copilot-CLI
synthesiser (`spec_determinism/view/llm.py`). All entries are critic-gated
(`spec_determinism/view/critic.py`); the verdict and any issues are stored
alongside each cached entry under `critic_verdict` / `critic_issues`.

## Round 1 — variety pass (2026-05-11 — see STATUS.md)

Sampled 6 entries across kinds: generic spec_fn newtype, fixed-size array
bitmask, tagged enum with `Option` payloads, byte-vec wrapper, HashMap
wrapper, recursive page-table node with `<NodeEntry as View>::V`. Verdict
of audit: **high quality**.

## Round 2 — tricky-shape pass (2026-05-11)

This round deliberately picks the hardest type shapes that the equal-fn
pipeline can throw at the synthesiser:

- `Tracked<...>` / `PointsTo<...>` runtime-only permission fields
- `Ghost<...>` proof-only fields
- `const N: usize` const generics
- `Box<MaybeUninit<S>>` with a `S: PmCopy` trait bound
- raw `*const` / `*mut` pointers
- `extern "C" fn` callbacks

| # | project / type | tricky shapes | verdict | quality |
|---|---|---|---|---|
| 1 | `atmosphere/PageTable`         | 4×`Tracked<Map<…, PointsTo<…>>>` + 4×`Ghost<Map<…>>` + 4×`Ghost<Seq<…>>` | `accept` | ✅ high |
| 2 | `atmosphere/StaticLinkedList`  | `<T, const N: usize>` + `[Node<T>; N]` + 4×`Ghost<Seq<…>>` head/tail/len cursors | `accept` | ✅ high |
| 3 | `atmosphere/ArraySet`          | `<const N: usize>` + `Array<bool, N>` + `Ghost<Set<usize>>` | `accept` | ✅ high |
| 4 | `atmosphere/PageMap`           | `Array<usize, 512>` (no View impl) + `Ghost<Seq<PageEntry>>` | `accept` | ⚠ check (see below) |
| 5 | `storage/MaybeCorruptedBytes`  | `Box<MaybeUninit<S>>` where `S: PmCopy` | `accept` | ❌ buggy (see ISSUES.md #4) |
| 6 | `ironkv/NetClientCPointers`    | three `extern "C"` function-pointer fields | `accept` | ✅ high |
| 7 | `memory-allocator/Node`        | sole field `ptr: *mut Node` | `accept` | ✅ high |

(7 entries — added one extra because raw-pointer & extern-fn-pointer are
distinct shapes worth showing side-by-side.)

### What the synthesiser got right

- **Tracked permissions stripped (PageTable).** All four
  `Tracked<Map<PageMapPtr, PointsTo<PageMap>>>` fields and the eight
  `Ghost<Map<…>>` reverse-map / TLB-shadow fields are correctly omitted
  from the view body; the rationale explicitly classes them as
  "proof-only / allocator-opaque". This is exactly the
  `Tracked<T>` rule from the prompt header (proof permissions never
  contribute to spec equality).
- **Const-generic collapse (StaticLinkedList, ArraySet).** The synthesiser
  picks the smallest spec-meaningful representation —
  `Seq<T>` for the linked list and `Set<usize>` for the array-set — and
  drops the concrete array storage. The const generic `N` becomes
  irrelevant after the collapse, which is the right outcome.
- **Raw-pointer & extern-fn-ptr → `()` (NetClientCPointers, allocator/Node).**
  Both correctly collapse to unit because their sole runtime fields are
  allocator-opaque. The synthesiser cites the `*mut T` rule and the
  "extern C function pointer" rule from the prompt.
- **Critic distinguishes legitimate `()` from over-collapse.** Compare
  with `ironkv/DuctTapeProfiler` (rejected — has real spec-relevant
  state fields `last_event`/`event_counter`) vs. `NetClientCPointers`
  (accepted — fields really are opaque callbacks). The critic correctly
  fires only on the over-collapse case.

### One pattern that still needs scrutiny — `PageMap`

`PageMap` keeps `ar: Array<usize, 512>` at identity (no `@`) inside
`PageMapView` and only `@`-unwraps the `Ghost<Seq<PageEntry>>`. The
rationale says "every bit is hardware-observable" so the array is
spec-meaningful, but:

- `Array<usize, 512>` has **no `View` impl in scope** (it's an uncovered
  leaf, per `_audit.json`).
- Carrying a concrete `Array` inside a `view()` body is suspect because
  `view()` must return a value of `Self::V` — i.e. a spec-only type.
  Whether Verus's stdlib accepts `Array<usize, 512>` in a spec-only
  position depends on the array's own representation (deep_view / arbitrary
  vs. concrete-spec); we should verify this compiles in the corpus rerun.

If the rerun shows `PageMap` consumers regressing to `verus_err`, the fix
is to `@`-project the array too (it does have a built-in deep_view that
returns `Seq<usize>`).

### One pattern the critic missed — `MaybeCorruptedBytes`

`MaybeCorruptedBytes<S> where S: PmCopy` wraps `Box<MaybeUninit<S>>`,
which means the byte contents are not statically known from the Rust
type alone. The synthesiser handled this by writing

```rust
impl<S> View for MaybeCorruptedBytes<S> where S: PmCopy {
    type V = Seq<u8>;
    closed spec fn view(&self) -> Seq<u8> {
        arbitrary()
    }
}
```

i.e. it returned `arbitrary()` from the view body. The critic accepted
this. **This is silently wrong**: `arbitrary::<Seq<u8>>()` is a fixed
witness, so `a@ == b@` evaluates to `arbitrary() == arbitrary()` which
is provably true for *any* pair `a, b`. The view therefore collapses
every value of `MaybeCorruptedBytes<S>` to equal, which is the
strongest possible over-collapse. See `ISSUES.md` issue #4.

(Won't affect the A-2 metric directly because storage has 0 baseline
witnesses — all functions are currently in `verus_err`. But the issue
will bite as soon as storage's verus errors are fixed and witnesses
appear.)

## How to refresh / regenerate

To re-audit a single type after editing the prompt or critic:

```bash
rm spec-determinism/results-verusage/view_registry/<project>/<Type>.json
python -m spec_determinism.view.llm prefill --project <project> --only <Type>
```

To re-audit all entries with a new critic prompt or model:

```bash
# (manually clear critic_verdict / critic_issues, or change critic key in the
# CacheEntry schema and let synthesize_view recompute on next miss)
```
