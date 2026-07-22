# vstd determinism study — handoff

Last updated: 2026-07-19

This document is the primary handoff for the vstd specification inventory and
determinism experiments under `spec-determinism/vstd-survey/`.

## 1. Executive summary

The current work has:

1. inventoried the visible vstd module/spec surface;
2. built a vstd-specific runner on top of the existing spec-determinism code;
3. added source-line-qualified extraction for same-named impl methods;
4. run determinism checks over 111 AST-visible public exec definitions with
   explicit postconditions in a matching Verus/vstd snapshot;
5. manually audited the original 27 `R0 = unknown` results;
6. fixed several general equal-fn/view-generation bugs found by the experiment.

The current effective experiment result is:

| Result | Count |
|---|---:|
| Complete | 87 |
| Remaining unknown | 20 |
| Unsupported mutable-reference returns | 4 |
| SMT-confirmed `sat` witnesses | 0 |
| Total tested definitions | 111 |

The 20 remaining unknowns are semantically audited:

| Audit category | Count |
|---|---:|
| Should be complete; tooling/proof gap | 7 |
| Intentional/permitted nondeterminism | 9 |
| Genuine semantic underconstraint | 4 |
| Unresolved | 0 |

**Critical scope warning:** the 111 targets are not the complete vstd exec
surface. The current scanner does not enter `verus_! { ... }` alias macro
blocks. This omits, among other things, the non-deprecated
`vstd::cell::invcell`, `cell::pcell`, and `cell::pcell_maybe_uninit` modules.
The deprecated `vstd::cell::InvCell` was tested; the replacement
`vstd::cell::invcell::InvCell` was not.

**Status updates (2026-07-21, see §15 for details):**

- The `verus_!` gap is fixed (P0): the scanner/extractor now normalize macro
  aliases; the visible target set grew to 137 (May) / 135 (July), and the 26
  newly visible targets have been run.
- All 7 remaining A-cases above are now automated and verify (P2); the
  unknown breakdown is 0 A / 9 B / 4 C for the original set (plus invcell:
  1 A-analog→complete, 3 C; B +3; `iter::next` unaudited; `iter::{new,next}`
  were removed upstream in July).
- The July snapshot (cf3b5c3) is fully validated end-to-end (P1); prefer it
  for new work.

## 2. Repository and environment

### Main repository

```text
/home/xuehaonan/intent_formalization
```

Project directory:

```text
/home/xuehaonan/intent_formalization/spec-determinism
```

The worktree was already heavily modified before this vstd work. Do not assume
that the entire diff of `gen_det.py` or `extractor.py` belongs to this effort.
The vstd-specific additions are described in this document and covered by
targeted self-tests.

At the original handoff, the entire `spec-determinism/vstd-survey/` directory was
still untracked (`?? vstd-survey/`). It has since been committed on the current
machine (`86127792 Add vstd determinism survey and experiments`), and the
documented paths have been migrated from `/home/chentianyu` to
`/home/xuehaonan`. The remaining storage concern is the large raw `verus_log/`
artifacts: do not blindly commit regenerated run logs until a large-artifact
storage policy is chosen.

### Current upstream Verus source

```text
~/verus
```

Pinned commit:

```text
cf3b5c3fb937b9effa9478d4735b49743d8646eb
```

vstd source:

```text
~/verus/source/vstd
```

This source is used by the latest inventory report.

### Matching executable experiment snapshot

The determinism experiments use:

```text
/home/xuehaonan/nanvix/toolchain/verus
```

Version:

```text
0.2026.05.17.e479cce
commit e479cce36490b8fa4b0fd7755aa742aec354372c
toolchain 1.95.0-x86_64-unknown-linux-gnu
```

Matching vstd source:

```text
/home/xuehaonan/nanvix/toolchain/verus/vstd
```

The experiments deliberately use this older source because source and compiled
vstd metadata must match. `~/verus` is newer and currently has no matching
built Verus/vstd bundle.

Do not use `/home/xuehaonan/intent_formalization/verus` for these experiments:
that bundle is missing required proc-macro shared libraries and cannot import
its bundled `libvstd.rlib` successfully.

## 3. What is being checked

For a function specification:

```text
requires P(x)
ensures  Q(x, y)
```

spec-determinism asks whether two outputs satisfying the same specification can
differ:

```text
P(x) && Q(x, y1) && Q(x, y2) ==> equal(y1, y2)
```

Interpretation:

- `R0 = unsat`: the specification determines the selected semantic output;
- `R0 = sat`: confirmed specification nondeterminism;
- `R0 = unknown`: no verdict; requires equality/proof/solver audit;
- compile/extraction errors: pipeline coverage issue, not a spec verdict.

