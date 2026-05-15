```json
{
  "viewed_type": "Map<K, ID>",
  "view_decl": "impl<K: KeyTrait + VerusClone> View for StrictlyOrderedMap<K> {\n    type V = Map<K, ID>;\n    closed spec fn view(&self) -> Self::V {\n        self.m@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "The ghost field `m: Ghost<Map<K, ID>>` is the abstract spec state of the map; `keys: StrictlyOrderedVec<K>` and `vals: Vec<ID>` are concrete representations kept in sync with `m` by the `map_valid` invariant. Semantic equality of two `StrictlyOrderedMap`s should therefore compare only the abstract key-to-ID mapping, which we obtain by unwrapping the Ghost wrapper via `self.m@`. This also matches the existing `pub closed spec fn view(self) -> Map<K, ID> { self.m@ }` already written in `delegation_map_v.rs`."
}
```
