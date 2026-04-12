# Sorted-Vec — Meta-Prompter Strategy

## Priority Ranking

### 🔴 Priority 1: sv_eq / == Chasm (PRIMARY)
1. **Structural presence after insert** — spec_contains (Ord) ≠ Seq::contains (structural)
2. **Replacement guarantees** — duplicate insert: new value structurally present?
3. **"Nothing extra" reverse frame** — does insert only add the expected element?

### 🟡 Priority 2: Frame Completeness
4. **Reverse frame missing** — no `forall|v| self@.contains(v) ==> old@.contains(v) || v == value`
5. **From<Vec> verification black hole** — no inv() guarantee

### 🟢 Priority 3: Low Risk
6. Uniqueness implicit (derivable from inv)
7. Boundary cases well-covered

## Key Insight
The spec freely mixes sv_eq and == without bridging them. Frame uses ==, presence uses sv_eq.
This asymmetry is the primary attack surface.

## FP Warnings
- No-duplicates: follows from inv + strictly sorted
- Overflow: Vec ops modeled as infallible
- remove !spec_contains: sound because at most one sv_eq element
