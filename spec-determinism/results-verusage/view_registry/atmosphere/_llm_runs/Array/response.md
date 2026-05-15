```json
{
  "viewed_type": "Seq<A::V>",
  "view_decl": "impl<A: View, const N: usize> View for Array<A, N> {\n    type V = Seq<A::V>;\n    closed spec fn view(&self) -> Self::V {\n        self.seq@@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "The ghost `seq` is the spec-level abstraction that mirrors the concrete `[A;N]` storage; the type's invariant ties `ar` to `seq`, so the array field carries no spec-visible information and is omitted. The first `@` on `self.seq` unwraps the `Ghost`, and the second projects the sequence's elements through `A`'s view, yielding `Seq<A::V>` so element-level semantic equality flows through."
}
```
