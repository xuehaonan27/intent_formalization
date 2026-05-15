```json
{
  "viewed_type": "Map<EndPoint, V>",
  "view_decl": "impl<V> View for HashMap<V> {\n    type V = Map<EndPoint, V>;\n    closed spec fn view(&self) -> Map<EndPoint, V> {\n        self.m@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "The struct is a thin wrapper holding a single std::collections::HashMap<EndPoint, V>; the spec only cares about the abstract key-to-value relation, not the hash-table's allocator/bucket layout. Projecting via vstd's HashMap view (View<V = Map<Key, Value>>) yields Map<EndPoint, V>, which discards physical-layout noise while preserving the full mapping. EndPoint is a leaf-identity type and V is generic, so neither is recursively @-projected at the key/value position."
}
```
