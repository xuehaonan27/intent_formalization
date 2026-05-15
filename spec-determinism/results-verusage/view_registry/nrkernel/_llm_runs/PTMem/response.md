```json
{
  "viewed_type": "PTMemView",
  "view_decl": "pub struct PTMemView { pub mem: Map<usize, usize>, pub pml4: usize }\n\nimpl View for PTMem {\n    type V = PTMemView;\n    closed spec fn view(&self) -> PTMemView {\n        PTMemView { mem: self.mem, pml4: self.pml4 }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are spec-meaningful and already in semantic form: `mem` is a Map keyed and valued by primitives (usize), and `pml4` is the primitive root page-table address. There are no allocator handles, raw pointers, or ghost wrappers to project away, so the view is an identity projection wrapped in a named PTMemView struct."
}
```
