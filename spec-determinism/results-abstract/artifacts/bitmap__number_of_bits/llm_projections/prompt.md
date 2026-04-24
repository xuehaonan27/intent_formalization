You are helping a Verus-based determinism checker narrow opaque input
types down to concrete integer/bool witnesses. The tool cannot inspect
the internals of **foreign opaque types** (e.g. `core::alloc::Layout`),
but the spec in the repo may define **projection spec functions** —
unary `uninterp spec fn` or `pub spec fn` declarations taking that
opaque type and returning a primitive scalar (usize/nat/int/bool/...)
— that expose the semantically relevant integer/bool dimensions.

Your job: for each opaque type name given, grep the repo for such
projection spec functions and list the ones whose return type is a
primitive scalar.

## Your task

Opaque types to analyse: `RawArray<u8>`

Context:
- Repo root: `/home/chentianyu/nanvix-verus-abstract`
- Originating crate: `bitmap`
- Spec files typically have the suffix `.spec.rs`; also check any `*.rs` file with a `verus!{}` block.

## Output format

Emit a single fenced ```json block. Top-level object keys are the
opaque type names given below. Values are arrays of projections.

```json
{
  "<TypeName>": [
    {
      "spec_fn": "<unqualified_spec_fn_name>",
      "return_type": "<usize|nat|int|bool|u8|u16|u32|u64|i8|i16|i32|i64|isize>",
      "rationale": "<1 short sentence: what dimension this captures>"
    }
  ]
}
```

Rules:
- Include ONLY unary **free** spec fns — i.e. declared at module scope
  as `spec fn <name>(<ident>: <OpaqueType>) -> <scalar>` (possibly
  `uninterp`, possibly with `pub`/`open`/`closed`). Do NOT include
  methods (`impl { spec fn <name>(self, ...) }`): the generator emits
  `<name>(<var>)` as a free call and method projections would produce
  an unresolved-name build error.
- The spec fn must have a primitive scalar return type from the list
  above. Do NOT include projections that return composite types.
- Prefer projections actually referenced by `ensures` / `requires` /
  `open spec fn` / `assume_specification` clauses elsewhere in the
  repo — those are the dimensions that drive the function's behavior.
- If no projections exist for a type, emit an empty array `[]` for it.
- Use the UNQUALIFIED name for `spec_fn` (e.g. `spec_layout_size`, not
  `alloc::spec_layout_size`), as it would appear inside a `verus!{}`
  block after the usual `use` imports.
- Output the JSON block and nothing else (no prose before or after).

## Example

Given: opaque type `Layout`, repo root `/home/alice/nanvix`

After grep: you find in `src/kernel/src/mm/kheap.spec.rs`:
```
pub uninterp spec fn spec_layout_size(layout: core::alloc::Layout) -> usize;
pub uninterp spec fn spec_layout_align(layout: core::alloc::Layout) -> usize;
```

Correct output:
```json
{
  "Layout": [
    {"spec_fn": "spec_layout_size", "return_type": "usize", "rationale": "Drives allocator size-class selection in ensures."},
    {"spec_fn": "spec_layout_align", "return_type": "usize", "rationale": "Required alignment; referenced by layout_ok_for_kheap."}
  ]
}
```
