```json
{
  "viewed_type": "EndpointState",
  "view_decl": "impl View for EndpointState {\n    type V = EndpointState;\n    closed spec fn view(&self) -> EndpointState {\n        *self\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "EndpointState is a Copy enum of two unit variants (RECEIVE, SEND) deriving PartialEq, so its structural equality is already semantic. The identity view projects to Self, letting the checker compare values directly."
}
```
