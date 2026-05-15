```json
{
  "viewed_type": "ExternalDigestView",
  "view_decl": "pub struct ExternalDigestView { pub digest: <Digest as View>::V }\n\nimpl View for ExternalDigest {\n    type V = ExternalDigestView;\n    closed spec fn view(&self) -> ExternalDigestView {\n        ExternalDigestView { digest: self.digest@ }\n    }\n}",
  "depends_on_views_of": ["Digest"],
  "rationale": "ExternalDigest is a single-field newtype wrapper around Digest with no additional state, so its semantic content is exactly the wrapped digest's view. We project through `self.digest@` and wrap in a thin ExternalDigestView record so the checker can still distinguish ExternalDigest from a bare Digest at the type level while comparing only Digest's semantic content."
}
```
