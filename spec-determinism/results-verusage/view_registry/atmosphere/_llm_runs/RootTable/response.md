```json
{
  "viewed_type": "RootTableView",
  "view_decl": "pub struct RootTableView {\n    pub root: Seq<usize>,\n    pub seq_ar: Seq<Seq<Seq<Option<(IOid, usize)>>>>,\n    pub deviecs: Seq<DeviceTable>,\n}\n\nimpl View for RootTable {\n    type V = RootTableView;\n    closed spec fn view(&self) -> RootTableView {\n        RootTableView {\n            root: self.root@,\n            seq_ar: self.seq_ar@,\n            deviecs: self.deviecs@,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All three fields carry spec-meaningful content: `root` is an indexed L4-style table of usize entries (project the fixed-size array to Seq<usize> via its built-in array view), `seq_ar` is the ghost mirror of the per-device IOMMU mapping whose inner type is already a pure spec composition over the primitive alias IOid=usize and usize (so a single `@` unwraps the Ghost — no further element-view needed since Seq/Option/tuple of primitives are identity), and `deviecs` is the array of device tables (project to Seq<DeviceTable>; DeviceTable is an uncovered leaf so its elements appear at identity)."
}
```
