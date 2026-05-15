```json
{
  "viewed_type": "Seq<T>",
  "view_decl": "impl<T, const N: usize> View for StaticLinkedList<T, N> {\n    type V = Seq<T>;\n    closed spec fn view(&self) -> Seq<T> {\n        self.spec_seq@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "The abstract value of a static linked list is the logical sequence of elements it stores; every other field (the physical Node array `ar`, the ghost index lists `value_list`/`free_list`, their head/tail/len cursors, `size`, and the mirror `arr_seq`) is allocator/implementation bookkeeping that the spec only constrains via `spec_seq`. So we project to `Seq<T>` by unwrapping the `Ghost<Seq<T>>` (single `@`); `Seq<T>` is already a spec-level type so no further element view is applied, which also avoids imposing an unwanted `T: View` bound."
}
```
