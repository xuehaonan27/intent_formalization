# Spec-Debug — Manual Patch Audit

For each known nanvix incompleteness, 5 different attempted spec patches were
applied and scored under METRICS.md. Each section lists the baseline witness,
the patch, the post-patch witness, and the metric values. Audit one patch at
a time.

**Workflow per patch** (per `/tmp/spec-debug-exp/run_one.sh` and `run_kheap.sh`):
1. Restore baseline `lib.rs` / `kheap.rs`.
2. Apply patch (textual replace of original ensures block).
3. `spec-determinism-regen <crate>::<fn>` (refreshes `det_check_template`).
4. `spec-determinism-run <crate>::<fn>` → witness.
5. `cargo +nightly-2025-12-08 verus build -p <crate>` with proper flags.
6. Record. Revert.

**Policy**: spec-determinism's default. Driving = assumes that witness the
`!det_*_equal(r1, r2)` distinguishability axis (discriminant pair, or any
field appearing in `det_*_equal` whose two values differ). Collateral =
input narrowing, error-code, error-reason, fields not in equal_fn.

**Hard gates** (METRICS.md): `policy_verdict.kind == "valid"`,
`impl_still_verifies`, `no_new_admissions_in_impl`, `symbol_table_stable`,
`equal_fn_def_stable`. Tier-2 score: `(driving_closed_ratio, ¬new_witness_driving)`.

**Status legend** in tables:
- ✅ pass  ❌ fail  ⚠️ syntax/type error  •  numeric values are
  `n_rounds_after / closed_count / driving_closed_ratio` where applicable.

---

## Case 1 — `bitmap::new`

### Baseline witness (n_rounds=20, schemas=271)

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

`det_new_equal ≡ (r1 is Ok) == (r2 is Ok) && (r1 is Ok ==> (r1->Ok_0)@ == (r2->Ok_0)@)`.

Driving = `{r1 is Ok, r2 is Err}` (the discriminant pair).
Collateral = everything else.

### Patches

#### B1 — constrain `Err.code` to set `{InvalidArgument, OutOfMemory}`

```rust
result matches Err(e) ==> {
    ||| e.code == ErrorCode::InvalidArgument
    ||| e.code == ErrorCode::OutOfMemory
},
```

Post-patch witness: same shape; only `r2->Err_0.code` shifts `OperationNotPermitted → OutOfMemory`. n_rounds 20→31.

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** |
| closed_count (raw) | 1 |
| new_witness_driving | True |
| symbol_table_stable | ✅ (271=271) |
| impl_still_verifies | ✅ |
| **verdict** | **Reject** — pure collateral motion, driving untouched |

#### B2 — constrain `Err.code` to single value `InvalidArgument`

```rust
result matches Err(e) ==> e.code == ErrorCode::InvalidArgument,
```

Post-patch witness: `Err.code` → `InvalidArgument`. Driving still `(Ok, Err)`. n_rounds 20→41.

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** |
| impl_still_verifies | **❌** — `RawArray::new(len)?` can return `Err(OutOfMemory)`, violating new postcondition |
| new_witness_driving | True |
| **verdict** | **Reject** — over-restrictive on collateral, breaks impl |

#### B3 — pin `Err.reason` to empty

```rust
result matches Err(e) ==> e.reason@.len() == 0,
```

Post-patch witness: same as baseline (no closure). n_rounds 20→20.

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** |
| impl_still_verifies | **❌** — impl's `Err::new` calls use literals like `"invalid length"` |
| new_witness_driving | True |
| **verdict** | **Reject** — pure over-spec, no driving impact, breaks impl |

#### B4 — reverse-implication on `Err`

```rust
result is Err ==> {
    ||| number_of_bits == 0
    ||| number_of_bits >= u32::MAX
    ||| number_of_bits % (u8::BITS as usize) != 0
},
```

Post-patch witness: **`new: deterministic (R0 unsat)`**, n_rounds=1, assumes=[].

| metric | value |
|---|---|
| driving_closed_ratio | **2/2** ✅ |
| impl_still_verifies | **❌** — `RawArray::new(len)?` exit branch fails the new postcondition (impl can OOM at any input) |
| symbol_table_stable | ✅ |
| no_new_admissions_in_impl | ✅ |
| **verdict** | **Reject by Axis E**, but the failure is the diagnostic — see "Lesson" below |

#### B5 — reverse-implication with OOM carve-out

```rust
result matches Err(e) ==> {
    ||| number_of_bits == 0
    ||| number_of_bits >= u32::MAX
    ||| number_of_bits % (u8::BITS as usize) != 0
    ||| e.code == ErrorCode::OutOfMemory
},
```

