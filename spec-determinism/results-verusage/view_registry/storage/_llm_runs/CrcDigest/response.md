```json
{
  "viewed_type": "CrcDigestView",
  "view_decl": "pub struct CrcDigestView { pub bytes_in_digest: Seq<Seq<u8>> }\n\nimpl View for CrcDigest {\n    type V = CrcDigestView;\n    closed spec fn view(&self) -> CrcDigestView {\n        CrcDigestView { bytes_in_digest: self.bytes_in_digest@@ }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Every ensures clause on CrcDigest's methods (new, write, sum64) inspects only self.bytes_in_digest(), never the underlying digest: ExternalDigest, which is an #[verifier::external_body] opaque allocator-managed handle. We therefore omit the digest field and project the ghost Seq<Seq<u8>> via self.bytes_in_digest@@ (first @ unwraps Ghost, second views Seq<Seq<u8>>, which is identity since u8 is primitive)."
}
```
