```json
{
  "Layout": [
    {"spec_fn": "spec_layout_size", "return_type": "usize", "rationale": "Size dimension of the layout; drives slab tier selection in layout_ok_for_kheap."},
    {"spec_fn": "spec_layout_align", "return_type": "usize", "rationale": "Alignment dimension of the layout; referenced by layout_ok_for_kheap."}
  ],
  "AllocError": []
}
```
