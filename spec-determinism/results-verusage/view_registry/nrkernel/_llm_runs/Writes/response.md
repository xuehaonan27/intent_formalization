```json
{
  "viewed_type": "WritesView",
  "view_decl": "pub struct WritesView { pub core: Core, pub tso: Set<usize>, pub nonpos: Set<Core> }\n\nimpl View for Writes {\n    type V = WritesView;\n    closed spec fn view(&self) -> WritesView {\n        WritesView { core: self.core, tso: self.tso, nonpos: self.nonpos }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All three fields are spec-meaningful: `core` names the current writer, `tso` records pending TSO addresses, and `nonpos` records cores with non-positional staleness. `Core` is an uncovered leaf (use it directly, no `@`) and `usize` is primitive, while `Set` already has semantic equality, so the projection is an identity-shaped struct that pins exactly these three dimensions."
}
```
