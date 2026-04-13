# Spec Testing Pipeline — Comprehensive Results

**Date:** 2026-04-13
**Project:** Specification completeness evaluation for Verus-verified Rust code
**Modules tested:** Bitmap, Slab Allocator, SortedVec (all from Nanvix OS)

---

## 1. Pipeline Evolution

### v1 — Manual (2026-03-26)
- Hand-written phi tests, 6 total for bitmap only
- No automated brainstorm, no critic

### v2 — Automated (2026-03-30 ~ 04-09)
- 5-step pipeline: Extract → Brainstorm → Formalize → Entailment → Critic
- Single LLM per step, no adversarial review
- Applied to bitmap (03-30), slab (04-09), sorted-vec (04-12)

### v3 — Enhanced with Agentic Reasoning (2026-04-12 ~ 04-13)
- Multi-agent protocol: Alpha(Meta-Prompter) → Beta(Reasoner) → Gamma(Verifier)
- Adversarial review at brainstorm and critic stages
- Task Force (Docker agents) for independent validation

---

## 2. Results by Module

### 2.1 Bitmap

**Source:** `nanvix/src/libs/bitmap/` — 8 exec functions

| Metric | v1 (manual) | v2 (auto) | Enhanced |
|--------|-------------|-----------|----------|
| φ generated | 6 | 55 | ~16 |
| Verified (entailed) | 2 | 18 | 2 |
| Critic TP | 2 | 14 | N/A |
| Critic FP (auto) | 4 | 4 | N/A |
| **FP after manual review** | — | **+1 (alloc frame)** | **Caught by Gamma** |
| **Distinct true gaps** | **2** | **3 → 2** | **2** |

**True gaps (confirmed):**

| # | Function | Gap | Severity | v1 | v2 | Enhanced |
|---|----------|-----|----------|----|----|----------|
| B1 | `new` | No liveness guarantee — valid inputs can return Err | High | ✅ | ✅ | ✅ |
| B2 | `set` | No liveness — `Err(_) => true` has zero constraints | High | ❌ | ✅ | ✅ |
| B3 | all fns | Error codes unconstrained — `Err(_)` wildcard | Medium | ❌ | partial | ✅ |

**False positives corrected:**

| FP | Claimed by | Corrected by | Issue |
|----|-----------|-------------|-------|
| `alloc` missing frame condition (v2 "Critical") | v2 pipeline critic | Enhanced Gamma | Spec HAS `forall\|i\| i!=index ==> is_bit_set(i)==old.is_bit_set(i)`. v2 critic missed it. |
| `alloc` nondeterministic bit choice | v2 pipeline | Manual review (04-09) | Deliberate design choice, not a gap |
| `alloc` always returns index 0 | v1 manual | v1 manual | Same — design choice |

### 2.2 Slab Allocator

**Source:** `nanvix/src/libs/slab/` — 3 exec functions (from_raw_parts, allocate, deallocate)

| Metric | v2 (auto) | Enhanced |
|--------|-----------|----------|
| φ generated | 97 (v2+v3) | ~14 |
| Verified (entailed) | 97 (all — assume-only bodies) | N/A |
| Critic TP (auto) | 32 | N/A |
| Critic FP (auto) | 25 | N/A |
| **FP after manual review (Tianyu + Lem)** | **+1 (nondeterminism)** | **0 new** |
| **Distinct true gaps** | **6** | **6 (confirmed)** |

**True gaps (confirmed):**

| # | Function | Gap | Severity |
|---|----------|-----|----------|
| S1 | `from_raw_parts` | No success guarantee — no requires, any input can Err | High |
| S2 | `from_raw_parts` | `free_addrs` unconstrained — allocated=empty but free=? | High |
| S3 | `from_raw_parts` | Loose address bounds — `>=`/`<=` instead of `==` | Low-med |
| S4 | `allocate` | Error code unconstrained — `Err(_)` wildcard | Low |
| S5 | `deallocate` | Error code unconstrained — `Err(_)` wildcard | Low |
| S6 | `SlabView::inv()` | No totality — `free ∪ allocated ≠ all blocks` | Med-high |

**Root cause:** S6 (totality) drives S1, S2. If inv had `forall|a| aligned(a) && in_range(a) ==> free.contains(a) || allocated.contains(a)`, then S2 auto-resolves.

**False positives corrected during manual review (04-09):**

