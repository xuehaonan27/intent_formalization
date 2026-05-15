```json
{
  "viewed_type": "SingleMessageView<MT>",
  "view_decl": "pub enum SingleMessageView<MT: View> {\n    Message { seqno: nat, dst: AbstractEndPoint, m: MT::V },\n    Ack { ack_seqno: nat },\n    InvalidMessage {},\n}\n\nimpl<MT: View> View for SingleMessage<MT> {\n    type V = SingleMessageView<MT>;\n    closed spec fn view(&self) -> SingleMessageView<MT> {\n        match self {\n            SingleMessage::Message { seqno, dst, m } => SingleMessageView::Message { seqno: *seqno, dst: *dst, m: m@ },\n            SingleMessage::Ack { ack_seqno } => SingleMessageView::Ack { ack_seqno: *ack_seqno },\n            SingleMessage::InvalidMessage {} => SingleMessageView::InvalidMessage {},\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Mirror the variant structure as a tagged view enum: the spec-meaningful `nat` counters (`seqno`, `ack_seqno`) are primitives carried by value, `AbstractEndPoint` is a leaf with no resolved `View` impl so it is held structurally (its `==` is treated as semantic by the checker), and the generic payload `m: MT` is projected through `m@` under an `MT: View` bound on the impl so message bodies are compared by their abstract view rather than structurally. `InvalidMessage` is a unit variant with nothing to project."
}
```
