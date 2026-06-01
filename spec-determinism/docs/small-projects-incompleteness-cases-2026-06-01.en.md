# small-projects spec-incompleteness case set

> **3 source-level cases / 3 unique spec functions / 3 raw corpus artifacts.**
> Each is the sole `unknown` record in its project after the 2026-05-26 verus_error closeout. The 2026-06-01 manual audit found **all three are real spec defects** (not z3 limits), so they were reclassified `unknown` → `incomplete` in `corpus_rerun11_results.md` §"Source-level distribution".
> Source: `spec-determinism/results-verusage-viewreg/{memory-allocator,nrkernel,anvil-library}/full_run.json`.
>
> | # | Project          | Function                  | Defect mechanism |
> |---|------------------|---------------------------|------------------|
> | 1 | memory-allocator | `CommitMask::next_run`    | Author commented out the strengthening ensures clauses |
> | 2 | nrkernel         | `PDE::new_entry`          | Per-bit `MASK_X` predicates omit bit 8 (Global flag), which `view()` reads |
> | 3 | anvil-library    | `vec_filter`              | Spec uses multiset-eq while impl + `filter`-convention are order-preserving |

## Witness format

Each witness lists assumed facts on inputs / outputs (`r1`, `r2`); the closing `!det_*_equal(...)` is the negated structural equality. "z3 sample" is the raw assumes from `full_run.json`; "constructed witness" is the manually-constructed concrete sat model demonstrating the spec gap.

---

## #1 `CommitMask::next_run`

