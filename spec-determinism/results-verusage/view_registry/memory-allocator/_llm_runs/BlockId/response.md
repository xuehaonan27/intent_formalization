```json
{
  "viewed_type": "BlockIdView",
  "view_decl": "pub struct BlockIdView { pub page_id: PageId, pub idx: nat, pub slice_idx: nat, pub block_size: nat }\n\nimpl View for BlockId {\n    type V = BlockIdView;\n    closed spec fn view(&self) -> BlockIdView {\n        BlockIdView { page_id: self.page_id, idx: self.idx, slice_idx: self.slice_idx, block_size: self.block_size }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "BlockId is a ghost identifier struct; every field is spec-relevant (which page, which slice within the segment, which block index, and the block size). PageId is a leaf type with identity view and the other fields are nat (primitive), so we project all four fields as-is into a parallel BlockIdView."
}
```
