```json
{
  "viewed_type": "Map<AbstractEndPoint, <CAckState as View>::V>",
  "view_decl": "impl View for CSendState {\n    type V = Map<AbstractEndPoint, <CAckState as View>::V>;\n    closed spec fn view(&self) -> Self::V {\n        self.epmap@.map_values(|v: CAckState| v@)\n    }\n}",
  "depends_on_views_of": ["HashMap", "CAckState"],
  "rationale": "CSendState is a thin single-field wrapper around HashMap<CAckState> keyed by endpoint; IronKV's abstract spec treats it as SendState<Message> = Map<AbstractEndPoint, AckState<Message>>. We project through HashMap<CAckState>'s inherent view (Map<AbstractEndPoint, CAckState>) and lift each value through CAckState's View, yielding Map<AbstractEndPoint, <CAckState as View>::V>. Mirroring the accepted CTombstoneTable shape, no wrapper struct is needed since the field is a single map; CAckState is still uncovered, so its `.view()` is flagged in depends_on_views_of."
}
```
