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

Qualified name: `Process`
Short name: `Process`

```rust
pub struct Process {
    pub owning_container: ContainerPtr,
    pub rev_ptr: SLLIndex,
    pub pcid: Pcid,
    pub ioid: Option<IOid>,
    pub owned_threads: StaticLinkedList<ThreadPtr, MAX_NUM_THREADS_PER_PROC>,
    pub parent: Option<ProcPtr>,
    pub parent_rev_ptr: Option<SLLIndex>,
    pub children: StaticLinkedList<ProcPtr, PROC_CHILD_LIST_LEN>,
    pub uppertree_seq: Ghost<Seq<ProcPtr>>,
    pub subtree_set: Ghost<Set<ProcPtr>>,
    pub depth: usize,
    pub dmd_paging_mode: DemandPagingMode,
}
```

## Dependency views already in scope

  - ContainerPtr: L2 → usize  (alias ContainerPtr → usize (primitive))
  - SLLIndex: L2 → i32  (alias SLLIndex → i32 (primitive))
  - Pcid: L2 → usize  (alias Pcid → usize (primitive))
  - IOid: L2 → usize  (alias IOid → usize (primitive))
  - StaticLinkedList: uncovered (no L1/L2/L3/L4 rule for StaticLinkedList (kind=leaf))
  - ThreadPtr: L2 → usize  (alias ThreadPtr → usize (primitive))
  - ProcPtr: L2 → usize  (alias ProcPtr → usize (primitive))
  - DemandPagingMode: uncovered (no L1/L2/L3/L4 rule for DemandPagingMode (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `ProcessView`

```rust
pub struct ProcessView {
    pub owning_container: ContainerPtr,
    pub rev_ptr: SLLIndex,
    pub pcid: Pcid,
    pub ioid: Option<IOid>,
    pub owned_threads: <StaticLinkedList<ThreadPtr, MAX_NUM_THREADS_PER_PROC> as View>::V,
    pub parent: Option<ProcPtr>,
    pub parent_rev_ptr: Option<SLLIndex>,
    pub children: <StaticLinkedList<ProcPtr, PROC_CHILD_LIST_LEN> as View>::V,
    pub uppertree_seq: Seq<ProcPtr>,
    pub subtree_set: Set<ProcPtr>,
    pub depth: usize,
    pub dmd_paging_mode: DemandPagingMode,
}

impl View for Process {
    type V = ProcessView;
    closed spec fn view(&self) -> ProcessView {
        ProcessView {
            owning_container: self.owning_container,
            rev_ptr: self.rev_ptr,
            pcid: self.pcid,
            ioid: self.ioid,
            owned_threads: self.owned_threads@,
            parent: self.parent,
            parent_rev_ptr: self.parent_rev_ptr,
            children: self.children@,
            uppertree_seq: self.uppertree_seq@,
            subtree_set: self.subtree_set@,
            depth: self.depth,
            dmd_paging_mode: self.dmd_paging_mode,
        }
    }
}
```

Generator's rationale: Pointer-like aliases (ContainerPtr, SLLIndex, Pcid, IOid, ProcPtr, ThreadPtr) are primitive usize/i32 identities, so they are carried into the view unchanged. The two StaticLinkedList containers are projected through their own (recursively-synthesised) View so internal slot/free-list layout is abstracted away while element identity is preserved. Ghost<Seq<ProcPtr>>/Ghost<Set<ProcPtr>> are unwrapped to their inner spec Seq/Set values, and DemandPagingMode (a leaf enum of unit-like modes) is kept structurally since its derived equality is already semantic.
