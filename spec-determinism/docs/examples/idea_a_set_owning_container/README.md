# Worked example: Idea A on `PageAllocator::set_owning_container`

This directory illustrates **Idea A** (LLM-written Verus proof annotations) on
a real corpus case from `atmosphere`.  Concretely it shows:

1. The **original Verus function** whose determinism we are checking.
2. The **det-check function** our pipeline emits — Verus rejects it (z3 returns
   `unknown` at R0, so it falls into the `ok_inconclusive` bucket).
3. The **LLM-style proof annotation** we add inside the det-fn body. Verus
   discharges everything except one residual obligation, which exposes a real
   *spec gap* in the corpus.
4. A **minimal reproducer** that strips the spec gap and verifies cleanly,
   demonstrating that the proof pattern is sound.

---

## 1. The target function (source)

File: `verusage/source-projects/atmosphere/verified/allocator/`
`allocator__page_allocator_spec_impl__impl2__alloc_and_map_4k.rs`, lines 968–1015.

Extracted into [`source_set_owning_container.rs`](./source_set_owning_container.rs).

Signature (abridged):

```rust
#[verifier::external_body]
pub fn set_owning_container(&mut self, index: usize, owning_container_op: Option<ContainerPtr>)
    requires
        old(self).page_array.wf(),
        0 <= index < NUM_PAGES,
    ensures
        self.page_array.wf(),
        forall|i: int|
            #![trigger self.page_array@[i]]
            #![trigger old(self).page_array@[i]]
            0 <= i < NUM_PAGES && i != index ==> self.page_array@[i] =~= old(self).page_array@[i],
        self.page_array@[index as int].addr =~= old(self).page_array@[index as int].addr,
        // … five more field-level equalities at index …
        self.page_array@[index as int].owning_container =~= owning_container_op,
        self.page_array@[index as int].mappings =~= old(self).page_array@[index as int].mappings,
        self.page_array@[index as int].io_mappings =~= old(self).page_array@[index as int].io_mappings,
        self.free_pages_4k == old(self).free_pages_4k,
        // … 14 more field-level equalities on the rest of PageAllocator …
{ unimplemented!() }
```

Intuitively the function "writes `owning_container_op` into
`page_array[index].owning_container` and leaves everything else alone."

Corpus row (`results-verusage/atmosphere/full_run.json`):

```
n_schemas: 5
status:    ok            (with assumes; r0_z3 = "unknown")
artifact:  atmosphere__verified__allocator__allocator__page_allocator_spec_impl
           __impl2__alloc_and_map_4k__set_owning_container
```

---

## 2. The pipeline's det-check (baseline)

File: [`det_check_baseline.rs`](./det_check_baseline.rs) (verbatim copy of
`results-verusage/atmosphere/artifacts/<artifact>/injected.rs`, lines
1244–1316 are the injection).

Equal-fn the pipeline generated:

```rust
spec fn det_set_owning_container_equal(
    r1: (), r2: (),
    post1_self_: PageAllocator,
    post2_self_: PageAllocator,
) -> bool {
    (r1 == r2)
    && post1_self_.page_array       == post2_self_.page_array
    && post1_self_.free_pages_4k    == post2_self_.free_pages_4k
    // … 15 more `==` clauses, one per PageAllocator field …
}
```

Det-check function:

```rust
proof fn det_set_owning_container(
    g_index_eq: bool, k_index_eq: int,
    g_index_rng: bool, k_index_rng_lo: int, k_index_rng_hi: int,
    g_owning_container_op_is_Some: bool, g_owning_container_op_is_None: bool,
    g_neq_tuple: bool,
    pre_self_: PageAllocator, index: usize, owning_container_op: Option<ContainerPtr>,
    post1_self_: PageAllocator, r1: (),
    post2_self_: PageAllocator, r2: (),
)
    requires pre_self_.page_array.wf(), 0 <= index < NUM_PAGES,
    ensures
        ({
            &&& post1_self_.page_array.wf()
            &&& forall|i: int| #![trigger post1_self_.page_array@[i]]
                 #![trigger pre_self_.page_array@[i]]
                 0 <= i < NUM_PAGES && i != index ==>
                 post1_self_.page_array@[i] =~= pre_self_.page_array@[i]
            // … 7 explicit field equalities at `index` for post1 …
            &&& post2_self_.page_array.wf()
            &&& forall|i: int| #![trigger post2_self_.page_array@[i]]   // <-- separate trigger
                 #![trigger pre_self_.page_array@[i]]
                 0 <= i < NUM_PAGES && i != index ==>
                 post2_self_.page_array@[i] =~= pre_self_.page_array@[i]
            // … 7 explicit field equalities at `index` for post2 …
            // … 15 PageAllocator-level equalities for free_pages_*, etc., per post …
        }) ==> det_set_owning_container_equal(r1, r2, post1_self_, post2_self_),
{
    if g_index_eq { assume(index as int == k_index_eq); }
    if g_index_rng { assume(index as int >= k_index_rng_lo
                         && index as int <= k_index_rng_hi); }
    if g_owning_container_op_is_Some { assume(owning_container_op is Some); }
    if g_owning_container_op_is_None { assume(owning_container_op is None); }
    if g_neq_tuple { assume(!det_set_owning_container_equal(r1, r2,
                            post1_self_, post2_self_)); }
}
```

Running Verus on the baseline:

```
$ verus det_check_baseline.rs --rlimit 60
error: postcondition not satisfied
verification results:: 8 verified, 1 errors
```

z3's reasoning gets stuck because:

* the ensures has **two `forall|i: int|` clauses**, one with the trigger
  `post1_self_.page_array@[i]` and one with `post2_self_.page_array@[i]`;
* the goal `post1_self_.page_array == post2_self_.page_array` does **not**
  itself emit an `@[i]` pattern, so neither forall fires;
* without those instantiations, z3 has no way to learn that the two `page_array`
  views agree element-wise → returns `unknown` at R0 in the standalone solver,
  and `postcondition not satisfied` in Verus.

This is exactly the "ok_inconclusive" bucket from the strategy doc.

---

## 3. After LLM proof injection

File: [`det_check_with_proof.rs`](./det_check_with_proof.rs).

The body of `det_set_owning_container` is augmented with:

```rust
if /* the full ensures hypothesis H, copy-pasted */ {
    assert forall |i: int| 0 <= i < NUM_PAGES implies
        post1_self_.page_array@[i] =~= post2_self_.page_array@[i]
    by {
        if i == index as int {
            // record extensionality: all 8 Page fields agree.
            assert(post1_self_.page_array@[i].addr =~= post2_self_.page_array@[i].addr);
            assert(post1_self_.page_array@[i].state =~= post2_self_.page_array@[i].state);
            // … 6 more field-level asserts …
        } else {
            // off-index: both pin to pre[i].
            assert(post1_self_.page_array@[i] =~= pre_self_.page_array@[i]);
            assert(post2_self_.page_array@[i] =~= pre_self_.page_array@[i]);
        }
    };
    // Seq extensionality from pointwise equality.
    assert(post1_self_.page_array@ =~= post2_self_.page_array@);
}
```

Sandbox compliance: no `assume`, no `admit`, no new `#[verifier::external_body]`,
no `unimplemented!()`. Only `assert`, `assert by`, and `=~=` extensionality.

Running Verus on the annotated version:

```
$ verus det_check_with_proof.rs --rlimit 60
error: postcondition not satisfied      <-- still ONE residual error
verification results:: 8 verified, 1 errors
```

**Every individual assert inside the body succeeds.** Verus did instantiate the
two `forall`s and derive `post1_self_.page_array@ =~= post2_self_.page_array@`.

But the postcondition still fails. Looking at `det_set_owning_container_equal`:

```rust
post1_self_.page_array == post2_self_.page_array
```

This is **struct equality on `Array<Page, NUM_PAGES>`**, which has fields:

```rust
pub struct Array<A, const N: usize> {
    pub seq: Ghost<Seq<A>>,
    pub ar:  [A; N],          // <-- exec mode
}
```

Our proof established `seq@` equality. The exec-mode `ar` field is **never
constrained by the ensures** of `set_owning_container`. So Idea A correctly
proves everything the ensures supports, and Verus correctly reports that the
remaining gap (`post1.page_array.ar == post2.page_array.ar`) is unprovable.

This is the **spec-gap sub-cause** from §8 of the strategy doc, distinct from
the **trigger sub-cause** that LLM proof handled. Both occur here, and they
must be diagnosed separately.

