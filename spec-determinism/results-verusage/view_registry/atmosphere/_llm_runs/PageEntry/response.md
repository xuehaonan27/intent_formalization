```json
{
  "viewed_type": "PageEntryView",
  "view_decl": "pub struct PageEntryView { pub addr: usize, pub perm: PageEntryPerm }\n\nimpl View for PageEntry {\n    type V = PageEntryView;\n    closed spec fn view(&self) -> PageEntryView {\n        PageEntryView { addr: self.addr, perm: self.perm }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "PAddr is a type alias for the primitive usize, so addr is taken structurally without `@`. PageEntryPerm is an uncovered leaf type with no resolved view, so we keep it as-is (treating its structural equality as semantic, analogous to the PageState case in the example). Both public fields are retained because they are the only spec-observable dimensions of a page-table entry."
}
```
