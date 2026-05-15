```json
{
  "viewed_type": "StateView",
  "view_decl": "pub enum StateView {\n    Receiving,\n    Sending,\n    Error,\n}\n\nimpl View for State {\n    type V = StateView;\n    closed spec fn view(&self) -> StateView {\n        match self {\n            State::Receiving => StateView::Receiving,\n            State::Sending => StateView::Sending,\n            State::Error => StateView::Error,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "State is a fieldless three-variant enum; its identity is the only spec-meaningful dimension. Since the type has no derives (notably no Copy), we mirror it as a parallel StateView enum and map each variant 1:1, giving an identity-like view whose structural equality coincides with semantic equality."
}
```