- **Project**: memory-allocator
- **Source**: [`verified/commit_mask/commit_mask__impl__next_run.rs:82`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/memory-allocator/verified/commit_mask/commit_mask__impl__next_run.rs#L82)
- **Pattern**: spec weakening — author-acknowledged

### Why this is incomplete

`next_run` is meant to "scan starting at `idx` and return `(start, length)` of the first maximal run of set bits". The implementation is a deterministic two-level bit scan, but the author **explicitly commented out** the two clauses needed for that semantics:

```rust
// This should be true, but isn't strictly needed to prove safety:
//forall |t| idx <= t < next_idx ==> !self@.contains(t),
// Likewise we could have a condition that `count` is not smaller than necessary
```

Without them, a degenerate "always return `(0, 0)`" implementation satisfies every clause for every input.

### Source function

```rust
pub fn next_run(&self, idx: usize) -> (res: (usize, usize))
    requires 0 <= idx < COMMIT_MASK_BITS,      // == 512
    ensures ({ let (next_idx, count) = res;
        next_idx + count <= COMMIT_MASK_BITS
        && (forall |t| next_idx <= t < next_idx + count ==> self@.contains(t))
    }),
{ /* … two-level bit scan … */ }
```

`self@: Set<int>` is the abstract view of the 8 × 64-bit mask.

### Generated equal_fn

```rust
spec fn det_next_run_equal(r1: (usize, usize), r2: (usize, usize)) -> bool { r1 == r2 }
```

### Witness

z3 sample (`full_run.json`, `n_schemas=11, n_rounds=33`):

```
  idx == 0
  r1 == (0, 0)   r2 == (0, 1)
  !det_next_run_equal(r1, r2)
```

Constructed sat model — input `self.mask[0] & 1 == 1`, all other bits 0 (so `self@ == {0}`), `idx == 0`:

```
  Impl A: r1 = (0, 0)         // 0+0 ≤ 512 ✓ ; forall t. 0 ≤ t < 0 vacuous ✓
  Impl B: r2 = (0, 1)         // 0+1 ≤ 512 ✓ ; self@.contains(0) ✓
  ⇒ both pass; !det_next_run_equal
```

### Suggested fix

Uncomment the two clauses the author already wrote:

```rust
ensures
    next_idx + count <= COMMIT_MASK_BITS,
    forall |t| next_idx <= t < next_idx + count ==> self@.contains(t),
    forall |t| idx <= t < next_idx ==> !self@.contains(t),                     // first-set-bit
    next_idx + count == COMMIT_MASK_BITS                                       // maximal
        || !self@.contains((next_idx + count) as int),
```

---

## #2 `PDE::new_entry`

- **Project**: nrkernel
- **Source**: [`verified/impl_u__l2_impl/impl_u__l2_impl__impl0__new_entry.rs:325`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/nrkernel/verified/impl_u__l2_impl/impl_u__l2_impl__impl0__new_entry.rs#L325)
- **Pattern**: per-bit predicate gap — Global flag (bit 8) unconstrained but view-observed

### Why this is incomplete

`PDE::new_entry` packs 8 inputs into a 64-bit x86 page directory entry via bit-OR. The implementation is deterministic. The ensures clauses constrain individual bits via `r.entry & MASK_X == MASK_X` predicates but **never mention `MASK_PG_FLAG_G` (bit 8, "Global")**, even though `PDE::view()` reads it and exposes it as the `G: bool` field of `GPDE::Page`.

The determinism check is view-level (`r1.view() == r2.view()`). For `is_page=true` the view is `GPDE::Page { addr, P, RW, US, PWT, PCD, G, PAT, XD }`; every field is pinned by ensures **except `G`**. Two implementations differing only on whether they OR-in `MASK_PG_FLAG_G` produce different views, and both pass ensures.

### Source function (ensures only)

```rust
ensures
    r.all_mb0_bits_are_zero(),
    if is_page { r@ is Page && r@->Page_addr == address }
    else       { r@ is Directory && r@->Directory_addr == address },
    r.hp_pat_is_zero(),
    r.entry & bit!(5) == 0,   r.entry & bit!(6) == 0,
    r.layer@ == layer,
    r.entry & MASK_ADDR == address,
    r.entry & MASK_FLAG_P  == MASK_FLAG_P,
    (r.entry & MASK_L1_PG_FLAG_PS == MASK_L1_PG_FLAG_PS) == (is_page && layer != 3),
    (r.entry & MASK_FLAG_RW  == MASK_FLAG_RW)  == is_writable,
    (r.entry & MASK_FLAG_US  == MASK_FLAG_US)  == !is_supervisor,
    (r.entry & MASK_FLAG_PWT == MASK_FLAG_PWT) == is_writethrough,
    (r.entry & MASK_FLAG_PCD == MASK_FLAG_PCD) == disable_cache,
    (r.entry & MASK_FLAG_XD  == MASK_FLAG_XD)  == disable_execute,
    // *** no clause constrains MASK_PG_FLAG_G ***
```

Implementation: `r.entry = address | MASK_FLAG_P | (PS if is_page&&layer!=3) | (RW if is_writable) | (US if !is_supervisor) | (PWT if is_writethrough) | (PCD if disable_cache) | (XD if disable_execute)`. No `MASK_PG_FLAG_G` ever set.

### View function (defines what the equal_fn observes)

```rust
pub open spec fn view(self) -> GPDE {
    let v = self.entry;
    let G = v & MASK_PG_FLAG_G == MASK_PG_FLAG_G;   // ← view reads bit 8
    // … if P set and mb0 ok: GPDE::Page { addr, P, RW, US, PWT, PCD, G, PAT, XD } …
}
```

### Generated equal_fn

```rust
spec fn det_new_entry_equal(r1: PDE, r2: PDE) -> bool { r1.view() == r2.view() }
```

### Witness

z3 sample (`full_run.json`, `n_schemas=17, n_rounds=21`) — all 8 inputs fully pinned; z3 returns unknown without concrete `(r1, r2)`:

```
  layer == 1; address == 0
  is_page == is_writable == is_supervisor == is_writethrough
           == disable_cache == disable_execute == true
  !det_new_entry_equal(r1, r2)
```

Constructed sat model:

```
  Impl A (source impl):       r1.entry = MASK_FLAG_P | MASK_L1_PG_FLAG_PS | MASK_FLAG_RW
                                       | MASK_FLAG_PWT | MASK_FLAG_PCD | MASK_FLAG_XD
                              r1.view().G == false
  Impl B (alt — also ORs G):  r2.entry = r1.entry | MASK_PG_FLAG_G
                              r2.view().G == true
  // every bit-wise ensures clause holds for both (G not in mb0 set, not in MASK_ADDR,
  //  bits 5/6/12 still 0, all P/RW/US/PWT/PCD/XD/PS predicates equal)
  // r1.view() and r2.view() differ only on G ⇒ !det_new_entry_equal
```

### Suggested fix

Add the missing Global-flag clause (minimal):

```rust
ensures r.entry & MASK_PG_FLAG_G == 0,
```

(Or pin `r.entry` to the literal bit-OR expression — also pins the unobserved bits 9/10/11.)

The 8 input parameters cover every flag the function is meant to control. The author clearly never intended `G` to be settable — it's an *omission*, not a deliberate weakening (contrast Case 1).

---

## #3 `vec_filter`

- **Project**: anvil-library
- **Source**: [`verified/vstd_exd/vec_lib/vec_lib.rs:13`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/anvil-library/verified/vstd_exd/vec_lib/vec_lib.rs#L13)
- **Pattern**: multiset-eq ensures vs sequence-eq equal_fn (impl + convention are order-preserving)

### Why this is incomplete

Spec is `r@.to_multiset() =~= v@.to_multiset().filter(f_spec)` — multiset equality, no ordering. Two valid impls may return the surviving elements in different orders; both pass ensures but are unequal as `Vec<V>` sequences, which is what `det_vec_filter_equal` compares. The source impl happens to preserve input order (single forward pass + `push`), and `filter` is order-preserving by universal convention (Rust `Iterator::filter`, Python, Haskell, JS). Only the spec dropped the constraint.

### Source function

```rust
fn vec_filter<V: VerusClone + View + Sized>(
    v: Vec<V>, f: impl Fn(&V) -> bool, f_spec: spec_fn(V) -> bool,
) -> (r: Vec<V>)
    ensures r@.to_multiset() =~= v@.to_multiset().filter(f_spec)
{
    let mut r = Vec::new();
    for i in 0..v.len() {
        if f(&v[i]) { r.push(v[i].verus_clone()); }
    }
    r
}
```

### Generated equal_fn

```rust
spec fn det_vec_filter_equal<V: ...>(r1: Vec<V>, r2: Vec<V>) -> bool { r1 == r2 }
```

### Witness

z3 sample (`full_run.json`, `n_schemas=7, n_rounds=6`) — this frame is not itself a valid sat model (`v.len=0` forces `r.len=0`); z3 returns unknown because multiset/`filter` quantifiers exceed its trigger heuristics:

```
  v@.len() == 0;  r1@.len() == 0;  r2@.len() == 1
  !det_vec_filter_equal(r1, r2)
```

Constructed sat model — two distinct elements `a, b` with `a@ != b@` and `f_spec(a) = f_spec(b) = true`, `v = vec![a, b]`:

```
  Impl A (preserves order):  r1 = vec![a, b]   to_multiset = {a, b} ✓
  Impl B (reverses):         r2 = vec![b, a]   to_multiset = {a, b} ✓
  ⇒ both pass; vec![a, b] ≠ vec![b, a]
```

### Suggested fix

Tighten the spec to sequence-preserving filter:

```rust
ensures r@ == v@.filter(f_spec)
```

`Seq::filter` exists in `vstd::seq_lib` and matches the impl exactly. This aligns spec with both the actual implementation and the universal `filter` convention.
