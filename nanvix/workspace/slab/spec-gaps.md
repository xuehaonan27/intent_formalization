# Slab Spec Gap Analysis

**Source:** `~/intent_formalization/nanvix/workspace/slab/original.rs`  
**Date:** 2026-04-08  
**Pipeline:** spec-consistency (brainstorm → formalize → entailment → critic)  
**Stats:** 57 candidates → 32 critic TP / 25 critic FP → **5 true gaps + 1 design-choice gap + 1 reclassified FP** after manual review

## Key Definitions

- `SlabView::inv()` — **open** spec: block_size > 0, alignment, addr range, **disjointness** of free/allocated
- `Slab::inv()` — **open** spec: `self@.inv() && self.internal_inv()`
- `Slab::view()` — **closed** spec: maps bitmap bits to free_addrs/allocated_addrs
- `Slab::internal_inv()` — **closed** spec: bitmap ↔ address set correspondence

---

## Gap 1: `from_raw_parts` — No success guarantee (6 TPs)

**Target:** `from_raw_parts`  
**φ:** neg_1_always_err ×3, gap_3 ×3

**Problem:** `from_raw_parts` has no `requires` clause. The ensures is a match on Ok/Err, but neither branch has conditions on inputs. A caller cannot prove that valid inputs guarantee Ok.

**Impact:** An implementation that always returns `Err(InvalidArgument)` satisfies the spec. Callers cannot use this API in verified code — they cannot prove construction will succeed.

**Body guarantees:** Returns Ok when: addr non-null, aligned to block_size, 0 < len < i32::MAX, len <= isize::MAX, no wrapping, 0 < block_size < i32::MAX, block_size <= len, num_index_blocks < total_num_blocks.

**Flip side (gap_3_null_addr):** The spec also allows Ok for null addr — the body rejects null but the spec doesn't encode this.

**Fix:** Add sufficient conditions to the ensures Ok branch (or add requires + separate Err conditions):
```rust
// Option A: sufficient condition for Ok
Ok(slab) => {
    // existing ensures ...
    // + input conditions that guarantee this branch
},
// Option B: necessary condition for Err  
Err(e) => {
    &&& e.code == ErrorCode::InvalidArgument
    &&& (addr.is_null() || len == 0 || block_size == 0 || ...)
},
```

**Severity:** High — blocks verified callers from using the API.

---

## Gap 2: `from_raw_parts` — `free_addrs` unconstrained (7 TPs)

**Target:** `from_raw_parts`  
**φ:** neg_3 ×3, neg_9 ×4, gap_1 ×3

**Problem:** The Ok branch ensures `allocated_addrs == empty` but says **nothing** about `free_addrs`. Callers only know from `SlabView::inv()` that free addrs are in range, aligned, and disjoint from allocated — but not how many exist, or even whether any exist.

**Impact chain:**
1. `from_raw_parts` returns Ok → caller gets slab
2. Caller wants to call `allocate`
3. `allocate` fails when `free_addrs == empty`
4. Caller cannot prove `free_addrs != empty` from the spec
5. Verified caller code cannot proceed

**Body guarantees:** Bitmap initialized from zeroed memory → all data bits = 0 (free). Guard ensures `num_data_blocks >= 1`. So `free_addrs.len() == num_data_blocks >= 1`.

**Why the information is lost:**
- `view()` is **closed** — caller cannot see the bitmap → free_addrs mapping
- Lemma `lemma_from_raw_parts_establishes_inv` proves inv but doesn't expose free_addrs count
- The ensures simply never mentions free_addrs

**Sub-issues:**
- No lower bound: free_addrs could be empty
- No upper bound: free_addrs.len() could exceed physical capacity
- No completeness: free_addrs might not cover all block-aligned addresses

**Fix:**
```rust
Ok(slab) => {
    // existing ...
    &&& !slab@.free_addrs.is_empty()
    // or more precisely:
    // &&& slab@.free_addrs.len() == (slab@.end_addr - slab@.start_addr) / slab@.block_size
},
```

