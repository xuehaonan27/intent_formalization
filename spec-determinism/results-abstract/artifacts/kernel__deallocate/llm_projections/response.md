```json
{
  "RawArray<u8>": [],
  "*mut u8": [],
  "*const u8": [],
  "Ghost<Map<int, nat>>": [],
  "Layout": [
    {"spec_fn": "spec_layout_size", "return_type": "usize", "rationale": "Logical size of the Layout; drives layout_ok_for_kheap and allocator size-class selection."},
    {"spec_fn": "spec_layout_align", "return_type": "usize", "rationale": "Logical alignment of the Layout; used in layout_ok_for_kheap and the pow2 axiom."}
  ],
  "AllocError": []
}
```
