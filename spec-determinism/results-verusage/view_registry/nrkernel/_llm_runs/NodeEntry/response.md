```json
{
  "viewed_type": "NodeEntryView",
  "view_decl": "pub enum NodeEntryView {\n    Directory(<Directory as View>::V),\n    Page(<PTE as View>::V),\n    Invalid,\n}\n\nimpl View for NodeEntry {\n    type V = NodeEntryView;\n    closed spec fn view(&self) -> NodeEntryView {\n        match self {\n            NodeEntry::Directory(d) => NodeEntryView::Directory(d@),\n            NodeEntry::Page(p) => NodeEntryView::Page(p@),\n            NodeEntry::Invalid => NodeEntryView::Invalid,\n        }\n    }\n}",
  "depends_on_views_of": ["Directory", "PTE"],
  "rationale": "NodeEntry is a tagged union of three cases; we mirror that with a NodeEntryView enum whose payloads are the abstract views of the carried types (Directory and PTE). Each non-unit variant projects its payload via `@` so equality reduces to semantic equality on the dependency views (to be synthesized recursively), while the payload-free `Invalid` variant remains a unit constructor."
}
```
