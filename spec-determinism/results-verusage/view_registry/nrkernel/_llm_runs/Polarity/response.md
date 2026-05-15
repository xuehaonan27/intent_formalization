```json
{
  "viewed_type": "PolarityView",
  "view_decl": "pub enum PolarityView {\n    Mapping,\n    Unmapping,\n}\n\nimpl View for Polarity {\n    type V = PolarityView;\n    closed spec fn view(&self) -> PolarityView {\n        match self {\n            Polarity::Mapping => PolarityView::Mapping,\n            Polarity::Unmapping => PolarityView::Unmapping,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Polarity is a unit-variant enum with no payload, so semantic equality coincides with variant identity. The view is a parallel tagged-union (PolarityView) that mirrors the two variants 1:1; structural equality on PolarityView is exactly the intended semantic equality."
}
```