Post-patch witness: same shape as B1, `Err.code = OutOfMemory`. n_rounds 20→31.

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** |
| impl_still_verifies | ✅ |
| new_witness_driving | True |
| **verdict** | **Reject** — OOM carve-out leaves `(Ok, Err(OOM))` permanently free |

### Lesson — `bitmap::new` is policy-fixable, not spec-fixable

B4 closes driving completely (spec-determinism declares the function deterministic). The `RawArray::new` dependency is `external_body` and its spec admits `Err(OutOfMemory)` for any input. Therefore *any* spec strengthening that closes the `(Ok, Err)` driving will be rejected by Verus on the OOM exit path. **The right fix is at the policy level**: extend spec-determinism to treat `(Ok, Err(OOM))` as equivalent for allocator-fronting functions. This drives `policy_verdict.suggestion = { name = "errs_equivalent_with_oom_as_ok", note = "..." }`.

This is exactly the case Axis A.1 was designed to detect.

---

## Case 2 — `slab::from_raw_parts`

### Baseline witness (n_rounds=20, schemas=291)

```
len == 1
block_size == 1
r1 is Ok / r1->Ok_0@.{block_size==1, start_addr==0, end_addr==1, allocated_addrs==∅, free_addrs==∅}
r2 is Ok / r2->Ok_0@.{block_size==1, start_addr==0, end_addr==1, allocated_addrs==∅, free_addrs.len()==1, contains(0)}
!det_from_raw_parts_equal(r1, r2)
```

Driving = `{r1 is Ok, r2 is Ok}` AND `r1.free_addrs ≠ r2.free_addrs` (the field appearing in equal_fn whose values differ).
Collateral = `len`, `block_size`, `allocated_addrs == ∅` (both agree).

Note: this witness is impl-impossible (impl returns Err for `len=1, block_size=1` because `num_index_blocks >= total_num_blocks`); the spec is one-way `Err ==> condition`.

### Patches

#### S1 — five reverse implications (Verus-unfriendly form)

```rust
len < block_size * 2 ==> result is Err,
block_size == 0 ==> result is Err,
len == 0 ==> result is Err,
addr as usize == 0 ==> result is Err,
addr as usize % block_size != 0 ==> result is Err,
```

Post-patch witness: input shifts `len 1→2`, otherwise same Ok-vs-Ok with different `free_addrs`. n_rounds 20→67.

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** (driving shape preserved at higher input) |
| closed_count (raw) | 2 |
| impl_still_verifies | **❌** — `len<bs*2 ==> Err` postcondition fails at final Ok return; Verus needs nonlinear lemma `total_num_blocks≥2 ==> len≥2*block_size` |
| new_witness_driving | True |
| **verdict** | **Reject** — partial closure on input axis, driving migrates |

#### S2 — same idea with Verus-friendlier `len/block_size`

```rust
len / block_size < 2 ==> result is Err,
block_size == 0 ==> result is Err,
len == 0 ==> result is Err,
addr as usize == 0 ==> result is Err,
```

Post-patch witness: identical to S1 shape (len shifts 1→2). n_rounds 20→67.

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** |
| impl_still_verifies | **❌** — even with division form, postcondition unprovable; impl returns Ok for `len=block_size*2` while spec demands Err for `len/bs < 2` (which holds when `len=2*bs−1`, etc.); subtler than expected |
| **verdict** | **Reject** — same as S1 |

#### S3 — pin Ok-side `start_addr` exactly

```rust
result matches Ok(slab) ==> slab@.start_addr == addr as usize,
```

Post-patch witness: identical to baseline. n_rounds unchanged.

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** |
| impl_still_verifies | **❌** — impl uses `data_addr = addr.add(num_index_blocks * block_size)` for the slab's start; not equal to `addr` |
| **verdict** | **Reject** — wrong assumption about layout |

#### S4 — collateral Ok-side constraints

```rust
result matches Ok(slab) ==> {
    &&& slab@.end_addr <= addr as usize + len
    &&& (slab@.end_addr - slab@.start_addr) % block_size == 0
    &&& slab@.free_addrs.finite()
},
```

| metric | value |
|---|---|
| driving_closed_ratio | n/a |
| impl_still_verifies | ⚠️ **type error** — Verus `int` vs `usize` mismatch in `% block_size`; would require `% block_size as int` |
| **verdict** | **Reject** — patch fails to type-check before Verus reasoning runs |

#### S5 — pin Ok-side `free_addrs == ∅` (over-restrictive)

```rust
result matches Ok(slab) ==> {
    &&& slab@.allocated_addrs == Set::<usize>::empty()
    &&& slab@.free_addrs == Set::<usize>::empty()
},
```

