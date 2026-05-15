```json
{
  "viewed_type": "NodeView<T::V>",
  "view_decl": "pub struct NodeView<T> { pub value: Option<T>, pub next: i32, pub prev: i32 }\n\nimpl<T: View> View for Node<T> {\n    type V = NodeView<T::V>;\n    closed spec fn view(&self) -> NodeView<T::V> {\n        NodeView {\n            value: self.value@,\n            next: self.next,\n            prev: self.prev,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Project value via Option's view (lifting T to T::V), which requires adding a T: View bound. next/prev are kept as i32 because SLLIndex is a primitive alias whose structural equality is already semantic, so no @ is applied."
}
```
