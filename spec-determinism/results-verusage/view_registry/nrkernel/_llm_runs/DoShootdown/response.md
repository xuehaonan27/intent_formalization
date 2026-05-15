```json
{
  "viewed_type": "DoShootdownView",
  "view_decl": "pub enum DoShootdownView {\n    Yes { vaddr: usize, size: usize },\n    No,\n}\n\nimpl View for DoShootdown {\n    type V = DoShootdownView;\n    closed spec fn view(&self) -> DoShootdownView {\n        match self {\n            DoShootdown::Yes { vaddr, size } => DoShootdownView::Yes { vaddr: *vaddr, size: *size },\n            DoShootdown::No => DoShootdownView::No,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both variants carry only primitive usize fields (vaddr, size) whose view is the value itself, and there are no raw pointers, allocator handles, or ghost wrappers to drop, so the view mirrors the source enum's tagged-union shape with the primitives passed through unchanged."
}
```
