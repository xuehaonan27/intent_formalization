```json
{
  "viewed_type": "AckStateView<MT>",
  "view_decl": "pub struct AckStateView<MT> {\n    pub num_packets_acked: nat,\n    pub un_acked: Seq<SingleMessage<MT>>,\n}\n\nimpl<MT> View for AckState<MT> {\n    type V = AckStateView<MT>;\n    closed spec fn view(&self) -> AckStateView<MT> {\n        AckStateView {\n            num_packets_acked: self.num_packets_acked,\n            un_acked: self.un_acked@,\n        }\n    }\n}",
  "depends_on_views_of": ["AckList"],
  "rationale": "Both fields are spec-meaningful: num_packets_acked is a nat (already its own view) and un_acked projects through AckList's view to Seq<SingleMessage<MT>>. No ghost/raw-pointer fields to drop."
}
```
