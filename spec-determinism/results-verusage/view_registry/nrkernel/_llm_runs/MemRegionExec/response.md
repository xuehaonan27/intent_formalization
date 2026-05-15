```json
{
  "viewed_type": "MemRegionExecView",
  "view_decl": "pub struct MemRegionExecView { pub base: usize, pub size: usize }\n\nimpl View for MemRegionExec {\n    type V = MemRegionExecView;\n    closed spec fn view(&self) -> MemRegionExecView {\n        MemRegionExecView { base: self.base, size: self.size }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields (base, size) are primitive usize values that describe the memory region's address and extent — these are exactly the spec-meaningful dimensions that ensures clauses constrain. Primitives are their own view, so the projection is the identity-shaped MemRegionExecView struct."
}
```
