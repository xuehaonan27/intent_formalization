# storage spec-incompleteness case set

> 14 incomplete cases on the rerun11 storage corpus (2 originally flagged by the `permissive_or` detector + 12 detector-missed, found by a manual audit of the remaining `unknown` bucket).
> Each case shows two implementations whose post-states differ on the same input even though both satisfy the spec — i.e. the spec is incomplete with respect to determinism.
> Source dataset: `spec-determinism/results-verusage-viewreg/storage/full_run.json`.
>
> The 14 cases fall into four patterns:
> - **Part 1 — On-disk byte layout under-specified** (2 cases): spec pins the *abstract recovered state* but leaves multiple concrete byte regions free.
> - **Part 2 — Error path under-specified** (1 case): even legitimate inputs are allowed to return `Err(...)`; on invalid inputs multiple `Err(...)` variants coexist and the `Ok` arm is vacuously satisfied.
> - **Part 3 — `impervious_to_corruption` pattern family** (7 cases): every `Err(...)` / `None` / `false` arm is guarded by `... ==> !impervious_to_corruption` (or just `!impervious_to_corruption`). Real hardware sets that constant to `false`, so the spec lets *any* implementation report a spurious corruption error on any valid input. Detector-missed because the current `permissive_or` test only fires on syntactic `|||`; these are implication-shaped (`==>`), so they currently land in the `unknown` (`r0_z3=unknown`) or `verus_error` (`Box<S>: SpecEq` residual) bucket.
> - **Part 4 — Opaque internal state under-specified** (4 cases): a struct contains an `#[verifier::external_body]` opaque field (e.g. `ExternalDigest`) plus a `Ghost<...>` view; the ensures pins only the ghost view, leaving the opaque field unconstrained. The generated equal_fn includes structural equality on the opaque field, so two impls with different opaque-field values both satisfy the spec yet are unequal.

## Overview

