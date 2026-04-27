# Run report — 2026-04-27

Session goals (set by user):
1. Re-run results to confirm soundness fix `a5e4f667` ("Fix witness soundness:
   load global Function-Axioms into z3 prelude") actually took.
2. Investigate and fix the bug where the LLM equal-policy did not recognise
   opaque-equal situations on the nanvix config.

VeruSAGE testing-support (originally proposed config-driven extension) was
deferred — the colleague had already shipped a working CLI-driven backend.

---

## 1. Bug found and fixed

**Surface:** `spec-determinism-regen --use-llm-policy` produced a `custom_body`
that referenced `post1_self_@.<field>`. The synthesized equal-fn signature
declares `post1_self_: <ViewType>` — i.e. the parameter is **already** the
spec view (the wrapper applies `@` at the call site). Re-applying `@` is a
type error: `method 'view' not found in BitmapView`.

**Root cause:** the LLM faithfully copied the few-shot Example C in
`spec_determinism/policy_llm.py:_FEW_SHOT`, which used `post1_self_@.allocations…`
— contradicting the actual generator convention in
`spec_determinism/gen_det.py:244-250`.

**Fix** (`spec_determinism/policy_llm.py`, +28/-7):
- Schema doc updated to explicitly state "the parameter is ALREADY the view
  type" and to forbid `post1_<name>@`/`post2_<name>@` in custom bodies.
- Example C corrected to use `post1_self_.allocations…`.
- Added `_sanitize_custom_body()` — defensive regex strip of any stray
  `post[12]_<id>@` from incoming LLM responses (belt-and-suspenders).
- Patched the 3 already-saved artifacts in place
  (`results/artifacts/{bitmap__alloc,slab__allocate}/det_spec.json` plus
  their inlined `equal_fn_def`).

**Cache hygiene:** before any LLM clobber, backed up
`results/artifacts/` → `results/artifacts.pre-llm-policy/` so the
pre-existing default-policy snapshot is preserved for rollback / comparison.

---

## 2. Validation

### 2a. Atmosphere soundness fix (commit `a5e4f667`)

Sample-tested 3 of the 121 atmosphere targets that previously showed the
trivial spurious witness pattern `r1=0 ∧ r2=0 ∧ !equal(r1, r2)`. All three
now return **`rounds=1, assumes=[]`** — genuinely R0 deterministic.

| target | pre-fix | post-fix |
|---|---|---|
| `…impl2__add_io_mapping_4k :: page_ptr2page_index` | rounds=20, trivial witness | rounds=1, no witness |
| `…impl2__add_io_mapping_4k :: page_index2page_ptr` | rounds=20, trivial witness | rounds=1, no witness |
| `…impl2__free_page_4k :: page_ptr2page_index`     | rounds=20, trivial witness | rounds=1, no witness |

**Conclusion:** the soundness fix works. `results-verusage/atmosphere/SUMMARY.md`
and `OBSERVATIONS.md` are **pre-fix snapshots** — their numbers should be
treated as stale until atmosphere is re-run end-to-end (~22h wall, deferred).

### 2b. Slab::allocate witness — investigated, not a soundness leak

The 127-round witness has `pre_self_.free_addrs == {0}` for a `[0, 2)` slab
with `block_size=1, allocated={}`. This *looked* like the same family as
the atmosphere spurious witnesses, but is in fact a real spec gap.

Verified:
- `Function-Axioms slab::Slab::inv` is at byte 429045 in `root.smt2`.
- It is **outside** all `(push)/(pop)` blocks → it IS loaded into the
  schema-search z3 prelude.

Read the actual `Slab::inv()` definition in
`/home/v-nongyudi/nanvix/src/libs/slab/src/lib.spec.rs`. It only requires:
- elements of `free_addrs` and `allocated_addrs` are aligned and in-range
- `allocated_addrs ∩ free_addrs == ∅`

It does **not** require `free_addrs ∪ allocated_addrs == { all aligned slots in [start, end) }`.

So a slab `[0, 2)` with `free={0}` and slot 1 simply unaccounted-for is a
legitimate `inv()` model. **The witness is a real spec finding** —
same family as the `slab::from_raw_parts` gap already documented in
`FINDINGS.md` §9.

### 2c. Nanvix pipeline regression check

Ran all 11 non-kernel functions (kheap excluded — proof.rs files missing).
All complete successfully; default-policy targets are unchanged from
the FINDINGS.md baseline:

| Function                | Prior rounds | Now | Note |
|---|---:|---:|---|
| `bitmap::number_of_bits`|    1 |    1 | unchanged |
| `bitmap::new`           |   20 |   20 | unchanged |
| `bitmap::from_raw_array`|    1 |    1 | unchanged |
| **`bitmap::alloc`**     | **65** | **1** | **R0 det** under LLM cardinality policy |
| `bitmap::alloc_range`   |   72 |   72 | unchanged (default policy) |
| `bitmap::set` / `clear` / `test` | 1 | 1 | unchanged |
| `slab::from_raw_parts`  |   67 |   67 | unchanged |
| **`slab::allocate`**    | **94** | **127** | LLM custom_body changed comparison; real spec gap |
| `slab::deallocate`      |    1 |    1 | unchanged |

All 8 default-policy targets returned identical round counts → the prompt
fix is scoped to LLM-touched artifacts and did not regress anything.

---

## 3. Bugs not investigated / out of scope

- **Kernel functions** (`kernel::allocate`, `kernel::deallocate`,
  `kernel::from_raw_parts`, `kernel::layout_to_allocator`) — user has a
  different version of the colleague's `kheap.{spec,proof}.rs`; the
  files are missing. Skipped per user direction.
- **Other 401 verus_errors** in `results-verusage/OBSERVATIONS.md` — these
  are gen_det generator surface bugs (`type annotations needed` ×173,
  `&mut T` returns ×22, opaque-datatype field reads ×13). Independent of
  the LLM-policy fix; not addressed in this session.
- **Full atmosphere re-run** — sample-validated the soundness fix on 3 of
  121 trivial-witness cases; full re-run (~22h wall) deferred.

---

## 4. Artifacts on disk

| Path | State |
|---|---|
| `results/artifacts/` | LLM-touched: `bitmap__alloc`, `slab__allocate`, `kernel__layout_to_allocator`. Other 12 unchanged from pre-existing baseline. |
| `results/artifacts.pre-llm-policy/` | Backup snapshot of the original 15 (default-policy) artifacts, taken before any LLM clobber. |
| `results/full_run.json` | 11 non-kernel results (this session). |
| `results-verusage/` | Untouched. SUMMARY.md / OBSERVATIONS.md are pre-`a5e4f667` (stale). |
| `spec_determinism/policy_llm.py` | Modified: prompt fix + sanitizer. |

---

## 5. Suggested next slices (priority order)

1. **Full atmosphere re-run** — confirms the 121 trivial witnesses → 0 at scale,
   gives us trustworthy atmosphere numbers. Cost: ~22h wall, single command.
2. **LLM-policy on remaining 5 nanvix functions** (`bitmap::alloc_range`,
   `bitmap::new`, `slab::from_raw_parts`, etc.) — would extend coverage of
   the prompt fix and may flip more "loose-by-design" verdicts to "tight".
3. **Tighten `Slab::inv()`** — add `free_addrs ∪ allocated_addrs ==
   spec_aligned_slots(start, end, block_size)`. Closes both
   `slab::from_raw_parts` and `slab::allocate` witnesses.
4. **Restore `kheap.{spec,proof}.rs`** to the version the pipeline expects,
   so kernel functions become testable again.
