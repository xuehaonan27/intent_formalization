```json
{
  "viewed_type": "Seq<u8>",
  "view_decl": "impl View for AbstractEndPoint {\n    type V = Seq<u8>;\n    closed spec fn view(&self) -> Seq<u8> {\n        self.id\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "AbstractEndPoint is a thin newtype around a byte-sequence identifier (e.g., an IP+port serialization). Its single field is the only spec-meaningful dimension, and ordering of the bytes matters for identity, so we project directly to Seq<u8>. u8 is primitive, so no recursive @ is applied."
}
```
