# Step 2 Failure Walkthrough — 7 cases (working doc)

Status legend per case: `pending` (not yet reviewed) | `discussed` (decision made,
not implemented) | `fix-drafted` | `fix-verified` (Verus accepts the proposed
spec change).

Generator: `/home/chentianyu/.copilot/session-state/.../files/step2_sweep/vq_step2_check.py`
Per-failure Step 2 source: `files/step2_sweep/failure_step2_srcs/<proj>__<fn>__<type>.rs`.
Reproduce with `verus <src> --verify-root --verify-function det_step2_<fn>`.

---

## Case 1 — `atmosphere::StaticLinkedList::len`

- inlines: 114 (largest single contributor in the corpus)
- artifact: `atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped__len`
- source (representative): `verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__remove_helper7.rs:43`
- status: **pending**

Spec (verbatim):
```rust
#[verifier::external_body]
#[verifier(when_used_as_spec(spec_len))]
pub fn len(&self) -> (l: usize)
    ensures
        l == self.value_list_len,
        self.wf() ==> l == self.len(),
        self.wf() ==> l == self@.len(),
```
View: `view(&self) -> Seq<T> { self.spec_seq@ }`.

Step 2 obligation (rejected by Verus):
```rust
proof fn det_step2_len<T, const N: usize>(self1, self2, r1, r2)
    requires
        self1@ == self2@,
        r1 == self1.value_list_len,
        self1.wf() ==> r1 == self1@.len(),
        r2 == self2.value_list_len,
        self2.wf() ==> r2 == self2@.len(),
    ensures det_len_equal(r1, r2),
```

Why it fails: without `self.wf()` we only learn `r_i == self_i.value_list_len`,
and `value_list_len` is not exposed by the view; `self1@ == self2@` does not
constrain it. The two `wf() ==>` implications become vacuous when wf is absent.

Proposed fixes (consistent with `view-quotient-failure-summary-2026-06-04.en.md`):
- **A. Strengthen `requires`** with `self.wf()`. Then `r1 == self1@.len() == self2@.len() == r2`.
- **B. Widen the view** so the projected `Seq<T>` carries length, e.g. include `value_list_len` in the view tuple or change the view to a `(Seq<T>, usize)` pair.

---

## Case 2 — `atmosphere::ArrayVec::len`

- inlines: 10
- artifact: `atmosphere__verified__memory_manager__memory_manager__spec_impl__impl0__alloc_iommu_table__len`
- status: **pending**

Spec (verbatim):
```rust
#[verifier::external_body]
#[verifier(when_used_as_spec(spec_len))]
pub fn len(&self) -> (ret: usize)
    requires self.wf(),
    ensures ret == self.spec_len(),

pub open spec fn spec_len(&self) -> usize { self.len }

pub open spec fn view(&self) -> Seq<T>
    recommends self.wf(),
{
    self.view_until(self.len() as nat)        // subrange(0, self.len)
}

pub open spec fn wf(&self) -> bool {
    &&& 0 <= N <= usize::MAX
    &&& self.len() <= self.capacity()
    &&& self.data.wf()
}
```

Step 2 obligation:
```rust
proof fn det_step2_len(self1, self2, r1, r2)
    requires
        self1@ == self2@,
        self1.wf(), self2.wf(),
        r1 == self1.spec_len(),
        r2 == self2.spec_len(),
    ensures det_len_equal(r1, r2),
```

Why it fails: `wf()` is already required, but `view()` is a closed projection
to `subrange(0, self.len)` and Verus does not unfold it to learn
`self_i@.len() == self_i.len` from `self1@ == self2@`. `spec_len()` returns
`self.len` directly, which is *not* in the view.

Proposed fixes:
- **A. Add a lemma/`ensures` that bridges view and len**, e.g. an axiom
  `self.wf() ==> self@.len() == self.spec_len()`, exposed by `view()` or by an
  external proof obligation.
- **B. Widen the view** so `len` is a separate component (return `(Seq<T>, usize)`
  or include `spec_len` in a richer abstract view).

---

## Case 3 — `atmosphere::StaticLinkedList::get_value`

- inlines: 8
- artifact: `atmosphere__verified__slinkedlist__slinkedlist__spec_impl_u__impl2__pop__get_value`
- status: **pending**

