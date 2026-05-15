```json
{
  "viewed_type": "QuotaView",
  "view_decl": "pub struct QuotaView { pub mem_4k: int, pub mem_2m: int, pub mem_1g: int, pub pcid: int, pub ioid: int }\n\nimpl View for Quota {\n    type V = QuotaView;\n    closed spec fn view(&self) -> QuotaView {\n        QuotaView {\n            mem_4k: self.mem_4k as int,\n            mem_2m: self.mem_2m as int,\n            mem_1g: self.mem_1g as int,\n            pcid: self.pcid as int,\n            ioid: self.ioid as int,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All five fields are spec-meaningful resource counts/IDs and must participate in semantic equality; there are no opaque/ghost/pointer fields to drop. Each usize is lifted to Verus `int` so the view compares mathematical values rather than machine-width representations, which keeps equality robust to width-dependent encodings while preserving every dimension the spec constrains."
}
```
