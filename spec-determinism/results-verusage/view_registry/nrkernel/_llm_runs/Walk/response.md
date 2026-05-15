```json
{
  "viewed_type": "WalkView",
  "view_decl": "pub struct WalkView {\n    pub vaddr: usize,\n    pub path: Seq<(usize, <GPDE as View>::V)>,\n    pub complete: bool,\n}\n\nimpl View for Walk {\n    type V = WalkView;\n    open spec fn view(&self) -> WalkView {\n        WalkView {\n            vaddr: self.vaddr,\n            path: self.path.map_values(|e: (usize, GPDE)| (e.0, e.1@)),\n            complete: self.complete,\n        }\n    }\n}",
  "depends_on_views_of": ["GPDE"],
  "rationale": "All three fields are spec-meaningful for a page-table walk: vaddr identifies the address being translated, path is the ordered sequence of (level-index, descriptor) pairs traversed so order matters and we keep it as Seq, and complete records termination. The inner GPDE is projected via its own view so equality on descriptors is semantic rather than structural; usize indices stay as identities."
}
```
