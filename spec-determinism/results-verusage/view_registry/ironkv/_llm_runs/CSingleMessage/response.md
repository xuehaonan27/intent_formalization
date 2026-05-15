```json
{
  "viewed_type": "CSingleMessageView",
  "view_decl": "pub enum CSingleMessageView {\n    Message { seqno: u64, dst: <EndPoint as View>::V, m: <CMessage as View>::V },\n    Ack { ack_seqno: u64 },\n    InvalidMessage,\n}\n\nimpl View for CSingleMessage {\n    type V = CSingleMessageView;\n    closed spec fn view(&self) -> CSingleMessageView {\n        match self {\n            CSingleMessage::Message { seqno, dst, m } => CSingleMessageView::Message { seqno: *seqno, dst: dst@, m: m@ },\n            CSingleMessage::Ack { ack_seqno } => CSingleMessageView::Ack { ack_seqno: *ack_seqno },\n            CSingleMessage::InvalidMessage => CSingleMessageView::InvalidMessage,\n        }\n    }\n}",
  "depends_on_views_of": [
    "EndPoint",
    "CMessage"
  ],
  "rationale": "CSingleMessage is a three-variant tagged union from the IronKV reliable-transport layer; every variant payload is spec-meaningful (sequence numbers govern delivery ordering, the destination endpoint and inner CMessage define the packet's semantic content), so the projection is a parallel CSingleMessageView enum that keeps all variants and fields. The two uncovered user-type fields (EndPoint, CMessage) are projected through their (to-be-synthesised) View impls via `@` and flagged in depends_on_views_of so a future pass can refine them recursively, following the same convention used in CSingleDelivery and CAckState. The u64 sequence numbers are primitive and carried by identity; InvalidMessage is a payload-less marker variant."
}
```
