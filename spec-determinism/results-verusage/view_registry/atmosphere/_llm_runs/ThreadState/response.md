```json
{
  "viewed_type": "ThreadState",
  "view_decl": "impl View for ThreadState {\n    type V = ThreadState;\n    closed spec fn view(&self) -> ThreadState {\n        *self\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "ThreadState is a Copy/PartialEq enum of three unit variants (SCHEDULED, BLOCKED, RUNNING) with no payload, so its structural equality is already semantic. The view is the identity: project to Self by returning *self."
}
```
