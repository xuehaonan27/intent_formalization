```json
{
  "viewed_type": "Map<(IOid, u8, u8, u8), bool>",
  "view_decl": "impl View for PCIBitMap {\n    type V = Map<(IOid, u8, u8, u8), bool>;\n    closed spec fn view(&self) -> Self::V {\n        self.ghost_map@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "The 32MB bit_map array is the concrete bit-packed implementation; the spec-relevant content is the ghost_map, which mirrors it as an abstract Map<(IOid, byte-idx, bit-idx)→bool>. Project the Ghost wrapper to its inner Map via self.ghost_map@; since IOid is a usize alias and u8/bool are primitives, Map<K@,V@> collapses to Map<K,V>, so no further @ is needed."
}
```
