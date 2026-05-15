```json
{
  "viewed_type": "Seq<K>",
  "view_decl": "impl<K: KeyTrait> View for StrictlyOrderedVec<K> {\n    type V = Seq<K>;\n    closed spec fn view(&self) -> Seq<K> {\n        self.v@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "The type's name and intended invariant (a strictly ordered vector of keys) make element order spec-meaningful, so we project the single Vec<K> field via Vec's built-in view to Seq<K>. K is a generic KeyTrait parameter with no resolved View, so we leave it as the identity type rather than adding an unsupported View bound."
}
```