The method checks uniqueness of the formal contract. It does **not** prove that
an `assume_specification` agrees with the real Rust implementation, and it does
not detect over-strong but deterministic specs.

Core conceptual references:

- [spec-determinism skill](../../skills/spec-determinism/SKILL.md)
- [pipeline reference](../docs/pipeline-2026-06-02.en.md)
- [determinism funnel](../docs/determinism-funnel-framework.md)
- [unknown-handling strategy](../docs/unknown-handling-strategy-2026-05-15.md)
- [Phase 2 summary](../docs/PHASE2_SUMMARY.en.md)
- [abstract/view-quotient determinism](../docs/abstract-determinism-plan-2026-06-04.en.md)

## 4. vstd-survey directory map

```text
vstd-survey/
├── TUTORIAL.md                        # newcomer tutorial: what this research does and why
├── HANDOFF.md                         # this document
├── README.md                          # inventory/big-picture report
├── scan_vstd.py                       # source-level inventory scanner
├── run_determinism.py                 # vstd experiment runner
├── generated/
│   ├── inventory.json                 # full current-upstream inventory
│   ├── modules.csv                    # one row per visible module
│   ├── groups.csv                     # aggregate module groups
│   └── exec_functions.csv             # visible exec definitions/signatures
└── experiments/
    ├── REVIEW-2026-07-14.md           # combined experiment review
    ├── UNKNOWN-AUDIT-2026-07-15.md    # semantic audit of original 27 unknowns
    ├── ALIAS-NEW-REVIEW-2026-07-21.md # review of the 26 alias-module targets (P0 follow-up)
    ├── JULY-RERUN-REVIEW-2026-07-21.md # July (cf3b5c3) full-rerun review (see §15.4)
    ├── P2-REVIEW-2026-07-21.md        # A-case automation review (see §13 P2)
    ├── pilot-2026-07-14/              # initial array/bytes pilot
    ├── public-free-2026-07-14/        # 34 public free definitions
    ├── raw-pointer-strict-2026-07-14/ # strict equality rerun for 6 pointer APIs
    ├── impl-methods-2026-07-14/       # 77 line-qualified impl methods
    ├── inventory-may-2026-07-21/      # regenerated May inventory (target set 137)
    ├── repro-2026-07-21-*/fixup-*     # machine reproduction evidence (see §15.2)
    ├── final-2026-07-21-*/            # clean 111+6 baseline on this machine
    ├── alias-new(-fixup)-2026-07-21/  # the 26 newly visible alias-module targets
    └── july-2026-07-21-*/             # full rerun on the July (cf3b5c3) snapshot
```

Primary reading order:

0. [TUTORIAL.md](TUTORIAL.md) if you are new to the research (concepts,
   method, results, open problems — in Chinese);
1. this handoff;
2. [README.md](README.md) for the module inventory and broad vstd structure;
3. [experiment review](experiments/REVIEW-2026-07-14.md);
4. [27-unknown audit](experiments/UNKNOWN-AUDIT-2026-07-15.md);
5. per-run `SUMMARY.md` and per-target artifacts.

## 5. Inventory methodology

Implemented in [scan_vstd.py](scan_vstd.py).

### Counting categories

The scanner separates:

- exec definitions with bodies;
- signature-only exec declarations;
- exec postconditions;
- `assume_specification` sites;
- model `spec fn` declarations;
- proof functions;
- axiom functions;
- external type/trait specs;
- View/DeepView implementations;
- macros and parser-error modules.

The current-upstream report at `cf3b5c3` contains:

```text
125 visible modules (build.rs excluded)
52,715 source lines
3,367 specification-related declaration sites
515 contract sites
286 visible exec declarations
220 visible exec definitions with bodies
126 visible public exec definitions
111 visible public exec definitions with postconditions
```

These are **source declaration-site** counts:

- macro templates count once, not once per expansion;
- parse-recovery modules are marked;
- the numbers are not semantic coverage percentages.

### Scanner implementation

The scanner uses `tree-sitter-verus` for functions and a lexical fallback for:

- `assume_specification`;
- `returns`;
- `default_ensures`;
- attributes and macro counts.

It writes JSON/CSV and updates the generated section of
[README.md](README.md) between marker comments.

### Known inventory gap: `verus_!`

**RESOLVED 2026-07-21 (P0).** `spec_determinism.extract.aliases
normalize_verus_aliases` is now applied at every parse entry point
(scanner, `extract_spec`, `type_registry`, `impl_scanner`); alias modules
are fully visible in the regenerated inventories (see §15.3 for numbers).
The historical description below is kept for context.

