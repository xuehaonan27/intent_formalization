# Consolidated Incompleteness Cases — Issue Bundle (2026-06-09)

# ironkv spec-incompleteness case set

## Overview

| # | Case | Functions covered | Source of non-determinism |
|---|------|------------------|---------------------------|
| 1 | `host_model_next_receive_message` | 1 | Top-level `\|\|\|` (process vs ignore-unparseable) with no guard saying when the ignore branch may fire |
| 2 | `values_agree` (also `keys_in_index_range_agree`) | 2 | Spec only constrains `ret.1` when `!ret.0`; `ret.0 == true` leaves `ret.1` free |
| 3 | `sht_demarshall_data_method` | 1 | The `InvalidMessage` branch is entirely unconstrained by the spec |

## #1 `host_model_next_receive_message` (×1 instance)

- **Source**: [`verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_receive_message.rs:759`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_receive_message.rs#L759)

### Why this is incomplete (under-specified error path)

The spec writes a 2-way `|||` at the top level of `ensures`: an implementation may either *process* a received packet via `process_message` or *drop* it as unparseable via `host_ignoring_unparseable`. **Crucially, the spec never says when the drop branch is allowed to fire** — there is no guard like `(cpacket.msg is well-formed) ==> process_message(...)`. As written, two implementations can disagree on the same well-formed input: one runs the appropriate handler, the other "gives up" and discards the packet. Both satisfy the ensures.

We do not believe this is an intentional IronFleet feature; the error path appears to have been added without specifying its trigger. The reasonable fix is to add a guard that pins down which branch the implementation must take for each class of input.

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

The pattern in case #1 — an `ensures` written as `||| normal_path ||| error_path` without any guard saying when the error path applies — recurs in several other ironkv functions:

- `host_model_next_delegate`
- `process_received_packet_next_impl`
- `parse_command_line_configuration`
- `host_model_next_shard`, `host_model_next_get_request`, `host_model_next_set_request`

## #2 `values_agree` (×2 instances; same issue in `keys_in_index_range_agree`, ×2 instances)

- **Source**: [`verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__values_agree.rs`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__values_agree.rs)

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


## #3 `sht_demarshall_data_method` (×1 instance)

- **Source**: [`verusage/source-projects/ironkv/verified/net_sht_v/net_sht_v__receive_with_demarshal.rs:381`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/ironkv/verified/net_sht_v/net_sht_v__receive_with_demarshal.rs#L381)

### Why this is incomplete

Two implementations are both compliant if one returns `InvalidMessage` while the other parses successfully.

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

**Fix directions**:
- Require the implementation to succeed when `buffer` is in `sht_demarshal_data`'s domain (e.g. `is_marshalable_data(buffer@) ==> !(out is InvalidMessage)`).
- Or accept the design choice and document the under-specification permanently.


---

# storage spec-incompleteness case set

| Pattern | Cases | Representative case | Notes |
|---|---|---|---|
| Error path under-specified | 1 (#2) | `read_log_variables` (`log_logimpl/logimpl_start.rs`) | On a `state.is_None()` input, multiple `Err(...)` variants are simultaneously admissible and the `Ok` arm is vacuously satisfied; even on a legitimate input an `Err(CRCMismatch)` return is admissible whenever `!impervious_to_corruption`. |
| `impervious_to_corruption` family | 7 (#3–#9) | `read_cdb` (`log_logimpl/logimpl_start.rs`) | `Err(CRCMismatch) => !pm_region.constants().impervious_to_corruption` with no `state.is_Some()` guard — spurious CRC error admissible unconditionally whenever the constant is `false` (i.e. on real hardware). |
| Opaque internal state under-specified | 4 (#11–#14) | `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc.rs`) | Spec pins only `output.bytes_in_digest() == Seq::empty()` (a `Ghost<...>` view); the `digest: ExternalDigest` field (an `#[verifier::external_body]` opaque) is unconstrained. Generated equal_fn does structural `==` on `digest`, so two impls with different initial digest values both satisfy ensures yet compare unequal. |

**All 12 cases by function name:**

- **Error path under-specified (1):**
  - #2 `read_log_variables` (`log_logimpl/logimpl_start.rs`)
- **`impervious_to_corruption` family (7):**
  - #3 `read_cdb` (`log_logimpl/logimpl_start.rs`)
  - #4 `read_cdb` (`log_start/start_read_cdb.rs`)
  - #5 `check_cdb` (`log_start/start_read_cdb.rs`)
  - #6 `check_cdb` (`pmem_pmemutil/pmemutil_check_cdb.rs`)
  - #7 `check_crc` (`pmem_pmemutil/pmemutil_check_crc.rs`)
  - #8 `check_crc` (`log_start/start_read_log_variables.rs`)
  - #9 `read_log_variables` (`log_start/start_read_log_variables.rs`)
- **Opaque internal state under-specified (4):**
  - #11 `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc.rs`)
  - #12 `CrcDigest::write<S>` (`pmem_pmemutil/pmemutil_calculate_crc.rs`)
  - #13 `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc_bytes.rs`)
  - #14 `CrcDigest::write_bytes` (`pmem_pmemutil/pmemutil_calculate_crc_bytes.rs`)

## Part 2 — Error path under-specified

### #2 `read_log_variables` (×1 instance)

- **Source**: [`verified/log_logimpl/logimpl_start.rs:100`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/log_logimpl/logimpl_start.rs#L100)

#### Why this is incomplete

`Err(CRCMismatch)` is admissible even on a legitimate input. The arm requires only `state.is_Some() ==> !pm_region.constants().impervious_to_corruption`. 

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

---

## Part 3 — `impervious_to_corruption` pattern family

### Why this is incomplete

The root cause is that the failure arm is guarded only by `!pm_region.constants().impervious_to_corruption`: when that deployment constant is `false`, `Err(CRCMismatch)` / `None` / `false` is allowed without any actual byte mismatch. The same valid input can therefore satisfy both the correct return (`Ok` / `Some` / `true`) and a spurious corruption return, so two implementations may disagree while both satisfy the spec.

#### #3 `read_cdb` (`log_logimpl/logimpl_start.rs`)

- **Source**: [`verified/log_logimpl/logimpl_start.rs:77`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/log_logimpl/logimpl_start.rs#L77)


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

---

## Part 4 — Opaque internal state under-specified

### Why this is incomplete

The root cause is that `CrcDigest` is checked structurally, but its ensures clauses only constrain the abstract method `bytes_in_digest()`; they do not constrain the concrete `digest: ExternalDigest` field, and the method-to-field relationship for `bytes_in_digest: Ghost<...>` is not visible because the spec method is closed/bodyless. Thus two implementations can satisfy the same ensures while producing structurally different `CrcDigest` values.

#### #11 `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc.rs`) — opaque field at construction

- **Source**: [`verified/pmem_pmemutil/pmemutil_calculate_crc.rs:114`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/pmem_pmemutil/pmemutil_calculate_crc.rs#L114)

```rust
#[verifier::external_body]
pub fn new() -> (output: Self)
    ensures
        output.bytes_in_digest() == Seq::<Seq<u8>>::empty(),
{ unimplemented!() }
```

**Other instances of the same pattern** (see overview table above):

- `CrcDigest::write<S>` — `pmem_pmemutil/pmemutil_calculate_crc.rs` (#12 — opaque field after update; same `digest` defect as #11)
- `CrcDigest::new` sibling — `pmem_pmemutil/pmemutil_calculate_crc_bytes.rs` (#13 — byte-for-byte the same spec as #11)
- `CrcDigest::write_bytes` — `pmem_pmemutil/pmemutil_calculate_crc_bytes.rs` (#14 — sibling of #12 with `&[u8]` parameter)

---


# memory-allocator spec-incompleteness case set

> **1 source-level case / 1 unique spec function / 1 raw corpus artifact.**
> `CommitMask::next_run` was reclassified `unknown` → `incomplete` in the 2026-06-01 manual audit.

## `CommitMask::next_run`

- **Source**: [`verified/commit_mask/commit_mask__impl__next_run.rs:82`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/memory-allocator/verified/commit_mask/commit_mask__impl__next_run.rs#L82)

### Why this is incomplete

`next_run` is meant to "scan starting at `idx` and return `(start, length)` of the first maximal run of set bits". The implementation is a deterministic two-level bit scan, but the author **explicitly commented out** the two clauses needed for those semantics:

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


# anvil-library spec-incompleteness case set

## `vec_filter`

- **Source**: [`verified/vstd_exd/vec_lib/vec_lib.rs:13`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/anvil-library/verified/vstd_exd/vec_lib/vec_lib.rs#L13)
- **Pattern**: multiset-eq ensures vs sequence-eq equal_fn (impl + convention are order-preserving)

### Why this is incomplete

The spec is `r@.to_multiset() =~= v@.to_multiset().filter(f_spec)` — multiset equality, no ordering. Two valid impls may return the surviving elements in different orders; both pass ensures but are unequal as `Vec<V>` sequences, which is what `det_vec_filter_equal` compares. The source impl happens to preserve input order (single forward pass + `push`), and `filter` is order-preserving by universal convention (Rust `Iterator::filter`, Python, Haskell, JS). Only the spec dropped the constraint.

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

### Suggested fix

Tighten the spec to sequence-preserving filter:

```rust
ensures r@ == v@.filter(f_spec)
```

`Seq::filter` exists in `vstd::seq_lib` and matches the impl exactly. This aligns spec with both the actual implementation and the universal `filter` convention.


---

# Atmosphere ecosystem

## Overview

| # | Case | Sibling | One-line summary |
|---|------|---------|------------------|
| 1 | `alloc_and_map_2m`              | —                              | No `contains(ret)` clause; impl may overwrite a *mapped* page |
| 2 | `merged_4k_to_2m`               | —                              | The ensures clause references neither `target_ptr` nor `target_page_idx` |
| 3 | `remove_io_mapping_4k_helper1`  | `remove_mapping_4k_helper1`    | `Free*` pools have no anchor; impl may steal an unrelated free page |
| 4 | `remove_mapping_4k_helper2`     | —                              | (**P0**) The ensures clause is byte-identical to `helper1` despite the opposite recycle path |
| 5 | `remove_mapping_4k_helper3`     | —                              | Cleanest "Free pool no anchor" instance |

---

## Concrete incompleteness cases (5, actionable)

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

**Problem.** The ensures clause references **neither** `target_ptr` **nor** `target_page_idx`. The only constraint on the free pools is the *count delta* (4k: −512, 2m: +1). An implementation may ignore the caller's input and merge any other 2m-aligned block of 512 consecutive `Free4k` pages.

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

**Problem.** The ensures clauses anchor `Mapped*`, `Allocated*`, and `container_map_*`, but provide **no anchor for the `Free*` pools or `page_perms_*`**. Page-array entries in state `Free4k` / `Unavailable4k` / `Pagetable` / `Io` are unconstrained. An implementation may, in addition to recycling `target_ptr`, secretly remove an unrelated `Free4k` page `q` from `free_pages_4k`, flip its state to `Unavailable4k`, and `tracked_remove` its perm. The dual `free_pages_4k_wf` invariant becomes vacuous because both directions are degenerate (state was flipped and the seq is empty).

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

**Problem (most serious of the set).** `helper2`'s ensures clause is **byte-for-byte identical** to `helper1`'s; only the `requires` flips `is_io_page == true → false`. But the two helpers have opposite *recycle paths*:

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


# Atmosphere's view-level determinism defects

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