| FP | Claimed by | Corrected by | Issue |
|----|-----------|-------------|-------|
| Nondeterministic allocation order (4 φ) | v2 critic (TP) | Tianyu + Lem manual review | Design choice |
| free_addrs outside data region (#11, #12) | v2 brainstorm | Lem manual review | inv() constrains range |
| Re-allocatability after dealloc (#10) | v2 brainstorm | Beta self-correction | Set reasoning works |
| ghost addresses in free_addrs (#11) | v2 brainstorm | Gamma review | inv() constrains alignment |

### 2.3 SortedVec

**Source:** `nanvix-verus/src/libs/sorted-vec/` — 14 verified exec functions

| Metric | v2 (first pass) | Enhanced |
|--------|-----------------|----------|
| φ generated | 4 | ~12 |
| Verified (entailed) | 2 | 4 |
| Rejected by Verus | 2 | 1 |
| **Distinct true gaps** | **2** | **4 (+2 new)** |

**True gaps (confirmed, all Verus-verified):**

| # | Function | Gap | Severity | v2 | Enhanced |
|---|----------|-----|----------|----|----|
| V1 | `insert` (new) | Value not structurally present — `spec_contains` (sv_eq) ≠ `Seq::contains` (==) | High | ✅ | ✅ |
| V2 | `insert` (replace) | Old element stays, new not stored | High | ✅ | ✅ |
| V3 | `insert` (replace) | Neither old nor new present — third sv_eq element | High | ❌ | ✅ **NEW** |
| V4 | `remove` | Return value not pinned to old sequence | High | ❌ | ✅ **NEW** |

**Root cause:** All 4 gaps stem from the same issue — spec uses `spec_contains` (sv_eq/Ord-equality) where `Seq::contains` (structural ==) is needed.

**Correctly rejected (non-gaps):**

| Candidate | Rejected by | Reason |
|-----------|------------|--------|
| Reverse frame — spurious elements | Gamma (counting argument) | N old elements + len=N+1 → only 1 free slot, forced to be sv_eq to value |
| Remove reverse frame — new elements appear | Gamma (counting argument) | N-1 elements + len=N-1 → zero free slots |
| Return non-old element on insert duplicate | Verus | `pre_seq.contains(result.unwrap())` blocks it |

---

## 3. Aggregate Statistics

### Gap Discovery

| Module | v1 | v2 | Enhanced | Net change (v2→Enhanced) |
|--------|----|----|----------|--------------------------|
| Bitmap | 2 | 3 → **2** | 2 | **-1 FP corrected** |
| Slab | — | 6 | 6 | 0 (confirmed) |
| SortedVec | — | 2 | 4 | **+2 new gaps** |
| **Total** | **2** | **11 → 10** | **12** | **+2 new, -1 FP** |

### False Positive Analysis

| Stage | Count | Source |
|-------|-------|--------|
| Critic auto-FP (bitmap v2) | 4 | Correctly filtered by critic |
| Critic auto-FP (slab v2) | 25 | Correctly filtered by critic |
| Manual review FP: bitmap alloc frame | 1 | **v2 missed → Enhanced Gamma caught** |
| Manual review FP: slab nondeterminism | 1 | Tianyu + Lem manual review |
| Manual review FP: slab inv-covered (#11,#12) | 2 | Lem manual → Enhanced Gamma confirmed |
| Enhanced Gamma FP kills (sorted-vec) | 1 | Counting argument |
| Enhanced Gamma FP kills (bitmap) | 2 | inv() usage tie-in |
| **Total FPs caught** | **36** | |

### Pipeline Precision

| Pipeline | φ verified | True gaps | Precision (post-critic) |
|----------|-----------|-----------|------------------------|
| v2 bitmap | 18 | 14 TP → 3 gaps (1 FP) | 78% → **67% after manual** |
| v2 slab | 97 | 32 TP → 6 gaps (1 FP) | 56% → **86% after manual** |
| Enhanced sorted-vec | 4 verified | 4 gaps | **100%** |

---

## 4. Key Findings

### Most Impactful
1. **Bitmap alloc frame FP corrected** — v2 reported this as "Critical" severity. It was wrong. The spec has the frame condition. Would have misled paper reviewers.
2. **SortedVec sv_eq vs == chasm** — a systematic gap affecting all insert/remove operations on types with non-trivial Ord implementations.
3. **Slab totality as root cause** — one missing invariant clause drives 4 of 6 gaps.

### Methodology Insights
1. **Adversarial Verifier (Gamma) is the highest-value role** — found 1 FP correction + 2 new gaps + multiple FP kills
2. **LLM spec-copy is the #1 error source** — must use AST extraction or original types
3. **Counting argument** is a powerful FP killer for frame condition claims
4. **Proof fn must use original types** (e.g., `SortedVec<T>` not `Seq<T>`) to avoid spec rewriting

---

## 5. File Inventory

| File | Contents |
|------|---------|
| `nanvix/workspace/bitmap/findings_v2.md` | Bitmap v2 pipeline report |
| `nanvix/workspace/bitmap/enhanced/` | Enhanced pipeline artifacts |
| `nanvix/workspace/slab/spec-gaps-final.md` | Slab comprehensive gap report |
| `nanvix/workspace/slab/enhanced/` | Enhanced pipeline artifacts |
| `nanvix/workspace/sorted-vec/spec-gaps-final.md` | SortedVec gap report |
| `nanvix/workspace/sorted-vec/enhanced/taskforce_phi_tests.rs` | Final Verus phi tests (v5) |
| `nanvix/workspace/enhanced_final_report.md` | Enhanced pipeline comparison |
| `nanvix/workspace/consolidated_brainstorm.md` | All brainstorm candidates |
| `skills/spec-testing/SKILL.md` | Skill definition (v0.7.0) |