Post-patch witness: r2 flips Ok→Err with `code is InvalidArgument`. So it forced the spec to require `free_addrs==∅` on Ok side, and the witness moved laterally to a different axis (Err-vs-Ok by impl rejecting len=1). n_rounds 20→64.

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** (driving shape changed: Ok-vs-Ok → Ok-vs-Err) |
| impl_still_verifies | **❌** — impl actually returns Ok with `free_addrs.len() > 0` for valid inputs; postcondition fails |
| new_witness_driving | True |
| **verdict** | **Reject** — patch contradicts impl; lateral motion, no real progress |

### Lesson — `slab::from_raw_parts` requires layout-aware spec

The driving is on Ok-side fields (`start_addr`, `end_addr`, `free_addrs`) being underspecified. To close it without breaking Verus you must pin them as functions of `(addr, len, block_size)` matching the impl's layout (`num_index_blocks`, `data_addr`, etc.). Any of S3/S4/S5 that *guesses* the layout breaks impl_verifies; S1/S2 only fence the input space, not the Ok-side fields, so the witness migrates. **The realistic path is iterative: introduce a spec helper `fn slab_layout(addr,len,bs) -> (start, end, count)` and pin Ok-side fields to it; this needs the LLM to read the impl** — which is exactly the regime spec-debug's "free repair, cargo path" design targets.

---

## Case 3 — `kernel::from_raw_parts` (Kheap)

### Current baseline witness (n_rounds=2461, schemas=519)

> NOTE: differs from `observations/v0/kernel__from_raw_parts/report.json` (which had `(Err, Err)` with different reason strings). The current nanvix workspace has uncommitted edits in `kheap.proof.rs`/`Cargo.toml`/`build/verus-version` that have changed the function's verifiable behaviour. The current baseline is `(Ok, Ok)` with differing per-slab fields.

Excerpted assumes:
```
addr == 0
size == 917504                (== MIN_HEAP_SIZE)
r1 is Ok
r1->Ok_0@.slabs.len() == 7
r1->Ok_0@.slabs[i].block_size == {8,16,32,64,128,256,512}
r1->Ok_0@.slabs[i].{start_addr, end_addr, allocated_addrs, free_addrs} pinned to specific values
r2->Ok_0@.slabs[i].{start_addr, end_addr} take different values from r1
!det_from_raw_parts_equal(r1, r2)
```

Driving = `(Ok, Ok)` Ok-side per-slab field divergence (start_addr / end_addr / free_addrs).
Collateral = the per-slab block_size sequence (impl pins these), per-slab `allocated_addrs == ∅`.

### Patches

> All five patches below were designed against the v0-documented `(Err, Err)` driving; they target `Err.reason`/`Err.code`. Under the current baseline they are *off-axis* and do not close the Ok-vs-Ok driving. Reported as-is for honesty; the takeaway is what they reveal about the misdirected attempts.

#### K1 — pin `Err.reason@.len() == 0`

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** (Ok-vs-Ok driving untouched) |
| impl_still_verifies | **❌** — impl uses non-empty reasons (`"unaligned start address"`, etc.); postcondition fails on every Err exit and on the Slab `?` propagation |
| **verdict** | **Reject** — wrong axis + impl-incompatible |

#### K2 — per-condition disjunction on `Err`

```rust
Err(e) => {
    &&& e.code == ErrorCode::InvalidArgument
    &&& {
        ||| addr as int % PAGE_SIZE as int != 0
        ||| size < MIN_HEAP_SIZE
        ||| size as int % MIN_HEAP_SIZE as int != 0
    }
}
```

Post-patch witness: dramatically smaller (n_rounds 2461→186). Suggests it pruned a lot of Err-side combinations, but driving is still Ok-vs-Ok.

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** (driving is Ok-vs-Ok; this patch only constrains Err-side) |
| closed_count (raw) | very high (Err-side branch heavily pruned) |
| impl_still_verifies | **❌** — Slab calls inside Kheap can return `Err(OOM)` via RawArray, violating the disjunction (same OOM problem as bitmap::new, propagated up) |
| **verdict** | **Reject** — off-axis closure on Err, driving on Ok-side preserved |

#### K3 — bound `Err.reason@.len() <= 64`

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** |
| impl_still_verifies | **❌** — same OOM-propagation issue as K1; also `e.code == InvalidArgument` is violated by Slab's `Err(OOM)` propagation |
| **verdict** | **Reject** — almost no semantic effect |

#### K4 — orthogonal reverse-implication on inputs

```rust
result is Err ==> {
    ||| addr as int % PAGE_SIZE as int != 0
    ||| size < MIN_HEAP_SIZE
    ||| size as int % MIN_HEAP_SIZE as int != 0
}
```

