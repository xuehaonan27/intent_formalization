```json
{
  "viewed_type": "PageView",
  "view_decl": "pub struct PageView {\n    pub addr: PagePtr,\n    pub state: PageState,\n    pub is_io_page: bool,\n    pub rev_pointer: SLLIndex,\n    pub ref_count: usize,\n    pub owning_container: Option<ContainerPtr>,\n    pub mappings: Set<(Pcid, VAddr)>,\n    pub io_mappings: Set<(IOid, VAddr)>,\n}\n\nimpl View for Page {\n    type V = PageView;\n    closed spec fn view(&self) -> PageView {\n        PageView {\n            addr: self.addr,\n            state: self.state,\n            is_io_page: self.is_io_page,\n            rev_pointer: self.rev_pointer,\n            ref_count: self.ref_count,\n            owning_container: self.owning_container,\n            mappings: self.mappings@,\n            io_mappings: self.io_mappings@,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "There are no raw pointers or opaque allocator handles to drop: PagePtr/ContainerPtr/SLLIndex/Pcid/VAddr/IOid are all primitive aliases (usize/i32) that serve as semantic identifiers, so they're kept by value with no `@`. PageState is an uncovered leaf type, so its structural equality is treated as semantic (used directly like the prompt example). The two `Ghost<Set<...>>` mapping fields are unwrapped with a single `@` because Set is already a Verus spec type whose elements are primitive-aliased and need no further projection."
}
```
