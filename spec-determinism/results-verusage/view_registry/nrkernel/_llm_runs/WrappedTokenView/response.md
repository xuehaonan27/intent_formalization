```json
{
  "viewed_type": "WrappedTokenView",
  "view_decl": "impl View for WrappedTokenView {\n    type V = WrappedTokenView;\n    closed spec fn view(&self) -> WrappedTokenView {\n        WrappedTokenView {\n            orig_st: self.orig_st,\n            args: self.args,\n            change_made: self.change_made,\n            regions: self.regions,\n            pt_mem: self.pt_mem,\n            result: self.result,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All fields are spec-meaningful: there are no raw pointers, no Ghost/Tracked wrappers, and no obviously-opaque allocator handles to drop. Because os::State, OpArgs, MemRegion, and crate::PTMem are uncovered leaf types with no View impl, we cannot recursively project them through `@`, so the view is the identity projection over WrappedTokenView's own fields (Map and Seq carry their identity-typed contents through unchanged)."
}
```
