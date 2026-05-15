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

Qualified name: `Container`
Short name: `Container`

```rust
pub struct Container {
    pub parent: Option<ContainerPtr>,
    pub parent_rev_ptr: Option<SLLIndex>,
    pub children: StaticLinkedList<ContainerPtr, CONTAINER_CHILD_LIST_LEN>,
    pub depth: usize,
    pub uppertree_seq: Ghost<Seq<ContainerPtr>>,
    pub subtree_set: Ghost<Set<ContainerPtr>>,
    pub root_process: Option<ProcPtr>,
    pub owned_procs: StaticLinkedList<ProcPtr, CONTAINER_PROC_LIST_LEN>,
    /// Right now we don't yet have linkedlist with unlimited length, 
    /// so we cannot kill an endpoint and release all the blocked threads.
    /// We we can do now to enable unconditional kill() is to add an invariant to
    /// ensure that each endpoint can ONLY be referenced by threads in the subtree of the container.
    /// So when we kill all the threads, all the endpoints are killed too. 
    pub owned_endpoints: Ghost<Set<EndpointPtr>>,
    pub owned_threads: Ghost<Set<ThreadPtr>>,
    // pub mem_quota: usize,
    // pub mem_quota_2m: usize,
    // pub mem_quota_1g: usize,
    // pub mem_used: usize,
    // pub mem_used_2m: usize,
    // pub mem_used_1g: usize,
    pub quota: Quota,
    pub owned_cpus: ArraySet<NUM_CPUS>,
    pub scheduler: StaticLinkedList<ThreadPtr, MAX_CONTAINER_SCHEDULER_LEN>,
    pub can_have_children: bool,
}
```

## Dependency views already in scope

  - ContainerPtr: L2 → usize  (alias ContainerPtr → usize (primitive))
  - SLLIndex: L2 → i32  (alias SLLIndex → i32 (primitive))
  - StaticLinkedList: uncovered (no L1/L2/L3/L4 rule for StaticLinkedList (kind=leaf))
  - ProcPtr: L2 → usize  (alias ProcPtr → usize (primitive))
  - EndpointPtr: L2 → usize  (alias EndpointPtr → usize (primitive))
  - ThreadPtr: L2 → usize  (alias ThreadPtr → usize (primitive))
  - Quota: uncovered (no L1/L2/L3/L4 rule for Quota (kind=leaf))
  - ArraySet: uncovered (no L1/L2/L3/L4 rule for ArraySet (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `ContainerView`

```rust
pub struct ContainerView {
    pub parent: Option<ContainerPtr>,
    pub parent_rev_ptr: Option<SLLIndex>,
    pub children: <StaticLinkedList<ContainerPtr, CONTAINER_CHILD_LIST_LEN> as View>::V,
    pub depth: usize,
    pub uppertree_seq: Seq<ContainerPtr>,
    pub subtree_set: Set<ContainerPtr>,
    pub root_process: Option<ProcPtr>,
    pub owned_procs: <StaticLinkedList<ProcPtr, CONTAINER_PROC_LIST_LEN> as View>::V,
    pub owned_endpoints: Set<EndpointPtr>,
    pub owned_threads: Set<ThreadPtr>,
    pub quota: <Quota as View>::V,
    pub owned_cpus: <ArraySet<NUM_CPUS> as View>::V,
    pub scheduler: <StaticLinkedList<ThreadPtr, MAX_CONTAINER_SCHEDULER_LEN> as View>::V,
    pub can_have_children: bool,
}

impl View for Container {
    type V = ContainerView;
    closed spec fn view(&self) -> ContainerView {
        ContainerView {
            parent: self.parent,
            parent_rev_ptr: self.parent_rev_ptr,
            children: self.children@,
            depth: self.depth,
            uppertree_seq: self.uppertree_seq@@,
            subtree_set: self.subtree_set@@,
            root_process: self.root_process,
            owned_procs: self.owned_procs@,
            owned_endpoints: self.owned_endpoints@@,
            owned_threads: self.owned_threads@@,
            quota: self.quota@,
            owned_cpus: self.owned_cpus@,
            scheduler: self.scheduler@,
            can_have_children: self.can_have_children,
        }
    }
}
```

Generator's rationale: Container contains no raw pointers and every field is potentially spec-relevant (parent/child links, subtree membership, owned resources, quota, scheduling state). Primitive-alias fields (ContainerPtr/SLLIndex/ProcPtr/EndpointPtr/ThreadPtr all resolve to usize/i32) and depth/can_have_children pass through by identity. Ghost<Seq|Set<*Ptr>> fields are unwrapped via `@@` so the comparison ignores ghost-wrapper representation and uses the abstract sequence/set of primitive pointers. The concrete linked-list, Quota, and ArraySet fields recurse through their own View impls to abstract away allocator-level layout (slot indices, free-list ordering, bitset internals).
