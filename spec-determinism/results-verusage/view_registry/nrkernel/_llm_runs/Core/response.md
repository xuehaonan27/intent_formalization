```json
{
  "viewed_type": "CoreView",
  "view_decl": "pub struct CoreView { pub node_id: nat, pub core_id: nat }\n\nimpl View for Core {\n    type V = CoreView;\n    closed spec fn view(&self) -> CoreView {\n        CoreView { node_id: self.node_id, core_id: self.core_id }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Core is a simple identifier pair; both node_id and core_id are spec-meaningful (they jointly identify a hardware core in NR's per-core state). Both fields are nat primitives, so the view copies them directly without any @ projection."
}
```
