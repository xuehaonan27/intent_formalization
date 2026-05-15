```json
{
  "viewed_type": "LogInfoView",
  "view_decl": "pub struct LogInfoView { pub log_area_len: u64, pub head: u128, pub head_log_area_offset: u64, pub log_length: u64, pub log_plus_pending_length: u64 }\n\nimpl View for LogInfo {\n    type V = LogInfoView;\n    closed spec fn view(&self) -> LogInfoView {\n        LogInfoView { log_area_len: self.log_area_len, head: self.head, head_log_area_offset: self.head_log_area_offset, log_length: self.log_length, log_plus_pending_length: self.log_plus_pending_length }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All five fields are primitive integer (u64/u128) geometry of the log: total area length, head position, head offset within the circular area, committed log length, and pending length. They are exactly the dimensions a spec constrains, so the view is an identity projection over the primitives with no fields to drop."
}
```
