```json
{
  "viewed_type": "LblView",
  "view_decl": "pub enum LblView {\n    Tau,\n    AcquireLock { core: Core },\n    ReleaseLock { core: Core },\n    InitShootdown { core: Core, vaddr: nat },\n    WaitShootdown { core: Core },\n    AckShootdown { core: Core },\n    Allocate { core: Core, res: MemRegion },\n    Deallocate { core: Core, reg: MemRegion },\n}\n\nimpl View for Lbl {\n    type V = LblView;\n    closed spec fn view(&self) -> LblView {\n        match *self {\n            Lbl::Tau => LblView::Tau,\n            Lbl::AcquireLock { core } => LblView::AcquireLock { core },\n            Lbl::ReleaseLock { core } => LblView::ReleaseLock { core },\n            Lbl::InitShootdown { core, vaddr } => LblView::InitShootdown { core, vaddr },\n            Lbl::WaitShootdown { core } => LblView::WaitShootdown { core },\n            Lbl::AckShootdown { core } => LblView::AckShootdown { core },\n            Lbl::Allocate { core, res } => LblView::Allocate { core, res },\n            Lbl::Deallocate { core, reg } => LblView::Deallocate { core, reg },\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Lbl is a label/transition tag — every variant and every payload field is spec-meaningful (the core that performed the action, the vaddr being shot down, the allocated/freed region), so the view mirrors the structure exactly. Core and MemRegion are leaf types with no View impl, so they appear by identity (their structural equality is treated as semantic); nat is a Verus spec primitive used as-is."
}
```