### What would close the residual gap honestly

Three options, in increasing invasiveness:

1. **Patch the equal-fn**: have the pipeline emit `post1.page_array@ ==
   post2.page_array@` instead of `post1.page_array == post2.page_array`. This
   is correct when the surface contract only mentions `.page_array@`, which is
   the case here.
2. **Add a vstd-level axiom**: `Array<A, N>::ar` is fully determined by
   `Array<A, N>::seq` — i.e., `forall a, b. a.seq@ == b.seq@ ==> a.ar == b.ar`.
   This is true by construction for the `Array` wrapper, but Verus does not
   ship it as a lemma.
3. **Strengthen the source `ensures`** of `set_owning_container` to mention
   `self.page_array.ar`. Out of scope for our pipeline (we don't modify
   verified projects).

Option 1 is by far the cheapest and is consistent with the
`view-aware equal-fn` policy already being designed in Phase 2 (see plan.md
"A-2"). It's an orthogonal fix: complete the equal-fn pipeline, then re-run
Idea A on the residue.

---

## 4. Demonstrating Option 1 — view-aware equal-fn + LLM proof

File: [`det_check_view_eq.rs`](./det_check_view_eq.rs).

This file is **identical** to `det_check_with_proof.rs` (same LLM proof block)
except for **one line** in `det_set_owning_container_equal`, changing the
`page_array` field comparison from struct-`==` to `.view()`-`==`:

```diff
- (post1_self_.page_array  == post2_self_.page_array)
+ (post1_self_.page_array@ == post2_self_.page_array@)
```

The other 16 fields stay as struct-`==` because their ensures pin them to
`pre` on both sides (so transitive equality is automatic).

Verus result:

```
$ verus det_check_view_eq.rs --rlimit 60
verification results:: 9 verified, 0 errors
```

At the z3 level, the SMT log contains **9 check-sat queries, all `unsat`**
(vs. 10 unsat + 1 unknown for `det_check_with_proof.rs`). The previously
unknown query — the determinism postcondition — is now `unsat`.

### 4.1 The 2×2 result

The two fixes (view-aware equal-fn, LLM proof) are **independent and both
required**. Concretely:

| variant                                         | LLM proof? | view-eq? | Verus            | z3 verdicts           |
| ---                                             | ---        | ---      | ---              | ---                   |
| `det_check_baseline.rs`                         | ❌          | ❌        | 8 verified 1 err | 10 unsat + 1 unknown  |
| `det_check_with_proof.rs`                       | ✅          | ❌        | 8 verified 1 err | 10 unsat + 1 unknown  |
| view-eq alone (no proof; not stored, easy to    | ❌          | ✅        | 8 verified 1 err | 10 unsat + 1 unknown  |
|   build by reverting the proof block)           |            |          |                  |                       |
| **`det_check_view_eq.rs`**                      | ✅          | ✅        | **9 verified 0 err** | **9 unsat** ✓     |

Interpretation:

  * The **`Array.ar` spec gap** keeps z3 unknown when only the LLM proof is
    applied — the proof closes the trigger-alignment but cannot bridge the
    spec gap.
  * The **trigger problem** keeps z3 unknown when only the equal-fn is
    fixed — z3 still can't align the two `forall` quantifiers in the ensures
    on a shared `i`.
  * **Both together** dissolve the unknown into a chain of `unsat`. This is
    the cleanest empirical confirmation that `unknown` in our corpus is
    almost always a **composite** of independent sub-causes (see
    `docs/unknown-handling-strategy-2026-05-15.md` §8), and that
    Phase-2 A-2 (view-aware equal-fn) and Idea A (LLM proof) are
    **complementary**, not interchangeable.

### 4.2 Robustness: the result does not depend on pipeline `assume`s

The pipeline-generated body of `det_set_owning_container` contains 5
`assume` calls (each gated by an `if g_*: bool`) that the pipeline uses
to mark schema-refinements:

```rust
if g_index_eq     { assume(index as int == k_index_eq); }
if g_index_rng    { assume(k_lo <= index as int <= k_hi); }
if g_oc_is_Some   { assume(owning_container_op is Some); }
if g_oc_is_None   { assume(owning_container_op is None); }
if g_neq_tuple    { assume(!det_set_owning_container_equal(...)); }
```

