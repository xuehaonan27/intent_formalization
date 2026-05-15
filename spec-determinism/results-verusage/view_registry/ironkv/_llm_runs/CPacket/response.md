```json
{
  "viewed_type": "CPacketView",
  "view_decl": "pub struct CPacketView { pub dst: <EndPoint as View>::V, pub src: <EndPoint as View>::V, pub msg: <CSingleMessage as View>::V }\n\nimpl View for CPacket {\n    type V = CPacketView;\n    closed spec fn view(&self) -> CPacketView {\n        CPacketView { dst: self.dst@, src: self.src@, msg: self.msg@ }\n    }\n}",
  "depends_on_views_of": ["EndPoint", "CSingleMessage"],
  "rationale": "CPacket is a plain aggregate of dst/src endpoints and the message payload — all three are spec-meaningful (network specs routinely inspect sender, receiver, and message). Each field is projected through its own View impl so semantic equality (e.g., endpoint wire identity, message content modulo representation) is honoured rather than relying on structural `==`."
}
```
