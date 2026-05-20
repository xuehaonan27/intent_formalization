# ironkv spec-incompleteness case set

> 4 cases / 6 unique spec functions / 10 underlying instances.
> In each case below, two compliant implementations can produce different post-states on the same input — i.e. the spec is incomplete with respect to determinism.
> Source dataset: `spec-determinism/results-verusage-viewreg/ironkv/full_run.json` (May 12 viewreg full run).
>
> **Status (2026-05-20)**: cases are partitioned into two groups.
> - **Part 1 — Pending review** (2 cases): we believe the spec genuinely admits more behaviours than intended (or our equality check is stricter than what the spec calls for), but we want a second pair of eyes before committing to a fix direction.
> - **Part 2 — Confirmed incompleteness** (2 cases): the cause has been triaged and a fix direction is agreed.
>
> **Note**: the case `keys` (previously listed here) was relocated to `ironkv-equal-fn-too-strict-cases-2026-05-19.md` — its spec is in fact deterministic at the `set` abstraction it picks; the apparent non-determinism comes from the codegen's overly strict `equal_fn`, not from the spec.

## Overview

| # | Case | Functions covered | Source of non-determinism | Status |
|---|------|------------------|---------------------------|--------|
| 1 | `retransmit_un_acked_packets` (also `retransmit_un_acked_packets_for_dst`) | 2 | Spec only constrains the `.to_set()` image of the produced `Vec<CPacket>`; equal_fn falls back to structural `Vec==` and so rejects permutations | Pending: equal_fn-too-strict candidate |
| 2 | `host_model_next_receive_message` | 1 | Top-level `|||` (process vs ignore-unparseable) with no guard saying when the ignore branch may fire | Pending: under-specified error path |
| 3 | `values_agree` (also `keys_in_index_range_agree`) | 2 | Spec only constrains `ret.1` when `!ret.0`; `ret.0 == true` leaves `ret.1` free | Confirmed: spec bug |
| 4 | `sht_demarshall_data_method` | 1 | The `InvalidMessage` branch is entirely unconstrained by the spec | Confirmed: spec design choice |

## Part 1 — Pending review

## #1 `retransmit_un_acked_packets` (×2 instances; same issue in `retransmit_un_acked_packets_for_dst`, ×2 instances)

- **Source**: [`verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__retransmit_un_acked_packets.rs`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__retransmit_un_acked_packets.rs)
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_noreceive_noclock_next__retransmit_un_acked_packets/`

### Why this is incomplete (candidate: equal_fn-too-strict)

The function returns `Vec<CPacket>`, but the spec only constrains the **set** image of `packets@.map_values(@)`:

```
abstractify_seq_of_cpackets_to_set_of_sht_packets(packets@) == self@.un_acked_messages(src@),
self@.un_acked_messages(src@) == packets@.map_values(|p: CPacket| p@).to_set(),
```

Two implementations may iterate the underlying `epmap` in different orders and produce permutations of the same packet set. The codegen, working purely from the return type, falls back to structural `Vec<CPacket>` equality, which rejects permutations. Even at the right view level the resulting `s1 =~= s2` would remain stricter than `s1.to_set() == s2.to_set()`.

**Same issue also seen in**: `retransmit_un_acked_packets_for_dst` (in-place accumulator variant in the same file). Its ensures uses the same `.to_set()`-equivalence on the post-state, so any order of appended packets is allowed; `det_*_equal` again falls back to structural `Vec==`. The `_for_dst` body is `unimplemented!()` (a trusted stub), so only the spec contributes to the witness.

### Source function (full)

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
{
    let mut packets = Vec::new();
    let dests = self.send_state.epmap.keys();
    let mut dst_i = 0;
    proof { /* ... assert_seqs_equal / assert_sets_equal / lemma_un_acked_messages_for_dests_empty ... */ }

    while dst_i < dests.len()
      invariant
          self.valid(),
          dests@.map_values(|ep: EndPoint| ep@).to_set() == self.send_state.epmap@.dom(),
          src.abstractable(),
          0 <= dst_i <= dests.len(),
          outbound_packet_seq_is_valid(packets@),
          outbound_packet_seq_has_correct_srcs(packets@, src@),
          packets@.map_values(|p: CPacket| p@).to_set() ==
              self@.un_acked_messages_for_dests(src@, dests@.subrange(0, dst_i as int).map_values(|ep: EndPoint| ep@).to_set()),
          Self::packets_are_valid_messages(packets@),
      decreases
          dests.len() - dst_i
    {
        let dst = &dests[dst_i];
        self.retransmit_un_acked_packets_for_dst(src, dst, &mut packets);
        dst_i = dst_i + 1;
        proof { /* ~30 lines: lemma_to_set_singleton_auto / lemma_map_values_singleton_auto /
                   lemma_flatten_sets_union_auto / set_map_union_auto / ... to relate the
                   updated packets-set to un_acked_messages_for_dests(...) */ }
    }
    proof { /* tail lemma assert_sets_equal!: dests covers all dests → un_acked_messages(src@) */ }
    packets
}
```