**Severity:** High — combined with Gap 1, caller can neither create nor use the allocator.

---

## Gap 3: `from_raw_parts` — Loose address bounds (1 TP)

**Target:** `from_raw_parts`  
**φ:** gap_2_loose_addr_bounds

**Problem:** The ensures only says `start_addr >= addr` and `end_addr <= addr + len`. It doesn't pin exact values.

**Memory layout:** The slab allocator stores metadata (bitmap index) and data blocks in the same contiguous region:
```
|<-- bitmap index -->|<------ allocatable data blocks ------>|<- tail waste ->|
addr                 start_addr                              end_addr         addr+len
```
- `[addr, start_addr)`: bitmap that tracks free/allocated status of each data block
- `[start_addr, end_addr)`: the actual allocatable blocks
- `[end_addr, addr+len)`: remainder too small for a full block, discarded

**Body computes exact values:**
```rust
num_index_blocks = ceil(total_num_blocks / (block_size * 8 + 1))
start_addr = addr + num_index_blocks * block_size   // skip bitmap area
end_addr   = addr + (len / block_size) * block_size  // align to block boundary
```
Given `len` and `block_size`, these values are **fully determined** — there is no runtime nondeterminism.

**Why the spec uses `>=`/`<=` instead of `==`:** This is likely a **deliberate abstraction choice**, not an oversight. The bitmap layout is an implementation detail — if the allocator were to switch to a different metadata structure (e.g., linked list), the formula would change. By using loose bounds, the spec avoids coupling callers to the specific bitmap layout.

