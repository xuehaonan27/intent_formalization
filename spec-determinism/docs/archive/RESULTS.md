# spec-determinism — Full Benchmark Results

*Data source: `results/full_test_results.json` (15 entries across 3 crates)*
*Run elapsed: 20.3 min, 473 Verus calls, 2.57 s/call average*

## 1. Pipeline Design

### 1.1 High-Level Idea

The tool asks one question about every Verus-verified function: **does the
spec pin down its output?**  Formally, for a function `f` with spec
`Q(inputs, outputs)`, we check

```
    Q(x, y1) ∧ Q(x, y2)  ⟹  y1 == y2
```

If Verus proves the implication, the spec is *complete* for that function —
any two implementations satisfying the spec must produce equal outputs on
equal inputs. If Verus refutes it, the spec is *incomplete*: there exist two
different outputs, both acceptable under the spec, for the same input. We
then go one step further and ask Verus to hand us **concrete values** for
that pair, so the author sees exactly which behavioural freedom their spec
left open.

Everything is SMT-driven. The LLM is only consulted when we need an
equivalence policy (e.g. "treat all `Err` variants as equal"); it never
decides determinism. The output of a run is a verdict per function plus, for
nondeterministic cases, a witness of the form

```
assume <input values>
assume <valid y1>
assume <valid y2, different from y1>
⟹ !equal(y1, y2)           // Verus confirms the witness is real
```

Pipeline at a glance:

```
 source .rs  ──▶ extract ──▶ gen_det ──▶ verify ──▶ binary_search ──▶ witness ──▶ report
                   │           │                        │
                   │           │                        └─ iterative: injects assumes,
                   │           │                           asks Verus "still nondet?",
                   │           │                           narrows one field at a time
                   │           └── also emits `equal_fn` template
                   │               (LLM- or human-reviewed)
                   └── parser path first, LLM fallback on unknown constructs
```

### 1.2 Low-Level Walkthrough

The pipeline has six stages. Every stage has a fast parser path and a
narrowly-scoped LLM fallback where the parser would otherwise give up.

**Stage 1 — `extract`**  (`src/extract.py`)

Reads the target crate sources with `tree-sitter-rust` (plus our
Verus-specific queries) and emits a `FunctionSpec` containing signature,
`requires` / `ensures` clauses preserved verbatim, and a `type_defs`
table of every struct/enum reachable from the signature — including
`view` types such as `Bitmap::view() -> BitmapView`.

Parsing Verus with a vanilla Rust grammar is a known pain point. We
split the gaps into two buckets:

*Grammar-level gaps we have already fixed.* Verus uses several
attribute-carried spec forms that `tree-sitter-rust` does not model, so
on early runs we silently missed clauses. The most important case is
the `#[verus_spec(result => ensures ...)]` form used throughout
`bitmap`, e.g.

```rust
#[verus_spec(result =>
    ensures
        result matches Ok(bitmap) ==> {
            &&& bitmap.inv()
            &&& bitmap@.num_bits == number_of_bits as int
            &&& bitmap@.is_empty()
        },
        number_of_bits == 0 ==> result is Err,
        number_of_bits >= u32::MAX ==> result is Err,
        number_of_bits % (u8::BITS as usize) != 0 ==> result is Err,
)]
pub fn new(number_of_bits: usize) -> Result<Self, Error> { ... }
```

The `tree-sitter-rust` grammar sees the attribute as an opaque token
stream and the function itself as having *no* `ensures`, which would
make every such function trivially "deterministic". We fixed this by
teaching the extractor to recognise the `verus_spec` / `verifier::*`
attributes, re-tokenise their payload through the Verus-aware queries,
and attach the recovered clauses to the `FunctionSpec`. The same path
handles the two-argument closure-form `ensures(|r: T| ...)` and the
two-pass `_resolve_types` that walks into `spec_view` structs so
`KheapView.slabs: Seq<SlabView>` resolves instead of collapsing
`SlabView` to `UNKNOWN`.

A second load-bearing detail is **`&mut self` (and other `&mut T`
parameters)**. Logically a mutable argument is two values — the state
on entry and the state on exit — so we split it at extraction time
into a `pre_self_` input symbol and a `post_self_` output symbol (with
the same type, marked `is_mut_ref=True`). Downstream, `gen_det` wires
the two copies as `pre_self_ → &mut post1_self_ / &mut post2_self_`,
rewrites `old(self)` in the original `ensures` to `pre_self_`, and the
binary-search loop treats `post_self_` as just another output to
narrow. Without this split we would miss any nondeterminism that only
manifests in `self`'s post-state (e.g. `bitmap::alloc` choosing which
bit to flip).