The parser recognizes normal `verus! { ... }` blocks but does not parse
functions inside aliases such as:

```rust
use verus as verus_;
verus_! {
    ...
}
```

In the matching May snapshot, files with apparent exec functions but zero
scanned exec bodies include:

```text
cell/invcell.rs
cell/pcell.rs
cell/pcell_maybe_uninit.rs
std_specs/cmp.rs
std_specs/core.rs
std_specs/iter.rs
std_specs/vec.rs
```

Other alias files also exist (`map.rs`, `tokens.rs`, `std_specs/slice.rs`,
`std_specs/maybe_uninit.rs`, etc.). Therefore:

- the module table remains useful for broad structure;
- the 111-target experiment is an AST-visible subset;
- claims such as “all public vstd exec functions” must not be made.

Concrete example:

- tested deprecated type:
  `vstd::cell::InvCell<T>` in `vstd/cell.rs`;
- omitted replacement:
  `vstd::cell::invcell::InvCell<T, Pred>` in
  `vstd/cell/invcell.rs`.

Both versions use the same weak `replace`/`get` result contract:

```rust
ensures self.inv(result)
```

but only the deprecated version appears in the current experiment target set.

## 6. Experiment runner architecture

Implemented in [run_determinism.py](run_determinism.py).

For each target:

1. resolve module file;
2. call `extract_spec(source, fn, source_line=...)`;
3. construct an `EqualPolicy`;
4. call `build_det_check_spec` with the vstd `ViewRegistry`;
5. enumerate schemas and render the guarded template;
6. build a standalone Verus harness importing precompiled vstd;
7. run Verus with SMT logging;
8. load the largest SMT2 query with `build_schema_ctx`;
9. run `run_schema_search`;
10. classify with `classify_ok`;
11. persist all artifacts and update a summary.

### Target identity

Targets use:

```text
module:function@source_line
```

Examples:

```text
hash_map:new@43
hash_map:new@209
cell:new@178
cell:new@344
```

The line is required because many methods repeat within one source file.

### View equality

The runner builds one `ViewRegistry` over the matching vstd source and passes it
to `build_det_check_spec`. This is necessary for wrappers such as:

- `HashMapWithView`;
- `HashSetWithView`;
- `StringHashMap`;
- `StringHashSet`.

Raw wrapper equality frequently produces false unknowns.

### Runner-specific compatibility handling

The runner currently contains snapshot-specific behavior:

- `extern crate alloc`;
- extra imports for `raw_ptr`, `hash_map`, and `hash_set`;
- suppression of invalid `reveal(...)` calls for imported closed spec
  functions;
- May-snapshot API rewrites:
  - `simple_pptr`: `.ptr().addr()` to `.pptr().addr()`;
  - deprecated `cell`: `.ptr().addr()` to `.id()`, with unusable scalar
    narrowing guards removed;
- detection of trivial `true` equal functions;
- optional strict pointer comparison;
- optional ViewRegistry disable switch;
- explicit unsupported status for returned `&mut T`.

These rewrites should not silently migrate into a general runner without
version gating.

## 7. Core code changes

### `extract/extractor.py`

File:

[spec_determinism/extract/extractor.py](../spec_determinism/extract/extractor.py)

Added:

- `source_line` argument to `_extract_fn_chunk`;
- line-aware function candidate selection;
- `_find_enclosing_node_by_line`;
- `source_line` argument to `extract_spec`;
- exact same-name function/method selection;
- line-aware impl context recovery;
- regression test selecting the second of two same-named impl methods.

Important current locations:

```text
_extract_fn_chunk(... source_line ...)       around line 416
_find_enclosing_node_by_line                 around line 1152
extract_spec(... source_line ...)             around line 1236
same-name regression test                     near end of extractor self-tests
```

### `codegen/gen_det.py`

File:

[spec_determinism/codegen/gen_det.py](../spec_determinism/codegen/gen_det.py)

vstd-driven fixes include:

1. `PointsToRaw` opacity checks only the outer type; a tuple containing a
   `PointsToRaw` field no longer collapses entirely to `true`.
2. `Tracked<T>`/`Ghost<T>` with an inner `spec_view` compare through `@@`.
3. registered View equality is preferred over `#[verifier::ext_equal]` wrapper
   equality.
4. the L3 generic-bound gate only requires View-like bounds for generic
   parameters actually projected through `T::V`.
5. concrete-key views such as `StringHashMap<Value> ->
   Map<Seq<char>, Value>` no longer incorrectly require `Value: View`.
6. regression self-tests cover all of the above.

Important current locations:

