```json
{
  "viewed_type": "Map<AbstractKey, AbstractEndPoint>",
  "view_decl": "impl View for AbstractDelegationMap {\n    type V = Map<AbstractKey, AbstractEndPoint>;\n    closed spec fn view(&self) -> Self::V {\n        self.0\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "AbstractDelegationMap is a newtype wrapper around a single Map field, so the view simply unwraps the tuple struct via self.0. AbstractKey and AbstractEndPoint are unresolved leaf types (no View rule), so they are treated as identity and require no further projection on keys/values."
}
```
