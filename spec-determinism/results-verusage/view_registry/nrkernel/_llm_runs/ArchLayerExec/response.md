```json
{
  "viewed_type": "ArchLayerExecView",
  "view_decl": "pub struct ArchLayerExecView { pub entry_size: usize, pub num_entries: usize }\n\nimpl View for ArchLayerExec {\n    type V = ArchLayerExecView;\n    closed spec fn view(&self) -> ArchLayerExecView {\n        ArchLayerExecView { entry_size: self.entry_size, num_entries: self.num_entries }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are primitive usize values describing the architectural layer's spec-meaningful dimensions (entry size and entry count); neither is an allocator handle, ghost index, or order-irrelevant collection, so the view preserves both fields verbatim and primitives carry their identity view."
}
```
