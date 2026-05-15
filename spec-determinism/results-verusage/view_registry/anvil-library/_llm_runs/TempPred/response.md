```json
{
  "viewed_type": "spec_fn(Execution<T>) -> bool",
  "view_decl": "impl<T> View for TempPred<T> {\n    type V = spec_fn(Execution<T>) -> bool;\n    closed spec fn view(&self) -> Self::V {\n        self.pred\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "TempPred is a thin newtype around a single spec_fn(Execution<T>) -> bool, and two temporal predicates are semantically equal iff their underlying predicates agree on every execution — exactly the extensional equality spec_fn already provides. Projecting to the bare spec_fn drops the struct wrapper so the checker compares predicates directly; Execution<T> is left at identity because it is currently uncovered (no view rule), and T has no View bound so it stays identity as well."
}
```
