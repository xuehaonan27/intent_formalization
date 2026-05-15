```json
{
  "viewed_type": "NetcReceiveResultView",
  "view_decl": "pub enum NetcReceiveResultView {\n    Received { sender: EndPoint, message: Seq<u8> },\n    TimedOut,\n    Error,\n}\n\nimpl View for NetcReceiveResult {\n    type V = NetcReceiveResultView;\n    closed spec fn view(&self) -> NetcReceiveResultView {\n        match self {\n            NetcReceiveResult::Received { sender, message } =>\n                NetcReceiveResultView::Received { sender: *sender, message: message@ },\n            NetcReceiveResult::TimedOut => NetcReceiveResultView::TimedOut,\n            NetcReceiveResult::Error => NetcReceiveResultView::Error,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Tagged-union view mirroring the original variants. EndPoint is uncovered (kind=leaf) so it is projected at identity; the message Vec<u8> is a serialized network payload whose byte order is semantically meaningful, so it views to Seq<u8>. TimedOut and Error carry no payload and map to themselves."
}
```
