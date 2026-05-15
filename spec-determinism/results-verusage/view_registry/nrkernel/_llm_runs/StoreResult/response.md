```json
{
  "viewed_type": "StoreResultView",
  "view_decl": "pub enum StoreResultView { Pagefault, Ok }\n\nimpl View for StoreResult {\n    type V = StoreResultView;\n    closed spec fn view(&self) -> StoreResultView {\n        match self {\n            StoreResult::Pagefault => StoreResultView::Pagefault,\n            StoreResult::Ok => StoreResultView::Ok,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "StoreResult is a tagged enum of two unit variants with no payload, so the only spec-meaningful dimension is which variant is selected. We project to a parallel StoreResultView enum (declared alongside the impl) so the checker compares variant tags, which is exactly the intended semantic equality."
}
```
