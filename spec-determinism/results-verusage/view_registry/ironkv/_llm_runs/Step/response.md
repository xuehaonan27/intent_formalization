```json
{
  "viewed_type": "Step",
  "view_decl": "impl View for Step {\n    type V = Step;\n    closed spec fn view(&self) -> Step {\n        *self\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Step is an enum of six unit variants with no payload, so structural equality is already semantic equality. The view is the identity projection: V = Step and view(&self) = *self."
}
```
