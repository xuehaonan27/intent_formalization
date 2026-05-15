```json
{
  "viewed_type": "OpArgsView",
  "view_decl": "pub enum OpArgsView {\n    Map { base: usize, pte: <PTE as View>::V },\n    Unmap { base: usize },\n}\n\nimpl View for OpArgs {\n    type V = OpArgsView;\n    closed spec fn view(&self) -> OpArgsView {\n        match self {\n            OpArgs::Map { base, pte } => OpArgsView::Map { base: *base, pte: pte@ },\n            OpArgs::Unmap { base } => OpArgsView::Unmap { base: *base },\n        }\n    }\n}",
  "depends_on_views_of": ["PTE"],
  "rationale": "OpArgs is a tagged union of two page-table operations; both variants carry a spec-relevant usize base address, and Map additionally carries a PTE projected through its own View. Mirroring the variant structure in OpArgsView preserves the discriminant so the checker compares both the operation tag and its semantically meaningful payload."
}
```