```text
_is_points_to_raw_type                      around line 120
Tracked/Ghost equality branch               around line 1862
view-first struct equality                  around line 2083
_generic_l3_view_bounds_satisfied           around line 2297
vstd regression fixtures                    in _run_self_tests
```

### Worktree warning

Both core files had substantial pre-existing modifications. The current
`git diff --stat` is much larger than the changes listed here. Review changes
by symbol/test, not by assuming every diff hunk was introduced by this work.

## 8. Experiment corpus

The matching May inventory selected 111 visible public exec definitions with
explicit postconditions:

- 34 free functions;
- 77 impl methods.

Selection criteria are read from the matching snapshot's generated
`exec_functions.csv`:

```text
node_kind == definition
visibility == public
contract_status == post
context == free       # free-function run
context != free       # impl-method run
```

### Free-function run

Directory:

[public-free-2026-07-14](experiments/public-free-2026-07-14/)

Default-policy summary:

```text
21 complete
5 unknown
6 invalid trivial raw-pointer equalities
2 unsupported mutable-reference returns
```

The six pointer targets were rerun strictly:

[raw-pointer-strict-2026-07-14](experiments/raw-pointer-strict-2026-07-14/)

All six strict-pointer checks are complete, producing the effective free
result:

```text
27 complete
5 unknown
2 unsupported
```

### Impl-method run

Directory:

[impl-methods-2026-07-14](experiments/impl-methods-2026-07-14/)

Current result after view/equality fixes:

```text
60 complete
15 unknown
2 unsupported
```

All 77 targets now compile; there are no residual runner/verus errors in the
final summary.

### Combined automated result

```text
87 complete
20 unknown
4 unsupported
0 R0=sat
```

“0 R0=sat” does not mean there is no incompleteness. Manual semantic audit
identified intentional and genuine underconstraint among solver-unknown cases.

## 9. Original 27-unknown audit

Primary document:

[UNKNOWN-AUDIT-2026-07-15.md](experiments/UNKNOWN-AUDIT-2026-07-15.md)

Original classification:

```text
14 A: should be complete; tool/equality/proof gap
 9 B: intentional/permitted nondeterminism
 4 C: genuine semantic underconstraint
 0 D: unresolved
```

Seven A-cases (`StringHashMap`) were fixed by the generic L3 view-bound change,
leaving the current 20 automated unknowns:

```text
 7 A
 9 B
 4 C
```

### Remaining A: should be complete

- `atomic::{fetch_and, fetch_xor, fetch_or}`
  - macro-generated permission types are invisible to source-level type/view
    discovery;
  - corrected equality over `.view()` fields verifies.
- `raw_ptr::ptr_ref2`
  - raw `SharedReference` equality is too strong;
  - equality over `value()`, address, and metadata verifies.
- `thread::thread_id`
  - requires tracked result components and `IsThread::agrees`.
- deprecated `InvCell::new`
  - equality should compare the exposed invariant predicate, not hidden cell
    identity.
- `RwLock::acquire_read`
  - `ReadHandle::lemma_readers_match` is the exact missing proof.

### B: intentional/permitted nondeterminism

- `float::float_cast`;
- `raw_ptr::allocate`;
- `thread::{spawn, join}`;
- deprecated `PCell::{empty, new}`;
- `simple_pptr::{empty, new}`;
- `RwLock::new`.

These should be classified as `incomplete_permitted` under concrete identity.
Fresh-handle cases can become complete only under an explicit quotient that
ignores identity and observes content/predicate.

### C: genuine semantic underconstraint

- deprecated `InvCell::{replace, get}`;
- `RwLock::{acquire_write, into_inner}`.

These contracts constrain a returned value only through an arbitrary invariant
predicate:

```text
inv(result)
```

An invariant predicate need not be functional. Two distinct values can satisfy
it, so the result is genuinely not uniquely specified. This may be an
intentional information-hiding design, but it is still semantic
underconstraint.

## 10. Artifact format

Each target directory under `experiments/*/artifacts/` contains:

```text
result.json
det_spec.json
harness.rs
verus_stdout.txt
verus_stderr.txt
verus_log/
```

`verus_log/` contains SMT/AIR/transcript artifacts, including the SMT2 consumed
by schema search.

Example:

```text
experiments/impl-methods-2026-07-14/
  artifacts/hash_map__insert__L106/
    result.json
    det_spec.json
    harness.rs
    verus_log/root.smt2
    ...
```

The artifacts are large. Current post-cleanup sizes are approximately:

```text
public-free experiment: approximately 64 MB
impl-method experiment: approximately 99 MB
strict-pointer experiment: approximately 11 MB
pilot experiment: approximately 28 MB
```

