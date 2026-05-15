```json
{
  "viewed_type": "KeyRangeView<K>",
  "view_decl": "pub struct KeyRangeView<K: KeyTrait + VerusClone> {\n    pub lo: KeyIterator<K>,\n    pub hi: KeyIterator<K>,\n}\n\nimpl<K: KeyTrait + VerusClone> View for KeyRange<K> {\n    type V = KeyRangeView<K>;\n    closed spec fn view(&self) -> KeyRangeView<K> {\n        KeyRangeView { lo: self.lo, hi: self.hi }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "A KeyRange semantically denotes the half-open interval [lo, hi); both endpoints are part of its meaning, so neither field can be dropped. KeyIterator is an uncovered leaf type (no View impl yet), so we carry it through the view struct structurally — once a View for KeyIterator is synthesised, this projection can be refined to use `self.lo@` / `self.hi@`."
}
```
