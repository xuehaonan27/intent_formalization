```json
{
  "viewed_type": "()",
  "view_decl": "impl View for Token {\n    type V = ();\n    closed spec fn view(&self) -> () { () }\n}",
  "depends_on_views_of": [],
  "rationale": "Token is a tracked unit struct with no fields, so it carries no spec-observable state; project to `()` so any two Tokens compare semantically equal under view equality."
}
```
