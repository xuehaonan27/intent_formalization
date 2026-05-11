# Corpus rerun comparison

| | commit |
|---|---|
| baseline  | `42c1248` |
| candidate | `33bd09a` |

Definitions:
- **ok_with_witness** — Verus accepted the equal-fn but z3 emitted
  a counterexample (`status=="ok" AND assumes!=[]`). The A-2
  false-positive metric.
- **fixed** — was ok_with_witness in baseline, now plain ok in
  candidate. **Wins go here.**
- **witness → verus_error** — was ok_with_witness, now Verus
  rejects the equal-fn. View compiled but blocked verification;
  not a clean win.
- **regressed** — was clean ok (no witness) in baseline, now
  verus_error in candidate. **This number must be ~0**
  to consider the change safe to land.

## Per-project totals

| project | n | ok | verus_err | ok_with_witness (base → cand) | Δ witness |
|---|---:|---:|---:|---|---:|
| anvil-controller | 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 |
| anvil-library | 1 | 0 → 0 | 1 → 1 | 0 → 0 | 0 |
| atmosphere | 1363 | 1262 → 1262 | 100 → 100 | 289 → 288 | **-1** |
| ironkv | 214 | 170 → 171 | 44 → 43 | 76 → 76 | 0 |
| memory-allocator | 16 | 15 → 15 | 1 → 1 | 9 → 1 | **-8** |
| node-replication | 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 |
| nrkernel | 8 | 6 → 6 | 2 → 2 | 1 → 0 | **-1** |
| storage | 43 | 0 → 0 | 43 → 43 | 0 → 0 | 0 |
| vest | 2 | 2 → 2 | 0 → 0 | 1 → 1 | 0 |
| **TOTAL** | **1647** | **1455 → 1456** | **191 → 190** | **376 → 366** | **-10** |

## Per-project A-2 transitions


### atmosphere

**fixed** (1 targets — witness → ok):
- `atmosphere__verified__pagetable__pagetable__pagemap__impl0__set__set`

### ironkv

**fixed** (1 targets — witness → ok):
- `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__parse_command_line_configuration`

### memory-allocator

**fixed** (8 targets — witness → ok):
- `memory-allocator__verified__commit_mask__commit_mask__impl__clear__clear`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create__create`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create__create_full`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create_empty__create_empty`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create_full__create_full`
- `memory-allocator__verified__commit_mask__commit_mask__impl__create_intersect__create_intersect`
- `memory-allocator__verified__commit_mask__commit_mask__impl__empty__empty`
- `memory-allocator__verified__commit_mask__commit_mask__impl__set__set`

### nrkernel

**fixed** (1 targets — witness → ok):
- `nrkernel__verified__spec_t_mmu__defs__spec_t__mmu__defs__x86_arch_exec__x86_arch_exec`

## Final transition matrix (PR-D4, post-quarantine)

```
                  candidate
baseline      ok   ok_w  verus  crash
ok          1079      0      0      0
ok_w          11    365      0      0
verus_err      0      1    190      0
crash          0      0      0      1
```

**Reading.**

- **11 clean fixes** (ok_w → ok) — matches the prediction exactly.
  Per-target list and root cause: see *Case studies* below.
- **0 clean regressions** (ok → verus_error) — view registry no
  longer breaks any previously-passing target.
- **1 soft improvement** (verus_error → ok_w) —
  `ironkv/host_model_receive_packet`: was a Verus parse failure in
  baseline (an upstream injected view triggered the failure), now
  compiles cleanly but z3 still emits an assume for the equal-fn.
  This explains the apparent "−10" net witness count (11 fixes
  − 1 new witness = 10), but it is a strict improvement, not a
  regression.
- **1 runner_crash** stable on the same target
  (`atmosphere/get_payload_as_va_range`); pre-existing, not
  view-related.

## Summary numbers

| metric | baseline (42c1248) | candidate (33bd09a) | Δ |
|---|---:|---:|---:|
| **ok_with_witness (A-2 false positives)** | **376** | **366** | **−10** |
| verus_error | 191 | 190 | −1 |
| ok (clean) | 1079 | 1090 | +11 |
| runner_crash | 1 | 1 | 0 |
| Total targets | 1647 | 1647 | 0 |

The A-2 metric drops from 22.8 % (376/1647) to 22.2 % (366/1647)
— a 2.7 % relative drop on the whole-corpus baseline.  Per the
project distribution this concentrates on `memory-allocator` (9 → 1
witnesses; 88.9 % drop) and on the four scope types that already
have hand-written `Vec→Seq` view structure (CommitMask, PageMap,
Constants, ArchExec).

## Case studies (the 11 clean fixes)

