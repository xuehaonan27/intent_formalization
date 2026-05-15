```json
{
  "viewed_type": "HeapId",
  "view_decl": "impl View for HeapId {\n    type V = HeapId;\n    closed spec fn view(&self) -> HeapId {\n        *self\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "HeapId is a ghost struct that already serves as an abstract identifier; all three fields (id, provenance, uniq) are the spec-meaningful coordinates the verifier uses to distinguish heaps, so the view is the identity projection. There are no raw pointers or allocator handles to omit, and since Provenance has no resolved view we keep it as-is, making structural equality coincide with semantic equality for HeapId."
}
```
