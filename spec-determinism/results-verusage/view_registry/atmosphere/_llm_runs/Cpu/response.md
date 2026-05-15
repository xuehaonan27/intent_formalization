```json
{
  "viewed_type": "CpuView",
  "view_decl": "pub struct CpuView {\n    pub owning_container: ContainerPtr,\n    pub active: bool,\n    pub current_thread: Option<ThreadPtr>,\n}\n\nimpl View for Cpu {\n    type V = CpuView;\n    closed spec fn view(&self) -> CpuView {\n        CpuView {\n            owning_container: self.owning_container,\n            active: self.active,\n            current_thread: self.current_thread,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All three fields are spec-meaningful (which container owns the CPU, whether it is active, and which thread it currently runs). ContainerPtr and ThreadPtr are aliases to the primitive usize, and bool is also primitive, so structural equality on these is already semantic — the view is essentially an identity projection wrapped in a named CpuView for clarity, with no `@` applied to primitive fields."
}
```
