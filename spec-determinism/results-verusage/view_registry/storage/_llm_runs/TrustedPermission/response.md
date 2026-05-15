```json
{
  "viewed_type": "spec_fn(Seq<u8>) -> bool",
  "view_decl": "impl View for TrustedPermission {\n    type V = spec_fn(Seq<u8>) -> bool;\n    closed spec fn view(&self) -> Self::V {\n        self.is_state_allowable\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "The struct's only content is the ghost predicate `is_state_allowable`, which fully characterises which byte-sequences the permission accepts. Two TrustedPermissions are semantically equivalent iff this predicate is extensionally equal, so we project directly to the spec_fn; Verus' logic gives extensional equality on spec_fn natively, and Seq<u8>/bool are primitives that need no view sugar."
}
```
