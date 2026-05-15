```json
{
  "viewed_type": "ParametersView",
  "view_decl": "pub struct ParametersView { pub max_seqno: u64, pub max_delegations: u64 }\n\nimpl View for Parameters {\n    type V = ParametersView;\n    closed spec fn view(&self) -> ParametersView {\n        ParametersView { max_seqno: self.max_seqno, max_delegations: self.max_delegations }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are u64 configuration parameters that the spec directly constrains (sequence-number and delegation bounds), so the view is an identity-style projection preserving both values. Primitives are their own view, so no `@` is applied."
}
```