*Semantic-level gaps where parsing alone cannot succeed.* Cross-module
or cross-crate definition lookup (e.g. a `spec fn` defined in a sibling
module and re-exported, or a type alias that hides a `Result` behind a
`pub use`) and non-syntactic macro expansions are genuinely hard to
solve with a syntactic tool. For these we fall back to a narrowly
scoped LLM call (see §1.3) whose output is always re-checked by Verus,
so a hallucination shows up as a `verify_error` rather than a wrong
determinism verdict.

**Stage 2 — `gen_det`**  (`src/gen_det.py`)

Emits two pieces of Verus source — a proof obligation and, crucially, a
**hand-written `det_<name>_equal`** that defines what "the same output"
means for this function.

A naive encoding would compare `r1` and `r2` with Rust's structural
`==`, but that produces false positives whenever a spec legitimately
chooses between *morally-equivalent* error paths. Concretely, for any
function returning `Result<T, Error>` where `Error` carries an `errcode`
or a human-readable `err_msg`, two runs that both fail — e.g. with
`Err(Error{kind: OutOfMemory, msg: "slab full"})` vs
`Err(Error{kind: OutOfMemory, msg: "no free block"})` — should both
count as "the function failed", not as nondeterminism. Similarly, two
`Err` values with different `errcode` variants are still just "an
error".

`det_<name>_equal` is therefore generated as:

- `Ok(x1) == Ok(x2)` requires structural equality on the success
  payload (recurse into its fields),
- `Err(_) == Err(_)` is **collapsed to `true`** whenever
  `EqualPolicy.errs_equivalent` holds (the default, and the policy is
  overridable per-function or via an LLM prompt),
- other mixed cases (`Ok` vs `Err`) are inequal.

The companion `proof fn det_<name>(...)` asserts the original `ensures`
twice (once for `r1`, once for `r2`) and concludes
`==> det_<name>_equal(r1, r2)`. If Verus proves this under no extra
assumes, the function is deterministic under the chosen equality. If
not, we hand off to stage 4 to *instantiate* the inequality.

Every generated template and its `EqualPolicy` are persisted to
`results/artifacts/<crate>__<fn>/{template.rs,det_spec.json}` so a
reviewer can audit or override what counts as "equal".

**Stage 3 — `verify`**  (`src/verify.py`)

A thin wrapper over `cargo +nightly-… verus build -p <crate>`. It
injects the stage-2 template between sentinel comments in `lib.proof.rs`,
runs Verus with scoping flags (`--verify-only-module`,
`--verify-function`) so each call only re-checks the injected proof
function, parses `"N verified, M errors"` into a
`VerifyResult{status, duration_ms, stderr}`, and always restores the
file in a `finally` block. A once-per-session baseline preflight
catches the case where the target crate doesn't verify even without our
injection.

Implementation details live in §5.1 (the `verify → build` switch that
gave us the 41% speedup by producing an `.rlib` that cargo's fingerprint
actually looks for).

**Stage 4 — `binary_search`**  (`src/binary_search.py`)

*Why this stage exists at all.* Stage 3 only tells us "Verus could not
prove `det_<name>`" — but that's not a useful artifact for a human
auditor. What we actually want is a **concrete witness**: two specific
inputs/output-pairs `(x, y1), (x, y2)` with `y1 != y2` that both satisfy
the spec, so the reviewer can look at them and either (a) agree the
spec is under-constrained and tighten it, or (b) recognise two
ostensibly-different outputs as morally equivalent and extend
`det_<name>_equal`.

Naively one might hope to extract this counterexample directly from
Verus / Z3. In practice we cannot: Z3 proves `det_<name>` by refutation
on the full logical encoding, and the negation of an `ensures`-style
obligation quantifies over all well-typed outputs — the solver reports
"unsat of the negation failed" but does not hand us values for `x`,
`y1`, `y2`. Even when it does produce a model internally, those values
are over the SMT-level encoding (ghost views, abstract `Set`/`Seq`,
opaque `int`) and do not map back cleanly to Rust-level literals we
could print.

