```json
{
  "viewed_type": "EndpointView",
  "view_decl": "pub struct EndpointView {\n    pub queue: <StaticLinkedList<ThreadPtr, MAX_NUM_THREADS_PER_ENDPOINT> as View>::V,\n    pub queue_state: <EndpointState as View>::V,\n    pub rf_counter: usize,\n    pub owning_threads: Set<(ThreadPtr, EndpointIdx)>,\n    pub owning_container: ContainerPtr,\n}\n\nimpl View for Endpoint {\n    type V = EndpointView;\n    closed spec fn view(&self) -> EndpointView {\n        EndpointView {\n            queue: self.queue@,\n            queue_state: self.queue_state@,\n            rf_counter: self.rf_counter,\n            owning_threads: self.owning_threads@@,\n            owning_container: self.owning_container,\n        }\n    }\n}",
  "depends_on_views_of": ["StaticLinkedList", "EndpointState"],
  "rationale": "Project queue and queue_state through their (to-be-resolved) View impls, copy the primitive-aliased usize fields rf_counter and owning_container as-is, and unwrap the Ghost<Set<(ThreadPtr, EndpointIdx)>> with `@@` (first `@` strips Ghost, second is the Set's identity view since its element tuple components are primitive usize aliases). There are no raw pointer fields, so nothing is dropped."
}
```
