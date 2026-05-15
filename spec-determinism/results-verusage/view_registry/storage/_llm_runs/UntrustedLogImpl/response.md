```json
{
  "viewed_type": "UntrustedLogImplView",
  "view_decl": "pub struct UntrustedLogImplView {\n    pub cdb: bool,\n    pub info: <LogInfo as View>::V,\n    pub state: <AbstractLogState as View>::V,\n}\n\nimpl View for UntrustedLogImpl {\n    type V = UntrustedLogImplView;\n    closed spec fn view(&self) -> UntrustedLogImplView {\n        UntrustedLogImplView {\n            cdb: self.cdb,\n            info: self.info@,\n            state: self.state@@,\n        }\n    }\n}",
  "depends_on_views_of": ["LogInfo", "AbstractLogState"],
  "rationale": "All three fields are spec-meaningful for a persistent log: cdb (the corruption-detecting boolean) selects which on-disk section is active, info is bookkeeping the spec inspects, and the Ghost<AbstractLogState> is the abstract refinement state. Keep primitive bool as-is, project LogInfo through its (to-be-synthesised) view, and use `@@` to unwrap the Ghost wrapper and then view the inner AbstractLogState."
}
```
