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

Qualified name: `rl2::History`
Short name: `History`

```rust
pub struct History {
    pub pending_maps: Map<usize, PTE>,
    pub pending_unmaps: Map<usize, PTE>,
}
```

## Dependency views already in scope

  (no dependency views resolved)

## Candidate view (from the generator LLM)

Declared `viewed_type`: `HistoryView`

```rust
pub struct HistoryView {
    pub pending_maps: Map<usize, <PTE as View>::V>,
    pub pending_unmaps: Map<usize, <PTE as View>::V>,
}

impl View for History {
    type V = HistoryView;
    closed spec fn view(&self) -> HistoryView {
        HistoryView {
            pending_maps: self.pending_maps.map_values(|v: PTE| v@),
            pending_unmaps: self.pending_unmaps.map_values(|v: PTE| v@),
        }
    }
}
```

Generator's rationale: Both fields are kept because the spec constrains pending map/unmap state. Per the rule 'Map<K, V> views to Map<K@, V@>', keys (usize, primitive) pass through as identity, while PTE values are projected recursively via map_values + v@ so semantic equality ignores any allocator-opaque or ghost dimensions inside PTE.
