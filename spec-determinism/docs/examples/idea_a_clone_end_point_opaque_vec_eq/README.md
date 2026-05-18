# Worked example: Idea A on `EndPoint::clone_end_point` — codegen mis-uses the Vec spec_view

This directory illustrates a representative **Idea A** (LLM-written
Verus proof annotations) failure on `ironkv`, where:

* the LLM agent correctly diagnoses the obligation as unprovable;
* but the **real root cause is upstream of the LLM** — our codegen
  generates an equal-fn body that compares `Vec<u8>` via *struct
  equality* even though the extractor already knew the field's spec
  view is `Seq<u8>`.

The fix is in our pipeline (codegen + extractor), **not** in the
proof. With either of two small changes, this obligation closes with
zero LLM rounds and an empty proof body.

---

## 1. The equal-fn is template-generated, not LLM-authored

The body of `det_clone_end_point_equal` comes from
[`spec_determinism/codegen/gen_det.py:_build_equal_fn`][1], which
recursively walks the function's output `TypeInfo` graph (built
during extraction) and emits a `&&`-joined conjunction of per-field
comparisons.

There is no LLM call on the equal-fn path. The only place an LLM
ever touches an equal-fn is the **escape hatch**
`EqualPolicy.custom_body` (a verbatim body the policy author can
inject) — and `det_spec.json` for this case shows the default policy
with `source="default"` and no custom_body:

```json
"equal_policy": {
  "errs_equivalent": true, "opaque_ok": false,
  "compare_raw_pointers": false,
  "ignore_fields": [], "opaque_types": [],
  "custom_body": null, "rationale": null,
  "source": "default"
}
```

So the body is 100% template output.

[1]: ../../spec_determinism/codegen/gen_det.py

## 2. The target function (source)

