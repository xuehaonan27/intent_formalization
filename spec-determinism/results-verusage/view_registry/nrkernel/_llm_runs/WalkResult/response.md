```json
{
  "viewed_type": "WalkResultView",
  "view_decl": "pub enum WalkResultView {\n    Valid { vbase: usize, pte: <PTE as View>::V },\n    Invalid { vaddr: usize },\n}\n\nimpl View for WalkResult {\n    type V = WalkResultView;\n    closed spec fn view(&self) -> WalkResultView {\n        match self {\n            WalkResult::Valid { vbase, pte } => WalkResultView::Valid { vbase: *vbase, pte: pte@ },\n            WalkResult::Invalid { vaddr } => WalkResultView::Invalid { vaddr: *vaddr },\n        }\n    }\n}",
  "depends_on_views_of": ["PTE"],
  "rationale": "WalkResult is a tagged union, so we mirror its shape with a parallel WalkResultView enum and dispatch via match. vbase and vaddr are usize primitives kept as values; pte is a user type projected to its semantic view via pte@ so equality reflects PTE's spec-meaningful dimensions rather than structural bits."
}
```
