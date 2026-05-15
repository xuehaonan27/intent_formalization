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

Qualified name: `AbstractHostState`
Short name: `AbstractHostState`

```rust
pub struct AbstractHostState {
    pub constants: AbstractConstants,
    pub delegation_map: AbstractDelegationMap,
    pub h: Hashtable,
    pub sd: SingleDelivery<Message>,
    pub received_packet: Option<Packet>,
    pub num_delegations: int,
    pub received_requests: Seq<AppRequest>,
}
```

## Dependency views already in scope

  - AbstractConstants: uncovered (no L1/L2/L3/L4 rule for AbstractConstants (kind=leaf))
  - AbstractDelegationMap: uncovered (no L1/L2/L3/L4 rule for AbstractDelegationMap (kind=leaf))
  - Hashtable: L2 → Map<AbstractKey, Seq<u8>>  (alias Hashtable → Map<AbstractKey, AbstractValue> (L1))
  - SingleDelivery: uncovered (no L1/L2/L3/L4 rule for SingleDelivery (kind=leaf))
  - Message: uncovered (no L1/L2/L3/L4 rule for Message (kind=leaf))
  - Packet: uncovered (no L1/L2/L3/L4 rule for Packet (kind=leaf))
  - AppRequest: uncovered (no L1/L2/L3/L4 rule for AppRequest (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `AbstractHostStateView`

```rust
pub struct AbstractHostStateView {
    pub constants: AbstractConstants,
    pub delegation_map: AbstractDelegationMap,
    pub h: Hashtable,
    pub sd: SingleDelivery<Message>,
    pub received_packet: Option<Packet>,
    pub num_delegations: int,
    pub received_requests: Seq<AppRequest>,
}

impl View for AbstractHostState {
    type V = AbstractHostStateView;
    closed spec fn view(&self) -> AbstractHostStateView {
        AbstractHostStateView {
            constants: self.constants,
            delegation_map: self.delegation_map,
            h: self.h,
            sd: self.sd,
            received_packet: self.received_packet,
            num_delegations: self.num_delegations,
            received_requests: self.received_requests,
        }
    }
}
```

Generator's rationale: All seven fields are spec-meaningful pieces of the abstract host state (cluster constants, key-owner delegation map, the K/V hashtable, single-delivery bookkeeping, last received packet, delegation count, and the ordered request log). There are no raw pointers, allocator handles, or ghost wrappers to drop. Every non-primitive dependency (AbstractConstants, AbstractDelegationMap, SingleDelivery<Message>, Option<Packet>, Seq<AppRequest>) is an uncovered leaf at synthesis time, so per the example pattern we project each field by value rather than calling `@`. Hashtable is a transparent alias for Map<AbstractKey, Seq<u8>> whose keys are a leaf type and whose values bottom out in primitives, so its structural identity is already semantic. num_delegations is the spec-primitive `int` and is kept as-is, and received_requests is kept as a Seq because the request log's ordering is part of the spec.
