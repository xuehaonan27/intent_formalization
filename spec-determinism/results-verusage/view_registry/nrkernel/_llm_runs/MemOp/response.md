```json
{
  "viewed_type": "MemOpView",
  "view_decl": "pub enum MemOpView {\n    Load { is_exec: bool, size: nat, result: LoadResult },\n    Store { new_value: Seq<u8>, result: StoreResult },\n}\n\nimpl View for MemOp {\n    type V = MemOpView;\n    closed spec fn view(&self) -> MemOpView {\n        match self {\n            MemOp::Load { is_exec, size, result } => MemOpView::Load { is_exec: *is_exec, size: *size, result: *result },\n            MemOp::Store { new_value, result } => MemOpView::Store { new_value: *new_value, result: *result },\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "MemOp is a tagged union whose every field is spec-meaningful: no raw pointers, no allocator handles, no ghost wrappers, and no Vec ordering ambiguity. LoadResult and StoreResult are uncovered leaves (identity view), while bool/nat/Seq<u8> are primitives or spec-mathy types, so the projection is a structural mirror enum MemOpView that preserves every variant and field."
}
```
