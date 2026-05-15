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

Qualified name: `PageEntry`
Short name: `PageEntry`

```rust
pub struct PageEntry {
    pub addr: PAddr,
    pub perm: PageEntryPerm,
    // pub ps: bool,
}
```

## Dependency views already in scope

  - PAddr: L2 → usize  (alias PAddr → usize (primitive))
  - PageEntryPerm: uncovered (no L1/L2/L3/L4 rule for PageEntryPerm (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `PageEntryView`

```rust
pub struct PageEntryView { pub addr: usize, pub perm: PageEntryPerm }

impl View for PageEntry {
    type V = PageEntryView;
    closed spec fn view(&self) -> PageEntryView {
        PageEntryView { addr: self.addr, perm: self.perm }
    }
}
```

Generator's rationale: PAddr is a type alias for the primitive usize, so addr is taken structurally without `@`. PageEntryPerm is an uncovered leaf type with no resolved view, so we keep it as-is (treating its structural equality as semantic, analogous to the PageState case in the example). Both public fields are retained because they are the only spec-observable dimensions of a page-table entry.
