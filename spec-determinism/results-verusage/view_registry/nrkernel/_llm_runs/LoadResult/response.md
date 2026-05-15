```json
{
  "viewed_type": "LoadResultView",
  "view_decl": "pub enum LoadResultView {\n    Pagefault,\n    Value(Seq<u8>),\n}\n\nimpl View for LoadResult {\n    type V = LoadResultView;\n    closed spec fn view(&self) -> LoadResultView {\n        match self {\n            LoadResult::Pagefault => LoadResultView::Pagefault,\n            LoadResult::Value(s) => LoadResultView::Value(s@),\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "LoadResult is a simple tagged union with no opaque or ghost fields, so we mirror it as LoadResultView. The Pagefault variant is unit; the Value variant carries a Seq<u8> whose element type is a primitive, and Seq's identity view preserves order and contents — exactly what the spec compares."
}
```