File:
[`verusage/source-projects/ironkv/verified/delegation_map_v/`
`delegation_map_v__impl4__set.rs`, lines 486–580](file:///home/chentianyu/verus-proof-synthesis/benchmarks/VeruSAGE-Bench/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs).
Extracted into [`source_clone_end_point.rs`](./source_clone_end_point.rs).

```rust
pub struct EndPoint {
    pub id: Vec<u8>,
}

impl EndPoint {
    pub open spec fn view(self) -> AbstractEndPoint {
        AbstractEndPoint { id: self.id@ }
    }

    pub fn clone_end_point(ep: &EndPoint) -> (cloned_ep: EndPoint)
        ensures cloned_ep@ == ep@
    { unimplemented!() }     // real source: #[verifier(external_body)]
}
```

The `ensures` clause only commits to **view equality**
(`AbstractEndPoint{ id: ep.id@ }`). It says nothing about the
underlying `Vec<u8>` struct value, which is intentional — `Vec` is
`external_body` in Verus and its spec-level `==` is uninterpreted.

## 3. What the extractor actually produced

From `det_spec.json` for this target (`symbols[0]`, the input `ep`):

```python
{'name': 'ep',
 'type': {'kind': 'struct', 'name': 'EndPoint',
          'fields': [{'name': 'id',
                      'type': {'kind': 'Seq',
                               'name': 'Vec<u8>',
                               'spec_view': {'kind': 'Seq', 'name': 'Seq<u8>',
                                             'type_args': [{'kind': 'u8'}]},
                               'type_args': [{'kind': 'u8'}]}}]}}
```

Two facts to notice:

1. **`EndPoint.spec_view` is missing** — the extractor did *not*
   record that `EndPoint` has its own `spec fn view -> AbstractEndPoint`.
2. **`EndPoint.id.spec_view = Seq<u8>` is present** — the extractor
   correctly tagged the `Vec<u8>` field with its spec projection.

If either had been used by codegen, the obligation would close. But
neither is — see next.

## 4. What codegen does next (the bug)

[`build_equal_expr`][1] dispatches on `TypeInfo.kind`. With the
TypeInfo above:

* `EndPoint` hits the `TypeKind.STRUCT` branch. Because
  `ty.spec_view is None` (fact #1 above), it falls to the
  field-by-field recursion (line 1344–1356).
* The field `id` (kind=`SEQ`) hits the `TypeKind.SEQ` branch at
  line 1174–1184:

  ```python
  if k == TypeKind.SEQ:
      elem_ty = ty.type_args[0] if ty.type_args else None
      if elem_ty is not None and _container_needs_elementwise(elem_ty, policy):
          ...                       # only fires when elem contains Result
      return f"{lhs} == {rhs}"      # ← raw struct equality, ignores spec_view
  ```

  This branch **does not consult `ty.spec_view`**. It emits raw
  `r1.id == r2.id`, which Verus reads as `Vec<u8>` struct equality.

So the emitted equal-fn body is:

```rust
spec fn det_clone_end_point_equal(r1: EndPoint, r2: EndPoint) -> bool {
    (r1.id == r2.id)        // <- demands Vec<u8> struct equality
}
```

…and the obligation is

```rust
(r1@ == ep@) && (r2@ == ep@) ==> det_clone_end_point_equal(r1, r2)
```

— provably **unsatisfiable** in Verus's spec semantics (see
[`repro_vec_view_eq_fails.rs`](./repro_vec_view_eq_fails.rs) for a
standalone reproducer).

The full det fn we emit (with all guard knobs from `schema_search`)
is in [`det_check_strict_policy.rs`](./det_check_strict_policy.rs).

## 5. The agent's diagnosis

After 5 verus invocations inside the agentic session, the agent
arrived at this proof and gave up
([`agent_rationale.txt`](./agent_rationale.txt)):

```rust
if r1@ == ep@ && r2@ == ep@ {
    assert(r1.id@ == ep.id@);   // ✓
    assert(r2.id@ == ep.id@);   // ✓
    assert(r1.id@ == r2.id@);   // ✓
    assert(r1.id == r2.id);     // ✗  ← verus rejects
}
```

[`verus_error.txt`](./verus_error.txt) records the exact rejection.
The rationale is correct: from view equality on `Vec<u8>` you cannot
derive struct equality, period.

## 6. What the fix actually is

The lazy framing is "give the agent better hints / more rounds". But
the obligation is **unprovable as stated** — no amount of LLM
iteration recovers it. The fix is to **change what we emit**.

Two minimal patches (either alone is sufficient) are exercised in
[`abc_probe_equal_fn_variants.rs`](./abc_probe_equal_fn_variants.rs),
which Verus accepts in 2/3 variants:

| Variant | Equal-fn body | Codegen path | Verus |
| --- | --- | --- | --- |
| **A** — what we emit today | `r1.id == r2.id` | SEQ branch ignores `spec_view` | ✗ FAIL |
| **B** — SEQ branch reads `spec_view` | `r1.id@ == r2.id@` | one-line patch to `build_equal_expr` SEQ case | ✓ pass, empty proof |
| **C** — extractor populates `EndPoint.spec_view` | `r1@ == r2@` | STRUCT branch fires its nested-view fallback at line 1327–1332 | ✓ pass, empty proof |

The **B-patch** is the most local and the most general — any
`TypeKind.SEQ` whose `spec_view` is set (i.e. extractor knows it's a
Vec-with-view, not a native spec Seq) should compare through the
view. Sketch:

```python
# gen_det.py, build_equal_expr, TypeKind.SEQ branch
if k == TypeKind.SEQ:
    ...
    if ty.spec_view is not None:        # <- new
        return f"({lhs})@ == ({rhs})@"  # <- new
    return f"{lhs} == {rhs}"
```

The **C-patch** is more invasive (touches the extractor) but also
fixes the parallel symptom for HashMap, Vec<T> where T is also
external_body, and any other "container with view" the extractor
might learn about later. For this corpus it is probably the right
long-term fix, paired with B as a defensive backstop.

## 7. Why this matters for the corpus story

In the v2 agentic run on ironkv (71 LLM-triggered targets, 2/71
pass), the dominant failure shape across `assertion_failed` and
`postcondition_unsat` buckets is exactly this: codegen demands a
struct-eq it has no way to derive, because the extractor knew the
view projection but codegen never reads it. The LLM iterates with a
real verus tool in the loop, correctly concludes the obligation is
unprovable, and exits.

In other words: a non-trivial fraction of our v2 "LLM failed"
column would flip to "z3 trivially passed" if we apply patch B
(+ ideally C). It is not a model-capability ceiling — it is a
codegen leak.

---

## Files

| File | What it is |
| --- | --- |
| [`source_clone_end_point.rs`](./source_clone_end_point.rs) | The real ironkv source items, extracted. |
| [`det_check_strict_policy.rs`](./det_check_strict_policy.rs) | The det fn we emit today + the agent's final proof block. **Verus rejects this.** |
| [`abc_probe_equal_fn_variants.rs`](./abc_probe_equal_fn_variants.rs) | Three candidate equal-fn shapes; verus run shows A fails, B and C pass with empty proof. |
| [`repro_vec_view_eq_fails.rs`](./repro_vec_view_eq_fails.rs) | Minimal standalone reproducer of "`v1@ == v2@ ⇏ v1 == v2`" for `Vec<u8>` — confirms why patch A is unsalvageable. |
| [`verus_error.txt`](./verus_error.txt) | Exact stderr tail from the failing re-verify. |
| [`agent_rationale.txt`](./agent_rationale.txt) | Verbatim rationale the LLM wrote on exit. |
