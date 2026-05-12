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
- a one-line verdict (A-1: under-constrained ensures; A-2:
  view-vs-concrete representation gap).

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

## 2. `vest::set_range` — verdict **A-2**

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

### Synthesised equal-fn

```rust
spec fn det_set_range_equal(
    r1: (), r2: (),
    post1_data: Vec<u8>, post2_data: Vec<u8>,
) -> bool {
    r1 == r2 && post1_data == post2_data
}
```

### Witness test case

```rust
proof fn witness_set_range(
    pre_data: Vec<u8>,
    i: usize,
    input: &[u8],
    post1_data: Vec<u8>, r1: (),
    post2_data: Vec<u8>, r2: (),
)
    requires 0 <= i + input@.len() <= pre_data@.len() <= usize::MAX,
    ensures
        (post1_data@.len() == pre_data@.len()
         && post1_data@ == seq_splice(pre_data@, i, input@))
        && (post2_data@.len() == pre_data@.len()
            && post2_data@ == seq_splice(pre_data@, i, input@))
        ==> det_set_range_equal(r1, r2, post1_data, post2_data),
{
    assume(i as int == 0);
    assume(!det_set_range_equal(r1, r2, post1_data, post2_data));
}
```

### Verdict — A-2 (spec pins `Seq<u8>` view; equal-fn compares `Vec<u8>`)

The ensures only pins `data@` (the `Seq<u8>` view); two `Vec<u8>`
values with equal element sequences can still differ structurally
(capacity, allocator metadata) and therefore differ under the `==`
that the synthesised equal-fn applies.

### Artifact pointers

```
results-verusage-viewreg/vest/artifacts/
  vest__verified__utils__utils__set_range__set_range/
    det_spec.json
    injected.rs
```

---

## 3. `ironkv::clone_option_vec_u8` — verdict **A-2**

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

### Synthesised equal-fn

```rust
spec fn det_clone_option_vec_u8_equal(
    r1: Option<Vec<u8>>, r2: Option<Vec<u8>>,
) -> bool {
    ((r1 is Some) == (r2 is Some))
    && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0))
}
```

### Witness test case

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
    assume(r1 is Some);
    assume(r2 is Some);
    assume(!det_clone_option_vec_u8_equal(r1, r2));
}
```

### Verdict — A-2 (`Vec<u8>` view-vs-concrete inside `Option`)

The Some-branch ensures pins `e1@ == res.get_Some_0()@` (view
equality on `Seq<u8>`); the equal-fn's Some-branch compares
`r1->Some_0 == r2->Some_0` (structural `Vec<u8> == Vec<u8>`). Two
clones with view-equal but structurally-different `Vec<u8>` buffers
satisfy ensures yet break equal-fn.

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
