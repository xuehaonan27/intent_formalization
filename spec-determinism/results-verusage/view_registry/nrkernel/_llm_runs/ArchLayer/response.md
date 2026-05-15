```json
{
  "viewed_type": "ArchLayerView",
  "view_decl": "pub struct ArchLayerView { pub entry_size: nat, pub num_entries: nat }\n\nimpl View for ArchLayer {\n    type V = ArchLayerView;\n    closed spec fn view(&self) -> ArchLayerView {\n        ArchLayerView { entry_size: self.entry_size, num_entries: self.num_entries }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are `nat` (a Verus primitive-like spec type) and are spec-meaningful: `entry_size` pins the address-space size mapped per entry and `num_entries` pins this layer's fan-out, so both must participate in semantic equality. There are no raw pointers, ghost wrappers, or allocator-opaque handles to drop, so the view simply re-exposes both fields verbatim (no `@` on `nat`)."
}
```
