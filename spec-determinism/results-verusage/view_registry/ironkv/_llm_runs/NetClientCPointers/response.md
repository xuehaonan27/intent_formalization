```json
{
  "viewed_type": "()",
  "view_decl": "impl View for NetClientCPointers {\n    type V = ();\n    closed spec fn view(&self) -> () {\n        ()\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All three fields are extern \"C\" function pointers binding to opaque C-side callbacks (get_time, receive, send); function pointers are allocator/runtime-opaque and the spec never inspects them, so the abstract view collapses to unit."
}
```