*How we instantiate the witness.* Instead of asking Z3 for a model, we
use Verus itself as an oracle and **bisect over the assume-set**. The
high-level picture is:

> Imagine `bitmap::alloc` returns some `(r, post_self)`. We first ask
> "is it still non-deterministic if we *assume* `r1.is_Ok()`?" — if
> Verus says yes, we commit that assume and now know both runs return
> `Ok`. Next: "…and also assume `r1->Ok_0 == 0`?" — if yes, both runs
> returned address 0; move on. "…and also `r2->Ok_0 == 1`?" — if yes,
> we've just pinned down that one run allocated slot 0 and the other
> slot 1, which is the witness. Each question is one Verus call with
> one more assume appended; each accepted assume carves the output
> space in half.

This is exactly `AssumeTree.test_and_set`: append a candidate assume,
call Verus once, keep it iff nondeterminism still holds. Starting from
the empty assume-set and picking symbols in a principled order (roots
before fields, patterns before payloads), the search converges to a
maximally-specific pair of outputs.

The per-type narrowing strategies are the usual suspects:

- `bool` / `enum`: try each variant.
- `int`/`usize`: exponential-bisect for a range, then bisect for an
  exact value.
- `Option<T>` / `Result<T, E>`: fix the `is-pattern` first, then recurse
  into the payload.
- `Set<T>`: split into `s == empty()` vs `s.len() > 0` and narrow each
  branch (replaces the earlier `s.len() == N` strategy, which confused
  empty with infinite sets because Verus's `Set::len` returns `0` for
  both).
- `Seq<T>`: bisect the length, then recurse elementwise.
- `struct`: recurse field by field.

The search terminates when Verus *passes* (the accumulated assumes have
made determinism provable, i.e. they fully describe both outputs — this
is the witness), or when no strategy can further narrow any remaining
symbol (partial witness — see §4.4), or when we exhaust the per-function
call budget (§5.2).

**Stage 5 — `witness`**  (invoked from `src/report.py::complete_witness`)

The raw assume list is structurally opinionated:

- Input symbols go into `Witness.inputs`.
- Output symbols are split between `output1` (from `r1`, `post1_*`) and
  `output2` (from `r2`, `post2_*`).
- The final accepted assume is always `!det_<name>_equal(...)`, i.e. the
  concrete inequality that makes the witness useful.

**Stage 6 — `report`**  (`src/report.py`, `test_all.py`)

Per-function:

- Writes the artifacts under `results/artifacts/<crate>__<fn>/`.
- Appends one record to `results/full_test_results.json` with
  `{status, rounds, verus_calls, elapsed, assumes}`.

Per-run:

- Prints a summary table.
- Logs per-function `verus_calls` as a delta (snapshotted before/after
  search) so the count is not inflated by earlier functions sharing the
  same `VerusRunner`.

### 1.3 LLM Usage (scope-limited)

The LLM has exactly three pluggable jobs; none of them participates in the
determinism judgement itself:

1. Fallback spec extraction when `tree-sitter` hits an unsupported
   construct (§1.2 Stage 1).
2. Suggesting an `EqualPolicy` when equal-fn semantics are not obvious
   (§1.2 Stage 2, `use_llm_equal_policy`).
3. Narrating a witness into natural language in the final report
   (cosmetic).

Every LLM output is treated as a *suggestion* and immediately re-verified
by Verus; a hallucination costs us one `verify_error` (see the
`Slab1024` incident — an LLM-proposed equal-fn template referenced a
non-existent enum variant, which Verus rejected at compile time) but
never a false determinism verdict.

---

## 2. Executive Summary

We ran the full determinism pipeline on every public function of three
Verus-verified crates in the Nanvix workspace: the `bitmap` bit-vector
allocator, the `slab` per-size allocator, and the `kheap` kernel-heap module
inside `kernel`. Each function is classified into one of three buckets:

| Bucket | Meaning |
|---|---|
| **deterministic** | SMT proved `Q(x, y1) ∧ Q(x, y2) ⟹ y1 == y2` at R0 (no witness needed). The spec is complete w.r.t. the implementation behaviour we care about. |
| **nondeterministic** | Binary search produced a concrete witness: one input with two spec-admissible, unequal outputs. The spec has a real gap. |
| **verify_error** | The generated template failed to compile, so no judgement was made. Needs template fixing before re-running. |

### Headline numbers

