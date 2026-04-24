```json
{
  "RawArray<u8>": [],
  "*mut u8": [],
  "*const u8": [],
  "Ghost<Map<int, nat>>": [],
  "Layout": [
    {"spec_fn": "spec_layout_size", "return_type": "usize", "rationale": "Size dimension of Layout; drives kheap size checks in layout_ok_for_kheap."},
    {"spec_fn": "spec_layout_align", "return_type": "usize", "rationale": "Alignment dimension of Layout; referenced by layout_ok_for_kheap."}
  ],
  "AllocError": []
}
```
