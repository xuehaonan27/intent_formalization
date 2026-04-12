# Slab Allocator — Meta-Prompter Spec Gap Brainstorm Strategy

## 1. Spec Structure Inventory

### Exec Functions & Their Specs

| Function | Style | Requires | Ensures |
|---|---|---|---|
| `from_raw_parts` | `#[verus_spec(result => ensures ...)]` | (none explicit — checks done at runtime) | Ok ⇒ inv(), block_size match, start_addr ≥ addr, end_addr ≤ addr+len, allocated = ∅; Err ⇒ code == InvalidArgument |
| `allocate` | `#[verus_spec(result => requires/ensures ...)]` | old(self).inv() | self.inv(); Ok ⇒ addr was free, view updated with insert/remove; Err ⇒ free_addrs was empty, view unchanged |
| `deallocate` | `#[verus_spec(result => requires/ensures ...)]` | old(self).inv() | self.inv(); Ok ⇒ addr was allocated, view updated; Err ⇒ addr not allocated, view unchanged |

### SlabView::inv() — What It Constrains
- block_size > 0
- start_addr, end_addr aligned to block_size
- end_addr > start_addr
- All addresses in allocated_addrs and free_addrs are in [start_addr, end_addr) and aligned
- allocated_addrs ∩ free_addrs = ∅ (disjointness)

### What inv() Does NOT Constrain
- No totality: Does NOT require free_addrs ∪ allocated_addrs = {all valid block addrs}
- No cardinality bound
- No relationship between (end_addr - start_addr)/block_size and set sizes

### view() — CLOSED
### Other: assume_specification on pointer ops, axiom_align_of_u8_is_1

## 3. Gap Category Checklist (Ranked)

### Tier 1: Almost Certain Gaps
1. **Totality** — inv has disjointness but no partition
2. **Constructor doesn't specify free_addrs** — allocated=empty but free_addrs unknown
3. **Error codes wildcarded** — Err(_) in allocate and deallocate

### Tier 2: Likely Gaps
4. **start_addr/end_addr are bounds, not exact** — >= and <= rather than ==
5. **No free_addrs cardinality** — can't reason about block count

### Tier 3: Worth Checking
6. **Deallocate error collapses failure modes** — ptr-out-of-range vs already-free vs unaligned

### Likely FP (inv covers)
- Disjointness, alignment, address range, block_size > 0, end > start