| metric | value |
|---|---|
| status | ⚠️ **patch generated invalid syntax** — extra closing brace from the `match`/`Err` arm replacement collided with the outer `verus!` block |
| **verdict** | **Reject** — would need a different patch site (outside the `match`) to be syntactically valid |

#### K5 — `Err.reason@.len() > 0`

| metric | value |
|---|---|
| driving_closed_ratio | **0/2** |
| impl_still_verifies | **❌** — Slab `Err` propagation produces strings empty-or-otherwise per dependency; same OOM-via-`?` issue |
| **verdict** | **Reject** — over-spec on a non-driving axis |

### Lesson — Kheap shares slab's structural problem AND inherits OOM from RawArray

Kheap's current Ok-vs-Ok driving is structurally identical to slab's: per-slab `start_addr`/`end_addr`/`free_addrs` underspecified. Independently, every `Err` exit through `Slab::from_raw_parts(...)?` can ultimately return `Err(OutOfMemory)` from `RawArray::new` — so any `Err.code == InvalidArgument` ensures will fail without the policy-level OOM-equivalence that bitmap::new also needs. **Two distinct fixes are required**: (a) policy-level OOM equivalence (same as Case 1); (b) layout-aware Ok-side pinning (same as Case 2). Neither was attempted in K1-K5; the off-axis patches were retained in this audit precisely to demonstrate what the metrics flag when an LLM picks the wrong axis.

---

## Cross-case summary

| Case | Closed driving? | Impl verifies? | Comment |
|---|---|---|---|
| B1 (Err.code set) | 0/2 | ✅ | Pure collateral; v0-style reading would mark this as ~progress |
| B2 (Err.code single) | 0/2 | ❌ | Over-restricts; impl OOMs |
| B3 (reason==∅) | 0/2 | ❌ | Pure over-spec |
| **B4 (Err==>bad_input)** | **2/2** | ❌ | Closes driving but breaks impl on OOM — diagnostic for policy fix |
| B5 (carve-out OOM) | 0/2 | ✅ | Soft; leaves OOM driving free |
| S1 (5 reverse impl) | 0/2 (lateral) | ❌ | Witness migrates, impl breaks |
| S2 (`len/bs < 2 ==> Err`) | 0/2 (lateral) | ❌ | Same as S1 |
| S3 (start_addr==addr) | 0/2 | ❌ | Wrong layout assumption |
| S4 (collateral Ok-side) | n/a | ⚠️ | Type error |
| S5 (free_addrs==∅) | 0/2 (lateral) | ❌ | Contradicts impl |
| K1 (reason==∅) | 0/2 | ❌ | Off-axis |
| K2 (per-condition Err) | 0/2 | ❌ | Off-axis but heavy collateral pruning |
| K3 (reason length) | 0/2 | ❌ | Off-axis |
| K4 (reverse on inputs) | n/a | ⚠️ | Patch syntax broken |
| K5 (reason.len()>0) | 0/2 | ❌ | Off-axis |

### Validation of the metrics framework

1. **`driving_closed_ratio` ≠ `closed_count`**: B1, K2 both close many collateral assumes while leaving driving intact. Raw count would falsely report progress.
2. **`new_witness_driving` catches lateral motion**: S1/S2/S5 illustrate this directly.
3. **`impl_still_verifies` is the active gate**: B2, B4, B5(no), K1-K3, K5, S1-S5 — most rejections come from this axis. B4 is the most informative case: closing driving forces the impl gate to expose a deeper truth.
4. **`policy_verdict` (Axis A.1) gap is real**: bitmap::new B4 and (transitively) Kheap K2 both demand a policy refinement, not a spec patch.
5. **Patch syntax errors do happen** (S4, K4): the framework needs a hard pre-check (rustc parse) before counting metrics.

## Recommended follow-ups

- bitmap::new: file `policy_verdict.suggestion = oom-as-ok`. Update spec-determinism FINDINGS.md classification from "Missing ensures" to "Policy-coverage gap".
- slab::from_raw_parts and Kheap: design layout-aware spec helpers; defer until prompt design lets the LLM read impl freely.
- METRICS.md: codify the "function declared deterministic ⇒ all baseline driving closed" simplification of Axis A.
- Patch harness: add a parse-only `cargo check` (or Verus syntax-only pass) before metric scoring; treat parse failures as a separate "patch invalid" bucket.

## Provenance

All raw logs at `/tmp/spec-debug-exp/{B1..B5,S1..S5,K0_baseline,K1..K5}/`:
- `regen.log` — `spec-determinism-regen` output
- `det.log` — `spec-determinism-run` output (includes `RESULT:` line)
- `verus.log` — `cargo verus build` output

Sources backed up at `/tmp/spec-debug-exp/{bitmap_lib,slab_lib,kheap}.rs.bak` and restored after each run.