Do not commit all logs without deciding on a storage policy. The Markdown/JSON
summaries and selected failing/interesting harnesses are much smaller.

## 11. Reproduction commands

Run from:

```bash
cd /home/xuehaonan/intent_formalization/spec-determinism
```

### Current-upstream inventory

```bash
python vstd-survey/scan_vstd.py \
  --vstd-root /home/xuehaonan/verus/source/vstd \
  --commit cf3b5c3fb937b9effa9478d4735b49743d8646eb \
  --snapshot-date 2026-07-13 \
  --source verus-lang/verus:source/vstd \
  --out-dir vstd-survey/generated
```

Remember that this regenerates the partial, alias-blind inventory.

### Matching May inventory for experiment selection

```bash
python vstd-survey/scan_vstd.py \
  --vstd-root /home/xuehaonan/nanvix/toolchain/verus/vstd \
  --commit e479cce36490b8fa4b0fd7755aa742aec354372c \
  --snapshot-date 2026-05-17 \
  --source local-matching-vstd \
  --out-dir vstd-survey/experiments/public-free-2026-07-14/inventory \
  --no-report
```

### One target

```bash
python vstd-survey/run_determinism.py \
  --vstd-root /home/xuehaonan/nanvix/toolchain/verus/vstd \
  --verus-root /home/xuehaonan/nanvix/toolchain/verus \
  --out /tmp/vstd-one \
  --target hash_map:insert@106 \
  --timeout 240 \
  --rlimit 60
```

### All visible public free definitions with postconditions

```bash
python vstd-survey/run_determinism.py \
  --vstd-root /home/xuehaonan/nanvix/toolchain/verus/vstd \
  --verus-root /home/xuehaonan/nanvix/toolchain/verus \
  --out vstd-survey/experiments/public-free-2026-07-14 \
  --targets-csv vstd-survey/experiments/public-free-2026-07-14/inventory/exec_functions.csv \
  --public-free-post \
  --timeout 240 \
  --rlimit 60
```

### All visible public impl methods with postconditions

```bash
python vstd-survey/run_determinism.py \
  --vstd-root /home/xuehaonan/nanvix/toolchain/verus/vstd \
  --verus-root /home/xuehaonan/nanvix/toolchain/verus \
  --out vstd-survey/experiments/impl-methods-2026-07-14 \
  --targets-csv vstd-survey/experiments/public-free-2026-07-14/inventory/exec_functions.csv \
  --public-impl-post \
  --timeout 300 \
  --rlimit 60
```

### Strict raw-pointer equality

Use `--compare-raw-pointers` for targets whose default equality is the trivial
raw-pointer opacity policy. The exact six-target command is reflected in:

[raw-pointer strict summary](experiments/raw-pointer-strict-2026-07-14/SUMMARY.md)

### Targeted self-tests

```bash
python -m spec_determinism.extract.extractor test
python -m spec_determinism.codegen.gen_det test
python -m py_compile vstd-survey/scan_vstd.py vstd-survey/run_determinism.py
```

## 12. Known limitations

### Coverage

1. ~~`verus_!` alias blocks are not scanned.~~ Resolved 2026-07-21 (see §5
   and §15.3).
2. macro-expanded functions/types/views are not enumerated.
3. `assume_specification` is inventoried lexically but not determinism-tested
   by this runner.
4. signature-only external trait specs are not tested.
5. current-upstream source has not been tested with a matching compiled
   toolchain.

### Extraction/codegen

1. returned `&mut T` is unsupported because result substitution does not model
   `old(result)`/`final(result)`;
2. macro-generated atomic permission views are not discovered;
3. split-accessor abstractions such as `SharedReference::{value, ptr}` need a
   data-driven projection policy;
4. proof-lemma discovery is manual (`IsThread::agrees`,
   `ReadHandle::lemma_readers_match`);
5. the runner's permitted flag is currently always set to `False`; semantic
   audit labels are in the audit document, not in `summary.json`;
6. ViewRegistry emits many parse-error warnings and may be incomplete.

### Solver interpretation

1. `unknown` is never a determinism verdict;
2. many queries report `incomplete quantifiers` or incomplete arithmetic;
3. schema narrowing cannot repair an over-strong equal-fn;
4. no SMT `sat` was observed, but manual probes established intentional and
   genuine nondeterminism.

## 13. Recommended next work

Priority order for the next owner:

### P0 — fix target coverage

**DONE 2026-07-21 (see §15.3).** Alias normalization landed and both
inventories were regenerated; the May experiment target set grew from 111 to
137 public-post definitions. Original text:

Teach the scanner/extractor to parse `verus_!` aliases or normalize them to
`verus!` before parsing. Then regenerate both current and matching-snapshot
inventories.

