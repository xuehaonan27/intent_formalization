```json
{
  "viewed_type": "PersistentMemoryRegionView",
  "view_decl": "impl<Perm, PMRegion> View for WriteRestrictedPersistentMemoryRegion<Perm, PMRegion>\n    where\n        Perm: CheckPermission<Seq<u8>>,\n        PMRegion: PersistentMemoryRegion,\n{\n    type V = PersistentMemoryRegionView;\n    closed spec fn view(&self) -> Self::V {\n        self.pm_region@\n    }\n}",
  "depends_on_views_of": ["PersistentMemoryRegionView"],
  "rationale": "The only spec-meaningful state of the wrapper is the underlying persistent-memory region's abstract bytes/outstanding-writes; the `ghost perm: Option<Perm>` exists solely to satisfy Rust's requirement that the `Perm` generic parameter be referenced (per the source comment) and is never inspected by any ensures clause. We therefore drop `perm` entirely and project `self.pm_region` through its `View` impl, yielding `PersistentMemoryRegionView` — matching the type's existing inherent `view(&self) -> PersistentMemoryRegionView` declaration."
}
```
