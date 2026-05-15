```json
{
  "viewed_type": "Map<CKey, Seq<u8>>",
  "view_decl": "impl View for CKeyHashMap {\n    type V = Map<CKey, Seq<u8>>;\n    closed spec fn view(&self) -> Map<CKey, Seq<u8>> {\n        self.m@.map_values(|v: Vec<u8>| v@)\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "CKeyHashMap is a thin wrapper around std::collections::HashMap<CKey, Vec<u8>>; the spec only cares about the abstract key→value relation and the byte content of each value, not the hash-table's bucket layout or Vec's allocator state. We take vstd's HashMap view (Map<CKey, Vec<u8>>) and lift each Vec<u8> value to its Seq<u8> view via map_values. CKey is uncovered (leaf alias for SHTKey), so we leave it at the key position with its structural identity — that matches IronKV's own abstract type Map<AbstractKey, Seq<u8>>."
}
```
