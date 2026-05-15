```json
{
  "viewed_type": "ReceiveResultView",
  "view_decl": "pub enum ReceiveResultView {\n    Fail,\n    Timeout,\n    Packet { cpacket: <CPacket as View>::V },\n}\n\nimpl View for ReceiveResult {\n    type V = ReceiveResultView;\n    closed spec fn view(&self) -> ReceiveResultView {\n        match self {\n            ReceiveResult::Fail => ReceiveResultView::Fail,\n            ReceiveResult::Timeout => ReceiveResultView::Timeout,\n            ReceiveResult::Packet { cpacket } => ReceiveResultView::Packet { cpacket: cpacket@ },\n        }\n    }\n}",
  "depends_on_views_of": ["CPacket"],
  "rationale": "ReceiveResult is a tagged sum: the spec uses the discriminant (`rr is Fail` / `is Timeout` / `is Packet`) and only ever inspects the payload through its abstract view (`rr.arrow_Packet_cpacket()@`). The projection therefore preserves the variant tag and forwards the `cpacket` field through `@`, so semantic equality is decided by `CPacket`'s view rather than by structural fields like marshalling buffers or socket-level identifiers."
}
```