**Trade-off:** Callers cannot compute exact usable capacity from inputs alone. For example, with `len=4096, block_size=64`, the body yields 63 data blocks, but the spec allows anywhere from 1 to 64 (constrained only by inv's `end_addr > start_addr`).

**Severity:** Low-medium — most callers interact through allocate/deallocate and don't need exact layout. But callers managing multiple slabs in a shared memory region, or reasoning about capacity, would be blocked.

---

## Gap 4: `allocate` — Error code unconstrained (2 TPs)

**Target:** `allocate`  
**φ:** gap_5 ×2

**Problem:** The `allocate` spec uses `Err(_)` wildcard. The body returns a specific error code from `Bitmap::alloc`, but callers can't distinguish "slab full" from other hypothetical errors.

**Fix:** `Err(e) => e.code == ErrorCode::ResourceBusy` (or whatever Bitmap::alloc returns)

**Severity:** Low — callers know the state is unchanged on error, but can't pattern-match on error type.

---

## Gap 5: `deallocate` — Error code unconstrained (8 TPs)

**Target:** `deallocate`  
**φ:** neg_8 ×4, gap_6 ×4

**Problem:** The `deallocate` spec uses `Err(_)` wildcard. The body returns `ErrorCode::BadAddress` for all three failure modes (out-of-bounds, unaligned, already-free). Callers can't distinguish a double-free from an invalid pointer.

**Fix:** `Err(e) => e.code == ErrorCode::BadAddress`

**Severity:** Low — same pattern as Gap 4.

---

## Gap 6: `allocate` — Nondeterministic block selection (4 TPs → **reclassified as FP**)

**Target:** `allocate`  
**φ:** neg_10 ×3, gap_4 ×3

**Problem:** The spec says the returned addr is some member of `free_addrs` but doesn't specify which. The body implements first-fit (lowest index in bitmap via `Bitmap::alloc`).

**Assessment: FALSE POSITIVE (design choice, not a bug).**

Nondeterministic allocation is standard allocator spec practice. The spec is intentionally *more general* than the implementation — it permits any selection strategy (first-fit, best-fit, LIFO, random), which means the spec remains valid if the implementation changes strategy later. Callers should not depend on allocation order.

All functional correctness guarantees are present:
- Returned address is genuinely free ✅
- Address is properly aligned ✅
- State correctly updated (moved from free to allocated) ✅
- Address in valid range (via inv) ✅

Exposing first-fit semantics (`forall|a| free_addrs.contains(a) ==> addr <= a`) would lock the implementation to a specific strategy — this is generally undesirable in spec design.

**Severity:** N/A — not a real gap.

---

## Gap 7: `SlabView::inv()` — No totality / partition guarantee (3 TPs)

**Target:** `SlabView::inv()` (invariant, not a specific exec function)  
**φ:** gap_7 ×3

**Note on classification:** These φ were generated against `allocate`'s spec frame (since the pipeline only targets exec functions), but the underlying gap is in `SlabView::inv()` itself — a shared invariant that affects all three functions.

**Problem:** `SlabView::inv()` enforces disjointness but not completeness — it doesn't require every block-aligned address in `[start_addr, end_addr)` to be in `free_addrs ∪ allocated_addrs`. Blocks can "disappear" — exist in neither set.

**Example:**
```
region: [0x1040, 0x1200), block_size = 64
block-aligned addrs: {0x1040, 0x1080, 0x10C0, 0x1100, 0x1140, 0x11C0}  (7 blocks)

allocated = {0x1040}
free      = {0x1080, 0x10C0}

0x1100, 0x1140, 0x11C0 → in neither set — "lost"
```

This state satisfies `SlabView::inv()`: disjointness ✅, all addrs in range ✅, all addrs aligned ✅. But 4 blocks have vanished.

**Impact:** Callers can't prove `allocated.len() + free.len() == capacity`. They can't prove that a non-full slab has free blocks available. This is the **root cause** behind part of Gap 2 — if totality held and `allocated == empty`, callers could derive `free.len() == capacity > 0`.

**Body guarantees:** The bitmap has exactly `num_data_blocks` bits, each either set (allocated) or unset (free). Every data block maps to exactly one set — a perfect partition. But `view()` is closed, so callers can't see this.

**Fix:** Add to `SlabView::inv()`:
```rust
&&& forall|a: usize| 
    (self.start_addr <= a < self.end_addr && a % self.block_size == 0) ==>
    (self.allocated_addrs.contains(a) || self.free_addrs.contains(a))
```

This upgrades disjointness to a **partition** — every block-aligned address is in exactly one set.

**Severity:** Medium-high — needed for capacity reasoning and liveness proofs. Root cause of several other gaps.

---

## Summary

| # | Target | Gap | Severity | Verdict |
|---|--------|-----|----------|---------|
| 1 | `from_raw_parts` | No success guarantee | High | TP |
| 2 | `from_raw_parts` | `free_addrs` unconstrained | High | TP |
| 3 | `from_raw_parts` | Loose address bounds | Low-med | TP (design choice) |
| 4 | `allocate` | Error code unconstrained | Low | TP |
| 5 | `deallocate` | Error code unconstrained | Low | TP |
| 6 | `allocate` | Nondeterministic selection | N/A | **FP** (design choice) |
| 7 | `SlabView::inv()` | No totality/partition | Med-high | TP |

**True gaps: 6** (Gaps 1–5, 7). **False positives: 1** (Gap 6).

---

## Pipeline Issues Found

1. **Brainstorm parsing bug (fixed):** `_parse_brainstorm` in slab script expected text format but LLM returned JSON → 0 properties. Fixed to parse JSON.
2. **Formalize timeout:** Batches 1/3/4 timed out on first attempt. Added retry (max 3) + timeout 1200s.
3. **Entailment check vacuous:** All 57 φ use assume-only bodies → trivially verify. Need assert-based entailment checking.
4. **Critic needed inv context:** First critic run missed that `SlabView::inv()` has disjointness → 3 false TPs. Re-critic with inv definition in prompt fixed this.

## False Positive Categories (25 critic FP + 1 reclassified)

- **Disjointness already in inv (4):** neg_6 ×4 — `SlabView::inv()` has `allocated_addrs.disjoint(free_addrs)`
- **Alignment already in inv (3):** neg_7 ×3 — inv enforces alignment, contradictory assumes
- **Nondeterminism is design choice (4+):** neg_10 / gap_4 — standard allocator spec practice
- **Contradictory assumes (misc):** Various φ with mathematically impossible assume combinations
