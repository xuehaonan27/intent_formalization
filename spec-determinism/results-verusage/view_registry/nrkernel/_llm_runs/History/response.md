```json
{
  "viewed_type": "HistoryView",
  "view_decl": "pub struct HistoryView {\n    pub pending_maps: Map<usize, <PTE as View>::V>,\n    pub pending_unmaps: Map<usize, <PTE as View>::V>,\n}\n\nimpl View for History {\n    type V = HistoryView;\n    closed spec fn view(&self) -> HistoryView {\n        HistoryView {\n            pending_maps: self.pending_maps.map_values(|v: PTE| v@),\n            pending_unmaps: self.pending_unmaps.map_values(|v: PTE| v@),\n        }\n    }\n}",
  "depends_on_views_of": ["PTE"],
  "rationale": "Both fields are kept because the spec constrains pending map/unmap state. Per the rule 'Map<K, V> views to Map<K@, V@>', keys (usize, primitive) pass through as identity, while PTE values are projected recursively via map_values + v@ so semantic equality ignores any allocator-opaque or ghost dimensions inside PTE."
}
```
