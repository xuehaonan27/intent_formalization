# verusage spec-determinism — observations (post fix #1 + #2)

Snapshot after commits `93de97f` (named return type) + `168b071`
(impl-context lift + guard-param regex). Run config: per-target
`--timeout 60`, single-file backend.

## Headline numbers

|              | prior (`cfed62f`) | this run | Δ |
|---           | ---:              | ---:     | ---:|
| ok           | 860               | **1235** | +375 |
| ok-w-witness | 837               | **1191** | +354 |
| verus_error  | 779               | **401**  | -378 |
| search_error | 7                 | 10       | +3 |
| runner_crash | 1                 | 1        | 0 |
| n            | 1647              | 1647     | 0 |

Per-project deltas:
- atmosphere: 757 → **1079** ok (+322), 602 → **280** verus_error
- ironkv:     85  → **137** ok (+52),  129 → **74**  verus_error
- memory-allocator: 10 → 11 ok, 2 → 1 verus_error
- nrkernel / vest / storage / anvil-library: unchanged

`anvil-controller` and `node-replication` still show n=0 — neither has
ensures-bearing exec fns under `verified/`, so the discovery walker
correctly emits no targets.

## Remaining verus_error breakdown (n=401)

Categorized by the first compiler diagnostic in each stderr tail.

### atmosphere (280)

| count | first diagnostic | likely cause |
|---:|---|---|
| 173 | `type annotations needed` | `r1 == r2` on generic / inferred-type returns; equal-fn body falls back to `==` and z3 can't pin the type. |
| 38  | `expected one of: identifier, '::', '<', '_', literal, 'const', 'ref', 'mut', '&'` | residual gen_det syntax — likely a return-type form not yet covered (e.g. closure / fn pointer / `impl Trait`). |
| 23  | `mismatched types` | post1/post2 field types vs derived equal-fn signature. |
| 13  | `Dereference this mutable reference …` | `&mut T` return type produces `r1 == r2` over references; needs `*r1 == *r2`. |
| 11  | `expected ','` | gen_det header / where-clause splice still off in some shapes. |
| 10  | `no field 'r1' on type 'Node<T>'` | extracted return shape mistakenly treated as tuple. |
| 7   | rlimit exceeded | timeout/resource — not a tool bug. |

### ironkv (74)

| count | first diagnostic | likely cause |
|---:|---|---|
| 13 | `disallowed: field expression for an opaque datatype` | gen_det reads `pre_self_.field` for opaque structs; needs view-aware substitution (`spec_get_X(pre_self_)`). |
| 9  | `function pointer types` | Verus inherent limitation. |
| 9  | `type 'HostState' cannot be dereferenced` | similar to atmosphere `&mut` case. |
| 4  | `mismatched types` | param/return mismatch in synthesized template. |
| 3  | `no method named 'r1' found for struct 'vstd::seq::Seq<A>'` | tuple-return mis-handling (expected single Seq, treated as tuple). |
| 3  | gen_det syntax | still residual. |

### storage (43)

All 43 are corpus dependency issues (the project depends on a sibling
crate `deps_hack` that doesn't exist standalone). Distribution:

- 26 — `unresolved import 'deps_hack'` / `unresolved module 'deps_hack'`
- 10 — `expected one of '!' or '::', found keyword 'fn'` (proc-macro
  expansion failed because `deps_hack` re-exports `verus!`)
- 7  — fallout from the above (`Self in this scope`, etc.)

Action: add a corpus-side skip rule for storage, or vendor `deps_hack`.

### memory-allocator (1) / nrkernel (2) / anvil-library (1)

- memory-allocator: 1 case using a `*const T` raw pointer — pointer
  semantics still not modeled.
- nrkernel: 2 cases using `Tracked<...>` ghost wrappers in the return
  type — equal-fn falls back to `r1 == r2` which Verus rejects on
  tracked types.
- anvil-library: only target uses `lemma_seq_properties::<V>()`, renamed
  to `group_seq_properties` in current vstd. Corpus vs stdlib version
  mismatch, not a tool bug.

## Witness-soundness reminder (atmosphere)

1079/1079 atmosphere ok cases produce witnesses, almost all of the form

```
ptr == 0  ∧  r1 == 0  ∧  r2 == 0  ∧  !equal(r1, r2)
```

Hypothesis: schema solver doesn't see uninterpreted spec-fn axioms, so
z3 doesn't know `f(x) = f(x)` and "satisfies" the contradiction. **None
of the atmosphere witnesses should be trusted as true nondeterminism
findings until this is investigated separately.**

## Suggested next slices (priority order)

1. **atmosphere "type annotations needed" (173 cases)** — biggest
   single bucket. Likely fixable by emitting a typed `==` (e.g.
   generating `equal_T(r1, r2)` per concrete return type) instead of
   bare `r1 == r2` when the return type is generic-but-resolvable.
2. **`&mut T` return types (~22 across atmosphere + ironkv)** — emit
   `*r1 == *r2` in `_build_equal_fn`.
3. **opaque-datatype field access in ironkv (13 cases)** — switch
   pre/post field reads to view/spec accessors when available.
4. **atmosphere witness soundness audit** — independent of the
   compile-rate work; gates any claim about the corpus.
5. **storage corpus skip rule** — cheap win to clean SUMMARY noise.
