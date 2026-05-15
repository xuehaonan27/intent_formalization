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

Qualified name: `SingleMessage`
Short name: `SingleMessage`

```rust
pub enum SingleMessage<MT> {
    Message { seqno: nat, dst: AbstractEndPoint, m: MT },
    Ack { ack_seqno: nat },
    InvalidMessage {  },
}
```

## Dependency views already in scope

  - AbstractEndPoint: uncovered (no L1/L2/L3/L4 rule for AbstractEndPoint (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `SingleMessageView<MT>`

```rust
pub enum SingleMessageView<MT: View> {
    Message { seqno: nat, dst: AbstractEndPoint, m: MT::V },
    Ack { ack_seqno: nat },
    InvalidMessage {},
}

impl<MT: View> View for SingleMessage<MT> {
    type V = SingleMessageView<MT>;
    closed spec fn view(&self) -> SingleMessageView<MT> {
        match self {
            SingleMessage::Message { seqno, dst, m } => SingleMessageView::Message { seqno: *seqno, dst: *dst, m: m@ },
            SingleMessage::Ack { ack_seqno } => SingleMessageView::Ack { ack_seqno: *ack_seqno },
            SingleMessage::InvalidMessage {} => SingleMessageView::InvalidMessage {},
        }
    }
}
```

Generator's rationale: Mirror the variant structure as a tagged view enum: the spec-meaningful `nat` counters (`seqno`, `ack_seqno`) are primitives carried by value, `AbstractEndPoint` is a leaf with no resolved `View` impl so it is held structurally (its `==` is treated as semantic by the checker), and the generic payload `m: MT` is projected through `m@` under an `MT: View` bound on the impl so message bodies are compared by their abstract view rather than structurally. `InvalidMessage` is a unit variant with nothing to project.