All 11 fixes follow the same algebraic recipe: the parent type has
one or more `Vec<T>` fields, the synthesised view lifts each to
`Seq<T>` via `field@`, and the V-type is either `Seq<T>` directly
(CommitMask, ArchExec) or a struct that bundles `Seq<T>` with
view-trivial sibling fields (PageMap with `Array<usize, 512>`;
Constants with copies of `EndPoint`).  Z3 can prove `equal_v(a, b)`
because both sides reduce to the same `Seq.equal` axiom after
view-projection.

### memory-allocator/CommitMask (×8)

`pub struct CommitMask { mask: Vec<u64> }` is the workhorse;
arithmetic is pointwise on the underlying `Vec<u64>`.  The cached
view body is
```
spec fn view(&self) -> Seq<u64> { self.mask@ }
```
8 of the 16 commit-mask functions had `ok_w` baselines and all 8
flip to `ok`.  This is the strongest single project win in the
PR-D4 set.

### atmosphere/PageMap.set

Parent type has `Vec<PageEntry>` (length-512 array of 512 entries)
plus a fixed-width `Array<usize, 512>` of permissions.  View
lifts both: `self.entries@` (→ `Seq<PageEntry>`) and
`self.perms@` (→ `Seq<usize>`).  z3 closes via
`Seq.equal == ext-equal == pointwise`.

### ironkv/Constants → parse_command_line_configuration

`Constants` bundles a `Vec<EndPoint>` ("hosts") plus a few
scalar config values.  View flattens to a struct of `Seq<EndPoint>`
+ scalars.  The `EndPoint` view is the same one we eventually had
to **quarantine for `M4` semantic mismatch in 12 ironkv targets**;
but in this single target it happens to be uninvolved in the
witness-emitting branch.  After the cascade closure quarantined
`EndPoint`, this target loses access to that view, but the L4
synthesiser is no longer the bottleneck for the witness; the
existing L3 / per-field equality is sufficient.

### nrkernel/ArchExec → x86_arch_exec

`ArchExec` wraps `Vec<ArchLayerExec>` (page-table arch layout).
View flattens to `Seq<ArchLayerExec>`.  Trivial alpha-renaming.

## Broken-view quarantine (PR-D4 ISSUES.md #7)

14 cached L4 views were quarantined ahead of this rerun because
they expanded to bodies that Verus rejected.  See ISSUES.md #7 for
the full per-view table; the reason taxonomy:

| failure mode | count | example |
|---|---:|---|
| **M1** `<Inner as View>::V` / `self.f@` on a head with no View | 5 | atmosphere/Kernel (`PageAllocator`/`MemoryManager`/`ProcessManager`) |
| **M2** `self.f@@` past Ghost into Set/Map (no inner View) | 1 | atmosphere/Endpoint (`Ghost<Set<ThreadId>>`) |
| **M3** parent type is `external_body` / `repr(C)` opaque | 2 | ironkv/CKeyHashMap, atmosphere/Registers |
| **M4** semantic V-type mismatch (right shape, wrong namespace) | 1 | ironkv/EndPoint (synthesiser picked `Seq<u8>`; project uses `AbstractEndPoint`) |
| cascade (deps on a quarantined root) | 5 + 0 | 5 ironkv types that transitively view `EndPoint` |

Detection sketches for M1/M2/M3 are in
[`docs/critic-criteria.md`](../docs/critic-criteria.md);
the cascade closure for M4 is enforced by the
`<name>.json.quarantine` sticky markers + the new
`prefill --include-quarantined` opt-in flag (see commit `33bd09a`).

## verus_error sanity check

Net verus_error 191 → 190.  Of the 14 quarantines, only 1 produced
a baseline → candidate ok-side transition (the soft improvement on
`host_model_receive_packet`).  The other 13 quarantines were
**already** verus_error in baseline (because the broken view was
also injected in baseline) and remain verus_error in candidate
(because the un-quarantined fallback still cannot derive equality
on a `Vec<T>` directly).  This is consistent with the prediction:
post-quarantine the view registry stops *adding* regressions, but
the underlying A-2 witnesses on those 13 targets can only be
removed by a future PR that synthesises *correct* views for those
types (PR-D5 candidate).

## Process & reproducibility

Baseline run: `eed6038` build, results in `results-verusage/`.
Candidate run: `33bd09a` build (quarantine-aware prefill + the
quarantined `.json.quarantine` markers under
`results-verusage/view_registry/`).  Re-derive with
```
bash scripts/rerun_corpus.sh results-verusage-viewreg
python scripts/compare_runs.py \
    --baseline results-verusage \
    --candidate results-verusage-viewreg \
    --baseline-commit 42c1248 \
    --candidate-commit 33bd09a \
    --out results-verusage-viewreg/COMPARE.md
```
