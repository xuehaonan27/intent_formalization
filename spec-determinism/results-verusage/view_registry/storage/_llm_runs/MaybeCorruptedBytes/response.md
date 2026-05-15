```json
{
  "viewed_type": "Seq<u8>",
  "view_decl": "impl<S> View for MaybeCorruptedBytes<S> where S: PmCopy {\n    type V = Seq<u8>;\n    closed spec fn view(&self) -> Seq<u8> {\n        arbitrary()\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "MaybeCorruptedBytes<S> wraps a Box<MaybeUninit<S>> holding bytes read from persistent memory that may have been corrupted; the Box pointer is allocator-opaque and the MaybeUninit storage is structurally meaningless, so we project to Seq<u8> — the byte sequence the spec actually constrains (e.g. via CRC checks and structural decoding). This matches the existing axiomatic `view(self) -> Seq<u8>` declared on the type in the source codebase. The body is `arbitrary()` because the raw maybe-uninit memory contents cannot be computed in pure spec; being `closed` hides this from callers so equality of views remains an opaque per-instance fact, which is exactly the determinism-checker semantics desired for this opaque external_body type."
}
```
