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

Qualified name: `ProcessManager`
Short name: `ProcessManager`

```rust
pub struct ProcessManager {
    pub root_container: ContainerPtr,
    pub container_perms: Tracked<Map<ContainerPtr, PointsTo<Container>>>,
    pub process_perms: Tracked<Map<ProcPtr, PointsTo<Process>>>,
    pub thread_perms: Tracked<Map<ThreadPtr, PointsTo<Thread>>>,
    pub endpoint_perms: Tracked<Map<EndpointPtr, PointsTo<Endpoint>>>,
    pub cpu_list: Array<Cpu, NUM_CPUS>,
}
```

## Dependency views already in scope

  - ContainerPtr: L2 → usize  (alias ContainerPtr → usize (primitive))
  - Container: uncovered (no L1/L2/L3/L4 rule for Container (kind=leaf))
  - ProcPtr: L2 → usize  (alias ProcPtr → usize (primitive))
  - Process: uncovered (no L1/L2/L3/L4 rule for Process (kind=leaf))
  - ThreadPtr: L2 → usize  (alias ThreadPtr → usize (primitive))
  - Thread: uncovered (no L1/L2/L3/L4 rule for Thread (kind=leaf))
  - EndpointPtr: L2 → usize  (alias EndpointPtr → usize (primitive))
  - Endpoint: uncovered (no L1/L2/L3/L4 rule for Endpoint (kind=leaf))
  - Array: uncovered (no L1/L2/L3/L4 rule for Array (kind=leaf))
  - Cpu: uncovered (no L1/L2/L3/L4 rule for Cpu (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `ProcessManagerView`

```rust
pub struct ProcessManagerView {
    pub root_container: usize,
    pub container_perms: Map<usize, Container>,
    pub process_perms: Map<usize, Process>,
    pub thread_perms: Map<usize, Thread>,
    pub endpoint_perms: Map<usize, Endpoint>,
    pub cpu_list: Seq<Cpu>,
}

impl View for ProcessManager {
    type V = ProcessManagerView;
    open spec fn view(&self) -> ProcessManagerView {
        ProcessManagerView {
            root_container: self.root_container,
            container_perms: Map::new(
                |k: usize| self.container_perms@.dom().contains(k),
                |k: usize| self.container_perms@[k].value(),
            ),
            process_perms: Map::new(
                |k: usize| self.process_perms@.dom().contains(k),
                |k: usize| self.process_perms@[k].value(),
            ),
            thread_perms: Map::new(
                |k: usize| self.thread_perms@.dom().contains(k),
                |k: usize| self.thread_perms@[k].value(),
            ),
            endpoint_perms: Map::new(
                |k: usize| self.endpoint_perms@.dom().contains(k),
                |k: usize| self.endpoint_perms@[k].value(),
            ),
            cpu_list: self.cpu_list@,
        }
    }
}
```

Generator's rationale: root_container is a usize-aliased pointer ID kept verbatim. Each Tracked<Map<Ptr, PointsTo<T>>> permission map is unwrapped through Tracked and re-built as Map<usize, T> by projecting each PointsTo to its underlying value via .value(), dropping the pointer/allocator bookkeeping that should not affect spec equality. cpu_list is projected through Array's natural Seq view so two ProcessManagers with the same per-CPU contents compare equal regardless of array storage internals; Container/Process/Thread/Endpoint/Cpu are leaf types with no synthesized view yet and so retain their identity view.