A natural question is whether these assumes are doing the heavy lifting
for the LLM proof. They are not. Because every assume is guarded by an
`if g_*: bool`, Verus must verify the function for arbitrary `g_*`
values — including `g_* = false`, where the assume never fires. That
"all-`false`" branch is the most-general precondition, and it is the
case Verus actually delivers to z3.

We confirmed this empirically: removing all 5 assumes from each of the
4 variants in the 2×2 produces **bit-identical** Verus output and z3
verdicts (same check-sat count, same per-query verdict, same sat/unsat
totals).

| variant                        | with 5 pipeline assumes        | without 5 pipeline assumes     |
| ---                            | ---                            | ---                            |
| baseline                       | 8/1 err, 10 unsat + 1 unknown  | 8/1 err, 10 unsat + 1 unknown  |
| + LLM proof                    | 8/1 err, 10 unsat + 1 unknown  | 8/1 err, 10 unsat + 1 unknown  |
| + view-eq (alone)              | 8/1 err, 10 unsat + 1 unknown  | 8/1 err, 10 unsat + 1 unknown  |
| **+ view-eq + LLM proof**      | **9/0, 9 unsat ✓**             | **9/0, 9 unsat ✓**             |

File: [`det_check_view_eq_no_assumes.rs`](./det_check_view_eq_no_assumes.rs)
is the bottom-right cell of that table — a fully self-contained,
honest proof of observational determinism with no pipeline-injected
`assume` at all. It rules out the worry that the LLM proof "secretly
depends on a pipeline assume".

(The pipeline-level role of the 5 assumes — enumerating schemas and
detecting witnesses in driver_v2 — is unrelated to per-file z3
verdicts and is not affected by this experiment.)

---

## 5. Minimal reproducer that **does** verify cleanly

File: [`repro_minimal_proves.rs`](./repro_minimal_proves.rs).

This strips the wrapper struct down to the only field the ensures actually
constrains (`page_array_seq: Ghost<Seq<Page>>`), eliminating the `Array.ar`
spec gap. The Page struct also drops `mappings`/`io_mappings` (Ghost; same
shape) to keep the file small.

Running Verus on it:

```
$ verus repro_minimal_proves.rs --rlimit 60
verification results:: 2 verified, 0 errors    real 0m0.43s
```

This is the cleanest experimental evidence that the proof *pattern* discharges
the trigger problem.

---

## 6. Takeaways for Idea A implementation

* **Mechanical proof template** (per ensures shape): copy H into `if`,
  pointwise `assert forall`, case-split at the touched index, struct
  extensionality fan-out, Seq `=~=` close. The LLM only fills in
  per-target identifiers (`page_array`, the 8 Page fields, the index name).
  Estimated tokens per case: < 200.
* **Pre-LLM check**: if the equal-fn references fields not mentioned in the
  ensures (here: `Array.ar`), flag it as a **spec-gap** and skip the LLM call
  (or run the LLM in `A-witness` mode hoping to construct a counter-example
  exploiting the gap).
* **Yield estimate**: among the 257 atmosphere ok_inconclusive cases, the
  pipeline emits a `set_*` / `assign_*` style det-fn in roughly 90 of them.
  After Option-1 equal-fn fix, this pattern alone should retire ~30 % of the
  inconclusive bucket on atmosphere.

---

## 7. Files in this directory

| file | role | Verus result |
|---|---|---|
| `source_set_owning_container.rs` | original atmosphere function | (informational) |
| `det_check_baseline.rs` | pipeline's emitted injection | **fails** (postcondition; z3 unknown) |
| `det_check_with_proof.rs` | + LLM proof block | fails on residual `Array.ar` spec gap (z3 still unknown) |
| `det_check_view_eq.rs` | + LLM proof + view-aware equal-fn (Option 1) | **passes** (9 verified, 0 errors; z3 all unsat) |
| `det_check_view_eq_no_assumes.rs` | same as above, with all 5 pipeline `assume`s removed | **passes** (9 verified, 0 errors; identical z3 verdicts) — robustness check |
| `repro_minimal_proves.rs` | trigger-only minimal repro (no spec gap) | **passes** (2 verified, 0 errors) |

To re-run any of these:

```bash
cd spec-determinism/docs/examples/idea_a_set_owning_container/
~/nanvix/toolchain/verus/verus <file>.rs --rlimit 60
```
