```json
{
  "viewed_type": "SHTKeyView",
  "view_decl": "pub struct SHTKeyView { pub ukey: u64 }\n\nimpl View for SHTKey {\n    type V = SHTKeyView;\n    closed spec fn view(&self) -> SHTKeyView {\n        SHTKeyView { ukey: self.ukey }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "SHTKey is a transparent newtype around a u64 identifier; the only spec-relevant dimension is the ukey value itself. Project to a SHTKeyView struct that exposes ukey unchanged (u64 is a primitive, so its view is the value)."
}
```
