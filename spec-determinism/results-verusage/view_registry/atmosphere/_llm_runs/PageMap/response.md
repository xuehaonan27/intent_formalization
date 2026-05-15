```json
{
  "viewed_type": "PageMapView",
  "view_decl": "pub struct PageMapView { pub ar: Array<usize, 512>, pub spec_seq: Seq<PageEntry> }\n\nimpl View for PageMap {\n    type V = PageMapView;\n    closed spec fn view(&self) -> PageMapView {\n        PageMapView { ar: self.ar, spec_seq: self.spec_seq@ }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are spec-meaningful: `ar` holds the 512 raw page-table entry words (every bit is hardware-observable) and `spec_seq` is the ghost interpretation as a sequence of PageEntry. Array<usize,512> and PageEntry have no View impl (uncovered leaves), so we use them as-is — only the Ghost<...> wrapper around spec_seq is unwrapped with a single `@`. There are no raw pointers or allocator-opaque fields to drop."
}
```
