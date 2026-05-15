```json
{
  "viewed_type": "Seq<<ArchLayer as View>::V>",
  "view_decl": "impl View for Arch {\n    type V = Seq<<ArchLayer as View>::V>;\n    closed spec fn view(&self) -> Self::V {\n        self.layers.map_values(|l: ArchLayer| l@)\n    }\n}",
  "depends_on_views_of": ["ArchLayer"],
  "rationale": "Arch is a ghost struct whose only field is an ordered Seq<ArchLayer> describing successive paging levels (512G/1G/2M/4K) — the position of each layer encodes its meaning, so order is spec-significant and we keep a Seq rather than a Set. Each ArchLayer is projected through its own view (.view()) so semantic equality of layers is delegated to ArchLayer's (future) view; we collapse the wrapper struct since Arch has a single field, making the view just the lifted sequence."
}
```
