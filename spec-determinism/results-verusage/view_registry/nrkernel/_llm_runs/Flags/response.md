```json
{
  "viewed_type": "Flags",
  "view_decl": "impl View for Flags {\n    type V = Flags;\n    closed spec fn view(&self) -> Flags {\n        *self\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Flags is a Copy/Clone struct of three bool fields (is_writable, is_supervisor, disable_execute), each a permission bit the spec genuinely constrains. Since all fields are primitives and structural equality on bools is already semantic equality, the identity view (Self::V = Flags, view = *self) is the correct minimal projection — no fields to drop, no nested views to call."
}
```
