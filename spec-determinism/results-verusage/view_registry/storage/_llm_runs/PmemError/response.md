```json
{
  "viewed_type": "PmemError",
  "view_decl": "impl View for PmemError {\n    type V = PmemError;\n    closed spec fn view(&self) -> PmemError {\n        *self\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "PmemError is a C-like enum of unit-only variants with no payloads, so structural equality is already semantic. We project to itself (identity view), returning *self in the spec function."
}
```
