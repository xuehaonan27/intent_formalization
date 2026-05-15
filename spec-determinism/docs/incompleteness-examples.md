# Incompleteness Examples — Reviewable Witnesses

Four `ok_with_witness` targets drawn from `results-verusage-viewreg/`
(rerun at commit `7ae4d69`). For each example we give:

- the source `.rs` file (with line range);
- the synthesised determinism equal-fn (verbatim from
  `det_spec.json`);
- a self-contained **witness test case** — a Verus `proof fn` whose
  ensures encodes the determinism check and whose body inlines the
  assumes that schema search recorded as the witness. *Drop the test
  case into a Verus file alongside the project's source crate and run
  `verus thatfile.rs`. The witness is confirmed when Verus rejects the
  proof.*
- a verdict — either a real ambiguity class (**A-1** under-constrained
  ensures / **A-2** view-vs-concrete representation gap) **or** an
  FP class our pipeline is known to surface.

## False-positive taxonomy

As we drilled into these examples we found that **3 of 4 "A-2" cases
in the original set are actually false positives** — Verus's spec
language is strong enough to deny them, but our codegen / narrow
pipeline produces a fake-looking witness for a fixable reason. The
FP categories we've identified so far:

| Class | Trigger | Symptom | Fix layer |
|---|---|---|---|
| **FP-A** Bare-`Vec` ensures, no view-lift | top-level `Vec<T>` in ensures + we compared structurally | bare `!equal(r1, r2)` witness | extractor: tag `Vec<T>` with `spec_view=Seq<T>` (ISSUES #14a/b, **landed**) |
| **FP-B** Nested `Vec` inside `Option` / `Result` / `Struct` | `Option<Vec<T>>` / `Result<_, Vec<T>>` / `Struct{f: Vec<T>}` — inner Vec not view-lifted | `r1@.len() == r2@.len()` forced by ensures, but `!equal` survives because inner `Vec == Vec` is uninterpreted | codegen: recursive view-lift in `_typeinfo_to_typeexpr` + `r.map(|v| v@)` projection at call site (TODO) |
| **FP-C** Custom struct with view fn, view not consulted | spec author wrote `impl View for T`, we compared structurally | `r1 == r2` opaque even when `r1@ == r2@` | view-registry L2 / L3 lookup before structural fallback (PR-B, partially landed) |

The diagnostic litmus for "real A-2 vs FP-B": **probe whether z3
will let you instantiate the two outputs with different observable
state**. If `r1@.len() != r2@.len()` (or any other view-level
disequality) is forced UNSAT by ensures, every legal witness has
identical observable state, and the only remaining gap is whatever
our codegen chose to compare beyond view — i.e. an artefact, not
an ambiguity.

**Determinism-check encoding.** Every test case has the shape

```
proof fn witness_<f>(<inputs>, <r1 outputs>, <r2 outputs>)
    requires <orig requires>,
    ensures  <orig ensures(r1)> && <orig ensures(r2)>
             ==> det_<f>_equal(r1, r2, …),
{
    assume(<narrowing fact 1>);
    …
    assume(!det_<f>_equal(r1, r2, …));
}
```

Verus must verify the ensures-implication from the assumed body. If
the spec is deterministic on this slice, Verus accepts (the assumes
collapse the slice to a single output, so `equal` holds). If the spec
admits two distinct outputs on this slice, the implication can't be
proven and Verus rejects — *the rejection is the witness*.

## Example index

| # | Function | Original verdict | Refined verdict |
|---|---|---|---|
| 1 | `memory-allocator::CommitMask::next_run` | A-1 | **A-1** (real, under-constrained ensures) |
| 2 | `vest::set_range` | A-2 (4-assume weak) | **FP-A**, cleared — `status=ok` after #14a/b |
| 3 | `ironkv::clone_option_vec_u8` | A-2 (4-assume weak) | **FP-B**, witness refined to 7 assumes (#14c); still reachable until #14d codegen fix |
| 4 | `ironkv::clone_end_point` | A-2 (bare `!equal`) | (in progress) |

---

## 1. `memory-allocator::CommitMask::next_run` — verdict **A-1**

### Source

`verusage/source-projects/memory-allocator/verified/commit_mask/commit_mask__impl__next_run.rs` (lines 82–87)

```rust
pub fn next_run(&self, idx: usize) -> (res: (usize, usize))
    requires 0 <= idx < COMMIT_MASK_BITS,
    ensures ({ let (next_idx, count) = res;
        next_idx + count <= COMMIT_MASK_BITS
        && (forall |t| next_idx <= t < next_idx + count ==> self@.contains(t))
    }),
```

`CommitMask` is defined at lines 52–63 of the same file with
`view(&self) -> Set<int>` returning the committed bit set.

### Synthesised equal-fn

```rust
spec fn det_next_run_equal(r1: (usize, usize), r2: (usize, usize)) -> bool {
    (r1.0 == r2.0) && (r1.1 == r2.1)
}
```

After ISSUES #14 (commits 377af18 + ee57c7d) tuples are extracted as
positional STRUCTs, so codegen builds the structural per-field
comparison instead of an opaque `r1 == r2`. The result is identical
semantically (Verus derives structural Eq for tuples) but is
now `policy.ignore_fields`-controllable per tuple position.

### Witness test case

```rust
proof fn witness_next_run(
    self_: CommitMask,
    idx: usize,
    r1: (usize, usize),
    r2: (usize, usize),
)
    requires 0 <= idx < COMMIT_MASK_BITS,
    ensures
        ({ let (next_idx, count) = r1;
           next_idx + count <= COMMIT_MASK_BITS
           && (forall |t| next_idx <= t < next_idx + count ==> self_@.contains(t)) })
        && ({ let (next_idx, count) = r2;
              next_idx + count <= COMMIT_MASK_BITS
              && (forall |t| next_idx <= t < next_idx + count ==> self_@.contains(t)) })
        ==> det_next_run_equal(r1, r2),
{
    assume(self_.mask.len() == 8);
    assume(self_.mask[0] as int == 0);
    assume(self_.mask[1] as int == 0);
    assume(self_.mask[2] as int == 0);
    assume(self_.mask[3] as int == 0);
    assume(self_.mask[4] as int == 0);
    assume(self_.mask[5] as int == 0);
    assume(self_.mask[6] as int == 0);
    assume(self_.mask[7] as int == 0);
    assume(idx as int == 0);
    assume(r1.0 as int == 0);
    assume(r1.1 as int == 0);
    assume(r2.0 as int == 0);
    assume(r2.1 as int == 1);
    assume(!det_next_run_equal(r1, r2));
}
```

### Verdict — A-1 (ensures under-constrains the result)

Concrete instance:
`next_run(CommitMask{mask: [0; 8]}, 0)` simultaneously admits
returning **`(0, 0)`** (vacuous forall, `count == 0`) and **`(0, 1)`**
(forall over the empty bitmap holds since `self_@` would still contain
position 0 in the "all bits set" reading; the ensures don't pin
which reading applies when `count` is small).

The ensures says nothing about:
- whether `count > 0`,
- whether `next_idx` must be the *first* run start at or after `idx`,
- whether `count` must be maximal.

The author flags these missing clauses in code comments on lines 88–90
of the source.

### Artifact pointers

```
results-verusage-viewreg/memory-allocator/artifacts/
  memory-allocator__verified__commit_mask__commit_mask__impl__next_run__next_run/
    det_spec.json        — full DetCheckSpec, including the equal-fn above
    injected.rs          — parameterised proof template that schema search ran
```

---

## 2. `vest::set_range` — **resolved** by spec_view-aware Vec narrows (ISSUES #14b follow-up)

### Source

`verusage/source-projects/vest/verified/utils/utils__set_range.rs` (lines 9–22)

```rust
pub open spec fn seq_splice(data: Seq<u8>, pos: usize, v: Seq<u8>) -> Seq<u8>
    recommends pos + v.len() <= data.len(),
{
    data.take(pos as int) + v + data.skip(pos + v.len() as int)
}

pub fn set_range<'a>(data: &mut Vec<u8>, i: usize, input: &[u8])
    requires
        0 <= i + input@.len() <= old(data)@.len() <= usize::MAX,
    ensures
        data@.len() == old(data)@.len()
        && data@ == seq_splice(old(data)@, i, input@),
```

### Status after fix

After tagging `Vec<T>` with `spec_view = Seq<T>` in the extractor
(`spec_determinism/extract/extractor.py` `_KNOWN_GENERICS` + the
`generic_type` branch), codegen now lifts equal-fn signatures from
`Vec<u8>` to `Seq<u8>` and emits `det_set_range_equal(r1, r2,
post1_data@, post2_data@)` at the call site. Narrow + schemas
likewise probe `pre_data@.len()`, `post1_data@[i]`, etc.

End-to-end result: `set_range` now resolves to `status=ok` in
**1 round, 0 assumes** — Verus's seq-equal axiom closes the
goal directly from the ensures `post@ == seq_splice(pre@, i, input@)`
on both branches. The previous "weak A-2 witness" was indeed a
false positive caused by structural `Vec<u8> == Vec<u8>` (which
z3 had no way to relate to the Seq view).

### What the synthesised equal-fn looks like now

```rust
spec fn det_set_range_equal(
    r1: (), r2: (),
    post1_data: Seq<u8>, post2_data: Seq<u8>,
) -> bool {
    r1 == r2 && post1_data == post2_data
}
```

— note the parameter types are `Seq<u8>`, not `Vec<u8>`. The call
site passes `post1_data@`/`post2_data@` to bridge.

### Regression test

Locked in by `spec_determinism.extract.narrow` selftest
(`narrow(Vec<u8>, "d", …)` must emit `d@.len()` / `d@[i]`,
*not* `d.len()` / `d[i]`) and end-to-end by the corpus run on
`vest::set_range` itself.

### Artifact pointers

```
results-verusage-viewreg/vest/artifacts/
  vest__verified__utils__utils__set_range__set_range/
    det_spec.json    # symbols pre_data/post1_data/post2_data: spec_view=Seq<u8>
    injected.rs      # equal_fn params: Seq<u8>; call site uses post1_data@
```

---

## 3. `ironkv::clone_option_vec_u8` — verdict **FP-B (codegen-level)**

### Source

`verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_get_request.rs` (lines 1346–1355)

```rust
#[verifier::external_body]
pub fn clone_option_vec_u8(ov: Option<&Vec<u8>>) -> (res: Option<Vec<u8>>)
    ensures
        match ov {
            Some(e1) => res.is_some() && e1@ == res.get_Some_0()@,
            None     => res.is_None(),
        }
```

### Synthesised equal-fn (current — bug)

```rust
spec fn det_clone_option_vec_u8_equal(
    r1: Option<Vec<u8>>, r2: Option<Vec<u8>>,
) -> bool {
    ((r1 is Some) == (r2 is Some))
    && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0))
}
```

Note the inner comparison is `r1->Some_0 == r2->Some_0`: structural
`Vec<u8> == Vec<u8>`. **`gen_det._typeinfo_to_typeexpr` lifts top-level
`Vec<T>` to `Seq<T>` (ISSUES #14a/b), but does NOT recurse into nested
`type_args`**. So `Vec<u8>` standing alone becomes `Seq<u8>`, but
`Option<Vec<u8>>` is rendered as-is and the inner `Vec` comparison
stays structural.

### Witness test case (after the ISSUES #14c length-probe fix)

```rust
proof fn witness_clone_option_vec_u8(
    ov: Option<&Vec<u8>>,
    r1: Option<Vec<u8>>,
    r2: Option<Vec<u8>>,
)
    ensures
        (match ov {
            Some(e1) => r1.is_some() && e1@ == r1.get_Some_0()@,
            None     => r1.is_None(),
        })
        && (match ov {
            Some(e1) => r2.is_some() && e1@ == r2.get_Some_0()@,
            None     => r2.is_None(),
        })
        ==> det_clone_option_vec_u8_equal(r1, r2),
{
    assume(ov is Some);
    assume(ov->Some_0@.len() == 0);
    assume(r1 is Some);
    assume(r2 is Some);
    assume(r1->Some_0@.len() == 0);
    assume(r2->Some_0@.len() == 0);
    assume(!det_clone_option_vec_u8_equal(r1, r2));
}
```

z3 accepts this — the input view, both output views are pinned to
the empty `Seq<u8>` (all view-equal, satisfying ensures), and the
structural inequality is uninterpreted.

### Why this is FP-B (codegen-level FP, not real A-2)

**Forced view-equality between r1 and r2.** The ensures says
`r1->Some_0@ == ov->Some_0@` and (for the *same* call site)
`r2->Some_0@ == ov->Some_0@`. Transitively `r1->Some_0@ == r2->Some_0@`
— two clones cannot differ in any spec-observable way. We
empirically confirmed this with z3:

```
   sat       [bare] ov/r1/r2 is Some, !equal              ← witness lives here
   sat       …+ r1@.len=0 & r2@.len=0                     ← still SAT (view-equal)
   sat       …+ ov@.len=1 & r1@.len=1 & r2@.len=1         ← still SAT
   unsat     …+ r1@.len=0 & r2@.len=1                     ← UNSAT, can't differ
```

So you **cannot** construct `r1` and `r2` with different lengths.
Every legal witness has `r1@ == r2@`, which is the semantically
intended equality on `Option<Vec<u8>>`. The residual inequality
`!equal(r1, r2)` only survives because the *codegen* picked
structural `Vec == Vec` instead of view `Seq == Seq` — and Verus's
spec models `Vec == Vec` as uninterpreted
(`assume_specification` at `vstd/std_specs/vec.rs:334`; no axiom
in the default `group_vec_axioms` bridges it to view equality).

**Fix is in codegen, not narrow.** Make `_typeinfo_to_typeexpr`
recurse into `type_args`: when an inner `TypeInfo` carries
`spec_view=Seq<u8>`, render the position as `Seq<u8>` too. Then
the equal-fn signature becomes `Option<Seq<u8>>` and the call site
becomes `det_xxx_equal(r1.map(|v| v@), r2.map(|v| v@))`. With this
lift, `r1->Some_0 == r2->Some_0` reads `Seq<u8> == Seq<u8>` — a
real predicate — and the ensures-implied view-equality closes the
proof. Result: `status=ok`, no witness.

### ISSUES #14c — bug we DID land for this case

A separate, real bug in the witness generator: `narrow_seq` emitted
`LenEqPred(var="r1->Some_0@", n=…)` but `enumerate_schemas` registered
the `SEQ_LEN_EQ` / `SEQ_LEN_RANGE` schema with `rust_var=var` (no
`@`). `match_and_bind` then failed `"r1->Some_0" == "r1->Some_0@"`
and every length probe was silently dropped as "pass_untranslatable".

Fix: `schema_search/schemas.py` SEQ_LEN_EQ / SEQ_LEN_RANGE now use
`rust_var=accessor` (`var@` when `ty.spec_view` is set). This lifted
the ironkv witness from 4 → 7 assumes (and **41 other ironkv
functions** similarly strengthened, none weakened). Even though the
case itself is an FP, the fix is load-bearing for the FP analysis:
without it we couldn't show that even the maximally-tight witness
still has view-equal r1/r2, which is what proves it's an FP.

### Artifact pointers

```
results-verusage-viewreg/ironkv/artifacts/
  ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__clone_option_vec_u8/
    det_spec.json
    injected.rs
```

---

## 4. `ironkv::clone_end_point` — verdict **A-2**

### Source

Function:
`verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_get_request.rs` (lines 1357–1363)

```rust
#[verifier::external_body]
pub fn clone_end_point(ep: &EndPoint) -> (cloned_ep: EndPoint)
    ensures
        cloned_ep@ == ep@
```

Type definition and view:
`verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__almost_all_keys_agree.rs` (lines 209–218)

```rust
pub struct EndPoint {
    pub id: Vec<u8>,
}

impl EndPoint {
    pub open spec fn view(self) -> AbstractEndPoint {
        AbstractEndPoint { id: self.id@ }
    }
}
```

### Synthesised equal-fn

```rust
spec fn det_clone_end_point_equal(r1: EndPoint, r2: EndPoint) -> bool {
    r1 == r2
}
```

### Witness test case

```rust
proof fn witness_clone_end_point(
    ep: EndPoint,
    r1: EndPoint,
    r2: EndPoint,
)
    ensures
        (r1@ == ep@) && (r2@ == ep@)
        ==> det_clone_end_point_equal(r1, r2),
{
    assume(!det_clone_end_point_equal(r1, r2));
}
```

Note: this witness needs *no* input narrowing — the bare distinctness
assume is already SAT, i.e. the spec admits two unequal outputs
without constraining `ep` at all.

### Verdict — A-2 (custom `view()` over `Vec<u8>`)

`EndPoint @` exposes `AbstractEndPoint { id: self.id@ }`, so
`cloned_ep@ == ep@` only forces `cloned_ep.id@ == ep.id@`
(`Seq<u8>`-level). The equal-fn's `r1 == r2` compares the concrete
`EndPoint`, including the underlying `Vec<u8>` representation of
`id`. Same root cause as example 3, generalised to any type whose
`view()` exposes a `Seq<…>` over a `Vec<…>` field.

### Artifact pointers

```
results-verusage-viewreg/ironkv/artifacts/
  ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__clone_end_point/
    det_spec.json
    injected.rs
```
