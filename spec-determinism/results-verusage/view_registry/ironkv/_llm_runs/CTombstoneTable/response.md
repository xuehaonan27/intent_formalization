```json
{
  "viewed_type": "TombstoneTable",
  "view_decl": "impl View for CTombstoneTable {\n    type V = TombstoneTable;\n    open spec fn view(&self) -> Self::V {\n        self.epmap@.map_values(|v: u64| v as nat)\n    }\n}",
  "depends_on_views_of": ["HashMap"],
  "rationale": "CTombstoneTable is a thin wrapper over a single HashMap<u64> from endpoints to last-seen sequence numbers; the spec abstracts it to TombstoneTable = Map<AbstractEndPoint, nat>. We project through HashMap<u64>'s view (Map<AbstractEndPoint, u64>) and lift each u64 to nat via map_values, matching the canonical inherent view already used throughout the ironkv spec."
}
```
