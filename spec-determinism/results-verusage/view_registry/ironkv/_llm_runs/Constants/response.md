```json
{
  "viewed_type": "ConstantsView",
  "view_decl": "pub struct ConstantsView {\n    pub root_identity: EndPoint,\n    pub host_ids: Seq<EndPoint>,\n    pub params: Parameters,\n    pub me: EndPoint,\n}\n\nimpl View for Constants {\n    type V = ConstantsView;\n    closed spec fn view(&self) -> ConstantsView {\n        ConstantsView {\n            root_identity: self.root_identity,\n            host_ids: self.host_ids@,\n            params: self.params,\n            me: self.me,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "EndPoint and Parameters are uncovered leaf types, so we keep them at identity (structural equality). The Vec<EndPoint> host_ids projects to Seq<EndPoint> because in the IronRSL/IronKV configuration the position of each host in the list defines its replica index and is referenced by spec predicates that index into the list, so order is semantically significant."
}
```
