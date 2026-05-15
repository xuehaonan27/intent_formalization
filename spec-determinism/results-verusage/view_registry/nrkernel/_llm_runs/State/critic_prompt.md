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

Qualified name: `rl1::State`
Short name: `State`

```rust
pub struct State {
    pub happy: bool,
    /// Byte-indexed physical (non-page-table) memory
    pub phys_mem: Seq<u8>,
    /// Page table memory
    pub pt_mem: PTMem,
    /// Per-node state (TLBs)
    pub tlbs: Map<Core, Map<usize, PTE>>,
    pub writes: Writes,
    /// Tracks the virtual addresses and entries for which we may see non-atomic results.
    /// If polarity is positive, translations may non-atomically fail.
    /// If polarity is negative, translations may non-atomically succeed.
    pub pending_maps: Map<usize, PTE>,
    pub pending_unmaps: Map<usize, PTE>,
    pub polarity: Polarity,
}
```

## Dependency views already in scope

  - PTMem: uncovered (no L1/L2/L3/L4 rule for PTMem (kind=leaf))
  - Core: uncovered (no L1/L2/L3/L4 rule for Core (kind=leaf))
  - Writes: uncovered (no L1/L2/L3/L4 rule for Writes (kind=leaf))
  - Polarity: uncovered (no L1/L2/L3/L4 rule for Polarity (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `StateView`

```rust
pub struct StateView {
    pub happy: bool,
    pub phys_mem: Seq<u8>,
    pub pt_mem: PTMem,
    pub tlbs: Map<Core, Map<usize, PTE>>,
    pub writes: Writes,
    pub pending_maps: Map<usize, PTE>,
    pub pending_unmaps: Map<usize, PTE>,
    pub polarity: Polarity,
}

impl View for State {
    type V = StateView;
    closed spec fn view(&self) -> StateView {
        StateView {
            happy: self.happy,
            phys_mem: self.phys_mem,
            pt_mem: self.pt_mem,
            tlbs: self.tlbs,
            writes: self.writes,
            pending_maps: self.pending_maps,
            pending_unmaps: self.pending_unmaps,
            polarity: self.polarity,
        }
    }
}
```

Generator's rationale: All eight fields of this refinement-layer kernel state are spec-meaningful (happy invariant flag, byte-addressed physical memory, page-table memory, per-core TLBs, write-tracking, pending map/unmap sets, and polarity), so none are dropped. PTMem, Core, Writes, Polarity, and PTE are leaf types without their own View impls, so they are projected structurally (no `@`); the primitive-typed fields (bool, Seq<u8>, Map<_, _> over usize keys) pass through directly. Wrapping the projection in a dedicated StateView struct lets a later pass swap in `@` recursively once those leaf views are synthesised.
