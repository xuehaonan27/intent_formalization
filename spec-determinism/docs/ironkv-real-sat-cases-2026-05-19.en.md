# ironkv REAL_SAT (genuine non-determinism) case set

> 5 unique spec functions / 9 witness instances.
> z3-discovered witnesses here are **not** incompleteness — they reflect non-determinism that the spec itself admits.
> Source dataset: `spec-determinism/results-verusage-viewreg/ironkv/full_run.json` (May 12 viewreg full run).
>
> **Note**: the case `keys` (former #5) has been relocated to `ironkv-equal-fn-too-strict-cases-2026-05-19.md` — the spec is in fact deterministic at the `set` abstraction it picks; the apparent non-determinism comes from the codegen's overly strict `equal_fn`, not from the spec. `retransmit_un_acked_packets` / `_for_dst` (#3 / #4) likely belong to the same category and are kept here pending a second review.

## Overview

| # | Function | Instances | Source of non-determinism |
|---|----------|-----------|---------------------------|
| 1 | `keys_in_index_range_agree` | ×2 | Spec only constrains `ret.1` when `!ret.0`; `ret.0 == true` leaves `ret.1` free |
| 2 | `values_agree` | ×2 | Same as #1 (`keys_in_index_range_agree` calls it and forwards the tuple) |
| 3 | `retransmit_un_acked_packets` | ×2 | Spec uses `set` (not `seq`) equivalence — `Vec` order is free (candidate for relocation to equal_fn-too-strict) |
| 4 | `retransmit_un_acked_packets_for_dst` | ×2 | Same as #3 (in-place accumulator variant) (candidate for relocation) |
| 5 | `sht_demarshall_data_method` | ×1 | The `InvalidMessage` branch is entirely unconstrained by the spec |

## Fix priority

- **High (spec bug, easy to fix)**: `keys_in_index_range_agree` / `values_agree` — missing constraint on `ret.1` in the `ret.0 == true` branch. One added clause suffices.
- **Medium (spec design choice)**: `sht_demarshall_data_method` — whether to canonicalize the `InvalidMessage` fallback depends on caller expectations.
- **Pending review (likely equal_fn-too-strict, not spec bugs)**: `retransmit_un_acked_packets` / `_for_dst` — the spec uses set-equality at the right abstraction; the real fix lives in the pipeline rather than the spec.

## A note on witness format

The generated witnesses (produced by z3 via the assume-guard schema in each synthetic `det_*` proof obligation) emit only the conjuncts that correspond to **activated guards** — so input-schema fields (`lo`, `hi`, …) and the structural-inequality marker show up, while `self_`, `v`, and the result variables (`r1`, `r2`, `post*_packets`) typically appear in the model but are not dumped. Hand-constructed witnesses below are written in the **same assume-style list format** so they can be read alongside the z3 output. Lines containing `==` describe equalities the witness commits to; lines starting with `!` are the negated equivalence that closes the witness.

---

## #1 `keys_in_index_range_agree` (×2 instances)

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__keys_in_index_range_agree.rs`
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__keys_in_index_range_agree/`
- **z3 cost (sample)**: n_rounds=14, n_schemas=5, verus_ms=448

### Why this is REAL_SAT

The function returns `(bool, bool)`. The spec only constrains `ret.1` in the `!ret.0` branch:

```
ret.0 == forall |i| lo <= i <= hi ==> self@[self.keys@[i]]@ == v@,
!ret.0 ==> (ret.1 == (self@[self.keys@[hi as int]]@ != v@
                       && forall |i| lo <= i < hi ==> self@[self.keys@[i]]@ == v@))
```

When `ret.0 == true`, the antecedent of the second ensure is false, so the entire clause holds vacuously and **`ret.1` is unconstrained**. Two compliant implementations may return `(true, true)` and `(true, false)`. z3's witness commits to the input shape (`lo == 0, hi == 0`) and the structural inequality on the tuple, leaving the rest implicit.

**Suggested spec fix**: add `ret.0 ==> ret.1 == ret.0` (or `ret.0 ==> !ret.1`, whichever matches caller expectations). One line.

### Source function

```rust
fn keys_in_index_range_agree(&self, lo: usize, hi: usize, v: &ID) -> (ret: (bool, bool))
    requires
        self.valid(),
        0 <= lo <= hi < self.keys@.len(),
    ensures
        ret.0 == forall |i| #![auto] lo <= i <= hi ==> self@[self.keys@[i]]@ == v@,
        !ret.0 ==> (ret.1 == (self@[self.keys@[hi as int]]@ != v@
                              && (forall |i| #![auto] lo <= i < hi ==> self@[self.keys@[i]]@ == v@))),
{
    assert(self.valid());
    assert(forall |i| lo <= i <= hi ==> self@[self.keys@[i]] == self.vals@[i]);
    let (agree, almost) = self.values_agree(lo, hi, v);
    (agree, almost)
}
```

### Generated equal_fn

```rust
spec fn det_keys_in_index_range_agree_equal(r1: (bool, bool), r2: (bool, bool)) -> bool {
    (r1 == r2)
}
```

### Generated det fn (synthetic proof obligation)

```rust
proof fn det_keys_in_index_range_agree<K: KeyTrait + VerusClone>(
    g_lo_eq: bool, k_lo_eq: int, g_lo_rng: bool, k_lo_rng_lo: int, k_lo_rng_hi: int,
    g_hi_eq: bool, k_hi_eq: int, g_hi_rng: bool, k_hi_rng_lo: int, k_hi_rng_hi: int,
    g_neq_tuple: bool,
    self_: StrictlyOrderedMap<K>, lo: usize, hi: usize, v: ID,
    r1: (bool, bool), r2: (bool, bool))
    requires self_.valid(), 0 <= lo <= hi < self_.keys@.len(),
    ensures
        ({
            &&& r1.0 == forall |i| #![auto] lo <= i <= hi ==> self_@[self_.keys@[i]]@ == v@
            &&& !r1.0 ==> (r1.1 == (self_@[self_.keys@[hi as int]]@ != v@
                                    && forall |i| #![auto] lo <= i < hi ==> self_@[self_.keys@[i]]@ == v@))
            &&& r2.0 == forall |i| #![auto] lo <= i <= hi ==> self_@[self_.keys@[i]]@ == v@
            &&& !r2.0 ==> (r2.1 == (self_@[self_.keys@[hi as int]]@ != v@
                                    && forall |i| #![auto] lo <= i < hi ==> self_@[self_.keys@[i]]@ == v@))
        }) ==> det_keys_in_index_range_agree_equal(r1, r2),
{
    if g_lo_eq      { assume(lo as int == k_lo_eq); }
    if g_lo_rng     { assume(lo as int >= k_lo_rng_lo && lo as int <= k_lo_rng_hi); }
    if g_hi_eq      { assume(hi as int == k_hi_eq); }
    if g_hi_rng     { assume(hi as int >= k_hi_rng_lo && hi as int <= k_hi_rng_hi); }
    if g_neq_tuple  { assume(!det_keys_in_index_range_agree_equal(r1, r2)); }
}
```

### z3-discovered witnesses

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__keys_in_index_range_agree`:

```
  lo == 0
  hi == 0
  !det_keys_in_index_range_agree_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__impl4__range_consistent_impl__keys_in_index_range_agree`:

```
  lo == 0
  hi == 0
  !det_keys_in_index_range_agree_equal(r1, r2)
```

### Hand-constructed witness (full assumes)

```
  lo == 0
  hi == 0
  self_.keys@.len() == 1
  self_.keys@[0] == K::zero_spec()
  self_.vals@.len() == 1
  self_.vals@[0] == EndPoint{ id: seq![1u8] }
  self_@[K::zero_spec()] == EndPoint{ id: seq![1u8] }
  v == EndPoint{ id: seq![1u8] }
  r1.0 == true
  r1.1 == true
  r2.0 == true
  r2.1 == false
  !det_keys_in_index_range_agree_equal(r1, r2)
```

Verification sketch: the universal `forall |i| 0 <= i <= 0 ==> self_@[k0]@ == v@` reduces to `(EndPoint{id:[1]}@ == EndPoint{id:[1]}@) == true`, so `r1.0 = r2.0 = true` is forced by the ensures. The second clause `!ret.0 ==> …` is vacuous, so `r1.1` and `r2.1` are free; the witness picks `true` vs `false`.

---

## #2 `values_agree` (×2 instances)

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__values_agree.rs`
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__values_agree/`
- **z3 cost (sample)**: n_rounds=14, n_schemas=5, verus_ms=436

### Why this is REAL_SAT

Identical pattern to #1: returns `(bool, bool)` with `ret.1` only constrained in the `!ret.0` branch.

```
ret.0 == forall |i| lo <= i <= hi ==> self.vals@[i]@ == v@,
!ret.0 ==> ret.1 == (self.vals@[hi as int]@ != v@
                     && forall |i| lo <= i < hi ==> self.vals@[i]@ == v@)
```

`keys_in_index_range_agree` simply forwards `values_agree`'s `(bool, bool)`, so the two cases share a single root cause. Fixing `values_agree`'s spec fixes #1 automatically.

### Source function

```rust
fn values_agree(&self, lo: usize, hi: usize, v: &ID) -> (ret: (bool, bool))
    requires
        self.valid(),
        0 <= lo <= hi < self.keys@.len(),
    ensures
        ret.0 == forall |i| #![auto] lo <= i <= hi ==> self.vals@[i]@ == v@,
        !ret.0 ==> (ret.1 == (self.vals@[hi as int]@ != v@
                              && forall |i| #![auto] lo <= i < hi ==> self.vals@[i]@ == v@)),
{ /* linear scan over self.vals[lo..=hi] */ }
```

### Generated equal_fn

```rust
spec fn det_values_agree_equal(r1: (bool, bool), r2: (bool, bool)) -> bool {
    (r1 == r2)
}
```

### Generated det fn (synthetic proof obligation)

```rust
proof fn det_values_agree<K: KeyTrait + VerusClone>(
    g_lo_eq: bool, k_lo_eq: int, g_lo_rng: bool, k_lo_rng_lo: int, k_lo_rng_hi: int,
    g_hi_eq: bool, k_hi_eq: int, g_hi_rng: bool, k_hi_rng_lo: int, k_hi_rng_hi: int,
    g_neq_tuple: bool,
    self_: StrictlyOrderedMap<K>, lo: usize, hi: usize, v: ID,
    r1: (bool, bool), r2: (bool, bool))
    requires self_.valid(), 0 <= lo <= hi < self_.keys@.len(),
    ensures
        ({
            &&& r1.0 == forall |i| #![auto] lo <= i <= hi ==> self_.vals@[i]@ == v@
            &&& !r1.0 ==> (r1.1 == (self_.vals@[hi as int]@ != v@
                                    && forall |i| #![auto] lo <= i < hi ==> self_.vals@[i]@ == v@))
            &&& r2.0 == forall |i| #![auto] lo <= i <= hi ==> self_.vals@[i]@ == v@
            &&& !r2.0 ==> (r2.1 == (self_.vals@[hi as int]@ != v@
                                    && forall |i| #![auto] lo <= i < hi ==> self_.vals@[i]@ == v@))
        }) ==> det_values_agree_equal(r1, r2),
{
    if g_lo_eq      { assume(lo as int == k_lo_eq); }
    if g_lo_rng     { assume(lo as int >= k_lo_rng_lo && lo as int <= k_lo_rng_hi); }
    if g_hi_eq      { assume(hi as int == k_hi_eq); }
    if g_hi_rng     { assume(hi as int >= k_hi_rng_lo && hi as int <= k_hi_rng_hi); }
    if g_neq_tuple  { assume(!det_values_agree_equal(r1, r2)); }
}
```

### z3-discovered witnesses

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__values_agree`:

```
  lo == 0
  hi == 0
  !det_values_agree_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__values_agree__values_agree`:

```
  lo == 0
  hi == 0
  !det_values_agree_equal(r1, r2)
```

### Hand-constructed witness (full assumes)

```
  lo == 0
  hi == 0
  self_.keys@.len() == 1
  self_.keys@[0] == K::zero_spec()
  self_.vals@.len() == 1
  self_.vals@[0] == EndPoint{ id: seq![1u8] }
  v == EndPoint{ id: seq![1u8] }
  r1.0 == true
  r1.1 == true
  r2.0 == true
  r2.1 == false
  !det_values_agree_equal(r1, r2)
```

---

## #3 `retransmit_un_acked_packets` (×2 instances)

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__retransmit_un_acked_packets.rs`
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_noreceive_noclock_next__retransmit_un_acked_packets/`
- **z3 cost (sample)**: n_rounds=2, n_schemas=1, verus_ms=1346

### Why this is REAL_SAT (candidate: equal_fn-too-strict)

The function returns `Vec<CPacket>`, but the spec only constrains the **set** image of `packets@.map_values(@)`:

```
abstractify_seq_of_cpackets_to_set_of_sht_packets(packets@) == self@.un_acked_messages(src@),
self@.un_acked_messages(src@) == packets@.map_values(|p: CPacket| p@).to_set(),
```

Two implementations may iterate the underlying `epmap` in different orders and produce permutations of the same packet set. The codegen, working purely from the return type, falls back to structural `Vec<CPacket>` equality (CPacket is quarantined), which rejects permutations. Even if wiring were enabled and CPacket got a view, the resulting `s1 =~= s2` would remain stricter than `s1.to_set() == s2.to_set()`.

This case is a strong candidate for relocation to `ironkv-equal-fn-too-strict-cases-2026-05-19.md`: the spec is already at the canonical abstraction level for "set of pending packets"; the apparent non-determinism is a tooling artifact rather than a spec defect.

### Source function

```rust
pub fn retransmit_un_acked_packets(&self, src: &EndPoint) -> (packets: Vec<CPacket>)
    requires
        self.valid(),
        src.abstractable(),
    ensures
        abstractify_seq_of_cpackets_to_set_of_sht_packets(packets@) == self@.un_acked_messages(src@),
        outbound_packet_seq_is_valid(packets@),
        outbound_packet_seq_has_correct_srcs(packets@, src@),
        self@.un_acked_messages(src@) == packets@.map_values(|p: CPacket| p@).to_set(),
        Self::packets_are_valid_messages(packets@),
{ /* loop over self.send_state.epmap.keys() … */ }
```

### Generated equal_fn

```rust
spec fn det_retransmit_un_acked_packets_equal(r1: Vec<CPacket>, r2: Vec<CPacket>) -> bool {
    (r1 == r2)
}
```

### Generated det fn (synthetic proof obligation)

```rust
proof fn det_retransmit_un_acked_packets(
    g_neq_tuple: bool,
    self_: CSingleDelivery, src: EndPoint,
    r1: Vec<CPacket>, r2: Vec<CPacket>)
    requires self_.valid(), src.abstractable(),
    ensures
        ({
            &&& abstractify_seq_of_cpackets_to_set_of_sht_packets(r1@) == self_@.un_acked_messages(src@)
            &&& outbound_packet_seq_is_valid(r1@)
            &&& outbound_packet_seq_has_correct_srcs(r1@, src@)
            &&& self_@.un_acked_messages(src@) == r1@.map_values(|p: CPacket| p@).to_set()
            &&& CSingleDelivery::packets_are_valid_messages(r1@)
            &&& abstractify_seq_of_cpackets_to_set_of_sht_packets(r2@) == self_@.un_acked_messages(src@)
            &&& outbound_packet_seq_is_valid(r2@)
            &&& outbound_packet_seq_has_correct_srcs(r2@, src@)
            &&& self_@.un_acked_messages(src@) == r2@.map_values(|p: CPacket| p@).to_set()
            &&& CSingleDelivery::packets_are_valid_messages(r2@)
        }) ==> det_retransmit_un_acked_packets_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_retransmit_un_acked_packets_equal(r1, r2)); }
}
```

### z3-discovered witnesses

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_noreceive_noclock_next__retransmit_un_acked_packets`:

```
  !det_retransmit_un_acked_packets_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets__retransmit_un_acked_packets`:

```
  !det_retransmit_un_acked_packets_equal(r1, r2)
```

### Hand-constructed witness (full assumes)

```
  src.abstractable()
  self_.valid()
  self_@.un_acked_messages(src@).len() == 2
  // Pick two distinct abstract messages M1, M2 in un_acked_messages(src@)
  // and two concrete CPackets cp_a, cp_b with the required src field:
  cp_a.src@ == src@
  cp_b.src@ == src@
  cp_a@ == M1
  cp_b@ == M2
  cp_a@ != cp_b@
  cp_a != cp_b
  outbound_packet_is_valid(&cp_a)
  outbound_packet_is_valid(&cp_b)
  r1@ == seq![cp_a, cp_b]
  r2@ == seq![cp_b, cp_a]
  r1@.map_values(|p: CPacket| p@).to_set() == set![M1, M2]
  r2@.map_values(|p: CPacket| p@).to_set() == set![M1, M2]
  abstractify_seq_of_cpackets_to_set_of_sht_packets(r1@) == self_@.un_acked_messages(src@)
  abstractify_seq_of_cpackets_to_set_of_sht_packets(r2@) == self_@.un_acked_messages(src@)
  outbound_packet_seq_is_valid(r1@)
  outbound_packet_seq_is_valid(r2@)
  outbound_packet_seq_has_correct_srcs(r1@, src@)
  outbound_packet_seq_has_correct_srcs(r2@, src@)
  CSingleDelivery::packets_are_valid_messages(r1@)
  CSingleDelivery::packets_are_valid_messages(r2@)
  !det_retransmit_un_acked_packets_equal(r1, r2)
```

The two `r1` and `r2` differ only in the order of `cp_a` / `cp_b`; both satisfy every ensures (which only sees `.to_set()`), but they fail structural `Vec` equality.

---

## #4 `retransmit_un_acked_packets_for_dst` (×2 instances)

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__retransmit_un_acked_packets_for_dst.rs`
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets__retransmit_un_acked_packets_for_dst/`
- **z3 cost (sample)**: n_rounds=2, n_schemas=1, verus_ms=899

### Why this is REAL_SAT (candidate: equal_fn-too-strict)

In-place accumulating sibling of #3; the spec retains the same `to_set()`-equivalence on the post-state:

```
packets@.map_values(|p: CPacket| p@).to_set() ==
    old(packets)@.map_values(|p: CPacket| p@).to_set()
    + self@.un_acked_messages_for_dest(src@, dst@),
```

So callers may push the newly retransmitted packets in any order onto `packets`. Equality on `Vec<CPacket>` therefore fails for any non-trivial set. Same relocation candidate as #3.

### Source function

```rust
pub fn retransmit_un_acked_packets_for_dst(
    &self, src: &EndPoint, dst: &EndPoint, packets: &mut Vec<CPacket>)
    requires
        self.valid(),
        src.abstractable(),
        outbound_packet_seq_is_valid(old(packets)@),
        outbound_packet_seq_has_correct_srcs(old(packets)@, src@),
        self.send_state@.contains_key(dst@),
        Self::packets_are_valid_messages(old(packets)@),
    ensures
        packets@.map_values(|p: CPacket| p@).to_set() ==
            old(packets)@.map_values(|p: CPacket| p@).to_set()
            + self@.un_acked_messages_for_dest(src@, dst@),
        outbound_packet_seq_is_valid(packets@),
        outbound_packet_seq_has_correct_srcs(packets@, src@),
        Self::packets_are_valid_messages(packets@),
{ /* loop over self.send_state.epmap[dst].un_acked … */ }
```

### Generated equal_fn

```rust
spec fn det_retransmit_un_acked_packets_for_dst_equal(
    r1: (), r2: (),
    post1_packets: Vec<CPacket>, post2_packets: Vec<CPacket>) -> bool
{
    (r1 == r2) && (post1_packets == post2_packets)
}
```

### Generated det fn (synthetic proof obligation)

```rust
proof fn det_retransmit_un_acked_packets_for_dst(
    g_neq_tuple: bool,
    self_: CSingleDelivery, src: EndPoint, dst: EndPoint,
    pre_packets: Vec<CPacket>,
    post1_packets: Vec<CPacket>, r1: (),
    post2_packets: Vec<CPacket>, r2: ())
    requires
        self_.valid(), src.abstractable(),
        outbound_packet_seq_is_valid(pre_packets@),
        outbound_packet_seq_has_correct_srcs(pre_packets@, src@),
        self_.send_state@.contains_key(dst@),
        CSingleDelivery::packets_are_valid_messages(pre_packets@),
    ensures
        ({
            &&& post1_packets@.map_values(|p: CPacket| p@).to_set() ==
                  pre_packets@.map_values(|p: CPacket| p@).to_set()
                  + self_@.un_acked_messages_for_dest(src@, dst@)
            &&& outbound_packet_seq_is_valid(post1_packets@)
            &&& outbound_packet_seq_has_correct_srcs(post1_packets@, src@)
            &&& CSingleDelivery::packets_are_valid_messages(post1_packets@)
            &&& post2_packets@.map_values(|p: CPacket| p@).to_set() ==
                  pre_packets@.map_values(|p: CPacket| p@).to_set()
                  + self_@.un_acked_messages_for_dest(src@, dst@)
            &&& outbound_packet_seq_is_valid(post2_packets@)
            &&& outbound_packet_seq_has_correct_srcs(post2_packets@, src@)
            &&& CSingleDelivery::packets_are_valid_messages(post2_packets@)
        }) ==> det_retransmit_un_acked_packets_for_dst_equal(r1, r2, post1_packets, post2_packets),
{
    if g_neq_tuple {
        assume(!det_retransmit_un_acked_packets_for_dst_equal(r1, r2, post1_packets, post2_packets));
    }
}
```

### z3-discovered witnesses

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets__retransmit_un_acked_packets_for_dst`:

```
  !det_retransmit_un_acked_packets_for_dst_equal(r1, r2, post1_packets, post2_packets)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets_for_dst__retransmit_un_acked_packets_for_dst`:

```
  !det_retransmit_un_acked_packets_for_dst_equal(r1, r2, post1_packets, post2_packets)
```

### Hand-constructed witness (full assumes)

```
  src.abstractable()
  self_.valid()
  self_.send_state@.contains_key(dst@)
  pre_packets@ == seq![]
  outbound_packet_seq_is_valid(pre_packets@)
  outbound_packet_seq_has_correct_srcs(pre_packets@, src@)
  CSingleDelivery::packets_are_valid_messages(pre_packets@)
  self_@.un_acked_messages_for_dest(src@, dst@).len() == 2
  // Two concrete packets cp_a, cp_b carrying the two un-acked messages:
  cp_a.src@ == src@
  cp_b.src@ == src@
  cp_a@ != cp_b@
  cp_a != cp_b
  outbound_packet_is_valid(&cp_a)
  outbound_packet_is_valid(&cp_b)
  post1_packets@ == seq![cp_a, cp_b]
  post2_packets@ == seq![cp_b, cp_a]
  post1_packets@.map_values(|p: CPacket| p@).to_set()
      == self_@.un_acked_messages_for_dest(src@, dst@)
  post2_packets@.map_values(|p: CPacket| p@).to_set()
      == self_@.un_acked_messages_for_dest(src@, dst@)
  outbound_packet_seq_is_valid(post1_packets@)
  outbound_packet_seq_is_valid(post2_packets@)
  outbound_packet_seq_has_correct_srcs(post1_packets@, src@)
  outbound_packet_seq_has_correct_srcs(post2_packets@, src@)
  CSingleDelivery::packets_are_valid_messages(post1_packets@)
  CSingleDelivery::packets_are_valid_messages(post2_packets@)
  r1 == ()
  r2 == ()
  !det_retransmit_un_acked_packets_for_dst_equal(r1, r2, post1_packets, post2_packets)
```

---

## #5 `sht_demarshall_data_method` (×1 instance)

- **Source**: `verusage/source-projects/ironkv/verified/net_sht_v/net_sht_v__receive_with_demarshal.rs:381`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__net_sht_v__net_sht_v__receive_with_demarshal__sht_demarshall_data_method/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=713

### Why this is REAL_SAT

The function is trusted (`unimplemented!()`). Its ensures is hedged by `!(out is InvalidMessage)`:

```rust
ensures
    !(out is InvalidMessage) ==> {
        &&& out.is_marshalable()
        &&& out@ == sht_demarshal_data(buffer@)@
        &&& out.abstractable()
    }
```

Two implementations are both compliant if one returns `InvalidMessage` while the other parses successfully — the spec puts **no** lower bound on the implementation's effort to actually demarshal. Concretely, even when `buffer` is a well-formed message, an implementation that gives up and returns `CSingleMessage::InvalidMessage` still satisfies the ensures.

(`CSingleMessage::InvalidMessage` is a fieldless variant, so two successful "bail out" returns are themselves structurally equal — the witness has to mix `InvalidMessage` against a successful parse.)

**Fix directions**:
- Require the implementation to succeed when `buffer` is in `sht_demarshal_data`'s domain (e.g. `is_marshalable_data(buffer@) ==> !(out is InvalidMessage)`).
- Or accept the design choice and label this REAL_SAT permanently.

### Source function

```rust
pub fn sht_demarshall_data_method(buffer: &Vec<u8>) -> (out: CSingleMessage)
    ensures
        !(out is InvalidMessage) ==> {
            &&& out.is_marshalable()
            &&& out@ == sht_demarshal_data(buffer@)@
            &&& out.abstractable()
        }
{
    unimplemented!()
}
```

### Generated equal_fn

```rust
spec fn det_sht_demarshall_data_method_equal(r1: CSingleMessage, r2: CSingleMessage) -> bool {
    (r1 == r2)
}
```

### Generated det fn (synthetic proof obligation)

```rust
proof fn det_sht_demarshall_data_method(
    g_neq_tuple: bool,
    buffer: Vec<u8>, r1: CSingleMessage, r2: CSingleMessage)
    ensures
        ({
            &&& !(r1 is InvalidMessage) ==> {
                &&& r1.is_marshalable()
                &&& r1@ == sht_demarshal_data(buffer@)@
                &&& r1.abstractable()
            }
            &&& !(r2 is InvalidMessage) ==> {
                &&& r2.is_marshalable()
                &&& r2@ == sht_demarshal_data(buffer@)@
                &&& r2.abstractable()
            }
        }) ==> det_sht_demarshall_data_method_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_sht_demarshall_data_method_equal(r1, r2)); }
}
```

### z3-discovered witness

**Instance 1** — `ironkv__verified__net_sht_v__net_sht_v__receive_with_demarshal__sht_demarshall_data_method`:

```
  !det_sht_demarshall_data_method_equal(r1, r2)
```

### Hand-constructed witness (full assumes)

```
  buffer@ == seq![0u8, 0u8, 0u8, 0u8, 0u8, 0u8, 0u8, 0u8, /* a marshalable Ack tag */]
  sht_demarshal_data(buffer@)@ == AbstractSingleMessage::Ack{ ack_seqno: 0 }
  r1 is InvalidMessage
  !(r2 is InvalidMessage)
  r2 == CSingleMessage::Ack{ ack_seqno: 0 }
  r2.is_marshalable()
  r2.abstractable()
  r2@ == sht_demarshal_data(buffer@)@
  !det_sht_demarshall_data_method_equal(r1, r2)
```

The first ensures clause is vacuous for `r1` (since `r1 is InvalidMessage`), so `r1` is free; `r2` is forced to match `sht_demarshal_data(buffer@)@` because `!(r2 is InvalidMessage)`. Structural equality `r1 == r2` fails because the variants differ.
