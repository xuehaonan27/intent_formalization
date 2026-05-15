```json
{
  "viewed_type": "NetClientView",
  "view_decl": "pub struct NetClientView {\n    pub history: Seq<NetEvent>,\n    pub end_point: EndPoint,\n}\n\nimpl View for NetClient {\n    type V = NetClientView;\n    closed spec fn view(&self) -> NetClientView {\n        NetClientView {\n            history: self.history@@,\n            end_point: self.end_point,\n        }\n    }\n}",
  "depends_on_views_of": ["History"],
  "rationale": "The abstract behavior of a NetClient is captured by its network-event trace (history) plus the endpoint identity it speaks for. We project Ghost<History> through History's view to Seq<NetEvent>, and keep EndPoint as identity since it is an uncovered leaf whose structural equality already encodes semantic identity. The Ghost<State> field is internal proof state, c_pointers is allocator/FFI-opaque, and DuctTapeProfiler is debug instrumentation — none are inspected by spec ensures clauses, so all three are omitted."
}
```
