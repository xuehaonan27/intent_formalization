```json
{
  "viewed_type": "AbstractParametersView",
  "view_decl": "pub struct AbstractParametersView { pub max_seqno: nat, pub max_delegations: nat }\n\nimpl View for AbstractParameters {\n    type V = AbstractParametersView;\n    closed spec fn view(&self) -> AbstractParametersView {\n        AbstractParametersView { max_seqno: self.max_seqno, max_delegations: self.max_delegations }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are spec-level `nat` capacity bounds (max sequence number and max delegations) that the spec directly constrains, so the view is an identity-style projection preserving both values. `nat` is a Verus spec primitive whose structural equality is already semantic, so no `@` is applied."
}
```