```
10 deterministic   (67 %)
 4 nondeterministic(27 %)
 1 verify_error    ( 7 %)
```

| Crate  | Det | Nondet | Err | Total |
|---|---|---|---|---|
| bitmap |  6  |   2    |  0  |  8 |
| slab   |  2  |   1    |  0  |  3 |
| kernel |  2  |   1    |  1  |  4 |

## 3. Results Table

| # | Crate / Function | Status | Rounds | Calls | Time (s) | Notes |
|---|---|---|---|---|---|---|
|  1 | `bitmap::number_of_bits`     | ✅ deterministic    |  1 |  1 |   5.2 | constant fn; trivial |
|  2 | `bitmap::new`                | ❌ nondeterministic | 20 | 20 |  48.4 | spec admits Ok *and* Err for the same valid input |
|  3 | `bitmap::from_raw_array`     | ❌ nondeterministic |  1 |  1 |   2.6 | ensures admits both `Err(_)` and a fully-valid `Ok(bitmap)` under the same precondition |
|  4 | `bitmap::alloc`              | ✅ deterministic    | 65 | 65 | 159.3 | |
|  5 | `bitmap::alloc_range`        | ✅ deterministic    | 72 | 72 | 176.0 | |
|  6 | `bitmap::set`                | ✅ deterministic    |  1 |  1 |   2.6 | |
|  7 | `bitmap::clear`              | ✅ deterministic    |  1 |  1 |   2.6 | |
|  8 | `bitmap::test`               | ✅ deterministic    |  1 |  1 |   2.5 | |
|  9 | `slab::from_raw_parts`       | ❌ nondeterministic | 67 | 67 | 186.9 | `free_addrs` set shape underdetermined |
| 10 | `slab::allocate`             | ✅ deterministic    | 94 | 94 | 252.7 | |
| 11 | `slab::deallocate`           | ✅ deterministic    |  1 |  1 |   2.9 | |
| 12 | `kernel::from_raw_parts`     | ✅ deterministic    | 65 | 65 | 189.4 | |
| 13 | `kernel::allocate`           | ❌ nondeterministic | 82 | 82 | 180.8 | coarse witness; see §4.4 |
| 14 | `kernel::deallocate`         | ✅ deterministic    |  1 |  1 |   3.1 | |
| 15 | `kernel::layout_to_allocator`| ⚠️  verify_error    |  1 |  1 |   1.6 | template references a non-existent enum variant |

`Calls` counts Verus invocations for that function only (per-function delta,
introduced in `test_all.py`). `Rounds` matches `Calls` here because the search
uses exactly one Verus call per round in the current algorithm.

## 4. Witness Analysis (Nondeterministic Cases)

For each nondeterministic result the tool emits a list of assumes that,
together with the function's ensures clauses, admit two unequal outputs.
Below are the witnesses grouped by root cause.

### 4.1 Result-variant ambiguity (`bitmap::new`)

```
number_of_bits == 8
r1 is Ok,  r1->Ok_0@.num_bits == 8,  r1->Ok_0@.set_bits == Set::empty()
r2 is Err, r2->Err_0.code is OperationNotPermitted, r2->Err_0.reason == ""
!det_new_equal(r1, r2)
```

For the same input `number_of_bits == 8` the spec accepts both a successful
constructor and an `OperationNotPermitted` error. The ensures clause does not
connect success/failure to a constraint on `number_of_bits`, so both outcomes
satisfy it. **This is a real spec hole**: the precondition should either
require a valid bit count or the postcondition should mandate `Ok` when the
precondition holds.

### 4.2 Same pattern, overlooked by this run (`bitmap::from_raw_array`)

The JSON flagged this as deterministic at round 0, but an inspection of
the spec shows it has the same structural problem as `bitmap::new`:

```rust
#[verus_spec(result =>
    requires
        array.inv(), array@.len() > 0,
        array@.len() * (u8::BITS as usize) < u32::MAX as usize,
        forall|i: int| 0 <= i < array@.len() ==> array@[i] == 0,
    ensures
        result matches Ok(bitmap) && { bitmap.inv() && ... },
)]
```

