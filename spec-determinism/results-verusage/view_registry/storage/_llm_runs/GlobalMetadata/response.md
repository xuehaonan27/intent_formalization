```json
{
  "viewed_type": "GlobalMetadataView",
  "view_decl": "pub struct GlobalMetadataView {\n    pub version_number: u64,\n    pub length_of_region_metadata: u64,\n    pub program_guid: u128,\n}\n\nimpl View for GlobalMetadata {\n    type V = GlobalMetadataView;\n    closed spec fn view(&self) -> GlobalMetadataView {\n        GlobalMetadataView {\n            version_number: self.version_number,\n            length_of_region_metadata: self.length_of_region_metadata,\n            program_guid: self.program_guid,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All fields are primitive integers (u64, u128) with no allocator handles, raw pointers, or ghost wrappers, and each is a spec-meaningful identifier/size that the determinism checker should compare. The view therefore mirrors the struct field-for-field using identity projections on primitives (no `@` since primitives are their own view)."
}
```
