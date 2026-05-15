```json
{
  "viewed_type": "Seq<T>",
  "view_decl": "impl<T, const N: usize> View for ArrayVec<T, N> {\n    type V = Seq<T>;\n    closed spec fn view(&self) -> Seq<T> {\n        self.data@.subrange(0, self.len as int)\n    }\n}",
  "depends_on_views_of": ["Array"],
  "rationale": "An ArrayVec is semantically the ordered sequence of its first `len` elements; storage slots beyond `len` hold uninitialized/garbage data the spec never inspects. We project via the underlying array's view and take the valid prefix as a Seq<T>, so two ArrayVecs compare equal iff they have the same logical contents regardless of tail bytes."
}
```
