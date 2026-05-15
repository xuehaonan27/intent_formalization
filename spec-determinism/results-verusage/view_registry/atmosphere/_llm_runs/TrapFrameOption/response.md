```json
{
  "viewed_type": "TrapFrameOptionView",
  "view_decl": "pub struct TrapFrameOptionView { pub reg: Registers, pub exists: bool }\n\nimpl View for TrapFrameOption {\n    type V = TrapFrameOptionView;\n    closed spec fn view(&self) -> TrapFrameOptionView {\n        TrapFrameOptionView { reg: self.reg, exists: self.exists }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are spec-meaningful (a trap frame's register state and presence flag are exactly what the spec constrains). Registers has no resolved View (leaf), so we project it by identity; exists is a primitive bool taken as-is."
}
```