Spec (verbatim):
```rust
#[verifier::external_body]
#[verifier(external_body)]
pub fn get_value(&self, index: SLLIndex) -> (ret: Option<T>)
    requires
        0 <= index < N,
        self.array_wf(),
    ensures
        ret == self.arr_seq@[index as int].value,
```
- `view()` is `self.spec_seq@` (a `Seq<T>` of currently-linked values, in list order).
- `array_wf()` only constrains `arr_seq.len() == N` and `size == N`.
- `arr_seq` is a separate ghost field; `wf()` (via `spec_seq_wf`) ties
  `arr_seq[value_list[i]].value` to `spec_seq[i]`, but *only for indices that
  are currently in `value_list`*.

Step 2 obligation:
```rust
proof fn det_step2_get_value(self1, self2, index, r1, r2)
    requires
        self1@ == self2@,
        0 <= index < N,
        self1.array_wf(), self2.array_wf(),
        r1 == self1.arr_seq@[index as int].value,
        r2 == self2.arr_seq@[index as int].value,
    ensures det_get_value_equal(r1, r2),
```

Why it fails: the result reads the raw ghost array at an arbitrary `index`. The
view fixes `spec_seq`, but `arr_seq[index].value` for an `index` that is *not*
currently in the value-list (a free or stale slot) is completely unconstrained.

Proposed fixes:
- **A. Restrict spec to in-view reads**: change the ensures to
  `ret == self@[self.value_list@.index_of(index)]` (or take a
  list-position parameter instead of a node index), making the read view-derived.
- **B. Widen the view** to expose `arr_seq` (e.g. abstract to the pair
  `(spec_seq, arr_seq)` or a richer node-indexed map).

---

## Case 4 — `atmosphere::StaticLinkedList::get_next`

- inlines: 6
- artifact: `atmosphere__verified__slinkedlist__slinkedlist__spec_impl_u__impl2__pop__get_next`
- status: **pending**

Spec:
```rust
pub fn get_next(&self, index: SLLIndex) -> (next: SLLIndex)
    requires 0 <= index < N, self.array_wf(),
    ensures next == self.arr_seq@[index as int].next,
```

Step 2 obligation: identical shape to Case 3, with `.next` instead of `.value`.

Why it fails: same ghost-field-not-in-view pattern. `arr_seq[index].next` is
a link pointer; the abstract `Seq<T>` view says nothing about node-level
linkage, and `wf` does not pin individual `.next` slots either.

Proposed fixes:
- **A. Drop from the public surface** (links are an implementation detail; the
  abstract view should be enough for clients).
- **B. Widen the view** to expose the linkage (e.g. `(Seq<T>, Seq<SLLIndex>, Seq<SLLIndex>)` for values + next + prev).

---

## Case 5 — `atmosphere::StaticLinkedList::get_prev`

- inlines: 4
- artifact: `atmosphere__verified__slinkedlist__slinkedlist__spec_impl_u__impl2__remove_helper3__get_prev`
- status: **pending**

Spec:
```rust
pub fn get_prev(&self, index: SLLIndex) -> (prev: SLLIndex)
    requires 0 <= index < N, self.array_wf(),
    ensures prev == self.arr_seq@[index as int].prev,
```

Step 2 obligation: identical shape to Case 4, with `.prev`.

Why it fails: same as Case 4. Symmetric leak on the backwards link.

Proposed fixes: same two options as Case 4.

---

## Case 6 — `ironkv::CKeyHashMap::to_vec`

- inlines: 14
- artifact: `ironkv__verified__host_impl_v__host_impl_v__impl2__deliver_packet_seq__to_vec`
- status: **pending**

Spec:
```rust
impl CKeyHashMap {
    pub uninterp spec fn view(self) -> Map<AbstractKey, Seq<u8>>;
    pub uninterp spec fn spec_to_vec(&self) -> Vec<CKeyKV>;

    #[verifier(when_used_as_spec(spec_to_vec))]
    pub fn to_vec(&self) -> (res: Vec<CKeyKV>)
        ensures res == self.spec_to_vec();
}
```

Step 2 obligation:
```rust
proof fn det_step2_to_vec(self1, self2, r1, r2)
    requires
        self1@ == self2@,
        r1 == self1.spec_to_vec(),
        r2 == self2.spec_to_vec(),
    ensures r1 == r2,                       // det_to_vec_equal is struct-eq
```

