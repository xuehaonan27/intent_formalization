# vstd 27 unknown audit

## Conclusion

The original 27 `R0 = unknown` targets are fully classified:

| Audit class | Count | Expected final bucket |
|---|---:|---|
| A — deterministic, blocked by tooling | 14 | `complete` after equal/view/proof repair |
| B — intentional nondeterminism | 9 | `incomplete_permitted`, or complete only under an explicit quotient equality |
| C — genuinely underconstrained semantic result | 4 | `incomplete` (possibly documented as permitted design abstraction) |
| D — unresolved | 0 | — |

Seven A-cases (`StringHashMap`) have already been fixed and now produce
`R0 = unsat`. The remaining automated experiment therefore contains 20
unknowns: 7 A, 9 B, and 4 C.

## Per-target classification

| Target | Class | What it should be | Evidence |
|---|---|---|---|
| `atomic::fetch_and@610` | A | Complete | Equal-fn compared opaque `PermissionPtr` identity; comparing pinned `.view()` fields verifies |
| `atomic::fetch_xor@630` | A | Complete | Same as `fetch_and` |
| `atomic::fetch_or@650` | A | Complete | Same as `fetch_and` |
| `raw_ptr::ptr_ref2@1038` | A | Complete under documented observable projections | `value()`, address, and metadata are fixed; opaque provenance/tag is intentionally hidden |
| `thread::thread_id@200` | A | Complete | `IsThread::agrees` proves two same-thread tokens have equal IDs; generated proof omitted the tracked axiom call |
| `cell::new@344` (`InvCell`) | A | Complete under invariant-predicate equality | Both results expose the same `inv(v) <==> f(v)` predicate; raw cell identity is irrelevant |
| `rwlock::acquire_read@620` | A | Complete | `ReadHandle::lemma_readers_match` is the exact missing proof lemma |
| `hash_map::new@209` | A | Complete | StringHashMap view-bound gate rejected unrelated `Value`; fixed, now UNSAT |
| `hash_map::with_capacity@220` | A | Complete | Same StringHashMap view fix |
| `hash_map::reserve@231` | A | Complete | Same StringHashMap view fix |
| `hash_map::insert@264` | A | Complete | Same StringHashMap view fix |
| `hash_map::remove@275` | A | Complete | Same StringHashMap view fix |
| `hash_map::clear@311` | A | Complete | Same StringHashMap view fix |
| `hash_map::union_prefer_right@320` | A | Complete | Same StringHashMap view fix |
| `float::float_cast@127` | B | Intentional/permitted nondeterminism | Source explicitly says "`(possibly) non-deterministic Rust cast`"; relation is uninterpreted |
| `raw_ptr::allocate@908` | B | Intentional/permitted nondeterminism | Identical size/alignment calls can return different allocator addresses/provenance |
| `thread::spawn@107` | B | Intentional/permitted nondeterminism | Fresh handle identity and one-way predicate constraint are not unique |
| `thread::join@27` | B | Intentional/permitted nondeterminism | Closure/handle predicate may admit multiple successful return values |
| `cell::empty@168` | B | Concrete nondeterminism; complete under content quotient | Fresh `CellId` is intentionally unconstrained |
| `cell::new@178` (`PCell`) | B | Concrete nondeterminism; complete under content quotient | Fresh `CellId` is intentionally unconstrained |
| `simple_pptr::empty@347` | B | Concrete nondeterminism; complete under content quotient | Fresh allocator address |
| `simple_pptr::new@386` | B | Concrete nondeterminism; complete under content quotient | Fresh allocator address |
| `rwlock::new@502` | B | Concrete nondeterminism; complete under predicate/content quotient | Embeds fresh PCell and protocol instance identities |
| `cell::replace@359` (`InvCell`) | C | Incomplete | `self.inv(ret)` is a non-functional possible-value predicate; two distinct return values can satisfy it |
| `cell::get@378` (`InvCell`) | C | Incomplete | Same non-functional invariant predicate |
| `rwlock::acquire_write@530` | C | Incomplete/permitted abstraction | Returned current value is constrained only by arbitrary lock invariant |
| `rwlock::into_inner@702` | C | Incomplete | Returned value is constrained only by arbitrary lock invariant |

## A — complete but blocked by tooling

### Atomic permissions

The three atomic fetch specs pin:

- returned pointer through `equal(old(perm).view().value, ret)`;
- final atomic ID;
- final pointer address, provenance, and metadata.

The generated equality used raw `PermissionPtr == PermissionPtr`. The type is
macro-generated, so the source-level extractor and ViewRegistry do not discover
its inherent `view()`. A temporary equal-fn comparing the pinned view fields
verifies all three targets.

### `ptr_ref2`

`SharedReference` intentionally gives a new pointer provenance/tag, but its
public contract fixes:

- `value()`;
- `ptr().addr()`;
- pointer metadata.

Raw wrapper equality is too strong. Equality over these three projections
verifies.

### `thread_id`

The result contains an opaque `ThreadId` and `Tracked<IsThread>`.
`IsThread::agrees` is the trusted same-thread equality axiom. A proof using
tracked result components and calling `agrees` verifies; the generated harness
did neither.

### `InvCell::new`

Two new cells have different hidden identities, but both expose the same
invariant predicate:

```text
forall v. result.inv(v) <==> f(v)
```

Extensional predicate equality verifies; raw struct equality does not.

### `RwLock::acquire_read`

vstd already provides `ReadHandle::lemma_readers_match`, documented to prove
that simultaneous read handles observe the same value. Adding that lemma call
closes the check.

### StringHashMap

The view is `Map<Seq<char>, Value>`. No generic parameter is projected through
`T::V`, but the old L3 gate nevertheless required `Value: View`, rejected the
view, and fell back to raw struct equality. The gate now accepts this concrete
key view; all seven targets verify at R0.

## B — intentional nondeterminism

These are not ordinary missing specs:

- float conversion intentionally uses a possibly nondeterministic relation;
- allocation/fresh-handle constructors intentionally choose identity;
- thread spawn/join intentionally abstract thread and closure execution.

They should be reported as `incomplete_permitted` for concrete identity
equality. If the evaluation chooses a quotient that ignores identity and
observes only abstract content/predicate, the fresh-handle constructors become
complete under that quotient.

## C — genuine semantic underconstraint

`InvCell` and `RwLock` expose an arbitrary invariant predicate rather than a
ghost accessor for the exact current value. A predicate can admit multiple
values:

```text
inv(0) && inv(1)
```

Therefore postconditions of the form `inv(result)` do not uniquely determine
the returned value. This is real specification nondeterminism, even if the
library intentionally uses it for information hiding.

## Pipeline actions

1. Add macro-expanded or synthesized views for atomic `Permission*` types.
2. Add a projection policy for `SharedReference`.
3. Preserve tracked output components and discover applicable axioms such as
   `IsThread::agrees`.
4. Feed `ReadHandle::lemma_readers_match` through the proof-hint/Tier-3 path.
5. Add permitted-nondeterminism rules for allocation, fresh identity,
   float-cast relations, and thread handles.
6. Detect possible-value predicates such as `inv(result)` and classify them as
   genuine/permitted incompleteness rather than solver unknown.
