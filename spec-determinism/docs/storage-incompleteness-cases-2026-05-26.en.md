# storage spec-incompleteness case set

> 2 incomplete cases on the rerun11 storage corpus.
> Each case shows two implementations whose post-states differ on the same input even though both satisfy the spec — i.e. the spec is incomplete with respect to determinism.
> Source dataset: `spec-determinism/results-verusage-viewreg/storage/full_run.json`.
>
> The 2 cases fall into two patterns:
> - **Part 1 — On-disk byte layout under-specified** (1 case): spec pins the *abstract recovered state* but leaves multiple concrete byte regions free.
> - **Part 2 — Error path under-specified** (1 case): even legitimate inputs are allowed to return `Err(...)`; on invalid inputs multiple `Err(...)` variants coexist and the `Ok` arm is vacuously satisfied.

## Overview

| # | Case | Pattern | Notes |
|---|------|---------|-------|
| 1 | `write_setup_metadata` | Byte layout under-specified | mkfs / format: spec pins abstract `recover_state == Some(initialize(log_capacity))`, leaves CDB-side choice, `_padding`, inactive metadata, gap, and log_area bytes all free. |
| 2 | `read_log_variables` | Error path under-specified | The error path is the gap: (a) a **legitimate input** (`state.is_Some()`, all CRCs / fields parse) still admits `Err(CRCMismatch)` whenever `!impervious_to_corruption`, so an Ok return is not forced even when nothing is wrong; (b) on a **state.is_None()** input multiple `Err(...)` variants are simultaneously admissible and the `Ok` arm is vacuously satisfied by any `LogInfo`. |

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
