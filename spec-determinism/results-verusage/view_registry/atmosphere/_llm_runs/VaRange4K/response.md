```json
{
  "viewed_type": "VaRange4KView",
  "view_decl": "pub struct VaRange4KView { pub start: VAddr, pub len: usize, pub view: Seq<VAddr> }\n\nimpl View for VaRange4K {\n    type V = VaRange4KView;\n    closed spec fn view(&self) -> VaRange4KView {\n        VaRange4KView { start: self.start, len: self.len, view: self.view@ }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "VAddr is a primitive alias to usize, so start and len are kept as-is (no `@` on primitives). The Ghost<Seq<VAddr>> field is unwrapped with a single `@` to expose the underlying Seq<VAddr> that the spec actually constrains; no inner view recursion is needed because the element type bottoms out at a primitive."
}
```
