```json
{
  "viewed_type": "Map<K, AbstractEndPoint>",
  "view_decl": "impl<K: KeyTrait + VerusClone> View for DelegationMap<K> {\n    type V = Map<K, AbstractEndPoint>;\n    closed spec fn view(&self) -> Map<K, AbstractEndPoint> {\n        self.m@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "DelegationMap is conceptually a map from keys to endpoints; the `m: Ghost<Map<K, AbstractEndPoint>>` field is its abstract spec representation while `lows: StrictlyOrderedMap<K>` is just a concrete range-based encoding tied to `m` by an internal invariant. Projecting to `self.m@` (unwrap Ghost) captures the semantic content the spec actually constrains and matches IronKV's own inherent `view` definition; the concrete `lows` field carries no extra spec-relevant information and is omitted."
}
```