At minimum, add coverage for:

```text
cell/invcell.rs
cell/pcell.rs
cell/pcell_maybe_uninit.rs
std_specs/cmp.rs
std_specs/core.rs
std_specs/iter.rs
std_specs/vec.rs
```

### P1 — build current upstream Verus/vstd

**DONE 2026-07-21 (see §15.1 and §15.4).** The runner was validated
end-to-end on the July snapshot: all 135 July targets ran with zero verdict
drift against the May baseline. Original text:

Build a matching toolchain for `~/verus@cf3b5c3` and stop mixing the July
inventory with the May experiment snapshot.

### P2 — automate the audited A-cases

**DONE 2026-07-21** — all five items are automated in `run_determinism.py`
via `EQUAL_FN_OVERRIDES` / `PROOF_HINTS`, and all 8 affected targets verify
(`r0=unsat`) on BOTH snapshots. See
[experiments/P2-REVIEW-2026-07-21.md](experiments/P2-REVIEW-2026-07-21.md)
for the per-target repairs and three Verus mode/antecedent subtleties that
matter for future proof hints. Original items:

1. synthesize views for macro-generated atomic permission types;
2. add a projection policy for `SharedReference`;
3. preserve/use tracked output components for `IsThread::agrees`;
4. add proof hints for `ReadHandle::lemma_readers_match`;
5. use invariant-predicate equality for `InvCell::new`.

### P3 — encode permitted nondeterminism

Add vstd-specific permitted rules for:

- allocator/fresh identity;
- float-cast relations;
- thread handles;
- PCell/PPtr/RwLock constructors.

Do not hide these by a global `equal == true`; record the quotient or permitted
reason explicitly.

### P4 — decide what to do with genuine C-cases

For:

- `InvCell::{replace, get}`;
- `RwLock::{acquire_write, into_inner}`;

choose one:

1. accept and document possible-value abstraction;
2. add a ghost exact-current-value accessor;
3. weaken/change the API so exact returned values are not promised.

The same review must be repeated for the non-deprecated
`cell::invcell::InvCell`, which has the same `inv(result)` contract shape.

**Review repeated 2026-07-21** (see
[ALIAS-NEW-REVIEW-2026-07-21.md](experiments/ALIAS-NEW-REVIEW-2026-07-21.md)):
`cell::invcell::InvCell::{replace, get, into_inner}` are all genuinely
underconstrained (C-class, same `inv(result)` shape); `new` is A-class under
invariant-predicate quotient equality, same as the deprecated version. The
three options above therefore apply unchanged.

### P5 — add structured audit annotations

Move the A/B/C labels from Markdown into machine-readable result metadata so
aggregators can report:

```text
complete
complete_tool_gap
incomplete_permitted
incomplete
unsupported
unknown
```

## 14. Takeover checklist

Before changing behavior:

1. preserve/commit the currently untracked `vstd-survey/` directory before any
   reset or cleanup;
2. read this document;
3. read `UNKNOWN-AUDIT-2026-07-15.md`;
4. confirm which source/toolchain snapshot is being used;
5. run extractor and gen_det self-tests;
6. run one known-complete target (`bytes:u16_from_le_bytes@79`);
7. run one line-disambiguated target (`hash_map:insert@106`);
8. inspect its `harness.rs` and `det_spec.json`;
9. verify the equal-fn is non-trivial and matches the contract's abstraction.

Before publishing numbers:

1. state that current inventory misses `verus_!` alias blocks;
2. state whether strict pointer equality is included;
3. separate automatic R0 results from manual semantic audit;
4. do not call `unknown` incomplete or complete;
5. do not claim the 111-target set is the full vstd.

## 15. Environment status and immediate next steps (2026-07-21)

Machine transfer: the project moved from `/home/chentianyu` to
`/home/xuehaonan`. All live documentation and scripts reference the new paths;
historical run artifacts (`result.json`, caches, logs) intentionally keep the
old paths as provenance.

Provisioned on this machine:

- `~/verus` clone at `cf3b5c3fb937b9effa9478d4735b49743d8646eb` (inventory
  source);
- `~/nanvix/toolchain/verus`: official release `0.2026.05.17.e479cce`
  (matching May snapshot; includes the proc-macro shared libraries that the
  repo-local `verus/` bundle lacks);
- rustup toolchain `1.95.0-x86_64-unknown-linux-gnu` (required by the release
  `verus` shim);
- conda env `specdet` (Python 3.11) with this package installed via
  `pip install -e .`;
