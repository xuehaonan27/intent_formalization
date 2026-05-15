```json
{
  "viewed_type": "LIoOpView<IdType, MessageType>",
  "view_decl": "pub enum LIoOpView<IdType, MessageType> {\n    Send { s: LPacket<IdType, MessageType> },\n    Receive { r: LPacket<IdType, MessageType> },\n    TimeoutReceive {},\n    ReadClock { t: int },\n}\n\nimpl<IdType, MessageType> View for LIoOp<IdType, MessageType> {\n    type V = LIoOpView<IdType, MessageType>;\n    closed spec fn view(&self) -> Self::V {\n        match self {\n            LIoOp::Send { s } => LIoOpView::Send { s: *s },\n            LIoOp::Receive { r } => LIoOpView::Receive { r: *r },\n            LIoOp::TimeoutReceive {} => LIoOpView::TimeoutReceive {},\n            LIoOp::ReadClock { t } => LIoOpView::ReadClock { t: *t },\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "LIoOp's variants only carry spec-meaningful payloads (an LPacket or an int clock value), so the view mirrors the tagged-union shape one-to-one. LPacket is an uncovered leaf type with no registered View impl, so it is propagated by identity (no `@`); int is a Verus spec primitive used directly; TimeoutReceive carries no fields."
}
```