## #2 `host_model_next_receive_message` (×1 instance)

- **Source**: [`verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_receive_message.rs:759`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_receive_message.rs#L759)
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_receive_message__host_model_next_receive_message/`

### Why this is incomplete (under-specified error path)

The spec writes a 2-way `|||` at the top level of `ensures`: an implementation may either *process* a received packet via `process_message` or *drop* it as unparseable via `host_ignoring_unparseable`. **Crucially, the spec never says when the drop branch is allowed to fire** — there is no guard like `(cpacket.msg is well-formed) ==> process_message(...)`. As written, two implementations can disagree on the same well-formed input: one runs the appropriate handler, the other "gives up" and discards the packet. Both satisfy the ensures.

We do not believe this is an intentional IronFleet feature; the error path appears to have been added without specifying its trigger. The reasonable fix is to add a guard that pins down which branch the implementation must take for each class of input.

**Pending question**: should we treat this family as a documented under-specification, or push back and ask for guards distinguishing the normal and error branches?

### Source function (full)

```rust
fn host_model_next_receive_message(&mut self) -> (sent_packets: Vec<CPacket>)
    requires /* received_packet is Some, host_state_common_preconditions, … */
    ensures
        match old(self).received_packet {
            Some(cpacket) => {
                &&& cpacket_seq_is_abstractable(sent_packets@)
                &&& self.host_state_common_postconditions(*old(self),
                      (*old(self)).received_packet.unwrap(), sent_packets@)
                &&& {
                    ||| process_message(old(self)@, self@,
                          abstractify_seq_of_cpackets_to_set_of_sht_packets(sent_packets@))
                    ||| Self::host_ignoring_unparseable(old(self)@, self@,
                          abstractify_seq_of_cpackets_to_set_of_sht_packets(sent_packets@))
                  }
            },
            None => false,
        },
{
    proof { self.delegation_map.valid_implies_complete(); }
    let cpacket = self.received_packet.as_ref().unwrap();
    match &cpacket.msg {
        CSingleMessage::Message{m, ..} =>
            match m {
                CMessage::GetRequest{..} => self.host_model_next_get_request(),
                CMessage::SetRequest{..} => self.host_model_next_set_request(),
                CMessage::Delegate{..}   => self.host_model_next_delegate(),
                CMessage::Shard{..}      => self.host_model_next_shard(),
                CMessage::Reply{..} | CMessage::Redirect{..} => {
                    self.received_packet = None;
                    let sent_packets = vec![];
                    proof { /* assert_sets_equal!: abstractify_..._to_set_of_sht_packets(sent_packets@) == Set::empty() */ };
                    sent_packets
                },
            },
        _ => { assert(false); unreached() },
    }
}
```

## Part 2 — Confirmed incompleteness

## #3 `values_agree` (×2 instances; same issue in `keys_in_index_range_agree`, ×2 instances)

- **Source**: [`verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__values_agree.rs`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__values_agree.rs)
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__values_agree/`

### Why this is incomplete

The function returns `(bool, bool)`. The spec only constrains `ret.1` in the `!ret.0` branch:

```
ret.0 == forall |i| lo <= i <= hi ==> self.vals@[i]@ == v@,
!ret.0 ==> ret.1 == (self.vals@[hi as int]@ != v@
                     && forall |i| lo <= i < hi ==> self.vals@[i]@ == v@)
```

When `ret.0 == true`, the antecedent of the second ensure is false, so the entire clause holds vacuously and **`ret.1` is unconstrained**. Two compliant implementations may return `(true, true)` and `(true, false)`.

**Suggested spec fix**: add `ret.0 ==> ret.1 == ret.0` (or `ret.0 ==> !ret.1`, whichever matches caller expectations). One line.

**Same issue also seen in**: `keys_in_index_range_agree` in `delegation_map_v__impl3` — a thin wrapper that calls `values_agree` and forwards the `(bool, bool)` return value, so the missing constraint on `ret.1` propagates one level up. Fixing `values_agree` fixes the wrapper automatically.

```rust
fn keys_in_index_range_agree(&self, lo: usize, hi: usize, v: &ID) -> (ret: (bool, bool))
    requires self.valid(), 0 <= lo <= hi < self.keys@.len(),
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

### Source function (full)

```rust
fn values_agree(&self, lo: usize, hi: usize, v: &ID) -> (ret: (bool, bool))
    requires
        self.valid(),
        0 <= lo <= hi < self.keys@.len(),
    ensures
        ret.0 == forall |i| #![auto] lo <= i <= hi ==> self.vals@[i]@ == v@,
        !ret.0 ==> (ret.1 == (self.vals@[hi as int]@ != v@
                              && forall |i| #![auto] lo <= i < hi ==> self.vals@[i]@ == v@)),
{
    let mut i = lo;
    while i <= hi
        invariant
            lo <= i,
            self.keys@.len() <= usize::MAX,
            hi < self.keys@.len() as usize == self.vals@.len(),
            forall |j| #![auto] lo <= j < i ==> self.vals@[j]@ == v@,
        decreases self.keys@.len() - i
    {
        let eq = do_end_points_match(&self.vals[i], v);
        if !eq {
            if i == hi { return (false, true); }
            else       { return (false, false); }
        } else {
            proof { /* K::cmp_properties(); — currently commented out */ }
        }
        i = i + 1;
    }
    (true, true)
}
```

## #4 `sht_demarshall_data_method` (×1 instance)

- **Source**: [`verusage/source-projects/ironkv/verified/net_sht_v/net_sht_v__receive_with_demarshal.rs:381`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/ironkv/verified/net_sht_v/net_sht_v__receive_with_demarshal.rs#L381)
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__net_sht_v__net_sht_v__receive_with_demarshal__sht_demarshall_data_method/`

### Why this is incomplete

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
- Or accept the design choice and document the under-specification permanently.

### Source function (full)

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

## Appendix: other under-specified error paths

The pattern in case #2 — an `ensures` written as `||| normal_path ||| error_path` without any guard saying when the error path applies — recurs in several other ironkv functions:

- `host_model_next_delegate` (via `next_delegate_postconditions`): `||| next_delegate(pre, post, ..., out) ||| Self::host_ignoring_unparseable(pre, post, out)`.
- `process_received_packet_next_impl` (called from two source locations): `||| process_received_packet_next ||| ignore_nonsensical_delegation_packet`.
- `parse_command_line_configuration`: 3-way disjunction in the `None` branch, listing three possible reasons for parse failure with no constraint on which one applies when several hold simultaneously.
- `host_model_next_shard`, `host_model_next_get_request`, `host_model_next_set_request`: same shape, but encoded as `exists |sm, m, b| next_*(...)` rather than an explicit `|||` — the binder leaks into the post-state, so the implementation effectively picks any witness.

In every instance, the spec offers two (or more) legal post-states for the same input without prescribing which one the implementation must produce. We believe this reflects an incomplete handling of the error path rather than an intentional under-specification: the original author wanted to model "the host may always reject an unparseable / nonsensical packet," but did not write down "...and otherwise must process it." The resulting spec is silent on the actual semantics for any non-trivial input.