- `tree-sitter-verus` **0.23.2**, installed from
  `git+https://github.com/secure-foundations/tree-sitter-verus.git`. The
  inventory numbers in this document and README were generated with 0.21.0,
  which is no longer resolvable from any package index. Self-tests, the
  direct Verus/vstd check, and both smoke targets pass on 0.23.2, but
  regenerating inventories will likely change parse-error counts (expected:
  fewer).

Grammar drift measured 2026-07-21 (dry-run scan of `~/verus/source/vstd@cf3b5c3`
with 0.23.2, `--no-report`, output discarded): parse-recovery modules
54 → **49** (`atomic`, `invariant`, `state_machine_internal`,
`std_specs::result`, `vstd` fixed; no regressions); exec bodies 220 → 222
(`pervasive` +1, `state_machine_internal` +1); contract sites 515, spec sites
3,367 and the 111 public-post target set are unchanged.

Using the provisioned environment:

- run every Python command in §11 and §14 with `/opt/conda/envs/specdet/bin/python`
  (or `conda activate specdet` first) — the system `python3` lacks the
  dependencies;
- the July toolchain builds from source with
  `cd ~/verus/source && ../tools/activate && vargo build --release`; its
  verifier binary is `~/verus/source/target-verus/release/verus`.

Verified after provisioning (takeover checklist §14):

- `python -m spec_determinism.extract.extractor test` — pass;
- `python -m spec_determinism.codegen.gen_det test` — pass;
- direct `verus` on a vstd-importing file — `2 verified, 0 errors`;
- `bytes:u16_from_le_bytes@79` — `ok r0=unsat class=complete`;
- `hash_map:insert@106` — `ok r0=unsat class=complete`.

Immediate next-step options (2026-07-21, in priority order):

1. **P0 coverage fix with the new grammar.** Teach the scanner/extractor to
   parse `verus_!` aliases (or normalize them to `verus!` before parsing),
   then regenerate both inventories (current-upstream `cf3b5c3` and the
   matching May snapshot) with tree-sitter-verus 0.23.2. Expect parse-recovery
   counts to drop; update the README numbers and re-derive the experiment
   target set.
2. **Full-machine reproduction.** **DONE 2026-07-21** — see §15.2.
3. **P1 July toolchain build.** **DONE 2026-07-21** — see §15.1.

### 15.1 July toolchain (P1) — built

`~/verus` (cf3b5c3) was built from source:
`cd ~/verus/source && ../tools/activate && vargo build --release`
(rustup toolchain 1.96.0 per `~/verus/rust-toolchain.toml`, Z3 4.12.5 via
`source/tools/get-z3.sh`). Result:

- verifier: `~/verus/source/target-verus/release/verus`
- version: `0.2026.07.13.cf3b5c3`, toolchain 1.96.0;
- build log: `vstd` itself verified (`2010 verified, 0 errors`);
  `../examples/vectors.rs` `9 verified, 0 errors`; a vstd-importing probe
  `2 verified, 0 errors`.

To run experiments on the July snapshot, point the runner at
`--verus-root ~/verus/source/target-verus/release`,
`--vstd-root ~/verus/source/vstd` and `--vstd-snapshot jul2026`
(**validated end-to-end 2026-07-21** — see §15.4).

### 15.2 Full-machine reproduction and snapshot-compat fixes

Full 111+6 rerun against the May snapshot (outputs in
`experiments/repro-2026-07-21-*`):

- 104/117 targets reproduced the documented verdicts exactly.
- 13 targets failed with `verus_error` (8× deprecated `cell`, 4× `raw_ptr`,
  1× `thread::spawn`). Root causes were **snapshot/code drift**, not the
  grammar version:
  - **RC1 (12 targets):** the schema layer's `POINTS_TO` branch emits
    `(pt).addr()` — the July-vstd API. The May snapshot has no `addr` on
    `cell::PointsTo`/`raw_ptr::PointsTo`; the address lives at
    `.ptr().addr()`. (May `simple_pptr::PointsTo` *does* have `addr()`,
    which is why its 13 targets were unaffected.) Fix:
    `enumerate_schemas(..., points_to_addr=)` version gate
    (`schemas.py::_POINTS_TO_ADDR_EXPR`); the runner passes
    `"ptr().addr()"` for modules `{cell, raw_ptr}`
    (`_MAY_PTR_ADDR_MODULES`), restoring the old behaviour including the
    existing `.id()`/`.pptr()` rewrites.
  - **RC2 (1 target):** the `g_neq_tuple` assume line rendered the equal-fn
    call without its turbofish, so `thread::spawn` — whose `F` generic
    never appears in the equal-fn argument types — failed with E0283.
    Fix: `DetCheckSpec.equal_fn_turbofish`, populated by `gen_det` next to
    `equal_fn_name`, consumed by `render_guarded_template`.
