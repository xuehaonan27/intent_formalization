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

Qualified name: `CSingleMessage`
Short name: `CSingleMessage`

```rust
pub enum CSingleMessage {
    Message { seqno: u64, dst: EndPoint, m: CMessage },
    Ack { ack_seqno: u64 },
    InvalidMessage,
}
```

## Dependency views already in scope

  - EndPoint: uncovered (no L1/L2/L3/L4 rule for EndPoint (kind=leaf))
  - CMessage: uncovered (no L1/L2/L3/L4 rule for CMessage (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `CSingleMessageView`

```rust
pub enum CSingleMessageView {
    Message { seqno: u64, dst: <EndPoint as View>::V, m: <CMessage as View>::V },
    Ack { ack_seqno: u64 },
    InvalidMessage,
}

impl View for CSingleMessage {
    type V = CSingleMessageView;
    closed spec fn view(&self) -> CSingleMessageView {
        match self {
            CSingleMessage::Message { seqno, dst, m } => CSingleMessageView::Message { seqno: *seqno, dst: dst@, m: m@ },
            CSingleMessage::Ack { ack_seqno } => CSingleMessageView::Ack { ack_seqno: *ack_seqno },
            CSingleMessage::InvalidMessage => CSingleMessageView::InvalidMessage,
        }
    }
}
```

Generator's rationale: CSingleMessage is a three-variant tagged union from the IronKV reliable-transport layer; every variant payload is spec-meaningful (sequence numbers govern delivery ordering, the destination endpoint and inner CMessage define the packet's semantic content), so the projection is a parallel CSingleMessageView enum that keeps all variants and fields. The two uncovered user-type fields (EndPoint, CMessage) are projected through their (to-be-synthesised) View impls via `@` and flagged in depends_on_views_of so a future pass can refine them recursively, following the same convention used in CSingleDelivery and CAckState. The u64 sequence numbers are primitive and carried by identity; InvalidMessage is a payload-less marker variant.
