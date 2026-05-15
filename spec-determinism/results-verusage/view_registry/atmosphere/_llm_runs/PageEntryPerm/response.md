```json
{
  "viewed_type": "PageEntryPermView",
  "view_decl": "pub struct PageEntryPermView { pub present: bool, pub ps: bool, pub write: bool, pub execute_disable: bool, pub user: bool }\n\nimpl View for PageEntryPerm {\n    type V = PageEntryPermView;\n    closed spec fn view(&self) -> PageEntryPermView {\n        PageEntryPermView {\n            present: self.present,\n            ps: self.ps,\n            write: self.write,\n            execute_disable: self.execute_disable,\n            user: self.user,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "All five fields are primitive `bool` flags that directly encode architectural page-table permission bits; the spec necessarily constrains each one, so the view preserves all fields verbatim. Since bools have identity views, the projection is effectively structural equality lifted into a dedicated View type for uniform handling by the checker."
}
```