- After the fixes all 13 targets compile and reproduce the documented
  verdicts (`experiments/repro-2026-07-21-fixup-*`, 13/13 match).
- Final clean full rerun under the fixed code:
  `experiments/final-2026-07-21-*` — **0/117 per-target diffs** against the
  documented baseline (public-free 21 complete + 6 trivial-equality +
  5 unknown + 2 unsupported; impl-methods 60 complete + 15 unknown +
  2 unsupported; strict-pointer 6 complete). The effective 87/20/4/0 split
  transfers to this machine unchanged.

Grammar availability note: the old `tree-sitter-verus 0.21.0` is
unobtainable — in `secure-foundations/tree-sitter-verus` the 0.21.x line is
still upstream `tree-sitter-rust` (zero Verus keywords in `grammar.js`); the
Verus grammar only exists in the 0.23.x line. 0.23.2 is therefore the pinned
grammar, and with the two fixes above the documented verdicts reproduce.

### 15.3 P0 done (2026-07-21): alias normalization + regenerated inventories

Implementation: new `spec_determinism/extract/aliases.py`
(`normalize_verus_aliases` — line-preserving, idempotent rewrite of
`<alias>!` to `verus!` for every `use verus as <alias>;` binding), wired
into `scan_vstd.py`, `extract_spec` (source + type_sources),
`type_registry.build_registry` and `impl_scanner.scan_source`. Self-tests
(extractor, gen_det, aliases) pass; `extract_spec` on the previously
invisible `cell/invcell.rs` (`InvCell::new`) validates end-to-end.

Current-upstream inventory (`~/verus@cf3b5c3`, regenerated into
`vstd-survey/generated/`, README updated):

- exec declarations 286 → **330**; exec bodies 220 → 247;
- public exec definitions with postconditions 111 → **135**;
- contract sites 515 → **553** (exec post 185 → 223, assume-post 330 flat);
- spec sites 3,367 → **3,405**;
- parse-recovery modules 54 → 58: 5 fixed by grammar 0.23.2, 9 alias-content
  modules newly partially visible with recovery (`cell::pcell`, `imap`,
  `map`, `tokens`, `std_specs::{cmp, iter, maybe_uninit, slice, vec}`) —
  their function-level numbers are lower bounds;
- `std_specs::cmp` jumped 14 → 25 contract sites once its alias block became
  visible.

Matching May inventory (regenerated into
`vstd-survey/experiments/inventory-may-2026-07-21/`, keeping the historical
`public-free-2026-07-14/inventory/` untouched):

- experiment target set (public definitions with postconditions):
  111 → **137** (37 free + 100 impl);
- newly covered targets (26): `cell::invcell` 4, `cell::pcell` 7,
  `cell::pcell_maybe_uninit` 10, `std_specs::core` 1, `std_specs::iter` 2,
  `std_specs::vec` 2;
- May parse-recovery modules 47 → 50 (same alias-exposure effect);
- the documented 111-target results (87/20/4/0) remain valid: the old set is
  a subset of the new one. The 26 new targets have since been run — see
  [ALIAS-NEW-REVIEW-2026-07-21.md](experiments/ALIAS-NEW-REVIEW-2026-07-21.md)
  (12 complete / 8 unknown / 3 unsupported / 2 no_ensures / 1 pipeline gap;
  the §13 P4 C-class review for `cell::invcell::InvCell` is done).

### 15.4 July-snapshot full rerun (2026-07-21)

The July toolchain (§15.1) was validated end-to-end with a full rerun of all
135 July public-post targets (37 free + 98 impl + 6 strict), using
`--vstd-snapshot jul2026` (new runner profile; the only substantive compat
delta is `MemContents` moving from `vstd::cell` to `vstd::raw_ptr`; the
`PointsTo` API shape is identical across the two snapshots, so the existing
version gates and the `pcell is_init` fold apply unchanged).

Result ([experiments/JULY-RERUN-REVIEW-2026-07-21.md](experiments/JULY-RERUN-REVIEW-2026-07-21.md)):
**zero verdict drift** — 122 same-line shared targets with 0 diffs; 13
line-drifted functions (`atomic`, `simple_pptr`, `index_set`) all verdict-
identical; 2 functions (`std_specs::iter::{new,next}`) removed upstream.
July tally: 98 complete / 27 unknown / 7 unsupported / 2 no_ensures /
1 pipeline gap (= May tally minus the two removed `iter` targets). C-class
underconstraints, B-class intentional nondeterminism and the strict-pointer
behaviour all reproduce on current upstream. The project no longer mixes
May/July artifacts; new work should default to the July snapshot.
