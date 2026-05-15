```json
{
  "viewed_type": "KernelView",
  "view_decl": "pub struct KernelView {\n    pub page_alloc: <PageAllocator as View>::V,\n    pub mem_man: <MemoryManager as View>::V,\n    pub proc_man: <ProcessManager as View>::V,\n    pub page_mapping: Map<PagePtr, Set<(ProcPtr, VAddr)>>,\n    pub page_io_mapping: Map<PagePtr, Set<(ProcPtr, VAddr)>>,\n}\n\nimpl View for Kernel {\n    type V = KernelView;\n    closed spec fn view(&self) -> KernelView {\n        KernelView {\n            page_alloc: self.page_alloc@,\n            mem_man: self.mem_man@,\n            proc_man: self.proc_man@,\n            page_mapping: self.page_mapping@,\n            page_io_mapping: self.page_io_mapping@,\n        }\n    }\n}",
  "depends_on_views_of": ["PageAllocator", "MemoryManager", "ProcessManager"],
  "rationale": "Kernel is a pure aggregate of three component managers plus two ghost page-mapping tables; none of its fields are raw pointers or allocator-opaque IDs, so every field carries spec-relevant content. Each manager is projected through its own (recursively synthesized) View so impl-internal storage layout, free-list ordering, and PointsTo permission bookkeeping inside the manager are collapsed away. The two Ghost<Map<PagePtr, Set<(ProcPtr, VAddr)>>> fields are unwrapped with a single `@` (the Ghost wrapper's view); their keys and tuple element types are primitive aliases (PagePtr/ProcPtr/VAddr → usize) which need no further `.view()`, so the inner spec-level Map<…, Set<(usize, usize)>> already is its own view."
}
```
