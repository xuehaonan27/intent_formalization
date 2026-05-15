```json
{
  "viewed_type": "PersistentMemoryByteView",
  "view_decl": "pub struct PersistentMemoryByteView {\n    pub state_at_last_flush: u8,\n    pub outstanding_write: Option<u8>,\n}\n\nimpl View for PersistentMemoryByte {\n    type V = PersistentMemoryByteView;\n    closed spec fn view(&self) -> PersistentMemoryByteView {\n        PersistentMemoryByteView {\n            state_at_last_flush: self.state_at_last_flush,\n            outstanding_write: self.outstanding_write,\n        }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Both fields are spec-meaningful: state_at_last_flush is the durable byte value and outstanding_write captures any pending (but not yet flushed) write. Both field types (u8 and Option<u8>) are primitives/Option-of-primitive whose structural equality is already semantic, so we copy them verbatim into the view struct without recursive `@` projection."
}
```