| # | Case | Pattern | Notes |
|---|------|---------|-------|
| 1 | `write_setup_metadata` (`log_logimpl/logimpl_setup.rs`) | Byte layout under-specified | mkfs / format: spec pins abstract `recover_state == Some(initialize(log_capacity))`, leaves CDB-side choice, `_padding`, inactive metadata, gap, and log_area bytes all free. |
| 2 | `read_log_variables` (`log_logimpl/logimpl_start.rs`) | Error path under-specified | The error path is the gap: (a) a **legitimate input** (`state.is_Some()`, all CRCs / fields parse) still admits `Err(CRCMismatch)` whenever `!impervious_to_corruption`, so an Ok return is not forced even when nothing is wrong; (b) on a **state.is_None()** input multiple `Err(...)` variants are simultaneously admissible and the `Ok` arm is vacuously satisfied by any `LogInfo`. |
| 3 | `read_cdb` (`log_logimpl/logimpl_start.rs`) | `impervious_to_corruption` | `Err(CRCMismatch) => !pm_region.constants().impervious_to_corruption`. No `state.is_Some()` guard — spurious CRC error admissible *unconditionally* when not impervious. Currently `unknown`. |
| 4 | `read_cdb` (`log_start/start_read_cdb.rs`) | `impervious_to_corruption` | Same spec as #3 (sibling copy in `log_start/`). Currently `unknown`. |
| 5 | `check_cdb` (`log_start/start_read_cdb.rs`) | `impervious_to_corruption` | `None => !impervious_to_corruption` on an `Option<bool>` return — admissible whenever not impervious, even though the precondition pins `true_cdb ∈ {CDB_FALSE, CDB_TRUE}`. Currently `unknown`. |
| 6 | `check_cdb` (`pmem_pmemutil/pmemutil_check_cdb.rs`) | `impervious_to_corruption` | Same spec as #5 (sibling copy in `pmem_pmemutil/`). Currently `unknown`. |
| 7 | `check_crc` (`pmem_pmemutil/pmemutil_check_crc.rs`) | `impervious_to_corruption` | `true_crc_bytes == spec_crc_bytes(true_data_bytes) ==> if b { ... } else { !impervious_to_corruption }` — even on matching-CRC input, `b=false` is admissible. Currently `unknown`. |
| 8 | `check_crc` (`log_start/start_read_log_variables.rs`) | `impervious_to_corruption` | Same spec as #7 (sibling copy embedded in the `start_read_log_variables.rs` file). Currently `verus_error` (`Box<S>: SpecEq` residual — same semantic issue as #7). |
| 9 | `read_log_variables` (`log_start/start_read_log_variables.rs`) | Error path under-specified + `impervious_to_corruption` | Same spec as #2 (sibling copy in `log_start/`). Currently `verus_error` (`Box<S>: SpecEq` residual). |
| 10 | `write_setup_metadata_to_region` (`log_setup/setup_write_setup_metadata_to_region.rs`) | Byte layout under-specified | Lower-level twin of #1: spec pins `memory_correctly_set_up_on_region(pm@.flush().committed(), region_size, log_id)` (which fixes CDB to `Some(false)`), still leaves `_padding`, inactive `LogMetadata`+`LogCRC`, gap `[168,256)`, and `log_area` bytes free. Slightly tighter than #1 (CDB pinned) but same defect family. Currently `unknown`. |
| 11 | `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc.rs`) | Opaque internal state under-specified | Spec pins only `output.bytes_in_digest() == Seq::empty()` (a `Ghost<...>` view). The `digest: ExternalDigest` field (an `#[verifier::external_body]` opaque) is not constrained. Generated `det_new_equal` compares `r1.digest == r2.digest` AND the ghost view; two impls with different initial digest state both satisfy ensures yet are structurally unequal. Currently `unknown`. |
| 12 | `CrcDigest::write<S>` (`pmem_pmemutil/pmemutil_calculate_crc.rs`) | Opaque internal state under-specified | Spec pins `self.bytes_in_digest() == old(self).bytes_in_digest().push(val.spec_to_bytes())`. The `digest` field update is unconstrained — two impls (e.g. incremental CRC32 vs. recompute-on-`sum64`) produce different opaque post-states. Currently `unknown`. |
| 13 | `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc_bytes.rs`) | Opaque internal state under-specified | Same spec as #11 (sibling file). Currently `unknown`. |
| 14 | `CrcDigest::write_bytes` (`pmem_pmemutil/pmemutil_calculate_crc_bytes.rs`) | Opaque internal state under-specified | Same defect as #12; `&[u8]` instead of `&S` argument. Currently `unknown`. |

## Witness format

Each witness is written as a list of assumed facts about inputs and the two outputs (`r1` / `r2`, `post1_*` / `post2_*`). Lines containing `==` are equalities the witness commits to; the closing line starting with `!det_*_equal(...)` is the negated equivalence that fails the structural equality check.

---

## Part 1 — On-disk byte layout under-specified

### #1 `write_setup_metadata` (×1 instance)

