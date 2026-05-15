```json
{
  "viewed_type": "Seq<PersistentMemoryRegionView>",
  "view_decl": "impl View for PersistentMemoryRegionsView {\n    type V = Seq<PersistentMemoryRegionView>;\n    closed spec fn view(&self) -> Self::V {\n        self.regions\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "PersistentMemoryRegionsView is a single-field wrapper whose only spec-meaningful content is the ordered `regions` sequence, so collapsing the view directly to that `Seq` makes semantic equality coincide with sequence equality. PersistentMemoryRegionView is an uncovered leaf, so it is treated with an identity view and kept as the Seq's element type without recursive `@` projection."
}
```
