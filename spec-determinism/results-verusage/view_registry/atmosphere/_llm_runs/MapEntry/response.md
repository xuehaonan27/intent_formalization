```json
{
  "viewed_type": "MapEntryView",
  "view_decl": "pub struct MapEntryView { pub addr: PAddr, pub write: bool, pub execute_disable: bool }\n\nimpl View for MapEntry {\n    type V = MapEntryView;\n    closed spec fn view(&self) -> MapEntryView {\n        MapEntryView { addr: self.addr, write: self.write, execute_disable: self.execute_disable }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All three fields are spec-meaningful and project as identity: addr is PAddr (alias for usize, a primitive), and write/execute_disable are bool primitives. There are no raw pointers, ghost wrappers, allocator handles, or opaque IDs to drop, so the view simply rebuilds the same triple in a parallel MapEntryView struct."
}
```
