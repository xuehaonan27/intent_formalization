```json
{
  "viewed_type": "DemandPagingModeView",
  "view_decl": "pub enum DemandPagingModeView {\n    NoDMDPG,\n    DirectParentPrc,\n    AllParentProc,\n    AllParentContainer,\n}\n\nimpl View for DemandPagingMode {\n    type V = DemandPagingModeView;\n    closed spec fn view(&self) -> DemandPagingModeView {\n        match self {\n            DemandPagingMode::NoDMDPG => DemandPagingModeView::NoDMDPG,\n            DemandPagingMode::DirectParentPrc => DemandPagingModeView::DirectParentPrc,\n            DemandPagingMode::AllParentProc => DemandPagingModeView::AllParentProc,\n            DemandPagingMode::AllParentContainer => DemandPagingModeView::AllParentContainer,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "DemandPagingMode is a C-style enum with four unit variants and no payload, so its semantic identity is fully captured by which variant is selected. We mirror it with a parallel view enum and map each variant 1:1, giving the checker a stable tag-only abstraction that ignores any future #[repr] / discriminant choices."
}
```
