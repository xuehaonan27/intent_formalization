```json
{
  "viewed_type": "PacketView",
  "view_decl": "pub struct PacketView { pub dst: AbstractEndPoint@, pub src: AbstractEndPoint@, pub msg: PMsg@ }\n\nimpl View for Packet {\n    type V = PacketView;\n    closed spec fn view(&self) -> PacketView {\n        PacketView { dst: self.dst@, src: self.src@, msg: self.msg@ }\n    }\n}",
  "depends_on_views_of": ["AbstractEndPoint", "PMsg"],
  "rationale": "Packet is a plain three-field aggregation; all of dst, src, and msg are user-defined types that the spec inspects semantically, so we keep every field and delegate each one to its own (to-be-synthesised) view via @. No allocator-opaque or ghost-only fields to drop."
}
```
