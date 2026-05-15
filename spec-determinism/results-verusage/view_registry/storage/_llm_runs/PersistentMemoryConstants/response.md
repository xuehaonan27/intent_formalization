```json
{
  "viewed_type": "bool",
  "view_decl": "impl View for PersistentMemoryConstants {\n    type V = bool;\n    closed spec fn view(&self) -> bool {\n        self.impervious_to_corruption\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "The struct has a single primitive bool field, impervious_to_corruption, which is exactly the spec-meaningful dimension. Project directly to that bool (primitives view to themselves), so semantic equality reduces to comparing the corruption-immunity flag."
}
```
