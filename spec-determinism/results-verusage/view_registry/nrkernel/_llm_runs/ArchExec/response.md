```json
{
  "viewed_type": "Seq<ArchLayerExec>",
  "view_decl": "impl View for ArchExec {\n    type V = Seq<ArchLayerExec>;\n    closed spec fn view(&self) -> Seq<ArchLayerExec> {\n        self.layers@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "ArchExec is a thin wrapper around a fixed-size array of 4 ArchLayerExec page-table layers, so the view projects to the array's built-in Seq view. Layer order is semantically meaningful (the index encodes the page-table level), so Seq — not Set/Multiset — is the right shape. ArchLayerExec is currently an uncovered leaf type with no resolved View impl, so its elements are kept as-is and compared structurally inside the Seq; this projection can be tightened later by synthesising a View for ArchLayerExec without changing ArchExec's view shape."
}
```
