```json
{
  "viewed_type": "int",
  "view_decl": "impl View for Progress {\n    type V = int;\n    closed spec fn view(&self) -> int {\n        match self {\n            Progress::Unready => 0,\n            Progress::Ready => 1,\n            Progress::TokenWithdrawn => 2,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Progress is a C-like enum of three unit variants with no payload, so semantic equality collapses to variant-tag equality. Project each variant to a distinct int (0/1/2) so the determinism checker compares views with ==, avoiding any reliance on derived structural equality (Progress has no derives)."
}
```
