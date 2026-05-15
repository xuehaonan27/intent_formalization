```json
{
  "viewed_type": "ConstantsView",
  "view_decl": "pub struct ConstantsView {\n    pub common: crate::Constants,\n    pub ult2core: Map<nat, Core>,\n    pub ult_no: nat,\n}\n\nimpl View for Constants {\n    type V = ConstantsView;\n    closed spec fn view(&self) -> ConstantsView {\n        ConstantsView {\n            common: self.common,\n            ult2core: self.ult2core,\n            ult_no: self.ult_no,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All three fields are spec-meaningful: `common` holds the shared mmu/os_ext state-machine constants, `ult2core` is the user-level-thread-to-core assignment the ensures clauses inspect, and `ult_no` bounds the active thread-id space. `crate::Constants` and `Core` are leaf types without their own View impls (per the resolved-views list), so they are projected structurally with no `@`; `ult_no: nat` is a primitive copied directly. A later pass can swap in `@` recursively once those leaf views are synthesised."
}
```
