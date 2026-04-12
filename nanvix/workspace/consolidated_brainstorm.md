# Consolidated Brainstorm — After Alpha→Beta→Gamma

## Bitmap — Final Candidates (after Gamma review)

### Confirmed Gaps (to formalize):
1. **new() no liveness** — valid inputs can return Err (HIGH)
2. **Error code opacity** — new/set/clear/test/alloc/alloc_range all use Err(_) (HIGH)
3. **set() merges OOB + already-set in Err** (MEDIUM)
4. **clear() merges OOB + already-clear in Err** (MEDIUM)

### Rejected:
- set() Err on valid unset bit (Err guard constrains)
- alloc() on non-full (is_full() constrains)
- **alloc frame condition — EXISTS in spec** (v2 Gap 3 was WRONG)

### Design choices (not gaps):
- Nondeterministic alloc bit/range choice
- next_free abstracted away

## Slab — Final Candidates (after Gamma review)

### Confirmed Gaps:
1. **Totality missing in inv()** — free ∪ allocated ≠ all blocks (HIGH, ROOT CAUSE)
2. **from_raw_parts free_addrs unconstrained** (HIGH)
3. **from_raw_parts no liveness** — valid inputs don't guarantee Ok (MEDIUM)
4. **allocate error code unconstrained** — Err(_) (MEDIUM)
5. **deallocate error code unconstrained** — Err(_) (MEDIUM)
6. **deallocate conflates failure modes** (MEDIUM)
7. **start_addr/end_addr loose bounds** (LOW-MEDIUM)
8. **No free_addrs cardinality** (MEDIUM)
9. **from_raw_parts Err code assumption** — sub-components may use different codes (MEDIUM)

### Rejected:
- #2 (free_addrs only subset) — inv constrains range/alignment
- #11/#12 (ghost addresses) — inv constrains

### Design choices:
- Allocation order nondeterministic

## Sorted-Vec — Final Candidates (after Gamma review)

### Confirmed Gaps:
1. **insert(new) — value not structurally present** (HIGH)
2. **insert(replace) — old element stays, new not stored** (HIGH)
3. **insert(replace) — NEITHER old nor new structurally present** (HIGH)
4. **From<Vec> — no inv() guarantee** (HIGH)
5. **insert+get composition — unknown payload after insert** (HIGH)
6. **remove return not pinned to old sequence** (HIGH, NEW from Gamma)

### Rejected:
- Reverse frame (spurious elements) — counting argument kills it
- Remove reverse frame — length + frame pins it

### Key Theme:
All insert/remove gaps stem from sv_eq vs == mismatch.
remove gap is NEW — Gamma found it, Beta missed it.

## Enhanced vs Original Comparison

### bitmap
- v2 had 3 gaps: new liveness ✓, set liveness ✓, **alloc frame ✗ (FALSE POSITIVE)**
- Enhanced: 4 gap categories (liveness + error codes + merged Err + merged Err)
- **Correction: alloc frame condition EXISTS** — v2's "Critical" gap was wrong

### slab
- Original had 6 gaps: all confirmed by enhanced pipeline
- Enhanced adds: #9 (Err code assumption for sub-components)
- Root cause analysis: #17 (totality) is root of #1/#3/#9/#14

### sorted-vec
- Original had 2 gaps (insert structural presence)
- Enhanced adds: #3 (neither old nor new present), #6 (remove return not pinned)
- #4 (reverse frame) correctly killed by counting argument
