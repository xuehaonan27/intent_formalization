```json
{
  "viewed_type": "AppRequestView",
  "view_decl": "pub enum AppRequestView {\n    AppGetRequest { seqno: nat, key: AbstractKey },\n    AppSetRequest { seqno: nat, key: AbstractKey, ov: Option<Seq<u8>> },\n}\n\nimpl View for AppRequest {\n    type V = AppRequestView;\n    closed spec fn view(&self) -> AppRequestView {\n        match self {\n            AppRequest::AppGetRequest { seqno, key } =>\n                AppRequestView::AppGetRequest { seqno: *seqno, key: *key },\n            AppRequest::AppSetRequest { seqno, key, ov } =>\n                AppRequestView::AppSetRequest { seqno: *seqno, key: *key, ov: ov@ },\n        }\n    }\n}",
  "depends_on_views_of": ["AbstractValue"],
  "rationale": "Project the enum to a parallel tagged-union view. seqno (nat) and key (AbstractKey, an uncovered leaf) are preserved structurally because their identity equality is what the spec inspects. ov projects through Option<AbstractValue>'s view, yielding Option<Seq<u8>> per AbstractValue's L1/L2 alias."
}
```
