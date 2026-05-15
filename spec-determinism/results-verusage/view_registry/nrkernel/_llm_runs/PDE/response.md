```json
{
  "viewed_type": "PDEView",
  "view_decl": "pub struct PDEView { pub entry: usize, pub layer: nat }\n\nimpl View for PDE {\n    type V = PDEView;\n    closed spec fn view(&self) -> PDEView {\n        PDEView { entry: self.entry, layer: self.layer@ }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are spec-meaningful: `entry` is the concrete page-directory entry word that the spec inspects directly, and `layer` records the page-table level the entry belongs to. We unwrap the Ghost<nat> to its inner nat (a primitive spec type, so no further `@`), and keep `entry: usize` as-is since usize is primitive."
}
```
