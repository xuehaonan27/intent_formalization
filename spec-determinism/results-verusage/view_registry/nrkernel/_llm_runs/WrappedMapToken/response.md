```json
{
  "viewed_type": "WrappedMapTokenView",
  "view_decl": "pub struct WrappedMapTokenView {\n    pub tok: <crate::os_code_vc::Token as View>::V,\n    pub change_made: bool,\n    pub orig_st: <os::State as View>::V,\n}\n\nimpl View for WrappedMapToken {\n    type V = WrappedMapTokenView;\n    closed spec fn view(&self) -> WrappedMapTokenView {\n        WrappedMapTokenView {\n            tok: self.tok@,\n            change_made: self.change_made,\n            orig_st: self.orig_st@,\n        }\n    }\n}",
  "depends_on_views_of": ["Token", "State"],
  "rationale": "All three fields carry spec-meaningful content: the tracked Token holds the live OS-transition state the operation manipulates, change_made tracks whether a mutating step has occurred, and orig_st pins the pre-state used in ensures clauses. Token and os::State are uncovered leaves, so we project them via `@` and list them as dependencies for future View synthesis rather than falling back to structural identity. The primitive bool is kept verbatim."
}
```
