```json
{
  "viewed_type": "Set<usize>",
  "view_decl": "impl<const N: usize> View for ArraySet<N> {\n    type V = Set<usize>;\n    closed spec fn view(&self) -> Set<usize> {\n        self.set@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "An ArraySet is semantically just the set of usize elements it holds; the `data: Array<bool, N>` bit-vector and `len` counter are concrete encoding/cardinality details derivable from the abstract set, and `Array` has no resolved view anyway. The Ghost<Set<usize>> field already carries the spec-level set, so unwrapping Ghost with `@` yields the canonical view (usize is primitive, so no further projection is needed)."
}
```
