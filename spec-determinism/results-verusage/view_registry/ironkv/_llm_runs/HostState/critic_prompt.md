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

Qualified name: `HostState`
Short name: `HostState`

```rust
pub struct HostState {
    next_action_index: u64,
    resend_count: u64,
    constants: Constants,
    delegation_map: DelegationMap<CKey>,
    h: CKeyHashMap,
    sd: CSingleDelivery,
    received_packet: Option<CPacket>,
    num_delegations: u64,
    received_requests: Ghost<Seq<AppRequest>>,
}
```

## Dependency views already in scope

  - Constants: uncovered (no L1/L2/L3/L4 rule for Constants (kind=leaf))
  - DelegationMap: uncovered (no L1/L2/L3/L4 rule for DelegationMap (kind=leaf))
  - CKey: uncovered (alias CKey → SHTKey unresolved: no L1/L2/L3/L4 rule for SHTKey (kind=leaf))
  - CKeyHashMap: uncovered (no L1/L2/L3/L4 rule for CKeyHashMap (kind=leaf))
  - CSingleDelivery: uncovered (no L1/L2/L3/L4 rule for CSingleDelivery (kind=leaf))
  - CPacket: uncovered (no L1/L2/L3/L4 rule for CPacket (kind=leaf))
  - AppRequest: uncovered (no L1/L2/L3/L4 rule for AppRequest (kind=leaf))

## Candidate view (from the generator LLM)

Declared `viewed_type`: `HostStateView`

```rust
pub struct HostStateView { pub next_action_index: u64, pub resend_count: u64, pub constants: Constants, pub delegation_map: DelegationMap<CKey>, pub h: CKeyHashMap, pub sd: CSingleDelivery, pub received_packet: Option<CPacket>, pub num_delegations: u64, pub received_requests: Seq<AppRequest> }

impl View for HostState {
    type V = HostStateView;
    closed spec fn view(&self) -> HostStateView {
        HostStateView {
            next_action_index: self.next_action_index,
            resend_count: self.resend_count,
            constants: self.constants,
            delegation_map: self.delegation_map,
            h: self.h,
            sd: self.sd,
            received_packet: self.received_packet,
            num_delegations: self.num_delegations,
            received_requests: self.received_requests@,
        }
    }
}
```

Generator's rationale: Primitive u64 fields are kept by value. All non-primitive dependency types (Constants, DelegationMap<CKey>, CKeyHashMap, CSingleDelivery, Option<CPacket>) are uncovered with no View impl available, so per the example pattern we use them as-is and rely on their structural equality. The Ghost<Seq<AppRequest>> field is unwrapped with a single `@` to expose the inner Seq<AppRequest>; AppRequest itself is uncovered so the sequence elements are kept identity-equal while ordering is preserved (Seq, not Set), since received_requests is a delivery/receipt log where order is spec-meaningful.
