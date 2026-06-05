# Mechanical Step 2 Sweep — Failed Cases (Verus-confirmed)

Sweep: 109 concretely-deterministic pub fns (`status=='ok' AND assumes==[]`,
then dedup'd) across 5 projects, run with Verus 0.2026.05.17.e479cce.
Status: **102 verified / 7 failed / 0 compile-fail**.

## Per-project results

| project | verified | failed | inl-verified | inl-failed |
|---|---:|---:|---:|---:|
| atmosphere       | 62 | 5 | 842 | 142 |
| ironkv           | 20 | 2 |  64 |  16 |
| memory-allocator | 13 | 0 |  14 |   0 |
| nrkernel         |  6 | 0 |   6 |   0 |
| vest             |  1 | 0 |   1 |   0 |

## All 7 failing pub fns

| project | type | fn | inlines | equal_fn | self kind | family |
|---|---|---|---:|:-:|:-:|---|
| atmosphere | `StaticLinkedList` | `len`       | 114 | S |     | length not in view |
| atmosphere | `ArrayVec`         | `len`       |  10 | S |     | length not in view |
| atmosphere | `StaticLinkedList` | `get_value` |   8 | S |     | ghost field not in view |
| atmosphere | `StaticLinkedList` | `get_next`  |   6 | S |     | ghost field not in view |
| atmosphere | `StaticLinkedList` | `get_prev`  |   4 | S |     | ghost field not in view |
| ironkv     | `CKeyHashMap`      | `to_vec`    |  14 | S |     | uninterp result not view-stable |
| ironkv     | `CSendState`       | `get`       |   2 | S |     | concrete return ignores view |

Equal-fn legend: `S` = struct-eq, `V` = view-based.

## Generated Step 2 sources

The exact source Verus rejected for each of the seven cases is persisted
under
[`failure_step2_srcs/`](../../.copilot/session-state/.../files/step2_sweep/failure_step2_srcs/):

- `atmosphere__len__StaticLinkedList.rs`
- `atmosphere__len__ArrayVec.rs`
- `atmosphere__get_value__StaticLinkedList.rs`
- `atmosphere__get_next__StaticLinkedList.rs`
- `atmosphere__get_prev__StaticLinkedList.rs`
- `ironkv__to_vec__CKeyHashMap.rs`
- `ironkv__get__CSendState.rs`

Re-running any of them with
`verus <file> --verify-root --verify-function det_step2_<fn>`
reproduces the `0 verified, 1 errors` outcome.

## What "not in scope" looks like

The 252-pub-fn pile that the broader `status == 'ok'` filter (without the
`assumes == []` clause) admits adds 143 functions that were verified
only after the pipeline injected `assume`-hypotheses. Those targets are
not part of the concrete-completeness pile and were excluded from this
sweep on purpose. The corresponding Step 2 leakage for those targets
should be analysed separately, against the spec-determinism semantics
that admits assume-rescue.
