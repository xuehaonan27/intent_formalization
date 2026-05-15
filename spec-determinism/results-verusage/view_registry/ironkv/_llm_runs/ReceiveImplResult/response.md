```json
{
  "viewed_type": "ReceiveImplResultView",
  "view_decl": "pub enum ReceiveImplResultView {\n    FreshPacket { ack: <CPacket as View>::V },\n    DuplicatePacket { ack: <CPacket as View>::V },\n    AckOrInvalid,\n}\n\nimpl View for ReceiveImplResult {\n    type V = ReceiveImplResultView;\n    closed spec fn view(&self) -> ReceiveImplResultView {\n        match self {\n            ReceiveImplResult::FreshPacket { ack } => ReceiveImplResultView::FreshPacket { ack: ack@ },\n            ReceiveImplResult::DuplicatePacket { ack } => ReceiveImplResultView::DuplicatePacket { ack: ack@ },\n            ReceiveImplResult::AckOrInvalid => ReceiveImplResultView::AckOrInvalid,\n        }\n    }\n}",
  "depends_on_views_of": ["CPacket"],
  "rationale": "ReceiveImplResult is a tagged union with two payload-carrying variants (FreshPacket, DuplicatePacket) each wrapping a CPacket, plus a payload-less AckOrInvalid. The view mirrors the variant structure as a parallel enum, projecting the CPacket payload through its own View (synthesised recursively via depends_on_views_of) so allocator-opaque or ghost details inside CPacket don't leak into structural comparison, while the unit variant maps to itself."
}
```
