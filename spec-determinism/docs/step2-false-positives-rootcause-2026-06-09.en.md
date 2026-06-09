# Step-2 sweep false positives — root-cause analysis (2026-06-09)

| # | Case | Root cause (one sentence) |
|---|------|---------------------------|
| 1 | [`atmosphere::ArrayVec::len`](#1-arrayveclen--no-proof-hints-so-the-subrange-length-axiom-is-not-triggered) | No proof hints were emitted, so Verus' auto-trigger never fires the `Seq::subrange` length axiom. |
| 2 | [`ironkv::CKeyHashMap::to_vec`](#2-ckeyhashmapto_vec--the-spec-function-is-not-actually-implemented) | The spec function is not actually implemented (`uninterp` ∘ `uninterp`, no bridging axiom). |
| 3 | [`ironkv::CSendState::get`](#3-csendstateget--meant-to-compare-views-but-compared-structs-instead) | We meant to compare views, but the auto-generated oracle compared structs instead. |

---

## 1. `ArrayVec::len` — no proof hints, so the `subrange` length axiom is not triggered

Source: [`verusage/.../syscall_mmap_to_iommu_table.rs`](../../verusage/source-projects/atmosphere/verified/kernel/kernel__syscall_io_mmap__impl0__syscall_mmap_to_iommu_table.rs#L1928).

```rust
impl<T: Copy, const N: usize> ArrayVec<T, N> {
    pub open spec fn spec_len(&self) -> usize { self.len }

    pub open spec fn view(&self) -> Seq<T> { self.view_until(self.len() as nat) }
    pub open spec fn view_until(&self, k: nat) -> Seq<T> { self.data@.subrange(0, k as int) }

    pub open spec fn wf(&self) -> bool {
        0 <= N <= usize::MAX
        && self.len() <= self.capacity()
        && self.data.wf()   // ⇒ data@.len() == N
    }
}
```

Step-2 obligation: `self1@ == self2@ ⇒ self1.spec_len() == self2.spec_len()` — i.e. `self1.len == self2.len`.

### Root cause

The proof chain is entirely contractual:

```
self1@ == self2@
  ⇒ subrange(0, self1.len) == subrange(0, self2.len)        (defn of view)
  ⇒ subrange(0, self1.len).len() == subrange(0, self2.len).len()
  ⇒ self1.len == self2.len                                  (Seq::subrange_len axiom)
```

The last step needs `Seq::subrange_len`; with an empty body, Verus' auto-trigger never picks `subrange(0, _)` from the equality hypothesis, so the axiom is never instantiated.

### What closes it

Two trigger-only `assert`s, one per side:

```rust
{
    assert(self1.data@.subrange(0, self1.len as int).len() == self1.len as nat);
    assert(self2.data@.subrange(0, self2.len as int).len() == self2.len as nat);
}
// 1 verified, 0 errors
```

---

## 2. `CKeyHashMap::to_vec` — the spec function is not actually implemented

Source: [`verusage/.../net_sht_v__receive_with_demarshal.rs`](../../verusage/source-projects/ironkv/verified/net_sht_v/net_sht_v__receive_with_demarshal.rs#L510).

```rust
impl CKeyHashMap {
    pub uninterp spec fn view(self) -> Map<AbstractKey, Seq<u8>>;
    pub uninterp spec fn spec_to_vec(&self) -> Vec<CKeyKV>;

    #[verifier(when_used_as_spec(spec_to_vec))]
    pub fn to_vec(&self) -> (res: Vec<CKeyKV>)
        ensures res == self.spec_to_vec();
}
```

Step-2 obligation: `self1@ == self2@ ⇒ self1.spec_to_vec() == self2.spec_to_vec()`.

### Root cause

Both `view()` and `spec_to_vec()` are declared `uninterp` — neither is implemented. There is no body, no bridging axiom, nothing for Step 2 to check.

---

## 3. `CSendState::get` — meant to compare views, but compared structs instead

Source: [`verusage/.../single_delivery_model_impl2__receive_ack_impl.rs`](../../verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__receive_ack_impl.rs#L486).

```rust
pub struct CSendState { pub epmap: HashMap<EndPoint, CAckState> }

impl CSendState {
    pub open spec fn view(&self) -> SendState<Message> {
        self.epmap@.map_values(|v: CAckState| v@)   // each CAckState is collapsed to its own view
    }

    pub fn get(&self, src: &EndPoint) -> (value: Option<&CAckState>)
        ensures
            value == match HashMap::get_spec(self.epmap@, src@) {
                Some(v) => Some(&v),
                None    => None,
            };
}
```

### What was actually emitted (wrong) vs. what we wanted (right)

The auto-generated oracle for the return type `Option<&CAckState>` came out as:

```rust
// WRONG — what the generator actually emits today
spec fn det_get_equal(r1: Option<&CAckState>, r2: Option<&CAckState>) -> bool {
    (r1 is Some == r2 is Some)
    && (r1 is Some ==> r1->Some_0.num_packets_acked == r2->Some_0.num_packets_acked
                    && r1->Some_0.un_acked         == r2->Some_0.un_acked)
}
```

What it *should* have emitted, for the same return type:

```rust
// RIGHT — compare the payload via view, not via fields
spec fn det_get_equal(r1: Option<&CAckState>, r2: Option<&CAckState>) -> bool {
    (r1 is Some == r2 is Some)
    && (r1 is Some ==> r1->Some_0@ == r2->Some_0@)
}
```

(Equivalently in lifted form: `r1.map(|v: &CAckState| v@) == r2.map(|v| v@)`.)

The difference is one line — the `Some` arm. The wrong version walks past `CAckState`'s `view()` and pokes at the underlying struct fields; the right version stops at the view boundary.
