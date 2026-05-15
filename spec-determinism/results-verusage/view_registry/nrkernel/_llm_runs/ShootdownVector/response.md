```json
{
  "viewed_type": "ShootdownVectorView",
  "view_decl": "pub struct ShootdownVectorView { pub vaddr: nat, pub open_requests: Set<Core> }\n\nimpl View for ShootdownVector {\n    type V = ShootdownVectorView;\n    closed spec fn view(&self) -> ShootdownVectorView {\n        ShootdownVectorView { vaddr: self.vaddr, open_requests: self.open_requests }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are spec-meaningful and need no further abstraction: vaddr is a Verus `nat` (a spec-level primitive whose value is its own view), and open_requests is a Set<Core> whose semantic (unordered, extensional) equality is exactly what the checker wants. Core is a leaf type with no View impl, so it is kept as Core rather than Core@."
}
```
