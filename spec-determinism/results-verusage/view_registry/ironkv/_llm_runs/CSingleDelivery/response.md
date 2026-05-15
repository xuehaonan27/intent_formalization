```json
{
  "viewed_type": "CSingleDeliveryView",
  "view_decl": "pub struct CSingleDeliveryView {\n    pub receive_state: <CTombstoneTable as View>::V,\n    pub send_state: <CSendState as View>::V,\n}\n\nimpl View for CSingleDelivery {\n    type V = CSingleDeliveryView;\n    closed spec fn view(&self) -> CSingleDeliveryView {\n        CSingleDeliveryView {\n            receive_state: self.receive_state@,\n            send_state: self.send_state@,\n        }\n    }\n}",
  "depends_on_views_of": ["CTombstoneTable", "CSendState"],
  "rationale": "CSingleDelivery is a plain product of two user-defined sub-state types with no raw pointers, ghost wrappers, or allocator handles to omit. Both fields carry spec-meaningful state (receive-side tombstones and send-side sequence numbers), so the view is a parallel product that projects each field through its own (to-be-synthesised) View impl via `@`."
}
```