- **Source**: [`verified/log_logimpl/logimpl_setup.rs:86`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/log_logimpl/logimpl_setup.rs#L86)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__log_logimpl__logimpl_setup__write_setup_metadata/`

#### What the function does

mkfs / format routine for a persistent-log on-disk layout. Given a fresh `PersistentMemoryRegion` of size `region_size`, write header bytes so that a later `recover_state(committed_bytes, log_id)` returns `Some(AbstractLogState::initialize(log_capacity))` (an empty log of the given capacity with `head == 0`).

On-disk layout (from `ABSOLUTE_POS_OF_*` constants):

```
byte offset                                     constraint after mkfs
  0 .. 32   GlobalMetadata {                    version_number=1,
              version_number: u64,              length_of_region_metadata
              length_of_region_metadata: u64,     = RegionMetadata::spec_size_of() = 32,
              program_guid: u128 }              program_guid = LOG_PROGRAM_GUID
 32 .. 40   GlobalCRC (u64)                     = CRC(GlobalMetadata bytes)
 40 .. 72   RegionMetadata {                    region_size = mem.len(),
              region_size: u64,                 log_id      = caller log_id,
              log_area_len: u64,                log_area_len= log_capacity
              log_id: u128 }
 72 .. 80   RegionCRC (u64)                     = CRC(RegionMetadata bytes)
 80 .. 88   LogCDB (u64)                        ∈ { CDB_FALSE, CDB_TRUE }  ← free!
 88 ..120   LogMetadata for CDB_FALSE           active iff CDB=FALSE
              { log_length: u64,                  → log_length=0, head=0
                _padding:  u64,                   → _padding   FREE!
                head:      u128 }
120 ..128   LogCRC      for CDB_FALSE (u64)     active iff CDB=FALSE
128 ..160   LogMetadata for CDB_TRUE            symmetric
160 ..168   LogCRC      for CDB_TRUE  (u64)     symmetric
168 ..256   gap (88 bytes)                      FREE!
256 .. end  LogArea (region_size - 256 bytes)   FREE!  (log_length=0 ⇒ unread)
```

CDB ("current data block") is a flip bit that lets future log updates atomically switch between two metadata slots; only the slot pointed to by `LogCDB` is "active".

#### Why this is incomplete

The ensures pins the *abstract* recovered state but leaves five disjoint concrete byte regions free:

1. **`LogCDB` value** — `recover_cdb` accepts either `CDB_FALSE` or `CDB_TRUE` (1 bit free).
2. **`_padding` field** of the active `LogMetadata` — 8 bytes free (CRC follows the chosen value).
3. **Inactive `LogMetadata` + `LogCRC`** (40 bytes) — `metadata_types_set` only checks the *active* slot's parseable/CRC conditions.
4. **Gap bytes `[168, 256)`** (88 bytes) — never referenced by any spec fn.
5. **`LogArea` bytes `[256, region_size)`** — `log_length == 0` makes `extract_log_from_log_area` return `Seq::empty()` regardless of contents.

`equal_fn` compares `post1_pm_region == post2_pm_region`, which (at the trait level, via Verus structural equality) collapses to byte-level equality on `committed()`. Two impls choosing different values for any of the five regions above produce different `committed()` bytes and fail `equal_fn`.

z3 returns `unknown` because materialising a concrete witness requires modelling byte-level `extract_bytes` + struct `spec_from_bytes`/`spec_to_bytes` + the CRC function `spec_crc_u64`, all of which are opaque or recursive. The classifier promotes the case to `incomplete` via the `permissive_or` detector triggered by the 4-way `|||` inside `recover_given_cdb` (region_size / log_id / log_area_len / total-length rejection at L759-762). That `|||` is not itself the source of nondeterminism — the byte under-specification is.

#### Source function

```rust
#[verifier::external_body]
pub fn write_setup_metadata<PMRegion: PersistentMemoryRegion>(
    pm_region: &mut PMRegion,
    region_size: u64,
    Ghost(log_capacity): Ghost<u64>,
    log_id: u128,
)
    requires
        old(pm_region).inv(),
        old(pm_region)@.len() == region_size,
        old(pm_region)@.len() >= ABSOLUTE_POS_OF_LOG_AREA + MIN_LOG_AREA_SIZE,
        old(pm_region)@.len() == log_capacity + ABSOLUTE_POS_OF_LOG_AREA,
        old(pm_region)@.no_outstanding_writes(),
    ensures
        pm_region.inv(),
        pm_region.constants() == old(pm_region).constants(),
        pm_region@.len() == old(pm_region)@.len(),
        pm_region@.no_outstanding_writes(),
        recover_state(pm_region@.committed(), log_id) == Some(
            AbstractLogState::initialize(log_capacity as int),
        ),
        metadata_types_set(pm_region@.committed()),
{ unimplemented!() }
```

Supporting spec fns (abbreviated):

```rust
pub open spec fn recover_state(mem: Seq<u8>, log_id: u128) -> Option<AbstractLogState> {
    match recover_cdb(mem) {
        Some(cdb) => recover_given_cdb(mem, log_id, cdb),
        None      => None,
    }
}

// recover_cdb accepts EITHER CDB_FALSE OR CDB_TRUE at offset 80..88:
pub open spec fn deserialize_and_check_log_cdb(mem: Seq<u8>) -> Option<bool> {
    let log_cdb = deserialize_log_cdb(mem);
    if      log_cdb == CDB_FALSE { Some(false) }
    else if log_cdb == CDB_TRUE  { Some(true)  }
    else                          { None        }
}

// recover_given_cdb -> Some(AbstractLogState{ head, log: extract_log_from_log_area(...), pending: empty, capacity })
// extract_log_from_log_area returns Seq::empty() when log_length == 0.

pub open spec fn metadata_types_set(mem: Seq<u8>) -> bool {
    // GlobalMetadata bytes_parseable + CRC matches
    // RegionMetadata bytes_parseable + CRC matches
    // active-side LogMetadata bytes_parseable + CRC matches
    // LogCDB ∈ {CDB_TRUE, CDB_FALSE}
    // ... (no constraint on inactive slot, gap, or log_area)
}
```

#### Generated equal_fn

```rust
spec fn det_write_setup_metadata_equal<PMRegion: PersistentMemoryRegion>(
    r1: (), r2: (),
    post1_pm_region: PMRegion, post2_pm_region: PMRegion,
) -> bool {
    (r1 == r2) && (post1_pm_region == post2_pm_region)
}
```

Structural equality on `PMRegion`. Two impls whose `committed()` byte sequences differ are unequal.

#### Witness

```
  pre_pm_region.inv()
  pre_pm_region@.len() == region_size == log_capacity + 256          // ABSOLUTE_POS_OF_LOG_AREA = 256
  pre_pm_region@.no_outstanding_writes()
  region_size == 257                                                 // log_capacity == 1 (smallest valid)
  log_id == 0x42

  // ---- Run 1 — Impl A: choose CDB_FALSE, fill all "free" regions with zeros ----
  r1 == ()
  post1_pm_region@.committed() ==
      GlobalMetadata { version_number: 1, length_of_region_metadata: 32, program_guid: LOG_PROGRAM_GUID }.spec_to_bytes()  // [0,32)
   ++ u64::spec_to_bytes(crc_of(GlobalMetadata { 1, 32, LOG_PROGRAM_GUID }))                                               // [32,40)
   ++ RegionMetadata   { region_size: 257, log_area_len: 1, log_id: 0x42 }.spec_to_bytes()                                 // [40,72)
   ++ u64::spec_to_bytes(crc_of(RegionMetadata { 257, 1, 0x42 }))                                                          // [72,80)
   ++ u64::spec_to_bytes(CDB_FALSE)                                                                                        // [80,88)
   ++ LogMetadata { log_length: 0, _padding: 0,            head: 0 }.spec_to_bytes()                                       // [88,120)  active
   ++ u64::spec_to_bytes(crc_of(LogMetadata { 0, 0,            0 }))                                                       // [120,128) active CRC
   ++ Seq::new(32, |_| 0u8)                                                                                                // [128,160) inactive LogMetadata
   ++ Seq::new( 8, |_| 0u8)                                                                                                // [160,168) inactive LogCRC
   ++ Seq::new(88, |_| 0u8)                                                                                                // [168,256) gap
   ++ Seq::new( 1, |_| 0u8)                                                                                                // [256,257) log_area

  // ---- Run 2 — Impl B: choose CDB_TRUE, vary every free region ----
  r2 == ()
  post2_pm_region@.committed() ==
      GlobalMetadata { 1, 32, LOG_PROGRAM_GUID }.spec_to_bytes()                                                           // [0,32)   same
   ++ u64::spec_to_bytes(crc_of(GlobalMetadata { 1, 32, LOG_PROGRAM_GUID }))                                               // [32,40)  same
   ++ RegionMetadata   { 257, 1, 0x42 }.spec_to_bytes()                                                                    // [40,72)  same
   ++ u64::spec_to_bytes(crc_of(RegionMetadata { 257, 1, 0x42 }))                                                          // [72,80)  same
   ++ u64::spec_to_bytes(CDB_TRUE)                                                                                         // [80,88)  DIFFERS
   ++ Seq::new(32, |_| 0xFFu8)                                                                                             // [88,120) inactive garbage
   ++ Seq::new( 8, |_| 0xFFu8)                                                                                             // [120,128) inactive garbage
   ++ LogMetadata { log_length: 0, _padding: 0xDEADBEEFDEADBEEF, head: 0 }.spec_to_bytes()                                 // [128,160) active, padding ≠ 0
   ++ u64::spec_to_bytes(crc_of(LogMetadata { 0, 0xDEADBEEFDEADBEEF, 0 }))                                                 // [160,168) active CRC (new padding)
   ++ Seq::new(88, |_| 0xCCu8)                                                                                             // [168,256) gap garbage
   ++ Seq::new( 1, |_| 0x99u8)                                                                                             // [256,257) log_area garbage

  // Both runs satisfy every ensures clause:
  //   - pm_region.inv()                                ✓ (assumed of the implementer)
  //   - constants() unchanged                          ✓
  //   - len() unchanged                                ✓
  //   - no_outstanding_writes()                        ✓
  //   - recover_state(committed, 0x42) == Some(AbstractLogState{ head:0, log:empty, pending:empty, capacity:1 })
  //       ↳ recover_cdb sees LogCDB ∈ {CDB_FALSE, CDB_TRUE} → Some(cdb)
  //       ↳ recover_given_cdb reads RegionMetadata (same in both), log_area_len=1=log_capacity,
  //         active-side LogMetadata has {log_length:0, head:0} → recover_log returns
  //         AbstractLogState{ head:0, log:empty (log_length=0), pending:empty, capacity:1 }
  //   - metadata_types_set(committed)                  ✓
  //       ↳ active-side CRC self-consistent in both
  //       ↳ inactive slot, gap, log_area unchecked
  //
  // committed() bytes differ in five disjoint regions: [80,88), [88,120), [120,128), [128,160),
  // [160,168), [168,256), [256,257). ⇒ post1_pm_region ≠ post2_pm_region.
  !det_write_setup_metadata_equal((), (), post1_pm_region, post2_pm_region)
```

#### Suggested fix

Pin every free byte region in the ensures. The cleanest form is canonicalising the choice and zeroing everything not load-bearing:

```rust
// (1) Pick a canonical CDB.
deserialize_log_cdb(pm_region@.committed()) == CDB_FALSE,

// (2) Pin the active LogMetadata bytes including _padding.
extract_log_metadata(pm_region@.committed(), false) =~=
    LogMetadata { log_length: 0, _padding: 0, head: 0 }.spec_to_bytes(),

// (3) Pin the inactive LogMetadata + CRC bytes (zeros, or any canonical value).
extract_log_metadata(pm_region@.committed(), true) =~= Seq::new(32, |_| 0u8),
extract_log_crc     (pm_region@.committed(), true) =~= Seq::new( 8, |_| 0u8),

// (4) Pin the gap bytes.
pm_region@.committed().subrange(168, ABSOLUTE_POS_OF_LOG_AREA as int) =~= Seq::new(88, |_| 0u8),

// (5) Pin the log_area bytes.
pm_region@.committed().subrange(ABSOLUTE_POS_OF_LOG_AREA as int, region_size as int)
    =~= Seq::new(log_capacity as nat, |_| 0u8),
```

Once these five are added, the post-state byte sequence is uniquely determined and any two implementations of `write_setup_metadata` must produce identical bytes.

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

#### #4 `read_cdb` (`log_start/start_read_cdb.rs`) — Form A

- **Source**: [`verified/log_start/start_read_cdb.rs:621`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/log_start/start_read_cdb.rs#L621)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__log_start__start_read_cdb__read_cdb/`
- **Status**: `unknown`.

Byte-for-byte the same ensures as #3; the file lives in `log_start/` rather than `log_logimpl/` because the `verusage` benchmark splits some functions into two files for measurement purposes. Same incompleteness.

#### #5 `check_cdb` (`log_start/start_read_cdb.rs`) — Form B

- **Source**: [`verified/log_start/start_read_cdb.rs:328`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/log_start/start_read_cdb.rs#L328)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__log_start__start_read_cdb__check_cdb/`
- **Status**: `unknown`.

```rust
pub fn check_cdb(
    cdb_c: MaybeCorruptedBytes<u64>,
    Ghost(mem): Ghost<Seq<u8>>,
    Ghost(impervious_to_corruption): Ghost<bool>,
    Ghost(cdb_addrs): Ghost<Seq<int>>,
) -> (result: Option<bool>)
    requires
        // ... true_cdb ∈ {CDB_FALSE, CDB_TRUE} ...
        if impervious_to_corruption {
            cdb_c@ == true_cdb_bytes
        } else {
            maybe_corrupted(cdb_c@, true_cdb_bytes, cdb_addrs)
        },
    ensures
        match result {
            Some(b) => if b { true_cdb == CDB_TRUE } else { true_cdb == CDB_FALSE },
            None    => !impervious_to_corruption,
        },
```

The precondition pins the *true* CDB; the implementation, on impervious hardware, can read it back directly. On non-impervious hardware (the only deployment that matters), `None` is admissible regardless of what the bytes actually decode to. So `Some(correct_b)` *and* `None` are both legal on every realistic input.

#### #6 `check_cdb` (`pmem_pmemutil/pmemutil_check_cdb.rs`) — Form B

- **Source**: [`verified/pmem_pmemutil/pmemutil_check_cdb.rs:254`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/pmem_pmemutil/pmemutil_check_cdb.rs#L254)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__pmem_pmemutil__pmemutil_check_cdb__check_cdb/`
- **Status**: `unknown`.

Byte-for-byte the same as #5; the file lives under `pmem_pmemutil/` (the lower-layer copy of the spec).

#### #7 `check_crc` (`pmem_pmemutil/pmemutil_check_crc.rs`) — Form C

- **Source**: [`verified/pmem_pmemutil/pmemutil_check_crc.rs:238`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/pmem_pmemutil/pmemutil_check_crc.rs#L238)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__pmem_pmemutil__pmemutil_check_crc__check_crc/`
- **Status**: `unknown`.

```rust
pub fn check_crc(
    data_c: &[u8], crc_c: &[u8],
    Ghost(mem): Ghost<Seq<u8>>,
    Ghost(impervious_to_corruption): Ghost<bool>,
    Ghost(data_addrs): Ghost<Seq<int>>,
    Ghost(crc_addrs):  Ghost<Seq<int>>,
) -> (b: bool)
    requires
        // ... if impervious_to_corruption { data_c == true_data && crc_c == true_crc } else { maybe_corrupted(...) } ...
    ensures
        true_crc_bytes == spec_crc_bytes(true_data_bytes) ==> {
            if b {
                &&& data_c@ == true_data_bytes
                &&& crc_c@  == true_crc_bytes
            } else {
                !impervious_to_corruption
            }
        },
```

When the antecedent `true_crc_bytes == spec_crc_bytes(true_data_bytes)` holds (i.e. the on-disk CRC really is the CRC of the on-disk data — the only case the function is meaningfully called on), the impl may return either `true` (when the read-back bytes match) **or** `false` (claiming corruption — admissible because `!impervious_to_corruption`). Different impls on the same input may legitimately return opposite booleans.

#### #8 `check_crc` (`log_start/start_read_log_variables.rs`) — Form C

- **Source**: same `check_crc` spec, embedded in `verified/log_start/start_read_log_variables.rs` alongside `read_log_variables`.
- **Status**: `verus_error` (residual `Box<S>: SpecEq<S>` source incompatibility — currently the pipeline can't even compile this case after closeout).

Byte-for-byte the same spec as #7; would be `unknown` under the current detector once the `Box<S>` residual is resolved.

#### #9 `read_log_variables` (`log_start/start_read_log_variables.rs`) — Form A + Part 2 issues

- **Source**: same spec as Part 2 case #2, lives in `verified/log_start/start_read_log_variables.rs:464`.
- **Status**: `verus_error` (residual `Box<S>: SpecEq<S>`).

This is the `log_start/`-copy of #2. The `Err(CRCMismatch) => state.is_Some() ==> !impervious_to_corruption` arm is the impervious-pattern half; the Err-vs-Err / Ok-vacuity issues from Part 2 also apply. Two layers of incompleteness stacked.

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

## Part 1 (continued) — `write_setup_metadata_to_region` (#10)

The same mkfs work is performed at two levels of the storage stack. Part 1 #1 (`write_setup_metadata` in `log_logimpl/logimpl_setup.rs`) is the **higher-level** entry point whose ensures speaks about the abstract `recover_state`. The **lower-level twin** lives in `log_setup/setup_write_setup_metadata_to_region.rs` and pins a more concrete (but still partial) on-disk predicate `memory_correctly_set_up_on_region`. Both leave the same byte regions free.

### #10 `write_setup_metadata_to_region` (×1 instance)

- **Source**: [`verified/log_setup/setup_write_setup_metadata_to_region.rs:599`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/log_setup/setup_write_setup_metadata_to_region.rs#L599)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__log_setup__setup_write_setup_metadata_to_region__write_setup_metadata_to_region/`
- **Status**: `unknown` (R0 = unknown, no permissive `|||` in ensures).

```rust
fn write_setup_metadata_to_region<PMRegion: PersistentMemoryRegion>(
    pm_region: &mut PMRegion,
    region_size: u64,
    log_id: u128,
)
    requires
        old(pm_region).inv(),
        old(pm_region)@.no_outstanding_writes(),
        old(pm_region)@.len() == region_size,
        region_size >= ABSOLUTE_POS_OF_LOG_AREA + MIN_LOG_AREA_SIZE,
    ensures
        pm_region.inv(),
        pm_region.constants() == old(pm_region).constants(),
        memory_correctly_set_up_on_region(pm_region@.flush().committed(), region_size, log_id),
        metadata_types_set(pm_region@.flush().committed()),
{ ... }
```

`memory_correctly_set_up_on_region` is the concrete on-disk predicate:

```rust
spec fn memory_correctly_set_up_on_region(mem: Seq<u8>, region_size: u64, log_id: u128) -> bool {
    let global_metadata    = deserialize_global_metadata(mem);
    let region_metadata    = deserialize_region_metadata(mem);
    let log_cdb            = deserialize_and_check_log_cdb(mem);
    let log_metadata       = deserialize_log_metadata(mem, false);
    // ... CRCs, GUID/version checks ...
    &&& region_metadata.region_size == region_size
    &&& region_metadata.log_id == log_id
    &&& region_metadata.log_area_len == region_size - ABSOLUTE_POS_OF_LOG_AREA
    &&& log_cdb == Some(false)             // CDB pinned to false (tighter than #1)
    &&& log_metadata.head == 0
    &&& log_metadata.log_length == 0
}
```

Vs Part 1 #1's ensures: this predicate pins `log_cdb == Some(false)` explicitly (instead of allowing either via `recover_cdb`). Everything else is still free:

1. **`_padding` field of active `LogMetadata`** — 8 bytes free (active LogCRC follows the chosen value).
2. **Inactive `LogMetadata` + `LogCRC`** (40 bytes free) — `metadata_types_set` only checks the active slot.
3. **Gap bytes `[168, 256)`** (88 bytes free).
4. **`LogArea` bytes `[256, region_size)`** — log_length=0 ⇒ unread.

Witness: identical structure to #1's witness, with the CDB byte fixed to `CDB_FALSE` in both runs and one of the four remaining regions differing between runs. The det fn equal_fn (`(post1_pm_region == post2_pm_region)`) compares full byte sequences, so two impls choosing different `_padding` (or any of the four free regions) are unequal.

**Suggested fix**: same as #1 with item (1) dropped — pin items (2)-(5):

```rust
extract_log_metadata(pm@.flush().committed(), false) =~=
    LogMetadata { log_length: 0, _padding: 0, head: 0 }.spec_to_bytes(),
extract_log_metadata(pm@.flush().committed(), true ) =~= Seq::new(32, |_| 0u8),
extract_log_crc     (pm@.flush().committed(), true ) =~= Seq::new( 8, |_| 0u8),
pm@.flush().committed().subrange(168, ABSOLUTE_POS_OF_LOG_AREA as int) =~= Seq::new(88, |_| 0u8),
pm@.flush().committed().subrange(ABSOLUTE_POS_OF_LOG_AREA as int, region_size as int)
    =~= Seq::new((region_size - ABSOLUTE_POS_OF_LOG_AREA) as nat, |_| 0u8),
```

---

## Part 4 — Opaque internal state under-specified

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

#### #12 `CrcDigest::write<S>` (`pmem_pmemutil/pmemutil_calculate_crc.rs`) — opaque field after update

- **Source**: [`verified/pmem_pmemutil/pmemutil_calculate_crc.rs:122`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/pmem_pmemutil/pmemutil_calculate_crc.rs#L122)
- **Artifact**: `spec-determinism/results-verusage-viewreg/storage/artifacts/storage__verified__pmem_pmemutil__pmemutil_calculate_crc__write/`
- **Status**: `unknown`.

```rust
#[verifier::external_body]
pub fn write<S>(&mut self, val: &S) where S: PmCopy
    ensures
        self.bytes_in_digest() == old(self).bytes_in_digest().push(val.spec_to_bytes()),
{ unimplemented!() }
```

Witness: identical `pre_self`, identical `val`, two posts whose `digest: ExternalDigest` fields differ. ensures says nothing about the post-`digest` field — any two values pass.

#### #13 `CrcDigest::new` (`pmem_pmemutil/pmemutil_calculate_crc_bytes.rs`)

- **Source**: [`verified/pmem_pmemutil/pmemutil_calculate_crc_bytes.rs:114`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/pmem_pmemutil/pmemutil_calculate_crc_bytes.rs#L114)
- **Status**: `unknown`.

Byte-for-byte the same spec as #11 (sibling file targeting `&[u8]` instead of `&S` in the `write*` companion).

#### #14 `CrcDigest::write_bytes` (`pmem_pmemutil/pmemutil_calculate_crc_bytes.rs`)

- **Source**: [`verified/pmem_pmemutil/pmemutil_calculate_crc_bytes.rs:122`](https://github.com/microsoft/verus-proof-synthesis/blob/main/benchmarks/VeruSAGE-Bench/source-projects/storage/verified/pmem_pmemutil/pmemutil_calculate_crc_bytes.rs#L122)
- **Status**: `unknown`.

```rust
#[verifier::external_body]
pub fn write_bytes(&mut self, val: &[u8])
    ensures
        self.bytes_in_digest() == old(self).bytes_in_digest().push(val@),
{ unimplemented!() }
```

Same opaque-field defect as #12; `&[u8]` parameter instead of `&S: PmCopy`.

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

The full audit covered all 11 `unknown` (R0=unknown, permitted=False) cases **and** the 4 historically-`permitted=True` cases in storage. The 5 `impervious_to_corruption` cases (#3-#7) and the 5 cases above (#10-#14) are real incompleteness; **three cases — one in the unknown bucket and two in the historical-incomplete bucket — were excluded as the same z3-weakness rather than spec defects**:

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
