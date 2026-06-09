# Consolidated Incompleteness Cases — Issue Bundle (2026-06-09)

Verbatim concatenation of the per-project incompleteness audit docs
linked in `progress/progress-2026-0609.md` Future Work §3, grouped by
the three issue-submission clusters. Each source file is included in
full; nothing is rewritten. The intent is a single artefact to read
through when drafting the three upstream issues (one per cluster).

## Cluster index

| Cluster              | Sources concatenated below                                                                                  |
|----------------------|-------------------------------------------------------------------------------------------------------------|
| Verus ecosystem      | ironkv, storage, small-projects (covers memory-allocator + nrkernel + anvil-library cases)                  |
| Anvil ecosystem      | (anvil-library case lives inside the `small-projects` doc included under Verus above; no AC doc yet)        |
| Atmosphere ecosystem | atmosphere-incompleteness-pr, view-quotient-failure-summary (the 4 SLL A-class)                             |

---

# Verus ecosystem


---

> **Source:** [`spec-determinism/docs/ironkv-spec-incompleteness-cases-2026-05-20.en.md`](./ironkv-spec-incompleteness-cases-2026-05-20.en.md)

# ironkv spec-incompleteness case set

> **Status (2026-05-20)**: cases are partitioned into two groups.
> - **Part 1 — Pending review** (2 cases): we believe the spec genuinely admits more behaviours than intended (or our equality check is stricter than what the spec calls for), but we want a second pair of eyes before committing to a fix direction.
> - **Part 2 — Confirmed incompleteness** (2 cases): the cause has been triaged and a fix direction is agreed.

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

---

> **Source:** [`spec-determinism/docs/storage-incompleteness-cases-2026-05-26.en.md`](./storage-incompleteness-cases-2026-05-26.en.md)

# storage spec-incompleteness case set

> 12 incomplete cases on the rerun11 storage corpus, included in this bundle.
> Each case shows two implementations whose post-states differ on the same input even though both satisfy the spec — i.e. the spec is incomplete with respect to determinism.
> Source dataset: `spec-determinism/results-verusage-viewreg/storage/full_run.json`.
>
> The 12 cases fall into three patterns:
> - **Part 2 — Error path under-specified** (1 case): even legitimate inputs are allowed to return `Err(...)`; on invalid inputs multiple `Err(...)` variants coexist and the `Ok` arm is vacuously satisfied.
> - **Part 3 — `impervious_to_corruption` pattern family** (7 cases): every `Err(...)` / `None` / `false` arm is guarded by `... ==> !impervious_to_corruption` (or just `!impervious_to_corruption`). Real hardware sets that constant to `false`, so the spec lets *any* implementation report a spurious corruption error on any valid input. Detector-missed because the current `permissive_or` test only fires on syntactic `|||`; these are implication-shaped (`==>`), so they currently land in the `unknown` (`r0_z3=unknown`) or `verus_error` (`Box<S>: SpecEq` residual) bucket.
> - **Part 4 — Opaque internal state under-specified** (4 cases): a struct contains an `#[verifier::external_body]` opaque field (e.g. `ExternalDigest`) plus a `Ghost<...>` view; the ensures pins only the ghost view, leaving the opaque field unconstrained. The generated equal_fn includes structural equality on the opaque field, so two impls with different opaque-field values both satisfy the spec yet are unequal.

## Overview

### Pattern 2 — Error path under-specified (1 case)

| # | Case | Notes |
|---|------|-------|
| 2 | `read_log_variables` (`log_logimpl/logimpl_start.rs`) | The error path is the gap: (a) a **legitimate input** (`state.is_Some()`, all CRCs / fields parse) still admits `Err(CRCMismatch)` whenever `!impervious_to_corruption`, so an Ok return is not forced even when nothing is wrong; (b) on a **state.is_None()** input multiple `Err(...)` variants are simultaneously admissible and the `Ok` arm is vacuously satisfied by any `LogInfo`. |

### Pattern 3 — `impervious_to_corruption` family (7 cases)

| # | Case | Notes |
|---|------|-------|
| 3 | `read_cdb` (`log_logimpl/logimpl_start.rs`) | `Err(CRCMismatch) => !pm_region.constants().impervious_to_corruption`. No `state.is_Some()` guard — spurious CRC error admissible *unconditionally* when not impervious. Currently `unknown`. |
| 4 | `read_cdb` (`log_start/start_read_cdb.rs`) | Same spec as #3 (sibling copy in `log_start/`). Currently `unknown`. |
| 5 | `check_cdb` (`log_start/start_read_cdb.rs`) | `None => !impervious_to_corruption` on an `Option<bool>` return — admissible whenever not impervious, even though the precondition pins `true_cdb ∈ {CDB_FALSE, CDB_TRUE}`. Currently `unknown`. |
| 6 | `check_cdb` (`pmem_pmemutil/pmemutil_check_cdb.rs`) | Same spec as #5 (sibling copy in `pmem_pmemutil/`). Currently `unknown`. |
| 7 | `check_crc` (`pmem_pmemutil/pmemutil_check_crc.rs`) | `true_crc_bytes == spec_crc_bytes(true_data_bytes) ==> if b { ... } else { !impervious_to_corruption }` — even on matching-CRC input, `b=false` is admissible. Currently `unknown`. |
| 8 | `check_crc` (`log_start/start_read_log_variables.rs`) | Same spec as #7 (sibling copy embedded in the `start_read_log_variables.rs` file). Currently `verus_error` (`Box<S>: SpecEq` residual — same semantic issue as #7). |
| 9 | `read_log_variables` (`log_start/start_read_log_variables.rs`) | Same spec as #2 (sibling copy in `log_start/`); the spec also carries the `impervious_to_corruption` arm so it sits in this pattern alongside Part 2's #2. Currently `verus_error` (`Box<S>: SpecEq` residual). |

### Pattern 4 — Opaque internal state under-specified (4 cases)

| # | Case | Notes |
|---|------|-------|
| 11 | `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc.rs`) | Spec pins only `output.bytes_in_digest() == Seq::empty()` (a `Ghost<...>` view). The `digest: ExternalDigest` field (an `#[verifier::external_body]` opaque) is not constrained. Generated `det_new_equal` compares `r1.digest == r2.digest` AND the ghost view; two impls with different initial digest state both satisfy ensures yet are structurally unequal. Currently `unknown`. |
| 12 | `CrcDigest::write<S>` (`pmem_pmemutil/pmemutil_calculate_crc.rs`) | Spec pins `self.bytes_in_digest() == old(self).bytes_in_digest().push(val.spec_to_bytes())`. The `digest` field update is unconstrained — two impls (e.g. incremental CRC32 vs. recompute-on-`sum64`) produce different opaque post-states. Currently `unknown`. |
| 13 | `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc_bytes.rs`) | Same spec as #11 (sibling file). Currently `unknown`. |
| 14 | `CrcDigest::write_bytes` (`pmem_pmemutil/pmemutil_calculate_crc_bytes.rs`) | Same defect as #12; `&[u8]` instead of `&S` argument. Currently `unknown`. |

## Witness format

Each witness is written as a list of assumed facts about inputs and the two outputs (`r1` / `r2`, `post1_*` / `post2_*`). Lines containing `==` are equalities the witness commits to; the closing line starting with `!det_*_equal(...)` is the negated equivalence that fails the structural equality check.

---

## Part 2 — Error path under-specified

### #2 `read_log_variables` (×1 instance)

