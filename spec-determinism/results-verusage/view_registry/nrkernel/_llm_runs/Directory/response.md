```json
{
  "viewed_type": "DirectoryView",
  "view_decl": "pub struct DirectoryView {\n    pub entries: Seq<<NodeEntry as View>::V>,\n    pub layer: nat,\n    pub base_vaddr: nat,\n    pub arch: <Arch as View>::V,\n}\n\nimpl View for Directory {\n    type V = DirectoryView;\n    closed spec fn view(&self) -> Self::V {\n        DirectoryView {\n            entries: self.entries.map_values(|e: NodeEntry| e@),\n            layer: self.layer,\n            base_vaddr: self.base_vaddr,\n            arch: self.arch@,\n        }\n    }\n}",
  "depends_on_views_of": ["NodeEntry", "Arch"],
  "rationale": "Directory models a page-table node, and all four fields are spec-meaningful: entries are an ordered Seq indexed by virtual-address slot (so we keep Seq, not Set/Multiset, and lift each NodeEntry through its view), layer and base_vaddr are nat primitives copied as-is, and arch is projected through Arch's view so semantic equality of the architecture descriptor is delegated to its own view. No allocator handles or ghost-only fields exist to drop."
}
```
