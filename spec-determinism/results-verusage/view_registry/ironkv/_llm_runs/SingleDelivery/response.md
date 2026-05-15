```json
{
  "viewed_type": "SingleDeliveryView<MT>",
  "view_decl": "pub struct SingleDeliveryView<MT> {\n    pub receive_state: Map<AbstractEndPoint, nat>,\n    pub send_state: Map<AbstractEndPoint, AckState<MT>>,\n}\n\nimpl<MT> View for SingleDelivery<MT> {\n    type V = SingleDeliveryView<MT>;\n    closed spec fn view(&self) -> SingleDeliveryView<MT> {\n        SingleDeliveryView {\n            receive_state: self.receive_state@,\n            send_state: self.send_state@,\n        }\n    }\n}",
  "depends_on_views_of": ["TombstoneTable", "SendState"],
  "rationale": "SingleDelivery is a plain pair of two map-typed sub-states with no opaque/raw/ghost fields, so the abstract view simply forwards each field through its already-resolved view: receive_state to Map<AbstractEndPoint, nat> (TombstoneTable's view) and send_state to Map<AbstractEndPoint, AckState<MT>> (SendState's view). The generic parameter MT is preserved verbatim so the projection composes for any message type."
}
```
