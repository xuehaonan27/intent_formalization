```json
{
  "viewed_type": "Seq<usize>",
  "view_decl": "impl View for CommitMask {\n    type V = Seq<usize>;\n    closed spec fn view(&self) -> Seq<usize> {\n        self.mask@\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "CommitMask is a fixed-size bitmask backed by `[usize; 8]`; the positional order of words is spec-meaningful (bit i lives in word i / usize::BITS), so we project the array to its standard `Seq<usize>` view. `usize` is primitive, so no further element-level `@` is needed."
}
```
