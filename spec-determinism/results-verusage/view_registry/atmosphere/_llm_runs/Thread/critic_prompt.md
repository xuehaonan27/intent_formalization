You are auditing a Verus `impl View` block that another LLM just generated.
A view is a pure spec-level projection of a runtime type to its
information content: anything spec assertions need to compare semantically
should survive; runtime ghost fields / permissions / raw pointers should
be collapsed away.

Your job is to spot **semantic** mistakes — the text already parses.
Report only mistakes that matter. Do not nitpick style.

## Common mistakes (non-exhaustive)

1. **Lost information.** A struct field is used in spec ensures (e.g.
   `post.field == old(self).field` or `self.field@`) but the view drops
   it or replaces it with `()`.
2. **Wrong container shape.** `Vec<T>` viewed as `Set<T@>` or `Multiset<T@>`
   when spec accesses by index (`v[i]`) — should be `Seq<T@>`.
3. **Primitive `@`.** A primitive (usize/u32/bool/char/…) cannot be
   `@`-projected — Verus rejects `5_usize@`. Primitives stay verbatim.
4. **type V mismatch.** The declared `type V = X;` doesn't match the body
   of `spec fn view(&self) -> Self::V { … }` — different shape or fields.
5. **Over-aggressive collapse.** A struct with real state (not just
   pointers) collapsed to `type V = ();` — fine only when all fields are
   ghost / raw-pointer.
6. **Missing dep view.** Field of type `T` (which has a known view) used
   as `self.field` instead of `self.field@`, leaving structural eq.
7. **Wrong dep view.** Field of type `Vec<T>` viewed as `Seq<T>` (no `@`
   on element) when spec actually inspects element fields.

## Output

Reply with a SINGLE fenced ```json block of this exact shape, nothing
else (no prose before or after):

```json
{
  "verdict": "accept" | "revise" | "reject",
  "issues": ["<short string per issue>", "..."]
}
```

- `accept`: no issues found, view looks correct.
- `revise`: minor concerns (cosmetic, edge cases) but the view still
  compiles and preserves enough info. List concerns in `issues`.
- `reject`: a hard mistake from the list above (or equivalent). The
  view will fail typecheck or lose spec-relevant information.

If you cannot tell whether the view is correct because of missing
context (e.g. the dependency view is unknown), prefer `accept` with an
issue noting the uncertainty. Do not reject for missing context alone.


## Target type (atmosphere)

Qualified name: `Thread`
Short name: `Thread`

```rust
pub struct Thread {
    pub owning_container: ContainerPtr,
    pub owning_proc: ProcPtr,
    pub state: ThreadState,
    pub proc_rev_ptr: SLLIndex,
    pub scheduler_rev_ptr: Option<SLLIndex>,
    pub blocking_endpoint_ptr: Option<EndpointPtr>,
    pub blocking_endpoint_index: Option<EndpointIdx>,
    pub endpoint_rev_ptr: Option<SLLIndex>,
    pub running_cpu: Option<CpuId>,
    pub endpoint_descriptors: Array<Option<EndpointPtr>, MAX_NUM_ENDPOINT_DESCRIPTORS>,
    pub ipc_payload: IPCPayLoad,
    pub error_code: Option<RetValueType>,  //this will only be set when it comes out of endpoint and goes to scheduler.
    pub trap_frame: TrapFrameOption,
}
```

## Dependency views already in scope

  - ContainerPtr: L2 → usize  (alias ContainerPtr → usize (primitive))
  - ProcPtr: L2 → usize  (alias ProcPtr → usize (primitive))
  - ThreadState: uncovered (no L1/L2/L3/L4 rule for ThreadState (kind=leaf))
  - SLLIndex: L2 → i32  (alias SLLIndex → i32 (primitive))
  - EndpointPtr: L2 → usize  (alias EndpointPtr → usize (primitive))
  - EndpointIdx: L2 → usize  (alias EndpointIdx → usize (primitive))
  - CpuId: L2 → usize  (alias CpuId → usize (primitive))
  - Array: uncovered (no L1/L2/L3/L4 rule for Array (kind=leaf))
  - IPCPayLoad: uncovered (no L1/L2/L3/L4 rule for IPCPayLoad (kind=leaf))
  - RetValueType: uncovered (no L1/L2/L3/L4 rule for RetValueType (kind=leaf))
  - TrapFrameOption: uncovered (no L1/L2/L3/L4 rule for TrapFrameOption (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `ThreadView`

```rust
pub struct ThreadView {
    pub owning_container: ContainerPtr,
    pub owning_proc: ProcPtr,
    pub state: <ThreadState as View>::V,
    pub proc_rev_ptr: SLLIndex,
    pub scheduler_rev_ptr: Option<SLLIndex>,
    pub blocking_endpoint_ptr: Option<EndpointPtr>,
    pub blocking_endpoint_index: Option<EndpointIdx>,
    pub endpoint_rev_ptr: Option<SLLIndex>,
    pub running_cpu: Option<CpuId>,
    pub endpoint_descriptors: <Array<Option<EndpointPtr>, MAX_NUM_ENDPOINT_DESCRIPTORS> as View>::V,
    pub ipc_payload: <IPCPayLoad as View>::V,
    pub error_code: Option<<RetValueType as View>::V>,
    pub trap_frame: <TrapFrameOption as View>::V,
}

impl View for Thread {
    type V = ThreadView;
    closed spec fn view(&self) -> ThreadView {
        ThreadView {
            owning_container: self.owning_container,
            owning_proc: self.owning_proc,
            state: self.state@,
            proc_rev_ptr: self.proc_rev_ptr,
            scheduler_rev_ptr: self.scheduler_rev_ptr,
            blocking_endpoint_ptr: self.blocking_endpoint_ptr,
            blocking_endpoint_index: self.blocking_endpoint_index,
            endpoint_rev_ptr: self.endpoint_rev_ptr,
            running_cpu: self.running_cpu,
            endpoint_descriptors: self.endpoint_descriptors@,
            ipc_payload: self.ipc_payload@,
            error_code: self.error_code@,
            trap_frame: self.trap_frame@,
        }
    }
}
```

Generator's rationale: Thread has no raw pointer or ghost wrapper fields, so every field is spec-meaningful and retained. Primitive-alias fields (ContainerPtr/ProcPtr/SLLIndex/EndpointPtr/EndpointIdx/CpuId all resolve to usize/i32) are kept as-is without `@` since primitives have identity view. Uncovered user types (ThreadState, IPCPayLoad, RetValueType, TrapFrameOption) and the fixed-size Array container are projected through their own `.view()` via `@` so the abstract view ignores any allocator/layout-opaque internals; Option's view propagates `@` element-wise to its inner type.