Why it fails: `spec_to_vec` is uninterpreted. It is a function of `self`, not
of `self@`, so two view-equal but otherwise distinct `CKeyHashMap` values may
yield two different `Vec<CKeyKV>` results.

Proposed fixes:
- **A. Give `spec_to_vec` an abstraction-respecting `ensures`** (e.g. an axiom
  `forall a, b. a@ == b@ ==> a.spec_to_vec() == b.spec_to_vec()`, or define
  `spec_to_vec` open over the view directly).
- **B. Compare results via view, not structurally** (change `det_to_vec_equal`
  to `r1@.to_multiset() == r2@.to_multiset()` or similar view-stable form).

---

## Case 7 — `ironkv::CSendState::get`

- inlines: 2
- artifact: `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__get`
- status: **pending**

Spec (verbatim):
```rust
pub struct CSendState { pub epmap: HashMap<CAckState> }

impl CSendState {
    pub open spec fn view(&self) -> SendState<Message> {
        self.epmap@.map_values(|v: CAckState| v@)
    }

    #[verifier::external_body]
    pub fn get(&self, src: &EndPoint) -> (value: Option<&CAckState>)
        ensures
            value == match HashMap::get_spec(self.epmap@, src@) {
                Some(v) => Some(&v), None => None,
            },
            value is Some ==> self@.contains_key(src@),
}

spec fn det_get_equal(r1, r2: Option<&CAckState>) -> bool {
    (r1 is Some == r2 is Some)
    && (r1 is Some ==> r1->Some_0.num_packets_acked == r2->Some_0.num_packets_acked
                    && r1->Some_0.un_acked == r2->Some_0.un_acked)
}
```

Step 2 obligation:
```rust
proof fn det_step2_get(self1, self2, src, r1, r2)
    requires
        self1@ == self2@,
        r1 == match HashMap::get_spec(self1.epmap@, src@) { Some(v) => Some(&v), None => None },
        r2 == match HashMap::get_spec(self2.epmap@, src@) { Some(v) => Some(&v), None => None },
        ...,
    ensures det_get_equal(r1, r2),
```

Why it fails: the view of `CSendState` is `epmap@.map_values(|v| v@)` — it
already collapses each `CAckState` to its abstract `AckState`. So
`self1@ == self2@` does **not** imply `self1.epmap@ == self2.epmap@`; two
concrete `CAckState`s with equal views may have different `num_packets_acked`
or `un_acked` fields. `det_get_equal` compares those concrete fields.

Proposed fixes:
- **A. Tighten the `CSendState` view** to `epmap@` directly (drop the
  `map_values(|v| v@)` projection), so view-eq pins the concrete entries.
- **B. Compare via view in `det_get_equal`** — `r1.map(|v| v@) == r2.map(|v| v@)`
  — so the determinism check respects the same abstraction the view does.

---

## Aggregate summary

| # | proj | type::fn | inl | family | fix candidates |
|---|---|---|---:|---|---|
| 1 | atmosphere | `StaticLinkedList::len`       | 114 | length not in view              | A: `requires self.wf()`  •  B: widen view to expose `value_list_len` |
| 2 | atmosphere | `ArrayVec::len`               |  10 | length not in view              | A: axiom `wf ==> @.len()==spec_len()`  •  B: widen view to include `len` |
| 3 | atmosphere | `StaticLinkedList::get_value` |   8 | ghost-field not in view         | A: re-shape spec to read via `self@`  •  B: widen view to expose `arr_seq` |
| 4 | atmosphere | `StaticLinkedList::get_next`  |   6 | ghost-field not in view         | A: drop from public surface       •  B: widen view to expose linkage |
| 5 | atmosphere | `StaticLinkedList::get_prev`  |   4 | ghost-field not in view         | same as #4 |
| 6 | ironkv     | `CKeyHashMap::to_vec`         |  14 | uninterp not view-stable        | A: add abstraction axiom on `spec_to_vec`  •  B: compare results view-wise |
| 7 | ironkv     | `CSendState::get`             |   2 | concrete return ignores view    | A: tighten view to `epmap@`        •  B: compare returns via `v@` |

We'll walk through them one by one and record the chosen fix + verification
status in the per-case sections.
