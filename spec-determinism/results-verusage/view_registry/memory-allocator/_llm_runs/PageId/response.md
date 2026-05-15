```json
{
  "viewed_type": "PageIdView",
  "view_decl": "pub struct PageIdView { pub segment_id: SegmentId, pub idx: nat }\n\nimpl View for PageId {\n    type V = PageIdView;\n    closed spec fn view(&self) -> PageIdView {\n        PageIdView { segment_id: self.segment_id, idx: self.idx }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "PageId is a ghost identifier whose semantic identity is fully determined by both fields: segment_id selects the segment and idx selects the page within it. SegmentId is an uncovered leaf type, so we use it as an identity view (no `@`); idx is the Verus primitive `nat` and is used as its value."
}
```
