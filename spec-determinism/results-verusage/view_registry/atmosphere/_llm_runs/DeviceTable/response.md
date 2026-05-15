```json
{
  "viewed_type": "DeviceTableView",
  "view_decl": "pub struct DeviceTableView { pub ar: Seq<usize> }\n\nimpl View for DeviceTable {\n    type V = DeviceTableView;\n    closed spec fn view(&self) -> DeviceTableView {\n        DeviceTableView { ar: self.ar@ }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "DeviceTable has a single indexed array field ar: [usize; 512] whose position-to-value mapping is the spec-meaningful content (the device table is addressed by index). Project the fixed-size array via its built-in array view to Seq<usize> so equality is element-wise on the abstract sequence, not on backing storage representation."
}
```
