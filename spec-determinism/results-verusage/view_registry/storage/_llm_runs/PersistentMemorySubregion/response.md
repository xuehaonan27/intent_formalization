```json
{
  "viewed_type": "PersistentMemorySubregionView",
  "view_decl": "pub struct PersistentMemorySubregionView { pub start_: u64, pub len_: nat }\n\nimpl View for PersistentMemorySubregion {\n    type V = PersistentMemorySubregionView;\n    closed spec fn view(&self) -> PersistentMemorySubregionView {\n        PersistentMemorySubregionView { start_: self.start_, len_: self.len_@ }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields define the subregion semantically: start_ is the absolute offset and len_ is the length, so neither can be dropped. u64 is a primitive and keeps its identity view, while Ghost<nat> is unwrapped with a single `@` to surface the underlying spec-level `nat` (a Verus spec primitive whose value is its own view, so no second `@` is applied)."
}
```
