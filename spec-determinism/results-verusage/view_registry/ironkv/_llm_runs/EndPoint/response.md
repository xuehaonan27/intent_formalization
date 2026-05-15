```json
{
  "viewed_type": "Seq<u8>",
  "view_decl": "impl View for EndPoint {\n    type V = Seq<u8>;\n    closed spec fn view(&self) -> Seq<u8> {\n        self.id@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "EndPoint is a thin wrapper around a byte vector that uniquely identifies a network endpoint (e.g. IP+port bytes). Byte order is significant for identity, so the spec-meaningful projection is Seq<u8>, obtained via Vec's standard view. There are no other fields to keep or drop."
}
```
