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

Qualified name: `IPCPayLoad`
Short name: `IPCPayLoad`

```rust
pub enum IPCPayLoad {
    Message { va: VAddr, len: usize },
    Pages { va_range: VaRange4K },
    Endpoint { endpoint_index: EndpointIdx },
    Pci { bus: u8, dev: u8, fun: u8 },
    PageFault { vaddr: VAddr },
    Empty,
}
```

## Dependency views already in scope

  - VAddr: L2 → usize  (alias VAddr → usize (primitive))
  - VaRange4K: uncovered (no L1/L2/L3/L4 rule for VaRange4K (kind=leaf))
  - EndpointIdx: L2 → usize  (alias EndpointIdx → usize (primitive))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `IPCPayLoadView`

```rust
pub enum IPCPayLoadView {
    Message { va: VAddr, len: usize },
    Pages { va_range: VaRange4K },
    Endpoint { endpoint_index: EndpointIdx },
    Pci { bus: u8, dev: u8, fun: u8 },
    PageFault { vaddr: VAddr },
    Empty,
}

impl View for IPCPayLoad {
    type V = IPCPayLoadView;
    closed spec fn view(&self) -> IPCPayLoadView {
        match self {
            IPCPayLoad::Message { va, len } => IPCPayLoadView::Message { va: *va, len: *len },
            IPCPayLoad::Pages { va_range } => IPCPayLoadView::Pages { va_range: *va_range },
            IPCPayLoad::Endpoint { endpoint_index } => IPCPayLoadView::Endpoint { endpoint_index: *endpoint_index },
            IPCPayLoad::Pci { bus, dev, fun } => IPCPayLoadView::Pci { bus: *bus, dev: *dev, fun: *fun },
            IPCPayLoad::PageFault { vaddr } => IPCPayLoadView::PageFault { vaddr: *vaddr },
            IPCPayLoad::Empty => IPCPayLoadView::Empty,
        }
    }
}
```

Generator's rationale: IPCPayLoad is a tagged union, so we mirror it with a parallel IPCPayLoadView enum and project each variant's fields via match. VAddr and EndpointIdx resolve to the primitive usize (L2 aliases), and bus/dev/fun/len are u8/usize primitives, so all are copied structurally with no `@`. VaRange4K is an uncovered leaf whose structural equality is treated as semantic (same convention as AbstractKey/PageEntryPerm), so it is also kept identity. No raw pointers, ghost wrappers, or allocator handles to drop; the Empty variant carries no fields.
