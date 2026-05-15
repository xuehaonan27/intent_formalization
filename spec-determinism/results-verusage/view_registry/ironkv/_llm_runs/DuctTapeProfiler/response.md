```json
{
  "viewed_type": "()",
  "view_decl": "impl View for DuctTapeProfiler {\n    type V = ();\n    closed spec fn view(&self) -> Self::V {\n        ()\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Every field is runtime instrumentation metadata that the spec never constrains: the two SystemTime fields are wall-clock timestamps (non-deterministic across runs) and event_counter is a HashMap (uncovered leaf, with non-deterministic iteration order) used only for profiling counts. Projecting to unit makes any two profilers semantically equal, avoiding spurious structural-equality witnesses."
}
```
