```json
{
  "viewed_type": "AbstractConstantsView",
  "view_decl": "pub struct AbstractConstantsView {\n    pub root_identity: AbstractEndPoint,\n    pub host_ids: Seq<AbstractEndPoint>,\n    pub params: AbstractParameters,\n    pub me: AbstractEndPoint,\n}\n\nimpl View for AbstractConstants {\n    type V = AbstractConstantsView;\n    closed spec fn view(&self) -> AbstractConstantsView {\n        AbstractConstantsView {\n            root_identity: self.root_identity,\n            host_ids: self.host_ids,\n            params: self.params,\n            me: self.me,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All four fields are spec-meaningful protocol constants (cluster root identity, ordered host membership, abstract parameters, and this node's identity) and none are allocator-opaque or ghost-only, so they all stay in the view. AbstractEndPoint (just a Seq<u8>) and AbstractParameters (two nat fields) are leaf types whose structural equality is already semantic, so we project them by value rather than via `@`. host_ids is a Verus Seq (order is part of its spec identity), so we keep it as Seq<AbstractEndPoint>."
}
```
