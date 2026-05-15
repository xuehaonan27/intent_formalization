```json
{
  "viewed_type": "RegionMetadataView",
  "view_decl": "pub struct RegionMetadataView { pub region_size: u64, pub log_area_len: u64, pub log_id: u128 }\n\nimpl View for RegionMetadata {\n    type V = RegionMetadataView;\n    closed spec fn view(&self) -> RegionMetadataView {\n        RegionMetadataView { region_size: self.region_size, log_area_len: self.log_area_len, log_id: self.log_id }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All three fields are primitive integers (u64, u128) that identify the persistent-memory region's size, log-area length, and log id — every one is spec-meaningful and none is allocator-opaque or ghost-only. The view mirrors the struct field-for-field, using the primitives directly (no `@` on primitives)."
}
```
