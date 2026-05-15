```json
{
  "viewed_type": "CKeyKVView",
  "view_decl": "pub struct CKeyKVView { pub k: <CKey as View>::V, pub v: Seq<u8> }\n\nimpl View for CKeyKV {\n    type V = CKeyKVView;\n    closed spec fn view(&self) -> CKeyKVView {\n        CKeyKVView { k: self.k@, v: self.v@ }\n    }\n}",
  "depends_on_views_of": ["CKey"],
  "rationale": "CKeyKV is a key/value pair where both components are spec-meaningful: project the key through CKey's semantic view, and project the Vec<u8> value blob to Seq<u8> since byte order is part of the value. No raw pointers, ghost wrappers, or opaque handles are present to omit."
}
```
