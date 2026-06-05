# Step 2 (view-quotient) — mechanical sweep of concretely-deterministic pub fns

Companion to the LLM-audited summary at
[view-quotient-failure-summary-2026-06-04.en.md](view-quotient-failure-summary-2026-06-04.en.md).
That note discusses two manually-constructed witnesses
(`StaticLinkedList::len`, `DelegationMap::get_internal`); this one is the
full Verus-driven Step 2 sweep across every public function that the
prior pipeline has already certified as concretely deterministic.

## 1. Scope

Targets are the public functions in the dedup'd corpus
(`results-verusage-viewreg/<proj>/full_run.json`, keyed on
`(proj, fn, type_base)`) that satisfy both:

- `status == 'ok'` — concrete-completeness check passed, and
- `assumes == []` — no additional `assume` hypotheses were needed.

The second filter excludes the assume-rescued pile: those functions
required counterexample-driven hypotheses to verify and therefore are
not part of the concretely-deterministic set in the first place.

After dedup + the `pub fn` filter, the target set is **109 entries**:

| project          | targets |
|------------------|--------:|
| atmosphere       |      67 |
| ironkv           |      22 |
| memory-allocator |      13 |
| nrkernel         |       6 |
| vest             |       1 |
| **total**        | **109** |

## 2. Procedure

For each target we mechanically generate the Step 2 obligation from the
artifact's `det_check_template` and run Verus
(`0.2026.05.17.e479cce`, `--verify-function det_step2_<fn>`).

Template family 1 (immutable / by-value / no self):
```
fn det_X(self_, args, r1, r2) ensures (BODY) ==> equal(r1, r2)
```
Step 2 transformation: split `self_ → self1, self2`; require
`self1@==self2@` if a `view` exists in this artifact, else
`self1==self2`; substitute per-side clauses; conclusion `equal(r1,r2)`.

Template family 2 (`&mut self`):
```
fn det_X(pre_self_, args, post1_self_, r1, post2_self_, r2)
    ensures (BODY uses pre/post1/post2) ==> equal(r1,r2,post1_self_,post2_self_)
```
Step 2 transformation: split `pre_self_ → pre1_self_, pre2_self_`; require
`pre1_self_@==pre2_self_@`; per-side substitution; conclusion uses the
full `equal_arg_pairs` list.

The generator also patches `&mut <param>` postconditions to the current
Verus migration: bare `<name>.f`, `<name>@`, `*<name>` become
`final(<name>).f`, `final(<name>)@`, `*final(<name>)`. Both `&mut self`
and `Tracked(<x>): Tracked<&mut T>` are handled.

Generator and inputs:
[`vq_step2_check.py`](../../.copilot/session-state/.../files/step2_sweep/vq_step2_check.py)
(this commit's copy);
[`results.json`](../../.copilot/session-state/.../files/step2_sweep/results.json) — full per-target output;
[`failure_step2_srcs/`](../../.copilot/session-state/.../files/step2_sweep/failure_step2_srcs/) — generated Step 2 source per failing target;
[`sweep9.log`](../../.copilot/session-state/.../files/step2_sweep/sweep9.log) — raw run log.

## 3. Aggregate result

109 pub fn targets, 0 compile-fail:

| project          | verified | failed | inl-verified | inl-failed |
|------------------|---------:|-------:|-------------:|-----------:|
| atmosphere       |       62 |      5 |          842 |        142 |
| ironkv           |       20 |      2 |           64 |         16 |
| memory-allocator |       13 |      0 |           14 |          0 |
| nrkernel         |        6 |      0 |            6 |          0 |
| vest             |        1 |      0 |            1 |          0 |
| **total**        |  **102** |  **7** |      **927** |    **158** |

"inl-*" weights each unique key by the number of corpus inlinings it
represents.

## 4. The 7 failures

All seven are real view-quotient leaks. They fall into four families:

| # | proj | type::fn | inl | family | how to fix |
|---|---|---|---:|---|---|
| 1 | atmosphere | `StaticLinkedList::len`   | 114 | length not in view | add `requires self.wf()`, or include `value_list_len` in the view |
| 2 | atmosphere | `ArrayVec::len`           |  10 | length not in view | add `requires self.wf()` and let view-axiom bridge, or include `len` in the view |
| 3 | atmosphere | `StaticLinkedList::get_value` | 8 | ghost field not in view | strengthen ensures to use `self@[i]`, or include the ghost `arr_seq` in the view |
| 4 | atmosphere | `StaticLinkedList::get_next`  | 6 | ghost field not in view | same as #3 (returns `arr_seq[index].next`) |
| 5 | atmosphere | `StaticLinkedList::get_prev`  | 4 | ghost field not in view | same as #3 (returns `arr_seq[index].prev`) |
| 6 | ironkv | `CKeyHashMap::to_vec` | 14 | uninterp `spec_to_vec` is not view-stable | give `spec_to_vec` an ensures linking it to the view, or compare returns view-wise |
| 7 | ironkv | `CSendState::get`     |  2 | concrete `&CAckState` return ignores view | tighten the view to `epmap@` (drop the `map_values(|v| v@)` projection), or compare the return via `view_equal` |

Family 1 (length not in view) is the prototype already documented in the
2026-06-04 companion: `StaticLinkedList::len` is the original witness.
`ArrayVec::len` is the same pattern (`view() == data@.subrange(0, len)`,
so the unfolded view length equals `self.len` only when `wf()` holds).

Family 2 (ghost field not in view) is the deeper version: the
implementation maintains a parallel ghost array (`arr_seq`) keyed by
node index, and the public spec exposes node-indexed reads. The view
`spec_seq` only projects the *values* that are currently linked into the
value-list, so an unlinked or free node's `value`/`next`/`prev` are not
pinned by view-equality.

Family 3 (uninterp not view-stable) is the dual of Family 1 on the
result side: `spec_to_vec` returns a concrete `Vec<CKeyKV>` whose
ordering is unconstrained by the abstract `Map<AbstractKey, Seq<u8>>`
view.

Family 4 (concrete return ignores view) is structural-eq on a result
type that itself has a coarser view than the projection embedded in the
`Self` view.

## 5. Comparison with the static (syntactic) scan

The earlier static scan (`vq_pubfn_scan.py`) used a purely-syntactic
heuristic: it flagged a function only when an ensures clause referenced
a `self.<hidden_field>` not in the view AND no `requires` mentioned
`wf()`. It reported only `StaticLinkedList::len`.

The mechanical sweep finds **7 leaks**. The 6 extra cases all need the
post-state shape to be a *function* of the view (`get_value`/`get_next`/
`get_prev` indexed reads, `to_vec` uninterp result, `CSendState::get`
result-view mismatch), which the static heuristic could not detect.

## 6. Witnesses

| witness | mechanical status | result |
|---|---|---|
| `StaticLinkedList::len` (atmosphere) | `failed 0v/1e` | Step 2 leak confirmed |
| `ArrayVec::len`         (atmosphere) | `failed 0v/1e` | identical pattern, 10 inlinings |
| `CKeyHashMap::len`      (ironkv)     | not in scope — `assumes != []`, did not pass concrete completeness |
| `DelegationMap::get_internal` is non-pub (`pub(crate)`); not in the pub-fn set |  | — |

`get_internal` is `pub(crate)`; the manual witness for it remains
[`spec-determinism/witnesses/get_internal_witness.rs`](../witnesses/get_internal_witness.rs).
