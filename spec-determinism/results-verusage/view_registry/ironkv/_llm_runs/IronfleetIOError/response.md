```json
{
  "viewed_type": "IronfleetIOErrorView",
  "view_decl": "pub struct IronfleetIOErrorView { pub message: Seq<char> }\n\nimpl View for IronfleetIOError {\n    type V = IronfleetIOErrorView;\n    closed spec fn view(&self) -> IronfleetIOErrorView {\n        IronfleetIOErrorView { message: self.message@ }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "The only field is a String error message; project it via String's built-in view (Seq<char>) so semantic equality compares message content rather than the underlying allocator-dependent buffer."
}
```