- **Source**: [`verified/log_logimpl/logimpl_start.rs:100`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/log_logimpl/logimpl_start.rs#L100)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__log_logimpl__logimpl_start__read_log_variables/`

#### What the function does

Reverse of `write_setup_metadata`: read a persistent-memory region that has already passed byte-level CRC self-checks (`metadata_types_set` holds and the CDB byte matches the input `cdb` parameter) and either:

- return `Ok(LogInfo)` describing the log's runtime state (`log_area_len`, `head`, `head_log_area_offset`, `log_length`, `log_plus_pending_length`), or
- return `Err(LogErr::...)` flagging *semantic* fields that disagree with what this caller expects: wrong `program_guid`, unsupported `version_number`, `log_id` mismatch, `region_size` mismatch, or a catch-all "invalid memory contents".

Note the precondition `metadata_types_set(committed)` already rules out byte-level parse failures and CRC mismatches on the active slot; everything checked by the ensures is at a *semantic* layer above that.

#### Why this is incomplete

The error path is the gap. Three compounding issues — the most important is the first one, which means **the spec does not even force `Ok` on legitimate input**:

1. **`Err(CRCMismatch)` is admissible even on a legitimate input.** The arm requires only `state.is_Some() ==> !pm_region.constants().impervious_to_corruption`. When `impervious_to_corruption == false` (a real and common hardware configuration), the consequent is true, so `Err(CRCMismatch)` is permitted on **any** `state.is_Some()` input — including inputs where the precondition `metadata_types_set(committed)` guarantees every CRC actually matches. In other words: on a fully valid header, the spec lets the impl claim "CRC mismatch" and abort even though no CRC actually mismatches. There is no `state.is_Some() ==> result.is_Ok()` clause anywhere.

2. **`Ok(info)` arm uses `==>` not `<==>`.** When `recover_given_cdb(committed, log_id, cdb).is_None()` (e.g. wrong `program_guid`, wrong `log_id`, oversized `log_length`), the implication `state.is_Some() ==> { consistency... }` has a false antecedent — the whole clause becomes **vacuously true**, so `Ok(arbitrary LogInfo)` is admissible on a clearly-invalid input.

3. **Multiple `Err(...)` variants are simultaneously legal on the same `state.is_None()` input.** When `state.is_None()`, all five Err variants admit it:

   | Err variant | Condition | Free fields |
   |---|---|---|
   | `CRCMismatch` | `state.is_Some() ==> ...` — **vacuously** when state is None | — |
   | `InvalidMemoryContents` | `len < min ||| state is None` | — |
   | `ProgramVersionNumberUnsupported { vn, max }` | `state is None && vn != max` | any two distinct u64s |
   | `LogIDMismatch { expected, read }` | `state is None && expected != read` | any two distinct u128s |
   | `RegionSizeMismatch { expected, read }` | `state is None && expected != read` | any two distinct u64s |

   On a single input where `state.is_None()` (e.g. on-disk `region_metadata.log_id ≠ caller log_id`), the spec permits Ok-with-arbitrary-info *and* any of 5 Err variants — six families of return values for one input.

The classifier promotes via the `|||` at L121-123 (`InvalidMemoryContents` arm), and the `permissive_or` finding is *real* here: that OR is the literal source of "two ways to legitimately return `InvalidMemoryContents`". But the deeper non-determinism is issues (1) and (2): the error path is admissible on inputs that should force `Ok`, and the `Ok` arm is vacuous on inputs that should force a specific `Err`.

A subtle artefact of the codegen: the generated `equal_fn` for `Result<LogInfo, LogErr>` only descends into the `Ok` payload (see below). So differences *between* `Err` variants are invisible to the determinism check — the materialisable witness has to use the **Ok-vs-Err split**, not the Err-vs-Err split. The Err-vs-Err split is also a real incompleteness, but the current tool only catches the Ok-vs-Err one.

#### Source function

```rust
#[verifier::external_body]
pub fn read_log_variables<PMRegion: PersistentMemoryRegion>(
    pm_region: &PMRegion,
    log_id: u128,
    cdb: bool,
) -> (result: Result<LogInfo, LogErr>)
    requires
        pm_region.inv(),
        pm_region@.no_outstanding_writes(),
        metadata_types_set(pm_region@.committed()),
        cdb == deserialize_and_check_log_cdb(pm_region@.committed()).unwrap(),
    ensures
        ({
            let state = recover_given_cdb(pm_region@.committed(), log_id, cdb);
            match result {
                Ok(info) => state.is_Some() ==> {
                    &&& metadata_consistent_with_info(pm_region@, log_id, cdb, info)
                    &&& info_consistent_with_log_area_in_region(pm_region@, info, state.unwrap())
                },
                Err(LogErr::CRCMismatch) =>
                    state.is_Some() ==> !pm_region.constants().impervious_to_corruption,
                Err(LogErr::StartFailedDueToInvalidMemoryContents) => {
                    ||| pm_region@.len() < ABSOLUTE_POS_OF_LOG_AREA + MIN_LOG_AREA_SIZE
                    ||| state is None
                },
                Err(LogErr::StartFailedDueToProgramVersionNumberUnsupported {
                    version_number, max_supported,
                }) => {
                    &&& state is None
                    &&& version_number != max_supported
                },
                Err(LogErr::StartFailedDueToLogIDMismatch { log_id_expected, log_id_read }) => {
                    &&& state is None
                    &&& log_id_expected != log_id_read
                },
                Err(LogErr::StartFailedDueToRegionSizeMismatch {
                    region_size_expected, region_size_read,
                }) => {
                    &&& state is None
                    &&& region_size_expected != region_size_read
                },
                _ => false,
            }
        }),
{ unimplemented!() }
```

Supporting spec fn (abbreviated):

```rust
// recover_given_cdb returns None when any of the following hold (the requires-clause
// rules out only byte-parse and CRC failures on the *active* slot, NOT these semantic checks):
pub open spec fn recover_given_cdb(mem: Seq<u8>, log_id: u128, cdb: bool) -> Option<AbstractLogState> {
    // ... extracts GlobalMetadata, RegionMetadata, active LogMetadata ...
    if mem.len() < ABSOLUTE_POS_OF_LOG_AREA + MIN_LOG_AREA_SIZE              { None }
    else if global_meta.program_guid != LOG_PROGRAM_GUID                     { None }
    else if global_meta.version_number != 1                                  { None }
    else if global_meta.length_of_region_metadata != RegionMetadata::spec_size_of() { None }
    else if region_meta.region_size != mem.len()                             { None }
    else if region_meta.log_id != log_id                                     { None }
    else if region_meta.log_area_len < MIN_LOG_AREA_SIZE                     { None }
    else if mem.len() < ABSOLUTE_POS_OF_LOG_AREA + region_meta.log_area_len  { None }
    else if log_meta.log_length > region_meta.log_area_len                   { None }
    else if log_meta.head + log_meta.log_length > u128::MAX                  { None }
    else { Some(AbstractLogState { head: log_meta.head as int, log: ..., pending: empty, capacity: ... }) }
}
```

Each `None` branch is a separate semantic-fail condition that can be reached *without* violating the requires clause.

#### Generated equal_fn

```rust
spec fn det_read_log_variables_equal(
    r1: Result<LogInfo, LogErr>,
    r2: Result<LogInfo, LogErr>,
) -> bool {
    ((r1 is Ok) == (r2 is Ok))
    && ((r1 is Ok) ==> ((r1->Ok_0).view() == (r2->Ok_0).view()))
}
```

The codegen for `Result<T, E>` only descends into the `Ok` payload — `Err` variants and their fields are not compared. So this equal_fn flags only:
- `Ok` vs `Err` discriminant disagreement, or
- two `Ok`s whose `LogInfo.view()` differs.

Different `Err` variants compare equal under this fn even though they carry different information; that part of the incompleteness is invisible to the current tool.

#### Witness

Pick an input where `state.is_None()` through the simplest semantic-mismatch path: the on-disk `region_metadata.log_id` (a fixed value baked into the bytes) differs from the caller's `log_id` parameter.

```
  pre_pm_region.inv()
  pre_pm_region@.no_outstanding_writes()

  // ---- Construct `committed` so metadata_types_set passes but region_meta.log_id ≠ caller log_id ----
  pre_pm_region@.committed() ==
       GlobalMetadata { version_number: 1, length_of_region_metadata: 32, program_guid: LOG_PROGRAM_GUID }.spec_to_bytes()  // [0,32)
    ++ u64::spec_to_bytes(crc_of(GlobalMetadata { 1, 32, LOG_PROGRAM_GUID }))                                               // [32,40)
    ++ RegionMetadata   { region_size: 257, log_area_len: 1, log_id: 0xAAA }.spec_to_bytes()                                // [40,72)
    ++ u64::spec_to_bytes(crc_of(RegionMetadata { 257, 1, 0xAAA }))                                                         // [72,80)
    ++ u64::spec_to_bytes(CDB_FALSE)                                                                                        // [80,88)
    ++ LogMetadata { log_length: 0, _padding: 0, head: 0 }.spec_to_bytes()                                                  // [88,120)  active
    ++ u64::spec_to_bytes(crc_of(LogMetadata { 0, 0, 0 }))                                                                  // [120,128) active CRC
    ++ Seq::new(40, |_| 0u8)                                                                                                // [128,168) inactive slot
    ++ Seq::new(88, |_| 0u8)                                                                                                // [168,256) gap
    ++ Seq::new( 1, |_| 0u8)                                                                                                // [256,257) log_area

  metadata_types_set(pre_pm_region@.committed())                       == true
  deserialize_and_check_log_cdb(pre_pm_region@.committed())            == Some(false)
  cdb                                                                  == false              // matches on-disk CDB_FALSE

  // Caller asks for log_id = 0xBBB; on-disk region_metadata.log_id = 0xAAA.
  log_id == 0xBBB

  // Therefore recover_given_cdb hits the `region_meta.log_id != log_id` branch.
  let state := recover_given_cdb(pre_pm_region@.committed(), 0xBBB, false)
            == None

  // ---- Run 1 — Impl A: report LogIDMismatch (honest) ----
  r1 == Err(LogErr::StartFailedDueToLogIDMismatch {
      log_id_expected: 0xBBB,
      log_id_read:     0xAAA,
  })
       // ensures arm for LogIDMismatch: state is None ✓, 0xBBB ≠ 0xAAA ✓.

  // ---- Run 2 — Impl B: return Ok with an arbitrary (junk) LogInfo (vacuous) ----
  r2 == Ok(LogInfo {
      log_area_len:            0,
      head:                    0,
      head_log_area_offset:    0,
      log_length:              0,
      log_plus_pending_length: 0,
  })
       // ensures arm for Ok: state.is_Some() ==> { ... }
       // state is None ⇒ antecedent false ⇒ clause vacuously true ⇒ any LogInfo is admissible.

  // Both runs satisfy every ensures clause on the same pre-state and inputs.
  (r1 is Ok) == false
  (r2 is Ok) == true
  ((r1 is Ok) == (r2 is Ok)) == false
  !det_read_log_variables_equal(r1, r2)
```

Aside — Err-vs-Err witnesses that the current equal_fn cannot see (still real incompleteness):
- r1 = `Err(LogIDMismatch { 0xBBB, 0xAAA })`, r2 = `Err(InvalidMemoryContents)`: both legal on the input above (state is None covers both arms), but equal_fn treats them as equal because it ignores Err variants.
- r1 = `Err(ProgramVersionNumberUnsupported { vn: 0, max: 1 })` on an input with the same `program_guid=LOG_PROGRAM_GUID` (i.e. version is fine), r2 = `Err(LogIDMismatch { ... })`: spec lets both through despite `version_number != max_supported` being a *fabricated* claim.

#### Suggested fix

Two layers of tightening, both needed:

(1) Make the `Ok` arm an iff and require `state.is_Some()`:

```rust
Ok(info) =>
    &&& state.is_Some()
    &&& metadata_consistent_with_info(pm_region@, log_id, cdb, info)
    &&& info_consistent_with_log_area_in_region(pm_region@, info, state.unwrap()),
```

(2) Bind each `Err` variant to the *unique* failure path that produces it, with a priority order so that for any input exactly one variant is admissible. Extract `global_meta = deserialize_global_metadata(committed)` and `region_meta = deserialize_region_metadata(committed)` and write:

```rust
Err(LogErr::CRCMismatch) =>
    // Byte-level corruption on a CRC-bearing slot. metadata_types_set guarantees
    // the active slot is self-consistent, so this can only fire if hardware can corrupt
    // (i.e. the caller violated metadata_types_set assumption transiently).
    state.is_Some() && !pm_region.constants().impervious_to_corruption,

Err(LogErr::StartFailedDueToProgramVersionNumberUnsupported { version_number, max_supported }) =>
    // iff the program version is wrong (highest-priority semantic check).
    global_meta.program_guid == LOG_PROGRAM_GUID
    && global_meta.version_number != 1
    && version_number == global_meta.version_number
    && max_supported  == 1,

Err(LogErr::StartFailedDueToLogIDMismatch { log_id_expected, log_id_read }) =>
    // iff GUID + version are OK but log_id mismatches.
    global_meta.program_guid == LOG_PROGRAM_GUID
    && global_meta.version_number == 1
    && global_meta.length_of_region_metadata == 32
    && region_meta.log_id != log_id
    && log_id_expected == log_id
    && log_id_read     == region_meta.log_id,

Err(LogErr::StartFailedDueToRegionSizeMismatch { region_size_expected, region_size_read }) =>
    // iff GUID + version + log_id are OK but region_size mismatches.
    global_meta.program_guid == LOG_PROGRAM_GUID
    && global_meta.version_number == 1
    && region_meta.log_id == log_id
    && region_meta.region_size != pm_region@.len()
    && region_size_expected == pm_region@.len()
    && region_size_read     == region_meta.region_size,

Err(LogErr::StartFailedDueToInvalidMemoryContents) =>
    // Strict catch-all: state is None for some *other* reason
    // (log_area_len too small / total length too short / log_length > area / head overflow).
    state.is_None()
    && global_meta.program_guid == LOG_PROGRAM_GUID
    && global_meta.version_number == 1
    && region_meta.log_id == log_id
    && region_meta.region_size == pm_region@.len(),

_ => false,
```

After these changes the input uniquely determines which arm is taken, the Ok arm forbids junk info, and the equal_fn's blindness to Err-variant differences no longer matters — different impls are forced to return the same Err with the same fields.

---

## Part 3 — `impervious_to_corruption` pattern family

### Shared shape

CapybaraKV's persistent-memory abstraction models hardware corruption with a constant `pm_region.constants().impervious_to_corruption: bool`. The convention throughout the storage layer is that **every spurious-failure arm** of a read/check function is permitted *whenever the hardware is not impervious*. Concretely each function's ensures contains one of three syntactic forms:

```rust
// Form A — Result return, Err admissible unconditionally when not impervious.
Err(LogErr::CRCMismatch) => !pm_region.constants().impervious_to_corruption,

// Form B — Option return, None admissible whenever not impervious.
None => !impervious_to_corruption,

// Form C — bool return, false admissible whenever not impervious (under a precondition antecedent).
true_crc_bytes == spec_crc_bytes(true_data_bytes) ==> {
    if b { ... } else { !impervious_to_corruption }
}
```

`impervious_to_corruption` is a hardware-deployment property — on real persistent memory it is `false`. On every concrete deployment the spec therefore admits **two valid outcomes on the same input**: the *correct* `Ok(b)` / `Some(b)` / `b=true` *and* the spurious-corruption `Err(CRCMismatch)` / `None` / `b=false`. The equal_fn is sensitive to the Ok-vs-Err / Some-vs-None / true-vs-false discriminant, so this is real determinism non-determinism — two implementations may legitimately disagree.

The 7 affected functions all sit on the log-startup read path and share the same idiom. Their precondition is strong enough to pin the *correct* answer (CDB ∈ {FALSE, TRUE}, CRC matches data); the only thing the spec doesn't force is "must return the correct answer when the hardware isn't claimed impervious".

### Why the current detector misses these

`spec_determinism.classify.ensures_uses_permissive_or` triggers on **syntactic disjunction in the ensures** (`|||` or `||`). The forms above are *implications* (`==>`), not disjunctions, so the detector lets them through. The functions then run through schema search; z3 cannot rule out the spurious arm (because it really is admissible under the spec), R0 comes back `unknown`, and the case lands in `ok_inconclusive` — what the public docs call **`unknown`**. The 2 sibling cases in `start_read_log_variables.rs` are additionally blocked by the residual `Box<S>: SpecEq<S>` source incompatibility and surface as `verus_error` rather than `unknown`, but the underlying spec defect is the same.

A reasonable detector extension that would catch all 7 (and the originally-flagged `read_log_variables`): treat `Err(_) | None | (... = false)` arms as "permitted" whenever the arm body is **implied by** `!pm_region.constants().impervious_to_corruption` (or has that term as a top-level conjunct on the right of `==>`). This requires a tiny AST scan, not a model query.

### Per-case spec snippets

#### #3 `read_cdb` (`log_logimpl/logimpl_start.rs`) — Form A

- **Source**: [`verified/log_logimpl/logimpl_start.rs:77`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/log_logimpl/logimpl_start.rs#L77)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__log_logimpl__logimpl_start__read_cdb/`
- **Status**: `unknown` (R0 = unknown).

Signature + ensures:

```rust
#[verifier::external_body]
pub fn read_cdb<PMRegion: PersistentMemoryRegion>(pm_region: &PMRegion) -> (result: Result<bool, LogErr>)
    requires
        pm_region.inv(),
        recover_cdb(pm_region@.committed()).is_Some(),
        pm_region@.no_outstanding_writes(),
        metadata_types_set(pm_region@.committed()),
    ensures
        match result {
            Ok(b) => Some(b) == recover_cdb(pm_region@.committed()),
            Err(LogErr::CRCMismatch) => !pm_region.constants().impervious_to_corruption,
            Err(e) => e == LogErr::PmemErr { err: PmemError::AccessOutOfRange },
        },
```

`recover_cdb(committed).is_Some()` is in the requires, so `Ok(b)` is always derivable with the unique `b` returned by `recover_cdb`. `Err(CRCMismatch)` is admissible whenever `!impervious_to_corruption`. On any concrete deployment (real hardware sets `impervious_to_corruption = false`), the spec allows both `Ok(correct_b)` *and* `Err(CRCMismatch)`.

**Other instances of the same pattern** (specs structurally identical to #3 — see overview table for one-line summaries):

- `read_cdb` Form A sibling — `log_start/start_read_cdb.rs` (#4)
- `check_cdb` Form B — `log_start/start_read_cdb.rs` (#5), `pmem_pmemutil/pmemutil_check_cdb.rs` (#6)
- `check_crc` Form C — `pmem_pmemutil/pmemutil_check_crc.rs` (#7), `log_start/start_read_log_variables.rs` (#8 — surfaces as `verus_error` from the `Box<S>: SpecEq` residual)
- `read_log_variables` — `log_start/start_read_log_variables.rs` (#9 — Form A + Part 2 issues stacked; `verus_error`)

### Shared witness pattern

All seven follow the same template — for any input that satisfies the (strong) precondition, the spec admits two outcomes:

| function | r1 (correct) | r2 (spurious, admissible iff `!impervious_to_corruption`) | discriminator |
|---|---|---|---|
| `read_cdb` ×2 | `Ok(true)` (or `Ok(false)`, matching `recover_cdb(committed)`) | `Err(LogErr::CRCMismatch)` | Ok vs Err |
| `check_cdb` ×2 | `Some(true)` (or `Some(false)`, matching `true_cdb`) | `None` | Some vs None |
| `check_crc` ×2 | `true` (when read-back bytes match the on-disk truth — they do, since the precondition allows the impervious branch) | `false` (claiming a mismatch the impl never actually observed) | true vs false |
| `read_log_variables` (`log_start/`) | `Ok(LogInfo { ... })` | `Err(LogErr::CRCMismatch)` | Ok vs Err |

A concrete `read_cdb` witness (for #3 and #4 — identical):

```
  pre_pm_region.inv()
  pre_pm_region@.no_outstanding_writes()
  metadata_types_set(pre_pm_region@.committed())
  pre_pm_region.constants().impervious_to_corruption == false      // real hardware

  // CDB bytes at offset 80..88 decode to CDB_FALSE, so recover_cdb returns Some(false).
  recover_cdb(pre_pm_region@.committed()) == Some(false)

  // ---- Run 1 — Impl A: honest, returns the correct CDB ----
  r1 == Ok(false)
       // ensures arm Ok(b): Some(false) == recover_cdb(committed) ✓

  // ---- Run 2 — Impl B: returns CRCMismatch despite no CRC actually mismatching ----
  r2 == Err(LogErr::CRCMismatch)
       // ensures arm Err(CRCMismatch): !impervious_to_corruption ✓ (= true)

  (r1 is Ok) == true
  (r2 is Ok) == false
  ((r1 is Ok) == (r2 is Ok)) == false
  !det_read_cdb_equal(r1, r2)
```

Equivalent witnesses for #5/#6 swap `Ok(false)` → `Some(false)` and `Err(CRCMismatch)` → `None`; for #7/#8 swap to `true` / `false`.

### Suggested fix (shared)

Tighten each arm into an `iff` that ties the return value to the actual on-disk bytes (or to genuine corruption, defined as `read_back ≠ true_bytes`), and drop the unconditional impervious escape:

```rust
// Form A (Result):
Ok(b) => Some(b) == recover_cdb(pm_region@.committed()),
Err(LogErr::CRCMismatch) =>
    !pm_region.constants().impervious_to_corruption
    && exists |i: int| 0 <= i < cdb_addrs.len()
       && pm_region@.committed()[cdb_addrs[i]] != true_cdb_bytes[i],     // actually witnessed corruption
Err(e) => e == LogErr::PmemErr { err: PmemError::AccessOutOfRange },

// Form B (Option):
Some(b) => if b { true_cdb == CDB_TRUE } else { true_cdb == CDB_FALSE },
None =>
    !impervious_to_corruption
    && exists |i: int| 0 <= i < cdb_addrs.len()
       && cdb_c@[i] != true_cdb_bytes[i],

// Form C (bool):
true_crc_bytes == spec_crc_bytes(true_data_bytes) ==> {
    b <==> (data_c@ == true_data_bytes && crc_c@ == true_crc_bytes)
}
```

The second conjunct ("there is an i where the read-back byte differs from the true byte") forces the impl to *witness* corruption before claiming it, eliminating the spurious-error degree of freedom. Two impls on the same uncorrupted input must now return the same value.

### Footnote — non-corpus instances of the same pattern

The pattern also appears verbatim on impl-method specs that the extractor does *not* target (the extractor only picks free-standing `pub fn`, not `impl` methods). The most prominent:

- `UntrustedLogImpl::start` (`verified/log_logimpl/logimpl_start.rs:1194`) — `Err(LogErr::CRCMismatch) => !wrpm_region.constants().impervious_to_corruption`. Same incompleteness; not counted in the 7 because the case never enters the `total` for this corpus.

If the developer's intuition is "virtually every CapybaraKV function" — including these impl methods — the count of structurally-identical incomplete cases grows further once impl methods are added to the corpus.

---

## Part 4 — Opaque internal state under-specified

### Case-pairing summary

The four cases pair up as line-exact sibling copies (verified by `diff`):

| sibling pair | files | difference |
|---|---|---|
| **#11 ≡ #13** (`new`) | `pmem_pmemutil/pmemutil_calculate_crc.rs:114-119` vs `..._calculate_crc_bytes.rs:114-119` | none — identical |
| **#12 ↔ #14** (`write` companion) | `..._calculate_crc.rs:122-127` (`write<S>(&S)`, `val.spec_to_bytes()`) vs `..._calculate_crc_bytes.rs:122-127` (`write_bytes(&[u8])`, `val@`) | input shape (typed value vs raw byte slice); spec shape identical |

So Part 4 is really 2 logically-distinct defects (`new`-shape + `write`-shape), each duplicated across the two sibling files. The "Shared shape" section below applies uniformly.

### Shared shape

CapybaraKV's CRC machinery uses a "ghost view + opaque backend" pattern. The relevant declarations (`pmemutil_calculate_crc.rs:100-142`, `pmemutil_calculate_crc_bytes.rs:100-142` is byte-for-byte identical):

```rust
#[verifier::external_body]
struct ExternalDigest {           // wraps a real CRC accumulator from a sibling crate
    digest: Digest,
}

pub struct CrcDigest {
    digest: ExternalDigest,                 // opaque, #[verifier::external_body]
    bytes_in_digest: Ghost<Seq<Seq<u8>>>,   // ghost field
}

impl CrcDigest {
    pub closed spec fn bytes_in_digest(self) -> Seq<Seq<u8>>;  // ← NO body
    pub fn new() -> (output: Self) ensures output.bytes_in_digest() == Seq::empty();
    pub fn write<S>(&mut self, val: &S) where S: PmCopy
        ensures self.bytes_in_digest() == old(self).bytes_in_digest().push(val.spec_to_bytes());
    pub fn sum64(&self) -> (output: u64)
        requires self.bytes_in_digest().len() != 0,
        ensures output == spec_crc_u64(self.bytes_in_digest().flatten()), ...;
}
```

What the spec actually tells z3:
- `ExternalDigest` is `#[verifier::external_body]` — z3 has no axioms about it; `==` is uninterpreted (only reflexivity).
- `bytes_in_digest(self)` is `pub closed spec fn ... ;` with **no body** — it is an abstract / uninterpreted function symbol whose codomain is `Seq<Seq<u8>>`. z3 only knows the equations the ensures provide.
- `spec_crc_u64` is similarly `closed` and bodyless (line 231).

The CRC interpretation ("`digest` is an incremental CRC32 accumulator") is **not** in the spec — it comes from the file names, type names, and the external library wired into `Digest`. Verus sees an unspecified byte-accumulator type whose only observable contract is "after `new` the abstract `bytes_in_digest()` is empty; `write(v)` appends `v.spec_to_bytes()` to it; `sum64` returns `spec_crc_u64(flatten(...))`".

The codegen produces a structural equal_fn for `CrcDigest` that includes both fields:

```rust
spec fn det_new_equal(r1: CrcDigest, r2: CrcDigest) -> bool {
    (r1.digest == r2.digest) && ((r1.bytes_in_digest)@ =~= (r2.bytes_in_digest)@)
}
```

(Note `r1.bytes_in_digest` is the **field** access — the `Ghost<...>` field — not the `bytes_in_digest()` method call.) z3 needs to discharge both conjuncts.

### Why this is incomplete (with respect to the equal_fn)

The ensures clauses do not constrain either of the two fields that the equal_fn checks:

1. **`digest: ExternalDigest` field.** No ensures clause on `new` / `write` mentions it. Even if one did, `ExternalDigest` is `#[verifier::external_body]` so z3 has no axioms beyond `==` reflexivity; arbitrary two values are not provably equal.
2. **`bytes_in_digest: Ghost<...>` field.** Ensures only mentions the **method** `bytes_in_digest(...)`, whose body is closed and missing. The method-to-field relationship is invisible to z3, so even though both `new()` returns satisfy `output.bytes_in_digest() == empty()`, z3 cannot conclude both have `output.bytes_in_digest@ == empty()`, hence cannot discharge `(r1.bytes_in_digest)@ =~= (r2.bytes_in_digest)@` either.

Strictly structural witness (no implementation semantics needed):

| witness pair | both legal w.r.t. ensures? | equal_fn |
|---|---|---|
| `r1 = CrcDigest { digest: D1, bytes_in_digest: Ghost(L1) }` | ✓ if `bytes_in_digest()` happens to satisfy the ensures-equation at this state | |
| `r2 = CrcDigest { digest: D2, bytes_in_digest: Ghost(L2) }` with `D1 ≠ D2` or `L1 ≠ L2` | ✓ similarly | structural inequality on either field → returns false |

z3 cannot rule this witness out because (a) ensures says nothing about `digest`, (b) the bodyless `bytes_in_digest()` decouples the method from the field. No assumption about CRC32 / CRC64 / Castagnoli / etc. is needed; the defect is purely "spec under-constrains the fields the equal_fn checks".

The judgement call about whether this is a "real" defect or a "fine" design choice still applies:

- **"Fine"**: `digest` is implementation-private state; observably, the only operation that exposes it is `sum64()`, which depends only on `bytes_in_digest()`. The spec's intent is "behaviour through the public API is deterministic", which is achieved.
- **"Defect"**: the type `CrcDigest` is `pub` and uses Verus's default structural equality. If any caller stores or compares `CrcDigest` values (e.g. inside another struct that derives equality), the non-determinism leaks.

Either reading, **the tool's structural-equality check flags it as incomplete**, and the spec as written does not constrain either field to be implementation-uniform.

### Per-case spec snippets

#### #11 `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc.rs`) — opaque field at construction

- **Source**: [`verified/pmem_pmemutil/pmemutil_calculate_crc.rs:114`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/pmem_pmemutil/pmemutil_calculate_crc.rs#L114)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__pmem_pmemutil__pmemutil_calculate_crc__new/`
- **Status**: `unknown`.

```rust
#[verifier::external_body]
pub fn new() -> (output: Self)
    ensures
        output.bytes_in_digest() == Seq::<Seq<u8>>::empty(),
{ unimplemented!() }
```

Witness: any pair `r1, r2` with `r1.digest ≠ r2.digest` (any two abstract `ExternalDigest` values; z3 has no axiom to refute the difference). Even if both `bytes_in_digest@` fields happen to equal `empty()`, the opaque-field disagreement defeats `det_new_equal`.

**Other instances of the same pattern** (see overview table and case-pairing summary above):

- `CrcDigest::write<S>` — `pmem_pmemutil/pmemutil_calculate_crc.rs` (#12 — opaque field after update; same `digest` defect as #11)
- `CrcDigest::new` sibling — `pmem_pmemutil/pmemutil_calculate_crc_bytes.rs` (#13 — byte-for-byte the same spec as #11)
- `CrcDigest::write_bytes` — `pmem_pmemutil/pmemutil_calculate_crc_bytes.rs` (#14 — sibling of #12 with `&[u8]` parameter)

### Suggested fix (shared)


Two ways to close the hole — pick one:

**(A) Pin the opaque field through a spec view.** Add a closed-spec accessor `spec fn digest_state(self) -> Seq<u8>` (or similar) and an ensures clause tying it to `bytes_in_digest()`:

```rust
pub closed spec fn digest_state(self) -> Seq<u8>;

#[verifier::external_body]
pub fn new() -> (output: Self)
    ensures
        output.bytes_in_digest() == Seq::<Seq<u8>>::empty(),
        output.digest_state() == seq_canonical_initial_crc_state(),    // pin the opaque field
{ unimplemented!() }
```

**(B) Make `digest` ghost-only.** If the opaque accumulator is never observed externally, replace `digest: ExternalDigest` with a `Ghost<...>` field or move it into the body of the external_body function (not in the struct). The struct then has only the ghost log, which the ensures already pins.

**(C) Pipeline-side: equal_fn ignores `#[verifier::external_body]` fields.** A tool-side workaround — when generating the structural equal_fn for a struct, skip fields whose type is `#[verifier::external_body]`. This treats opaque state as "outside the determinism contract". Subjective; some projects might prefer pinning explicitly via (A) or (B).

---

## Audit footnote — cases reviewed but NOT counted as incomplete

The full audit covered all 11 `unknown` (R0=unknown, permitted=False) cases **and** the 4 historically-`permitted=True` cases in storage. The 5 `impervious_to_corruption` cases (#3-#7) and the 4 cases above (#11-#14) are real incompleteness; **three cases — one in the unknown bucket and two in the historical-incomplete bucket — were excluded as the same z3-weakness rather than spec defects**:

All three are instances of the same shape — a `serialize_and_write` exec fn on a trait-bound generic where the spec pins `self@` uniquely but the equal_fn does structural `==` on the trait-bound `Self`:

  - Ensures: `self@ == old(self)@.write(addr as int, to_write.spec_to_bytes())`, `self.constants() == old(self).constants()`, plus a `subrange()` agreement clause. The post-`self@` is uniquely pinned by `old@.write(...)`.
  - Equal_fn: `(post1_self_ == post2_self_)` — structural equality on a trait-bound generic.
  - Why unknown / why the tool calls it incomplete: z3 has no model for what `==` means on a generic trait-bound type. The trait declares `spec fn view(&self) -> PersistentMemoryRegionView` and `spec fn constants(...) -> PersistentMemoryConstants` but not how those relate to `Self`'s structural equality. So even though both runs derive the same `@` and the same `constants()`, z3 cannot conclude `post1_self_ == post2_self_`.
  - Verdict: **z3-weakness, not spec incompleteness.** A pipeline-side fix would replace structural `==` with `(post1@, post1.constants()) == (post2@, post2.constants())` for trait-bound `&mut self` exec fns. Out of scope for this document.

The three instances:

- **Trait declaration — `serialize_and_write` (`verified/log_setup/setup_write_setup_metadata_to_region.rs:281`, trait method on `PersistentMemoryRegion`).** Lands in the `unknown` bucket (`r0_z3=unknown, permitted=False`).
- **Subregion impl — `subregion_serialize_and_write_absolute3.rs:225`** (impl of the same trait method on the absolute-addressing subregion wrapper).
- **Subregion impl — `subregion_serialize_and_write_relative3.rs:247`** (impl on the relative-addressing wrapper).

The two subregion impls are the tool's "previously reported 4 incomplete cases, last 2 of which do not count" — they have identical ensures shape (line-for-line copy of the trait spec), and were reclassified from `incomplete` → `complete` in [3dcccb58](https://github.com/q5438722/intent_formalization/commit/3dcccb58) on the basis that subsequent z3 runs gave `r0_z3=unsat` on the same artifacts. On this rerun they regressed back to `r0_z3=unknown, permitted=True`. The verdict is z3-jitter on top of a generic z3-weakness; treating them as complete (as the corpus_rerun11 / progress-2026-05-26 numbers do) is the right call.

---

> **Source:** [`spec-determinism/docs/small-projects-incompleteness-cases-2026-06-01.en.md`](./small-projects-incompleteness-cases-2026-06-01.en.md)

# small-projects spec-incompleteness case set

> **3 source-level cases / 3 unique spec functions / 3 raw corpus artifacts.**
> Each is the sole `unknown` record in its project after the 2026-05-26 verus_error closeout. The 2026-06-01 manual audit found **all three are real spec defects** (not z3 limits), so they were reclassified `unknown` → `incomplete` in `corpus_rerun11_results.md` §"Source-level distribution".
> Source: `spec-determinism/results-verusage-viewreg/{memory-allocator,nrkernel,anvil-library}/full_run.json`.
>
> | # | Project          | Function                  | Defect mechanism |
> |---|------------------|---------------------------|------------------|
> | 1 | memory-allocator | `CommitMask::next_run`    | Author commented out the strengthening ensures clauses |
> | 2 | nrkernel         | `PDE::new_entry`          | Per-bit `MASK_X` predicates omit bit 8 (Global flag), which `view()` reads |
> | 3 | anvil-library    | `vec_filter`              | Spec uses multiset-eq while impl + `filter`-convention are order-preserving |

## Witness format

Each witness lists assumed facts on inputs / outputs (`r1`, `r2`); the closing `!det_*_equal(...)` is the negated structural equality. "z3 sample" is the raw assumes from `full_run.json`; "constructed witness" is the manually-constructed concrete sat model demonstrating the spec gap.

---

## #1 `CommitMask::next_run`

- **Project**: memory-allocator
- **Source**: [`verified/commit_mask/commit_mask__impl__next_run.rs:82`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/memory-allocator/verified/commit_mask/commit_mask__impl__next_run.rs#L82)
- **Pattern**: spec weakening — author-acknowledged

### Why this is incomplete

`next_run` is meant to "scan starting at `idx` and return `(start, length)` of the first maximal run of set bits". The implementation is a deterministic two-level bit scan, but the author **explicitly commented out** the two clauses needed for that semantics:

```rust
// This should be true, but isn't strictly needed to prove safety:
//forall |t| idx <= t < next_idx ==> !self@.contains(t),
// Likewise we could have a condition that `count` is not smaller than necessary
```

Without them, a degenerate "always return `(0, 0)`" implementation satisfies every clause for every input.

### Source function

```rust
pub fn next_run(&self, idx: usize) -> (res: (usize, usize))
    requires 0 <= idx < COMMIT_MASK_BITS,      // == 512
    ensures ({ let (next_idx, count) = res;
        next_idx + count <= COMMIT_MASK_BITS
        && (forall |t| next_idx <= t < next_idx + count ==> self@.contains(t))
    }),
{ /* … two-level bit scan … */ }
```

`self@: Set<int>` is the abstract view of the 8 × 64-bit mask.

### Generated equal_fn

```rust
spec fn det_next_run_equal(r1: (usize, usize), r2: (usize, usize)) -> bool { r1 == r2 }
```

### Witness

z3 sample (`full_run.json`, `n_schemas=11, n_rounds=33`):

```
  idx == 0
  r1 == (0, 0)   r2 == (0, 1)
  !det_next_run_equal(r1, r2)
```

Constructed sat model — input `self.mask[0] & 1 == 1`, all other bits 0 (so `self@ == {0}`), `idx == 0`:

```
  Impl A: r1 = (0, 0)         // 0+0 ≤ 512 ✓ ; forall t. 0 ≤ t < 0 vacuous ✓
  Impl B: r2 = (0, 1)         // 0+1 ≤ 512 ✓ ; self@.contains(0) ✓
  ⇒ both pass; !det_next_run_equal
```

### Suggested fix

Uncomment the two clauses the author already wrote:

```rust
ensures
    next_idx + count <= COMMIT_MASK_BITS,
    forall |t| next_idx <= t < next_idx + count ==> self@.contains(t),
    forall |t| idx <= t < next_idx ==> !self@.contains(t),                     // first-set-bit
    next_idx + count == COMMIT_MASK_BITS                                       // maximal
        || !self@.contains((next_idx + count) as int),
```

---

## #2 `PDE::new_entry`

- **Project**: nrkernel
- **Source**: [`verified/impl_u__l2_impl/impl_u__l2_impl__impl0__new_entry.rs:325`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/nrkernel/verified/impl_u__l2_impl/impl_u__l2_impl__impl0__new_entry.rs#L325)
- **Pattern**: per-bit predicate gap — Global flag (bit 8) unconstrained but view-observed

### Why this is incomplete

`PDE::new_entry` packs **8 permission / flag bits** (plus the address) into a 64-bit page directory entry, and these 8 bits are exactly what `GPDE::Page` exposes via `view()`: `P, RW, US, PWT, PCD, G, PAT, XD`. The ensures pins **7** of them — `P`, `RW`, `US`, `PWT`, `PCD`, `XD` via per-bit `==` predicates, and `PAT` via `r.hp_pat_is_zero()` — but **omits the Global flag (`MASK_PG_FLAG_G`, bit 8)**. Two implementations that disagree on whether to OR-in `MASK_PG_FLAG_G` produce different `view().G` and both pass ensures.

The real implementation leaves bit 8 at 0 by omission — the OR-chain at lines 357–368 simply never includes `MASK_PG_FLAG_G` — but the spec doesn't say so.

### Source function (ensures only)

```rust
ensures
    r.all_mb0_bits_are_zero(),
    if is_page { r@ is Page && r@->Page_addr == address }
    else       { r@ is Directory && r@->Directory_addr == address },
    r.hp_pat_is_zero(),
    r.entry & bit!(5) == 0,   r.entry & bit!(6) == 0,
    r.layer@ == layer,
    r.entry & MASK_ADDR == address,
    r.entry & MASK_FLAG_P  == MASK_FLAG_P,
    (r.entry & MASK_L1_PG_FLAG_PS == MASK_L1_PG_FLAG_PS) == (is_page && layer != 3),
    (r.entry & MASK_FLAG_RW  == MASK_FLAG_RW)  == is_writable,
    (r.entry & MASK_FLAG_US  == MASK_FLAG_US)  == !is_supervisor,
    (r.entry & MASK_FLAG_PWT == MASK_FLAG_PWT) == is_writethrough,
    (r.entry & MASK_FLAG_PCD == MASK_FLAG_PCD) == disable_cache,
    (r.entry & MASK_FLAG_XD  == MASK_FLAG_XD)  == disable_execute,
    // *** no clause constrains MASK_PG_FLAG_G ***
```

Implementation: `r.entry = address | MASK_FLAG_P | (PS if is_page&&layer!=3) | (RW if is_writable) | (US if !is_supervisor) | (PWT if is_writethrough) | (PCD if disable_cache) | (XD if disable_execute)`. No `MASK_PG_FLAG_G` ever set.

### View function (defines what the equal_fn observes)

```rust
pub open spec fn view(self) -> GPDE {
    let v = self.entry;
    let G = v & MASK_PG_FLAG_G == MASK_PG_FLAG_G;   // ← view reads bit 8
    // … if P set and mb0 ok: GPDE::Page { addr, P, RW, US, PWT, PCD, G, PAT, XD } …
}
```

### Generated equal_fn

```rust
spec fn det_new_entry_equal(r1: PDE, r2: PDE) -> bool { r1.view() == r2.view() }
```

### Witness

z3 sample (`full_run.json`, `n_schemas=17, n_rounds=21`) — all 8 inputs fully pinned; z3 returns unknown without concrete `(r1, r2)`:

```
  layer == 1; address == 0
  is_page == is_writable == is_supervisor == is_writethrough
           == disable_cache == disable_execute == true
  !det_new_entry_equal(r1, r2)
```

Constructed sat model:

```
  Impl A (source impl):       r1.entry = MASK_FLAG_P | MASK_L1_PG_FLAG_PS | MASK_FLAG_RW
                                       | MASK_FLAG_PWT | MASK_FLAG_PCD | MASK_FLAG_XD
                              r1.view().G == false
  Impl B (alt — also ORs G):  r2.entry = r1.entry | MASK_PG_FLAG_G
                              r2.view().G == true
  // every bit-wise ensures clause holds for both (G not in mb0 set, not in MASK_ADDR,
  //  bits 5/6/12 still 0, all P/RW/US/PWT/PCD/XD/PS predicates equal)
  // r1.view() and r2.view() differ only on G ⇒ !det_new_entry_equal
```

### Suggested fix

Add the missing Global-flag clause (minimal):

```rust
ensures r.entry & MASK_PG_FLAG_G == 0,
```

(Or pin `r.entry` to the literal bit-OR expression — also pins the unobserved bits 9/10/11.)

The 8 input parameters cover every flag the function is meant to control. The author clearly never intended `G` to be settable — it's an *omission*, not a deliberate weakening (contrast Case 1).

---

## #3 `vec_filter`

- **Project**: anvil-library
- **Source**: [`verified/vstd_exd/vec_lib/vec_lib.rs:13`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/anvil-library/verified/vstd_exd/vec_lib/vec_lib.rs#L13)
- **Pattern**: multiset-eq ensures vs sequence-eq equal_fn (impl + convention are order-preserving)

### Why this is incomplete

Spec is `r@.to_multiset() =~= v@.to_multiset().filter(f_spec)` — multiset equality, no ordering. Two valid impls may return the surviving elements in different orders; both pass ensures but are unequal as `Vec<V>` sequences, which is what `det_vec_filter_equal` compares. The source impl happens to preserve input order (single forward pass + `push`), and `filter` is order-preserving by universal convention (Rust `Iterator::filter`, Python, Haskell, JS). Only the spec dropped the constraint.

### Source function

```rust
fn vec_filter<V: VerusClone + View + Sized>(
    v: Vec<V>, f: impl Fn(&V) -> bool, f_spec: spec_fn(V) -> bool,
) -> (r: Vec<V>)
    ensures r@.to_multiset() =~= v@.to_multiset().filter(f_spec)
{
    let mut r = Vec::new();
    for i in 0..v.len() {
        if f(&v[i]) { r.push(v[i].verus_clone()); }
    }
    r
}
```

### Generated equal_fn

```rust
spec fn det_vec_filter_equal<V: ...>(r1: Vec<V>, r2: Vec<V>) -> bool { r1 == r2 }
```

### Witness

z3 sample (`full_run.json`, `n_schemas=7, n_rounds=6`) — this frame is not itself a valid sat model (`v.len=0` forces `r.len=0`); z3 returns unknown because multiset/`filter` quantifiers exceed its trigger heuristics:

```
  v@.len() == 0;  r1@.len() == 0;  r2@.len() == 1
  !det_vec_filter_equal(r1, r2)
```

Constructed sat model — two distinct elements `a, b` with `a@ != b@` and `f_spec(a) = f_spec(b) = true`, `v = vec![a, b]`:

```
  Impl A (preserves order):  r1 = vec![a, b]   to_multiset = {a, b} ✓
  Impl B (reverses):         r2 = vec![b, a]   to_multiset = {a, b} ✓
  ⇒ both pass; vec![a, b] ≠ vec![b, a]
```

### Suggested fix

Tighten the spec to sequence-preserving filter:

```rust
ensures r@ == v@.filter(f_spec)
```

`Seq::filter` exists in `vstd::seq_lib` and matches the impl exactly. This aligns spec with both the actual implementation and the universal `filter` convention.


---

# Atmosphere ecosystem


---

> **Source:** [`spec-determinism/docs/atmosphere-incompleteness-pr-2026-06-01.en.md`](./atmosphere-incompleteness-pr-2026-06-01.en.md)

# atmosphere page-allocator spec — incompleteness audit (PR-ready summary)

> **7 actionable spec defects** in `verified/allocator/` (+ 2 entries filed for discussion).
> Audit derived from a determinism analysis of the VeruSAGE-Bench atmosphere corpus.
> Long-form rationale, full witnesses, and per-case source / equal-fn listings are in [`atmosphere-incompleteness-cases-2026-05-26.en.md`](./atmosphere-incompleteness-cases-2026-05-26.en.md); this file is the compressed PR companion.

## TL;DR

For each function below, the public `ensures` admits two implementations whose post-states differ observably on the same input — i.e. the spec is incomplete with respect to determinism.

| Group | Cases | Nature | Suggested action |
|---|---|---|---|
| **Part 1 — Spec gaps**          | 5 | Missing constraints; spec under-promises | Per-case ensures additions (each is 1–6 lines) |
| **Part 2 — Set vs Seq anchor**  | 2 | Public `=~=` (Set) hides the underlying `StaticLinkedList` `Seq` order | Bulk fix in **Appendix A**: tighten `=~=` → `==` on `free_pages_*` in the affected public APIs |
| **Discussion only** (#8, #9)    | 2 | Knowingly accepted in the project (Array fresh-alloc, slinkedlist::push slot choice) | Discussion required with spec authors before acting (latent intent / API shape decisions) |

The 5 Part-1 cases are independent and each can be merged in isolation.
The 2 Part-2 cases collapse into the single setter-mirror change described in Appendix A.

## Overview

| # | Case | Sibling | Group | One-line summary |
|---|------|---------|-------|------------------|
| 1 | `alloc_and_map_2m`              | —                              | Spec gap         | No `contains(ret)` clause; impl may overwrite a *mapped* page |
| 2 | `merged_4k_to_2m`               | —                              | Spec gap         | ensures references neither `target_ptr` nor `target_page_idx` |
| 3 | `remove_io_mapping_4k_helper1`  | `remove_mapping_4k_helper1`    | Spec gap         | `Free*` pools have no anchor; impl may steal an unrelated free page |
| 4 | `remove_mapping_4k_helper2`     | —                              | Spec gap (**P0**) | ensures byte-identical to `helper1` despite opposite recycle path |
| 5 | `remove_mapping_4k_helper3`     | —                              | Spec gap         | Cleanest "Free pool no anchor" instance |
| 6 | `add_io_mapping_4k`             | `add_mapping_4k`               | Set vs Seq       | `free_pages_*` permutation legal under `=~=` |
| 7 | `free_page_4k`                  | —                              | Set vs Seq       | Insertion position of `target_ptr` in the free list unspecified |
| 8 | `Array::new`                    | —                              | Discussion       | `ensures ret.wf()` (= `len==N`) only; sole caller overwrites |
| 9 | `StaticLinkedList::push`        | —                              | Discussion       | Returned `SLLIndex` reveals which free slot was popped; all callers `permitted=True` |

---

## Part 1 — Spec gaps (5 cases, actionable)

### #1 `alloc_and_map_2m`

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_2m.rs:590`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__alloc_and_map_2m.rs#L590)

**Problem.** Unlike its 4k sibling, the ensures never says `old(self).free_pages_2m().contains(ret)`. The only clause linking `ret` to the free pool is `self.free_pages_2m() =~= old.free_pages_2m().remove(ret)`, which is also satisfied when `ret ∉ old.free_pages_2m` (`Set::remove` is a no-op there). An implementation may return a page that is **already mapped** in `old(self)`, overwriting its existing mapping rather than allocating from the free pool.

**Suggested fix.** Add the missing anchor, mirroring `alloc_page_4k` line 627:

```rust
ensures
    old(self).free_pages_2m().contains(ret),
```

---

### #2 `merged_4k_to_2m`

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__merged_4k_to_2m.rs:610`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__merged_4k_to_2m.rs#L610)

**Problem.** The ensures references **neither** `target_ptr` **nor** `target_page_idx`. The only constraint on the free pools is the *count delta* (4k: −512, 2m: +1). An implementation may ignore the caller's input and merge any other 2m-aligned block of 512 consecutive `Free4k` pages.

**Suggested fix.** Bind the input to the post-state:

```rust
ensures
    self.free_pages_2m() =~= old(self).free_pages_2m().insert(target_ptr),
    self.free_pages_4k() =~= old(self).free_pages_4k().difference(
        Set::new(|p: PagePtr| exists|i: int|
            target_page_idx <= i < target_page_idx + 512
                && p == page_index2page_ptr(i as usize))
    ),
    self.page_array@[target_page_idx as int].state == PageState::Free2m,
    forall|i: int| target_page_idx < i < target_page_idx + 512
        ==> self.page_array@[i].state == PageState::Merged2m,
```

---

### #3 `remove_io_mapping_4k_helper1` (and sibling `remove_mapping_4k_helper1`)

- **Source (io)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_io_mapping_4k_helper1.rs:552`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_io_mapping_4k_helper1.rs#L552)
- **Source (sibling)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper1.rs:551`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper1.rs#L551)

**Problem.** The ensures anchors `Mapped*`, `Allocated*`, and `container_map_*`, but provides **no anchor for the `Free*` pools or `page_perms_*`**. Page-array entries in state `Free4k` / `Unavailable4k` / `Pagetable` / `Io` are unconstrained. An implementation may, in addition to recycling `target_ptr`, secretly remove an unrelated `Free4k` page `q` from `free_pages_4k`, flip its state to `Unavailable4k`, and `tracked_remove` its perm. The dual `free_pages_4k_wf` invariant becomes vacuous because both directions are degenerate (state was flipped and the seq is empty).

**Suggested fix.**

```rust
ensures
    self.free_pages_4k() =~= old(self).free_pages_4k(),
    self.free_pages_2m() =~= old(self).free_pages_2m(),
    self.free_pages_1g() =~= old(self).free_pages_1g(),
    self.page_perms_4k@ =~= old(self).page_perms_4k@.remove(target_ptr),
    self.page_perms_2m@ =~= old(self).page_perms_2m@,
    self.page_perms_1g@ =~= old(self).page_perms_1g@,
    self.page_array@[page_ptr2page_index(target_ptr) as int].state == PageState::Unavailable4k,
```

The mapping sibling has identical ensures and takes the same fix.

---

### #4 `remove_mapping_4k_helper2` — **P0**

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper2.rs:598`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper2.rs#L598)

**Problem (most serious of the set).** `helper2`'s ensures is **byte-for-byte identical** to `helper1`'s; only the `requires` flips `is_io_page == true → false`. But the two helpers have opposite *recycle paths*:

- `helper1` (IO page, hand-off): target's `state → Unavailable4k`, perm dropped, **not** in free pool.
- `helper2` (RAM page, recycle): target's `state → Free4k`, perm kept, **pushed into** `free_pages_4k`.

Because the spec doesn't distinguish them, an implementation of `helper2` may walk the `helper1` path (treat the RAM page as MMIO and silently drop it = **memory leak**), or vice versa (hand a MMIO address back to the general allocator = **IO safety bug**). Both wrong impls pass Verus.

**Suggested fix.** Mirror `helper1`'s shape but flip the recycle target (the two clauses marked below are precisely what makes the two helpers semantically different):

```rust
ensures
    self.page_array@[page_ptr2page_index(target_ptr) as int].state == PageState::Free4k,
    self.free_pages_4k() =~= old(self).free_pages_4k().insert(target_ptr),  // ← KEY diff vs helper1
    self.free_pages_2m() =~= old(self).free_pages_2m(),
    self.free_pages_1g() =~= old(self).free_pages_1g(),
    self.page_perms_4k@.dom() =~= old(self).page_perms_4k@.dom(),           // ← KEY diff vs helper1
    self.page_perms_2m@ =~= old(self).page_perms_2m@,
    self.page_perms_1g@ =~= old(self).page_perms_1g@,
```

---

### #5 `remove_mapping_4k_helper3`

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper3.rs:570`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper3.rs#L570)

**Problem.** The cleanest demonstration of the "Free pool no anchor" pattern: `helper3` is the `ref_count != 1` branch (target stays `Mapped4k`, only a single `(pcid, va)` entry is removed). Target is fully anchored via `container_map_4k =~= old`; the only freedom left is the same cross-page free-pool attack as #3. Target's `state` / `ref_count` / `owning_container` are already locked by `container_map_4k =~= old` + `*_wf`.

**Suggested fix.**

```rust
ensures
    self.free_pages_4k() =~= old(self).free_pages_4k(),
    self.free_pages_2m() =~= old(self).free_pages_2m(),
    self.free_pages_1g() =~= old(self).free_pages_1g(),
    self.page_perms_4k@ =~= old(self).page_perms_4k@,
    self.page_perms_2m@ =~= old(self).page_perms_2m@,
    self.page_perms_1g@ =~= old(self).page_perms_1g@,
```

---

## Part 2 — Set vs Seq anchor (2 cases, one bulk fix)

Both cases use Set-level `=~=` on `free_pages_*` whose underlying field is a `StaticLinkedList<PagePtr, _>` (`View = Seq<PagePtr>`). Two implementations may compute the same `to_set()` image with different `Seq` orderings and structurally distinct post-states. The same bulk fix described in **Appendix A** closes both.

### #6 `add_io_mapping_4k` (and sibling `add_mapping_4k`)

- **Source (io)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k.rs:566`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__add_io_mapping_4k.rs#L566)
- **Source (sibling)**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__add_mapping_4k.rs:570`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__add_mapping_4k.rs#L570)

**Problem.** The function only writes to `target_ptr`'s `io_mappings` (resp. `mappings`). `free_pages_*` should be untouched — and the underlying setters (`set_io_mapping`, `set_ref_count`) **do** promise field-level `==` (see Appendix A). The public ensures, however, only writes Set-level `=~=`, so an impl may re-shuffle the `StaticLinkedList` (updating each Free page's `rev_pointer` to keep `free_pages_4k_wf`) and pass verification.

**Suggested fix.** Replace the three Set-level lines:

```rust
self.free_pages_4k() =~= old(self).free_pages_4k(),
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),
```

with the Seq-level lines the underlying setters already promise:

```rust
self.free_pages_4k == old(self).free_pages_4k,
self.free_pages_2m == old(self).free_pages_2m,
self.free_pages_1g == old(self).free_pages_1g,
```

See Appendix A for the rationale and a list of the other functions in this file family that should receive the same treatment.

*Note:* `add_io_mapping_4k.rs` line 582 and `add_mapping_4k.rs` line 582 contain a duplicate `free_pages_4k() =~= old(self).free_pages_4k()` line that appears to be a copy-paste of the line above; almost certainly intended to be `free_pages_2m`.

---

### #7 `free_page_4k`

- **Source**: [`verified/allocator/allocator__page_allocator_spec_impl__impl2__free_page_4k.rs:613`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl2__free_page_4k.rs#L613)

**Problem.** Same shape as #6, but for the *insertion* direction: ensures says `self.free_pages_4k() =~= old.free_pages_4k().insert(target_ptr)` (Set-level), so the freedom is *where* `target_ptr` lands in the underlying `Seq` (head / tail / any middle slot) and how the other entries' `rev_pointer`s rotate.

**Suggested fix.** Match the real impl's `push` semantics at the Seq level:

```rust
self.free_pages_4k@ == old(self).free_pages_4k@.push(target_ptr),
self.free_pages_2m == old(self).free_pages_2m,
self.free_pages_1g == old(self).free_pages_1g,
```

---

## Appendix A — Setter vs public-API ensures inconsistency

> **Applies to:** primarily **#6** and **#7** (Part 2 — Set vs Seq anchor) — tightening the public ensures as described below closes both wholesale. The same pattern also strengthens the free-pool / perm-map anchors in **#3** and **#5** (Part 1) and matches what the per-case fix snippets for those entries already propose.

Every `impl2__*.rs` file in `verified/allocator/` contains two layers:

1. **Low-level setters** (marked `#[verifier(external_body)]`, e.g. `set_state`, `set_io_mapping`, `set_mapping`, `set_ref_count`, `set_owning_container`, `set_rev_pointer`): ensures use **field-level `==`** on every untouched field — including `self.free_pages_4k == old(self).free_pages_4k` (Seq-level), plus all 12+ ghost / tracked maps.

2. **Public APIs that compose these setters** (the Part 2 functions above): ensures use **closed-spec-fn `=~=`** comparison, e.g. `self.free_pages_4k() =~= old(self).free_pages_4k()` (Set-level, via `closed spec fn free_pages_4k() = self.free_pages_4k@.to_set()`).

Example — `add_io_mapping_4k.rs` lines 580–583 (public API) vs lines 801–815 (`set_io_mapping` setter):

```rust
// Public API add_io_mapping_4k.ensures:
self.free_pages_4k.len() == old(self).free_pages_4k.len(),   // Seq.len()
self.free_pages_4k() =~= old(self).free_pages_4k(),          // Set =~=
self.free_pages_2m() =~= old(self).free_pages_2m(),
self.free_pages_1g() =~= old(self).free_pages_1g(),

// Underlying setter set_io_mapping.ensures:
self.free_pages_4k == old(self).free_pages_4k,               // Seq == (STRONGER)
self.free_pages_2m == old(self).free_pages_2m,
self.free_pages_1g == old(self).free_pages_1g,
self.allocated_pages_4k == old(self).allocated_pages_4k,     // Ghost<Set> ==
self.mapped_pages_4k    == old(self).mapped_pages_4k,
self.page_perms_4k      == old(self).page_perms_4k,          // Tracked<Map> ==
/* ... 12+ ghost/tracked fields with == ... */
```

The setter library is the only way an implementation can mutate state. So every public API in this family is *actually* constrained at the Seq / ghost-identity level — but only writes the weaker Set-level statement to its callers and to the verifier.

**Question for the spec author.**

1. Is the weak public ensures intentional (e.g. to allow future impls that bypass these setters, or to keep proof obligations lighter)?
2. Or is it accidental — should the public API ensures simply mirror the setters?

If accidental: tightening `=~=` to `==` on `free_pages_*` (and adding the missing `page_perms_*` / `allocated_pages_*` / `mapped_pages_*` lines) closes Part 2 in one pass and eliminates the entire Set-vs-Seq class. The affected public APIs in this family are at least:

- `add_io_mapping_4k`, `add_mapping_4k`               (#6 + sibling)
- `free_page_4k`                                       (#7)
- `remove_*_helper*` family                            (also covers #3, #5)
- the alloc-and-map functions

Tightening `=~=` → `==` would not, however, close Part 1 (#1, #2, #4) — those have genuinely missing constraints that need new ensures lines.

---

## Discussion only

These two entries are technically incomplete with respect to determinism but are **not** filed as PR-actionable bugs in this audit — either the project explicitly marks the callers `permitted=True`, or the under-specification is provably unobservable in this codebase. They are included so spec authors can see the full audit result.

### #8 `Array::new` — sole caller already overwrites

- **Source**: [`verified/array/array_set__impl0__new.rs:17`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/array/array_set__impl0__new.rs#L17)

`Array::new()` is an `#[verifier(external_body)]` constructor whose ensures only pins `ret.wf()` (= `ret.seq@.len() == N`); element values are free. Two impls returning, e.g., `seq![false]` and `seq![true]` (for `A=bool, N=1`) both satisfy ensures but produce different views.

**Why not filed for action.** The only call site in the corpus is `ArraySet::new`, which runs `for i in 0..N { ret.data.set(i, false); }` immediately after `Array::new()`, with a loop invariant `forall|j: int| 0 <= j < i ==> ret.data@[j] == false`. The under-specified initial `seq@` is overwritten before any client can observe it.

**Note on unstated intent.** That the sole caller bothers to run a full coverage loop is itself evidence of a *latent* design intent — the freshly constructed array is supposed to be predictable / safe to read — but this intent is currently enforced ad-hoc at the call site, not expressed anywhere in the spec. If a future caller forgets the overwrite loop, Verus will silently accept reads of undefined ghost contents. Worth a discussion with the spec authors on whether to surface this intent in the API (e.g. via stronger ensures, a different constructor name, or both).

### #9 `StaticLinkedList::push` — slot choice exposed but project-tolerated

- **Source**: [`verified/slinkedlist/slinkedlist__spec_impl_u__impl2__push.rs:232`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__push.rs#L232)

`push` returns `ret: SLLIndex` = the free-list slot it popped to host the new element. The return is pinned only via `post.get_node_ref(*new_value) == ret`, which by the closed body of `get_node_ref` resolves to `post.value_list@[…]` — the **internal** allocation slot. When `pre.free_list@.len() ≥ 2`, two impls may pop different free-list elements; both pass ensures (`post@ = pre@.push(*new_value)`, existing slot indices preserved, `post.wf()`), but return different `SLLIndex` values.

**Recommended spec tightening (low cost).** Every real implementation already maintains `free_list_head` as part of `wf()` and pops it as the natural / canonical choice (popping any other slot would require either a linear scan or extra bookkeeping). So pinning `ret` to `free_list_head` is strictly stronger than the current spec without forcing any impl change:

```rust
ensures
    ret == pre.free_list_head,
    post.value_list@ == pre.value_list@.push(pre.free_list_head),
```

Adopting this would let all four caller sites drop their `permitted=True` annotation, and would surface any future regression that secretly randomises the slot choice. The alternative — exposing a `spec fn next_free_slot() -> SLLIndex` accessor and requiring `ret == old(self).next_free_slot()` — gives the same guarantee with one extra layer of indirection.

---

> **Source:** [`spec-determinism/docs/view-quotient-failure-summary-2026-06-05.en.md`](./view-quotient-failure-summary-2026-06-05.en.md)

# StaticLinkedList — view-quotient determinism defects (2026-06-05)

| # | Function(s) | Why it fails (one sentence) | Suggested fix |
|---|-------------|-----------------------------|---------------|
| 1 | [`StaticLinkedList::len`](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L65) (atmosphere) | An ensures clause reads the hidden field `value_list_len` directly, and the function has no `requires` constraining the precondition | Add `requires self.wf()`, or widen `view` to include `value_list_len` |
| 2 | [`StaticLinkedList::get_value`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L401) / [`get_next`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L413) / [`get_prev`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__remove_helper3.rs#L367) (atmosphere) | All three take a **physical slot index** and return the raw `arr_seq[index].{value/next/prev}`; the view only sees the abstract value-list `spec_seq`, leaving `arr_seq` unconstrained | `pub` → `pub(crate)/private` (preferred — these are internal slab-navigation helpers) |

---

## 1. Case 1: `StaticLinkedList::len`

Source: [`atmosphere/.../free_pages_are_not_mapped.rs`](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs) — struct at [L42](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L42), `len` at [L65](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L65), `view` at [L82](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L82).

### 1.1 Struct

```rust
struct StaticLinkedList<T, N> {
    spec_seq:       Ghost<Seq<T>>,   // view fields = {spec_seq}
    value_list_len: usize,           // hidden
    head, tail, free_head, ...       // hidden
}
spec fn view(self) -> Seq<T> { self.spec_seq@ }
```

### 1.2 Function

```rust
fn len(&self) -> (l: usize)
    ensures
        l == self.value_list_len,            // (E1) directly exposes a hidden field
        self.wf() ==> l == self@.len(),      // (E2) conditional; aligns with the view only under wf
```

The function has **no `requires`**. (E2) is conditional: once the input fails `wf()`, it degenerates to `true`, leaving only (E1), which constrains a hidden field and says nothing about the view side.

### 1.3 Minimal counterexample

Let both `s1` and `s2` have `spec_seq@` equal to the empty sequence, with `value_list_len` set to `0` and `7` respectively; other fields are arbitrary. Neither state satisfies `wf()`, but because there is no precondition enforcing `wf()`, both calls are legal inputs.

- `pre1@ == pre2@ == ε` ✓
- Both satisfy ensures (only (E1) is active; (E2) trivially holds)
- `r1 = 0`, `r2 = 7`; `usize` has no view, so comparison falls back to `==` — fails.

### 1.4 Fixes

- **Add `requires self.wf()`**.
- **Widen `view` to include `value_list_len`**, e.g. `view(self) -> (Seq<T>, usize)`.

---

## 2. Case 2: `StaticLinkedList::get_value` / `get_next` / `get_prev`

These three functions share one signature shape, one precondition, one root cause, and one fix. 

Source (all on the same `StaticLinkedList<T, N>`):
- struct at [`slinkedlist__spec_impl_u__impl2__pop.rs:L20`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L20)
- `view`           at [`...pop.rs:L59`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L59)
- `array_wf`       at [`...pop.rs:L196`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L196)
- `spec_seq_wf`    at [`...pop.rs:L201`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L201)
- `get_value`      at [`...pop.rs:L401`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L401)
- `get_next`       at [`...pop.rs:L413`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L413)
- `get_prev`       at [`slinkedlist__spec_impl_u__impl2__remove_helper3.rs:L367`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__remove_helper3.rs#L367)

### 2.1 Struct (three-layer ghost design)

```rust
pub struct Node<T> { pub value: Option<T>, pub next: SLLIndex, pub prev: SLLIndex }

pub struct StaticLinkedList<T, const N: usize> {
    pub ar:              [Node<T>; N],            // exec — actual slab memory
    pub spec_seq:        Ghost<Seq<T>>,           // abstract value-list (== view)
    pub value_list:      Ghost<Seq<SLLIndex>>,    // logical-position ↔ physical-slot permutation
    pub value_list_head: SLLIndex,
    pub value_list_tail: SLLIndex,
    pub value_list_len:  usize,
    pub free_list:       Ghost<Seq<SLLIndex>>,
    pub free_list_head:  SLLIndex,
    pub free_list_tail:  SLLIndex,
    pub free_list_len:   usize,
    pub size:            usize,
    pub arr_seq:         Ghost<Seq<Node<T>>>,     // spec-mode shadow of `ar` (a Seq, not a [T;N])
}
pub open spec fn view(&self) -> Seq<T> { self.spec_seq@ }
```

### 2.2 Function

```rust
pub fn get_value(&self, index: SLLIndex) -> (ret: Option<T>)
    requires 0 <= index < N, self.array_wf(),
    ensures  ret == self.arr_seq@[index as int].value;

pub fn get_next (&self, index: SLLIndex) -> (next: SLLIndex)
    requires 0 <= index < N, self.array_wf(),
    ensures  next == self.arr_seq@[index as int].next;

pub fn get_prev (&self, index: SLLIndex) -> (prev: SLLIndex)
    requires 0 <= index < N, self.array_wf(),
    ensures  prev == self.arr_seq@[index as int].prev;
```

All three take a **physical slot index**, require only `array_wf()` (just `arr_seq.len() == N && size == N`), and return the raw `arr_seq` cell entry.

### 2.3 Where the defect lies

All three functions' return values are read from `arr_seq@[index]`. Their precondition is only `array_wf()`, which says nothing more than `arr_seq.len() == N && size == N` — **it does not constrain the relationship between `arr_seq` and `spec_seq`**. Under just `array_wf()`, two states with the same `spec_seq@` (i.e. the same view) can hold completely different `arr_seq@`, and so the returned `arr_seq@[index].{value,next,prev}` can differ.

### 2.4 Minimal counterexample (`get_value` representative)

Let `N = 3`, `index = 1`. Both states have `spec_seq@ == seq![1]`, `value_list@ == seq![0]` (so logical position 0 maps to physical slot 0):

| state | `spec_seq@` | `arr_seq@[0].value` | `arr_seq@[1].value` | `arr_seq@[2].value` | `value_list_len` | `wf()` |
|-------|-------------|---------------------|---------------------|---------------------|:----------------:|:------:|
| `s1`  | `seq![1]`   | `Some(1)` | `None`       | `None` | `1` | ✓ |
| `s2`  | `seq![1]`   | `Some(1)` | `Some(999)`  | `None` | `1` | ✓ |

Both have view `seq![1]`. But `s1.get_value(1) = None ≠ Some(999) = s2.get_value(1)`. The same construction works for `get_next` / `get_prev` (slot 1's `next`/`prev` fields are unconstrained by the view because slot 1 is outside `value_list`).

### 2.5 Fixes

- **`pub` → `pub(crate)/private` (recommended)** — call-site survey shows `get_value` / `get_next` / `get_prev` are used only by internal slab-navigation paths (`pop`, `remove_helper2`, `remove_helper3`).
- **Strengthen `fn wf`** — add clauses that determine the full contents of `arr_seq` from the view, and tighten the three functions' precondition from `array_wf()` to `wf()`.