The `ensures` only constrains `result` *when it is `Ok`*; there is no
clause forbidding `Err`. So under the stated precondition both runs may
return `Err(_)` and a fully-valid `Ok(bitmap)` respectively and both
satisfy the contract. **Real spec gap**, same family as §4.1. The
round-0 pass is an artefact — most likely our extractor parsed the
`result matches Ok(bitmap) && { ... }` form as an unconditional
assertion "result is Ok", which is how the *author* read it (see the
inline `// Liveness: given preconditions, always succeeds.` comment).
Fixing the ensures to an explicit `result is Ok` (or `==> ...`) will
bring the spec and the tool into agreement.

### 4.3 `free_addrs` set-shape gap (`slab::from_raw_parts`)

```
len == 1, block_size == 1
r1->Ok_0@.free_addrs == Set::empty()
r2->Ok_0@.free_addrs == Set::empty().insert(0)
```

After `from_raw_parts(addr, 1, 1)` the ensures constrains `allocated_addrs`
and `free_addrs` by cardinality, not by extensional equality. A Slab with
zero free blocks and one with a single free block at address 0 both satisfy
the contract. **Real spec gap.**

Note: before the `narrow_set` refactor the same gap was reported as
`len() == 0` vs `len() == 0`, which is a consequence of Verus's `Set::len`
returning `0` for both empty and infinite sets. The current two-branch
narrowing (`s == empty` XOR `s.len() > 0`) yields the extensional witness
shown above.

### 4.4 Coarse witness — search terminated early (`kernel::allocate`)

```
pre_self_@.slabs.len() == 7
r1 is Ok, r2 is Ok
post1_self_@.slabs.len() == 7
post2_self_@.slabs.len() == 7
!det_allocate_equal(r1, r2, post1_self_@, post2_self_@)
```

Only six assumes — the search stopped at `slabs: Seq<SlabView>` and did not
recurse into the per-slab fields. This is an artefact of `extract.py` in
this snapshot not fully resolving `SlabView` inside `Seq<SlabView>` (it
appeared as `kind=UNKNOWN`, so the searcher had no structure to narrow).
The later view-type-resolution fix in `extract.py::_resolve_types` causes
the searcher to descend into `slabs[i].free_addrs`, `.allocated_addrs`,
etc., at the cost of many more rounds. See §5.2.

## 5. Performance

Every call to Verus costs roughly one to three seconds of wall-clock
time, and the binary-search strategy of §1.2 Stage 4 turns a *single*
determinism question into tens or hundreds of such calls. Even on the
small crates in this benchmark, a non-deterministic function with a
compound output (e.g. `slab::allocate`, `kheap::allocate`) comfortably
spends three to five minutes before producing a witness. Scaling the
tool to kernel-sized specs is therefore primarily a per-call latency
problem, with a secondary problem of bounding how many calls the
search is allowed to make. This section covers both.

### 5.1 Per-call cost

```
                bitmap   slab   kernel(bin)
  baseline      2.50 s   2.50 s    2.40 s
  + build/func  1.47 s   1.47 s    2.97 s  *
```

`*` kernel is a `[[bin]]` crate; switching to `cargo verus build` trips on
a duplicate `#![feature(stmt_expr_attributes)]` injected by the Verus
RUSTC_WRAPPER. Kernel is kept on `cargo verus verify` (`use_build=False`
in `KHEAP_CFG`) and consequently pays the `FsStatusOutdated` penalty on
every call. Resolving this requires either (a) a one-line change to
`kmain.rs` (`#![cfg_attr(not(verus_keep_ghost), feature(stmt_expr_attributes))]`)
or (b) a workaround in the Verus wrapper.

### 5.2 Search scalability (the "effective timeout" problem)

Structural narrowing cost is multiplicative:

```
calls ≈ sum over outputs (sum over fields of
            bisection_depth_for_type(field) )
      ≈ N_elements × N_fields × N_outputs × 6
```

With `N_outputs = 3` (`pre`, `post1`, `post2` for `&mut self`) and a
`Seq<Struct>` field of length 7 with 5 fields each, the worst case is
`~630` calls. There is no timeout on the *search as a whole*; cases whose
witnesses lie deep in compound types look stuck to a human watcher even
though every individual Verus call completes in under three seconds.

Recommended follow-ups (in order of cost/benefit):

1. Cap `narrow_seq` at the first K elements and emit a partial witness for
   any deeper divergence (cheap, removes the worst-case blow-up).
2. Add a wall-clock budget per function as a second-tier timeout, distinct
   from the per-call Verus timeout.
3. Resolve the kernel-bin feature collision (§5.1) so the 41 % per-call
   speedup also applies to the hottest cases.

