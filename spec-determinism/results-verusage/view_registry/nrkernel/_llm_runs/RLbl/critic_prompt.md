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


## Target type (nrkernel)

Qualified name: `RLbl`
Short name: `RLbl`

```rust
pub enum RLbl {
    Tau,
    MemOp      { thread_id: nat, vaddr: nat, op: MemOp },
    MapStart   { thread_id: nat, vaddr: nat, pte: PTE },
    MapEnd     { thread_id: nat, vaddr: nat, result: Result<(), ()> },
    UnmapStart { thread_id: nat, vaddr: nat },
    UnmapEnd   { thread_id: nat, vaddr: nat, result: Result<(), ()> },
    AckShootdownIPI { core: Core },
}
```

## Dependency views already in scope

  - MemOp: uncovered (no L1/L2/L3/L4 rule for MemOp (kind=leaf))
  - Core: uncovered (no L1/L2/L3/L4 rule for Core (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `RLblView`

```rust
pub enum RLblView {
    Tau,
    MemOp { thread_id: nat, vaddr: nat, op: MemOp },
    MapStart { thread_id: nat, vaddr: nat, pte: <PTE as View>::V },
    MapEnd { thread_id: nat, vaddr: nat, result: Result<(), ()> },
    UnmapStart { thread_id: nat, vaddr: nat },
    UnmapEnd { thread_id: nat, vaddr: nat, result: Result<(), ()> },
    AckShootdownIPI { core: Core },
}

impl View for RLbl {
    type V = RLblView;
    closed spec fn view(&self) -> RLblView {
        match self {
            RLbl::Tau => RLblView::Tau,
            RLbl::MemOp { thread_id, vaddr, op } =>
                RLblView::MemOp { thread_id: *thread_id, vaddr: *vaddr, op: *op },
            RLbl::MapStart { thread_id, vaddr, pte } =>
                RLblView::MapStart { thread_id: *thread_id, vaddr: *vaddr, pte: pte@ },
            RLbl::MapEnd { thread_id, vaddr, result } =>
                RLblView::MapEnd { thread_id: *thread_id, vaddr: *vaddr, result: *result },
            RLbl::UnmapStart { thread_id, vaddr } =>
                RLblView::UnmapStart { thread_id: *thread_id, vaddr: *vaddr },
            RLbl::UnmapEnd { thread_id, vaddr, result } =>
                RLblView::UnmapEnd { thread_id: *thread_id, vaddr: *vaddr, result: *result },
            RLbl::AckShootdownIPI { core } =>
                RLblView::AckShootdownIPI { core: *core },
        }
    }
}
```

Generator's rationale: RLbl is a transition-label enum whose every field (thread_id, vaddr, op, pte, result, core) is consulted by the spec, so the view mirrors the variant structure rather than dropping anything. nat values are their own view; MemOp and Core are uncovered leaves whose structural equality is already semantic so we copy them as-is; Result<(),()> is composed entirely of primitives; PTE is projected through its own View so allocator-opaque internals (e.g. raw frame pointers inside a page-table entry) don't produce spurious inequality witnesses.
