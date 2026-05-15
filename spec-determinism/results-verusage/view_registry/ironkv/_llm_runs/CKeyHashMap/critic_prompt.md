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


## Target type (ironkv)

Qualified name: `CKeyHashMap`
Short name: `CKeyHashMap`

```rust
pub struct CKeyHashMap {
    m: collections::HashMap<CKey, Vec<u8>>,
}
```

## Dependency views already in scope

  - HashMap: uncovered (no L1/L2/L3/L4 rule for HashMap (kind=leaf))
  - CKey: uncovered (alias CKey → SHTKey unresolved: no L1/L2/L3/L4 rule for SHTKey (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `Map<CKey, Seq<u8>>`

```rust
impl View for CKeyHashMap {
    type V = Map<CKey, Seq<u8>>;
    closed spec fn view(&self) -> Map<CKey, Seq<u8>> {
        self.m@.map_values(|v: Vec<u8>| v@)
    }
}
```

Generator's rationale: CKeyHashMap is a thin wrapper around std::collections::HashMap<CKey, Vec<u8>>; the spec only cares about the abstract key→value relation and the byte content of each value, not the hash-table's bucket layout or Vec's allocator state. We take vstd's HashMap view (Map<CKey, Vec<u8>>) and lift each Vec<u8> value to its Seq<u8> view via map_values. CKey is uncovered (leaf alias for SHTKey), so we leave it at the key position with its structural identity — that matches IronKV's own abstract type Map<AbstractKey, Seq<u8>>.
