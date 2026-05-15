```json
{
  "viewed_type": "PTDirView",
  "view_decl": "pub struct PTDirView {\n    pub region: MemRegion,\n    pub entries: Seq<Option<PTDirView>>,\n    pub used_regions: Set<MemRegion>,\n}\n\nimpl View for PTDir {\n    type V = PTDirView;\n    closed spec fn view(&self) -> PTDirView {\n        PTDirView {\n            region: self.region,\n            entries: self.entries@,\n            used_regions: self.used_regions,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All three fields are spec-meaningful for a page-table directory: `region` is the backing physical memory, `entries` are the child sub-directories, and `used_regions` is the reflexive-transitive closure invariant referenced by the spec. The self-referential `Seq<Option<PTDir>>` is projected recursively via `self.entries@`, which composes Seq/Option's View impls with PTDir's own (this) View impl. `MemRegion` is an uncovered leaf type with no view, so it is passed through structurally inside both `region` and `Set<MemRegion>`."
}
```
