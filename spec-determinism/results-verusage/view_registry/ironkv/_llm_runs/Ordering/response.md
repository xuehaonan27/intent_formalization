```json
{
  "viewed_type": "int",
  "view_decl": "impl View for Ordering {\n    type V = int;\n    closed spec fn view(&self) -> int {\n        match self {\n            Ordering::Less => 0,\n            Ordering::Equal => 1,\n            Ordering::Greater => 2,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Ordering is a payload-free enum whose only semantic content is which of the three variants it is, so we project to a stable int tag (0/1/2). Using int avoids needing the original enum to derive Eq/PartialEq and gives the checker a primitive type with built-in semantic equality."
}
```
