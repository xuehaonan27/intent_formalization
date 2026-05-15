```json
{
  "viewed_type": "TokStateView",
  "view_decl": "pub enum TokStateView { Init, ProphecyMade, Validated, Spent }\n\nimpl View for TokState {\n    type V = TokStateView;\n    closed spec fn view(&self) -> TokStateView {\n        match self {\n            TokState::Init => TokStateView::Init,\n            TokState::ProphecyMade => TokStateView::ProphecyMade,\n            TokState::Validated => TokStateView::Validated,\n            TokState::Spent => TokStateView::Spent,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "TokState is an enum of unit variants with no payload, so structural variant equality already coincides with semantic equality. We mirror it into a parallel TokStateView enum and project each variant 1:1 so the determinism checker has an explicit identity-style view to compare against."
}
```
