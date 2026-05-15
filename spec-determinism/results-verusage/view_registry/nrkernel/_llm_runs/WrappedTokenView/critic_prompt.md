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

Qualified name: `WrappedTokenView`
Short name: `WrappedTokenView`

```rust
pub struct WrappedTokenView {
    pub orig_st: os::State,
    pub args: OpArgs,
    pub change_made: bool,
    pub regions: Map<MemRegion, Seq<usize>>,
    /// We also keep the flat memory directly because this is what the MMU's interpretation is
    /// defined on.
    pub pt_mem: crate::PTMem,
    // result is only relevant for mapping (TODO: and maybe we can get rid of it there?)
    pub result: Result<(),()>,
}
```

## Dependency views already in scope

  - State: uncovered (no L1/L2/L3/L4 rule for State (kind=leaf))
  - OpArgs: uncovered (no L1/L2/L3/L4 rule for OpArgs (kind=leaf))
  - MemRegion: uncovered (no L1/L2/L3/L4 rule for MemRegion (kind=leaf))
  - PTMem: uncovered (no L1/L2/L3/L4 rule for PTMem (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `WrappedTokenView`

```rust
impl View for WrappedTokenView {
    type V = WrappedTokenView;
    closed spec fn view(&self) -> WrappedTokenView {
        WrappedTokenView {
            orig_st: self.orig_st,
            args: self.args,
            change_made: self.change_made,
            regions: self.regions,
            pt_mem: self.pt_mem,
            result: self.result,
        }
    }
}
```

Generator's rationale: All fields are spec-meaningful: there are no raw pointers, no Ghost/Tracked wrappers, and no obviously-opaque allocator handles to drop. Because os::State, OpArgs, MemRegion, and crate::PTMem are uncovered leaf types with no View impl, we cannot recursively project them through `@`, so the view is the identity projection over WrappedTokenView's own fields (Map and Seq carry their identity-typed contents through unchanged).
