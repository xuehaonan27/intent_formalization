```json
{
  "viewed_type": "PTEView",
  "view_decl": "pub struct PTEView {\n    pub frame: <MemRegion as View>::V,\n    pub flags: <Flags as View>::V,\n}\n\nimpl View for PTE {\n    type V = PTEView;\n    closed spec fn view(&self) -> PTEView {\n        PTEView { frame: self.frame@, flags: self.flags@ }\n    }\n}",
  "depends_on_views_of": ["MemRegion", "Flags"],
  "rationale": "Both fields of `PTE` are spec-meaningful: `frame` identifies the physical memory region the entry maps to, and `flags` carries the permission/attribute bits asserted by the page-table invariant; neither is allocator-opaque or ghost-only, so we keep both. Each is projected through its (recursively synthesized) `View` via `@` so equality on `PTEView` reduces to semantic equality on the abstract `MemRegion`/`Flags` views rather than their structural representations."
}
```
