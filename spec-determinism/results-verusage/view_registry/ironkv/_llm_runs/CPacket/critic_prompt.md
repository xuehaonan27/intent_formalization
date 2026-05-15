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

Qualified name: `CPacket`
Short name: `CPacket`

```rust
pub struct CPacket {
    pub dst: EndPoint,
    pub src: EndPoint,
    pub msg: CSingleMessage,
}
```

## Dependency views already in scope

  - EndPoint: uncovered (no L1/L2/L3/L4 rule for EndPoint (kind=leaf))
  - CSingleMessage: uncovered (no L1/L2/L3/L4 rule for CSingleMessage (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `CPacketView`

```rust
pub struct CPacketView { pub dst: <EndPoint as View>::V, pub src: <EndPoint as View>::V, pub msg: <CSingleMessage as View>::V }

impl View for CPacket {
    type V = CPacketView;
    closed spec fn view(&self) -> CPacketView {
        CPacketView { dst: self.dst@, src: self.src@, msg: self.msg@ }
    }
}
```

Generator's rationale: CPacket is a plain aggregate of dst/src endpoints and the message payload — all three are spec-meaningful (network specs routinely inspect sender, receiver, and message). Each field is projected through its own View impl so semantic equality (e.g., endpoint wire identity, message content modulo representation) is honoured rather than relying on structural `==`.
