# Step-2 sweep false positives — Type B / C / D (2026-06-05)

Companion to [`view-quotient-failure-summary-2026-06-05.en.md`](view-quotient-failure-summary-2026-06-05.en.md). That doc catalogues the **A-class** (real abstract incompleteness) cases. This doc catalogues the **framework-side false positives** — Step 2 sweep failures where the source is actually view-deterministic but the sweep rejected it for tool-internal reasons. Treating them as design defects would be wrong; the fix is in our framework (oracle generator / SMT triggering), not in the user's spec.

| Type | Pattern (one sentence) | Case | Where the fix lives |
|------|------------------------|------|---------------------|
| **B** | Spec is fine; Verus rejects with empty body only because an SMT lemma isn't auto-triggered | [`ArrayVec::len`](#type-b--smt-trigger-gap-1-case) | Step-2 generator: emit standard trigger asserts in the body |
| **C** | Both `view()` *and* the spec-fn under test are `uninterp`; the Step-2 obligation has no semantic content (vacuous) | [`CKeyHashMap::to_vec`](#type-c--vacuous-uninterp-obligation-1-case) | Filter pipeline: skip Step 2 when the spec is `uninterp ∘ uninterp` |
| **D** | Source IS view-deterministic on the spec; the auto-generated oracle (`det_*_equal`) compares the return value **struct-wise** even though the return type carries a `view()` | [`CSendState::get`](#type-d--oracle-struct-eq-on-view-bearing-return-1-case) | Oracle generator: when `R: View`, use `r1@ == r2@` instead of struct `==` |

Methodology recap (also defined in the A-class doc and in `step2-failure-walkthrough-2026-06-05.en.md`): in the otherwise-empty Step-2 body we are allowed **only** `assert` / lemma-call **proof hints** — no `requires` / `ensures` change, no `assume`. If Verus accepts under that rule, the spec is abstract-complete; the sweep flagged a tooling issue and the case is a false positive (Type B/C/D below). If Verus still rejects, the obligation is truly unprovable on the contract domain (Type A).

---

## Type B — SMT trigger gap (1 case)

The spec admits a closed-form proof from the contract alone, but the Verus auto-trigger heuristic doesn't fire the relevant axiom inside an empty proof body. Two hand-written `assert`s drag the lemma in and the obligation closes.

### B.1 `atmosphere::ArrayVec::len`

Source: [`verusage/.../kernel__syscall_io_mmap__impl0__syscall_mmap_to_iommu_table.rs`](../../verusage/source-projects/atmosphere/verified/kernel/kernel__syscall_io_mmap__impl0__syscall_mmap_to_iommu_table.rs) — struct `impl ArrayVec` at [L1928](../../verusage/source-projects/atmosphere/verified/kernel/kernel__syscall_io_mmap__impl0__syscall_mmap_to_iommu_table.rs#L1928), `spec_len` at [L1930](../../verusage/source-projects/atmosphere/verified/kernel/kernel__syscall_io_mmap__impl0__syscall_mmap_to_iommu_table.rs#L1930), `len` at [L1940](../../verusage/source-projects/atmosphere/verified/kernel/kernel__syscall_io_mmap__impl0__syscall_mmap_to_iommu_table.rs#L1940), `view` at [L1959](../../verusage/source-projects/atmosphere/verified/kernel/kernel__syscall_io_mmap__impl0__syscall_mmap_to_iommu_table.rs#L1959), `view_until` at [L1965](../../verusage/source-projects/atmosphere/verified/kernel/kernel__syscall_io_mmap__impl0__syscall_mmap_to_iommu_table.rs#L1965), `wf` at [L1972](../../verusage/source-projects/atmosphere/verified/kernel/kernel__syscall_io_mmap__impl0__syscall_mmap_to_iommu_table.rs#L1972).

```rust
impl<T: Copy, const N: usize> ArrayVec<T, N> {
    pub open spec fn spec_len(&self) -> usize { self.len }

    #[verifier::external_body]
    #[verifier(when_used_as_spec(spec_len))]
    pub fn len(&self) -> (ret: usize)
        requires self.wf(),
        ensures  ret == self.spec_len();

    pub open spec fn view(&self) -> Seq<T>
        recommends self.wf(),
    { self.view_until(self.len() as nat) }

    pub open spec fn view_until(&self, len: nat) -> Seq<T>
        recommends 0 <= len <= self.len() as nat,
    { self.data@.subrange(0, len as int) }

    pub open spec fn wf(&self) -> bool {
        &&& 0 <= N <= usize::MAX
        &&& self.len() <= self.capacity()
        &&& self.data.wf()        // ⇒ data@.len() == N
    }
}
```

The Step-2 obligation is:

```rust
proof fn det_step2_len(self1, self2, r1, r2)
    requires
        self1@ == self2@,
        self1.wf(), self2.wf(),
        r1 == self1.spec_len(),
        r2 == self2.spec_len(),
    ensures r1 == r2,
{ }   // empty body → Verus rejects
```

#### B.1.a Why the sweep rejected it

`view = subrange(0, len)` — to deduce `self1.len == self2.len` from `self1@ == self2@` one needs the `Seq::subrange_len` axiom `subrange(0, n).len() == n` (under `0 ≤ n ≤ seq.len()`). With an empty body, Verus' trigger selection on `subrange(0, n)` inside a `Seq<T>` equality hypothesis does not fire that axiom.

#### B.1.b Why it is a false positive — 2-line hint closes it

```rust
proof fn det_step2_len(self1, self2, r1, r2)
    requires …same as above…
    ensures r1 == r2,
{
    assert(self1.data@.subrange(0, self1.len as int).len() == self1.len as nat);
    assert(self2.data@.subrange(0, self2.len as int).len() == self2.len as nat);
}
// verification results:: 1 verified, 0 errors
```

Hint source: `files/step2_sweep/hint_attempts/c2_h.rs`.

The proof chain is purely contractual: `data.wf() ⇒ data@.len() == N`, `wf ⇒ self.len ≤ N`, `subrange(0, self.len).len() == self.len`, and finally `self1@.len() == self2@.len() ⇒ self1.len == self2.len`. There is no `(s1, s2)` satisfying the contract with `s1@ == s2@` and `s1.len ≠ s2.len`.

#### B.1.c Recommended framework fix

In the Step-2 generator, when the view is of the shape `self.X.subrange(0, k)` (or any `Seq::subrange(_, _, _)`), emit a `Seq::subrange_len` trigger assert per side as a standard prelude in the body. No spec change needed; no per-project ergonomic hint required either.

---

## Type C — Vacuous uninterp obligation (1 case)

The spec function under test and the view are *both* `uninterp`, with no axiom relating them. The Step-2 obligation `s1@ == s2@ ⇒ f(s1) == f(s2)` is then trivially unprovable in both directions — not because the source is non-deterministic, but because the spec carries no information at all. Such an obligation should never have been generated.

### C.1 `ironkv::CKeyHashMap::to_vec`

Source: [`verusage/.../net_sht_v__receive_with_demarshal.rs`](../../verusage/source-projects/ironkv/verified/net_sht_v/net_sht_v__receive_with_demarshal.rs) — `impl CKeyHashMap` block around [L510-L514](../../verusage/source-projects/ironkv/verified/net_sht_v/net_sht_v__receive_with_demarshal.rs#L510).

```rust
impl CKeyHashMap {
    pub uninterp spec fn view(self) -> Map<AbstractKey, Seq<u8>>;
    pub uninterp spec fn spec_to_vec(&self) -> Vec<CKeyKV>;

    #[verifier(when_used_as_spec(spec_to_vec))]
    pub fn to_vec(&self) -> (res: Vec<CKeyKV>)
        ensures res == self.spec_to_vec();
}
```

Step-2 obligation (oracle uses struct-eq because `Vec<CKeyKV>` does not register a `View`):

```rust
proof fn det_step2_to_vec(self1, self2, r1, r2)
    requires
        self1@ == self2@,
        r1 == self1.spec_to_vec(),
        r2 == self2.spec_to_vec(),
    ensures r1 == r2,
{ }
```

#### C.1.a Why this is *not* an A-class incompleteness

Both `view()` and `spec_to_vec()` are `uninterp`. No axiom ties them together; nothing else in the source does either. Concretely:

- the obligation is **unprovable** with hints (no usable equation feeds the `r1 == r2` goal), but
- the obligation is also **unrefutable as a real determinism defect**, because adding any `s1, s2` with `s1@ == s2@` carries no constraint on `s1.spec_to_vec()` vs `s2.spec_to_vec()`. The spec literally does not say what `to_vec` does.

This is the only `uninterp ∘ uninterp` case in the 109-pub-fn corpus. The concrete impl side passes only because `spec_to_vec` returns whatever Verus picks for the uninterp; there is no concrete-side determinism content either.

#### C.1.b Recommended framework fix

In the Step-2 target-filter, skip any `(view, spec_under_test)` pair where **both** are `uninterp` and the source provides no axiom relating them. The check has no semantic content and reporting it as a determinism failure is misleading. (If a future spec adds an abstraction axiom such as `forall a b. a@ == b@ ⇒ a.spec_to_vec() == b.spec_to_vec()`, the case re-enters the sweep automatically.)

---

## Type D — Oracle struct-eq on view-bearing return (1 case)

The source IS view-deterministic on the spec, and the underlying Verus proof is short. But the oracle generator picked **struct-eq** for the return-type equality (`r1 == r2`) even though the return type carries a `view()`. Switching the oracle to view-eq (`r1@ == r2@`, lifted point-wise through `Option`) makes Step 2 discharge.

### D.1 `ironkv::CSendState::get`

Source: [`verusage/.../single_delivery_model_impl2__receive_ack_impl.rs`](../../verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__receive_ack_impl.rs) — struct `CSendState` at [L486](../../verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__receive_ack_impl.rs#L486), `view` at [L499](../../verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__receive_ack_impl.rs#L499), `get` at [L529](../../verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__receive_ack_impl.rs#L529); `CAckState::view` at [L277](../../verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__receive_ack_impl.rs#L277).

```rust
pub struct CSendState { pub epmap: HashMap<EndPoint, CAckState> }

impl CSendState {
    pub open spec fn view(&self) -> SendState<Message> {
        self.epmap@.map_values(|v: CAckState| v@)   // collapses each CAckState to its view
    }

    #[verifier::external_body]
    pub fn get(&self, src: &EndPoint) -> (value: Option<&CAckState>)
        ensures
            value == match HashMap::get_spec(self.epmap@, src@) {
                Some(v) => Some(&v),
                None    => None,
            },
            value is Some ==> self@.contains_key(src@);
}

// Auto-generated oracle (struct-eq on Option<&CAckState>):
spec fn det_get_equal(r1: Option<&CAckState>, r2: Option<&CAckState>) -> bool {
    (r1 is Some == r2 is Some)
    && (r1 is Some ==> r1->Some_0.num_packets_acked == r2->Some_0.num_packets_acked
                    && r1->Some_0.un_acked         == r2->Some_0.un_acked)
}
```

#### D.1.a Why the sweep rejected it

`CSendState::view` projects through `map_values(|v| v@)`. Two `CSendState`s with view-equal `epmap`s can disagree on the underlying `CAckState` fields (`num_packets_acked`, `un_acked`) as long as the projected `AckState`s agree. `det_get_equal` checks the **concrete fields**, so Verus can construct a counterexample.

#### D.1.b Why it is *not* an A-class incompleteness — the source IS view-deterministic

Walk through the views, not the structs:

```
self1@ == self2@
⇒ self1.epmap@.map_values(view) == self2.epmap@.map_values(view)
⇒ ∀ k. (self1.epmap@[k]).view() == (self2.epmap@[k]).view()   -- for shared keys
⇒ get(self1, src).view() == get(self2, src).view()             -- map() lifts View through Option
```

The proof is short; the obligation closes if and only if the oracle compares via view (`r1@ == r2@`, or `r1.map(|v| v@) == r2.map(|v| v@)` for `Option<&_>`). The source itself is fine.

#### D.1.c Recommended framework fix

In the oracle generator, when the return type `R` (or each `T_i` for a tuple / `Option<T>` / `Result<T, E>`) registers a `View` impl, emit `r1@ == r2@` (lifted through `Option`/`Result`) instead of struct `==`. This is consistent with how view-quotient determinism is supposed to behave at the boundary: the return value should be compared in the same abstract universe that the inputs were equated in.

---

## Aggregate summary

| # | Type | proj | type::fn | inlines | family | Root cause | Where fix belongs |
|---|------|------|----------|---------|--------|------------|-------------------|
| 1 | B | atmosphere | `ArrayVec::len` | 10 | length not in view | `Seq::subrange_len` auto-trigger gap | Step-2 generator: standard subrange-len trigger prelude |
| 2 | C | ironkv | `CKeyHashMap::to_vec` | 14 | uninterp not view-stable | `view` and `spec_to_vec` both `uninterp`, no axiom relating them | Sweep filter: skip vacuous uninterp obligations |
| 3 | D | ironkv | `CSendState::get` | 2 | concrete return ignores view | Oracle emits struct-eq for a `View`-bearing return type | Oracle generator: lift to view-eq when `R: View` |

None of the three needs any change to the source spec. All three reductions can be implemented in the framework once and will retroactively delete any further occurrences from the corpus.
