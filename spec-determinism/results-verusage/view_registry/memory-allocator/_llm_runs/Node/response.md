```json
{
  "viewed_type": "()",
  "view_decl": "impl View for Node {\n    type V = ();\n    closed spec fn view(&self) -> () {\n        ()\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Node's only field is the raw pointer `ptr: *mut Node`, which is allocator-opaque and must be omitted per the rules for `*mut T` fields. With no spec-meaningful fields remaining, the abstract view collapses to the unit type `()`, so any two Nodes are semantically equal under view-equality."
}
```
