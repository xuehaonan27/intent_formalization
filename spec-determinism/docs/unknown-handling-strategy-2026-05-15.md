# Handling z3 `unknown` in the determinism check — strategy note

> **Status**: discussion document. Idea A wired into the pipeline
> 2026-05-15 (see `spec_determinism/llm_proof/` package and the
> `--use-llm-proof` flag on `verusage_run`).
> **Audience**: anyone working on the schema-search or its post-processing.
> **Context**: empirical findings 2026-05-13 / 14, T0 bucket split landed 2026-05-15.

---

## 1. Background

### 1.1 What the pipeline does today

For each `exec` fn `f` with an `ensures` clause, we generate `injected.rs`
containing a proof obligation:

```rust
proof fn det_<f>(g_neq_tuple: bool, g_<schema_1>: bool, ..., k_<...>: int, ...,
                 <inputs>, r1: T, r2: T)
    requires <ensures_of_f>(<inputs>, r1) && <ensures_of_f>(<inputs>, r2),
    ensures
        ({ <expanded ensures-conjunction over r1 and r2> })
            ==> det_<f>_equal(r1, r2),
{
    if g_<schema_1> { assume(<schema_1>); }
    ...
    if g_neq_tuple { assume(!det_<f>_equal(r1, r2)); }
}
```

Verus emits SMT2 for this. The schema-search reloads that SMT2 into a fresh
`z3.Solver`, enables `g_neq_tuple` (and optionally narrower schema guards),
and calls `solver.check()`:

  * `unsat` → no counterexample exists under the enabled refinements → `f`
    is deterministic on that slice (`ok_proved` at the corpus level).
  * `sat`   → z3 produced a concrete `(r1, r2)` witnessing nondeterminism
    (`ok_witness`).
  * `unknown` → z3 surrendered; nothing concluded (`ok_inconclusive`).

### 1.2 Empirical state of the `unknown` bucket

Pilot (2026-05-13/14) re-ran z3 on every artifact reported as
`ok_with_witness` in the corpus snapshot:

| Project          | unknowns | sat | unsat |
| ---              | ---:     | ---:| ---:  |
| atmosphere       | 257      | 0   | 0     |
| ironkv           | 76       | 0   | 0     |
| memory-allocator | 9        | 0   | 0     |
| **total**        | **342**  | **0** | **0** |

→ The entire historical "witness" bucket is **100 % z3 `unknown`**, not
real witnesses. The "we find hundreds of nondeterminism witnesses" claim
must be retracted; the corpus actually finds **zero confirmed witnesses**
to date.

### 1.3 Sub-population breakdown (atmosphere unknowns, n=257)

| `n_schemas` band | share  | meaning                                       |
| ---              | ---:   | ---                                           |
| `==1`            | 18.7 % | only `g_neq_tuple` — zero refinement vocabulary |
| 2–5              | 6.6 %  | minimal refinement                            |
| 6–19             | 2.7 %  | sweet spot for sampling                       |
| 20–50            | 2.7 %  | sweet spot for sampling                       |
| 51–200           | 47.1 % | dominant, mixed                               |
| `>200`           | 22.2 % | rarely closed even at K=100                   |

Hand-pilot of 37 cases × 30–200 samples (K=10–100):

  * 2/5 cross-sectional + 4/20 random + 6/12 stratified = **~25–30 %**
    flipped to 200/200 `unsat` under deep sampling alone.
  * 0 cases produced any `sat`.
  * The `n_schemas==1` and the largest-vocab cases stayed `unknown` even
    at K=100.

---

## 2. The case study — `resolve_pagetable_mapping`

A representative `n_schemas=25` case from atmosphere; sampling closed it
200/200 in the pilot. Useful as a concrete reference for both ideas.

### 2.1 The function and its determinism question

```rust
// (paraphrased)
spec fn resolve_pagetable_mapping(self_: MemoryManager, pcid: Pcid, va: VAddr)
    -> Option<PageEntry>
    ensures {
        let m = self_.get_pagetable_by_pcid(pcid).unwrap().mapping_4k();
        m.dom().contains(va) == result.is_Some()
        && (result.is_Some() ==> m[va] == page_entry_to_map_entry(&result.unwrap()))
    }
```

Two callers with the same `(self_, pcid, va)` get `r1` and `r2`. We want
to prove they're equal componentwise (Option-tag + `addr` + 5 bool perm
bits).

### 2.2 Why z3 R0 returns `unknown`

The ensures only constrains `result` *via* `page_entry_to_map_entry`:

```rust
#[verifier(when_used_as_spec(spec_page_entry_to_map_entry))]
pub fn page_entry_to_map_entry(p: &PageEntry) -> (ret: MapEntry)
    ensures ret =~= spec_page_entry_to_map_entry(p),
{ unimplemented!() }
```

So we know `spec_page_entry_to_map_entry(r1) == m[va] == spec_page_entry_to_map_entry(r2)`
but we **do not** know whether `spec_page_entry_to_map_entry` is
**injective**. Without that axiom (or a body for the function that z3
can reason about), z3 cannot rule out `r1 ≠ r2` projecting to the same
`MapEntry`. → R0 = `unknown`.

### 2.3 The 24 schemas + 1 NEQ guard

```text
g_r1_is_Some                              g_r2_is_Some
g_r1_is_None                              g_r2_is_None
g_r1__Some_0_perm_present_is_true         g_r2__Some_0_perm_present_is_true
g_r1__Some_0_perm_present_is_false        g_r2__Some_0_perm_present_is_false
g_r1__Some_0_perm_ps_is_true              g_r2__Some_0_perm_ps_is_true
g_r1__Some_0_perm_ps_is_false             g_r2__Some_0_perm_ps_is_false
g_r1__Some_0_perm_write_is_true           g_r2__Some_0_perm_write_is_true
g_r1__Some_0_perm_write_is_false          g_r2__Some_0_perm_write_is_false
g_r1__Some_0_perm_execute_disable_is_true g_r2__Some_0_perm_execute_disable_is_true
g_r1__Some_0_perm_execute_disable_is_false g_r2__Some_0_perm_execute_disable_is_false
g_r1__Some_0_perm_user_is_true            g_r2__Some_0_perm_user_is_true
g_r1__Some_0_perm_user_is_false           g_r2__Some_0_perm_user_is_false
g_neq_tuple
```

All `bool_eq` schemas (no `k_param`). Note that `addr: PAddr` (=`usize`) is
**not** in the schema vocabulary — that's a likely contributor to
"`unknown`"; we have no way of pinning `r1.addr` or `r2.addr`.

---

## 3. Idea B — deep sampling at z3 level

### 3.1 Mechanism

After R0 returns `unknown`, run **N=20–50 deep samples**, each enabling
**K=10–100 schema guards** simultaneously and calling `solver.check()`
once. Each guard is `solver.assert(g_xxx)` (and `solver.assert(k_xxx ==
value)` for schemas with `k` slots).

### 3.2 Strategy applied to the case

For `resolve_pagetable_mapping`, sampling enabled 5–10 of the 24 bool
guards at a time. Closes 200/200 as `unsat`.

### 3.3 Why this works (when it works)

By pinning many bool guards at once, the solver doesn't have to do open
case analysis at quantifier instantiation. With the ensures saying

  `spec_pte_to_map_entry(r1) == m[va]`
  `spec_pte_to_map_entry(r2) == m[va]`

and pinned guards like `r1.perm.present = true` and `r2.perm.present =
true`, z3 sees the lhs-rhs equation and, **if** `spec_pte_to_map_entry`'s
SMT encoding is field-projecting (which it likely is for bitfield
encoding), z3 immediately derives `r2.perm.present = true`. Repeat over
all 5 bools and the `addr` field via the M[va] constraint. Conclusion:
`unsat`.

### 3.4 Open risks for Idea B

  * **Vacuous unsat from contradictory schemas.** Enable both
    `g_r1__perm_present_is_true` *and* `g_r1__perm_present_is_false` →
    contradictory premise → trivially `unsat`. Our deduper (one guard
    per `(symbol, kind)`) usually avoids this, but stratified random
    can still produce e.g. `r1.perm.present=true ∧ r2.perm.present=false`
    which together with the equality chain forces precondition unsat,
    not a real proof. **Required mitigation**: every claimed `unsat`
    must be paired with a *consistency* check: `solver.check(*assumes,
    *witness_negation_negated)` must be `sat` for the proof to be valid.
    Currently NOT implemented; needs to be part of Idea B design.

  * **Schema vocabulary blind spots.** `r1.addr` (a `usize`) is not
    pinned by any of the bool schemas above. Sampling can close this
    case only because `addr` is forced by the `m[va]` equation; a case
    where the missing field is independent of the equation would not
    close.

  * **No effect on `n_schemas==1`** (18.7 % of corpus).

### 3.5 Cost model

z3 `solver.check()` over the reloaded smt2: ~100–500 ms.
N=50 samples per case: 5–30 s per case wall time.
Parallel across cases: linear with cores. Per-case state: in-memory.
No external services. Fully deterministic given (seed, schema list).

---

## 4. Idea A — LLM-written Verus proof annotations

### 4.1 Mechanism

For each R0-unknown case, ask an LLM to insert **proof annotations** into
the body of `det_<f>` *between* the existing `if g_xxx { assume(...) }`
lines and the final `if g_neq_tuple { assume(!det_equal); }`. Then re-run
Verus on the modified file. Repeat up to K=3 times with the previous
attempt's error tail as feedback.

The LLM-rewritten body might be:

```rust
proof fn det_resolve_pagetable_mapping(... existing args ...)
    requires self_.wf(), self_.pcid_active(pcid), va_4k_valid(va),
    ensures <existing ensures>,
{
    // (existing assume body — unchanged)
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1__Some_0_perm_present_is_true { assume(r1 is Some); assume(r1->Some_0.perm.present == true); }
    // ... 22 more lines ...
    if g_neq_tuple { assume(!det_resolve_pagetable_mapping_equal(r1, r2)); }

    // ====== LLM-INSERTED PROOF HINTS ======

    // Bind the shared map state.
    let m = self_.get_pagetable_by_pcid(pcid).unwrap().mapping_4k();

    // Case split on Option tag; both branches share the same fate.
    if m.dom().contains(va) {
        assert(r1 is Some);
        assert(r2 is Some);
        let p1 = r1->Some_0;
        let p2 = r2->Some_0;

        // Both project to the same map slot ⇒ same MapEntry.
        assert(page_entry_to_map_entry(&p1) == m[va]);
        assert(page_entry_to_map_entry(&p2) == m[va]);
        assert(page_entry_to_map_entry(&p1) == page_entry_to_map_entry(&p2));

        // Componentwise injectivity — this is the critical step.
        // (THIS is where the LLM's freedom either lands a real lemma call
        //  or, more honestly, exposes the gap in the spec.)
        assert(p1.addr == p2.addr) by {
            // hope #1: appeal to MapEntry's bitfield decoding.
            // hope #2: invoke a lemma if one is in scope.
            // realistic outcome: Verus rejects — the spec is genuinely
            // under-constrained, and the LLM cannot fake it.
        };
        assert(p1.perm.present == p2.perm.present) by { /* … */ };
        // … etc.
    } else {
        assert(r1 is None);
        assert(r2 is None);
        // det_equal trivially holds when both None.
    }
}
```

### 4.2 Two modes

Because the determinism check semantically asks *both* "is `f`
deterministic?" *and* "if not, give a witness", Idea A has two sub-modes:

  * **A-prove**: LLM writes `assert / by / reveal / lemma_<x>(...)` to
    push the determinism proof through. Goal: Verus accepts → bucket as
    `ok_proved_llm`.
  * **A-witness**: LLM writes a `proof { let r1 = … ; let r2 = … ;
    assert(<ensures>(r1)); assert(<ensures>(r2)); assert(!det_equal(r1,
    r2)); }` block constructing a concrete counterexample. Goal: Verus
    accepts → bucket as `ok_witness_llm`.

The pipeline tries A-prove first (since 100 % of the historical
`unknown` bucket is empirically deterministic). A-witness is the
fallback for the rare case where the LLM rejects the deterministic
hypothesis and offers a concrete counterexample instead.

### 4.3 Sandbox (REQUIRED)

The LLM has every incentive to "succeed" by smuggling an
`assume(false)`. Sandboxing must be enforced **before** the file is
shipped to Verus:

| Token / construct                          | allowed? | rationale                                  |
| ---                                        | ---      | ---                                        |
| `assert(...)`, `assert ... by { ... }`     | ✅        | sound proof step                           |
| `assert forall \| ... \| ... by { ... }`   | ✅        | quantifier hint                            |
| `reveal(fn_name)`, `reveal_with_fuel(...)` | ✅        | opens opaque spec fns                      |
| `broadcast use lemma_*;`                   | ✅        | brings axioms into scope                   |
| `lemma_xxx::<T>(...)` (callsite only)      | ✅        | invokes an existing lemma                  |
| `proof { ... }` blocks                     | ✅        | normal proof scoping                       |
| `let` / `if` / `match` (plain bindings)    | ✅        | unfolding the goal                         |
| `assume(...)`                              | ❌        | NEVER: smuggles unfounded facts            |
| `admit()`                                  | ❌        | NEVER                                      |
| `unimplemented!()`, `unreachable!()`       | ❌        | bypasses proof                             |
| `#[verifier::external_body]`               | ❌        | drops proof obligation                     |
| `assume_specification`                     | ❌        | re-axiomatises arbitrary fn                |
| `pub spec fn / proof fn` (new definitions) | ❌        | restrict to body of existing det fn        |

Implementation: lex-level scan after LLM response, reject on any
blacklisted token; do not rely solely on Verus rejecting the file (Verus
will accept many uses of `assume` silently in proof bodies).

#### 4.3.1 Empirical confirmation (2026-05-15)

We ran five variants of the minimal trigger repro (`array_view.rs`
shape, see `docs/examples/idea_a_set_owning_container/`) to confirm the
allowlist is non-optional. Each variant injects one "bad proof" pattern
into the body of an otherwise-passing proof fn; we captured the SMT log
(`verus --log smt --log-dir`) and ran the standalone z3 binary on each
`root.smt2`. Results:

| Variant                             | Verus verdict             | z3 check-sat sequence                |
| ---                                 | ---                       | ---                                  |
| (control) good proof                | ✓ 2 verified 0 errors     | `unsat, unsat`                       |
| `assert(false);`                    | ✗ 1 error: assertion fail | `unsat, unknown, unsat, unsat`       |
| `assert(P); assert(¬P);` (contrad.) | ✗ 1 error: assertion fail | `unsat, unknown, unknown, unsat`     |
| wrong unprovable assert             | ✗ 1 error: assertion fail | `unsat, unknown, unsat, unknown, unsat` |
| **`assume(false);`** ⚠              | **✓ 2 verified 0 errors** | **`unsat, unsat`**                   |

Two takeaways:

  1. **For `assert`-based bad proofs, z3 returns `unknown` (not `sat`)**
     on the failing query — the quantifiers in `H` prevent z3 from
     constructing a clean counter-example — but Verus treats every
     non-`unsat` verdict as a failed obligation, so the user sees an
     `assertion failed` error. **There is no way for a bad `assert`
     chain to silently pass.** The proof pipeline can trust Verus's
     accept/reject on assert-only programs.
  2. **`assume(P)` does NOT generate a check-sat for `P`** — it directly
     adds `P` to z3's context. `assume(false);` thus makes every
     downstream query trivially `unsat`, and Verus reports `2 verified,
     0 errors`. This is the soundness hole the allowlist exists to
     close. **The lex-level scan is the only defense; Verus will not
     catch it.**

Also note: a wrong assertion can **propagate downstream** (variant 4: a
second, later assertion also goes from `unsat` to `unknown` because the
unproven fact is still added to context and corrupts later reasoning).
This means the iteration feedback loop (§4.5) should always show the
LLM **the first failing assert**, not just "verification failed".

### 4.4 Cost model

Per case, an A-prove attempt costs:

  * 1 LLM call (~2–5 s + tokens).
  * 1 Verus run on the rewritten injected.rs (~20–60 s — full pipeline).
  * Up to K=3 iterations on failure.

So a single case is 1–3 minutes wall time, $0.01–0.10 in LLM tokens.
Compare to Idea B which is 5–30 s, $0.

### 4.5 Open questions

  * **Prompt format**: does the LLM see the full `det_<f>` body, or just
    the spec fn and ensures? What context window for axiom-discovery?
  * **Axiom retrieval**: should we pre-extract a list of `proof fn
    lemma_*` in the crate and offer it to the LLM as a tool? Otherwise
    the LLM has to guess names.
  * **Iteration feedback**: on Verus reject, do we pass the error
    message verbatim, structurally parse, or just say "try again"?
  * **Confidence threshold**: how many failed A-prove rounds before
    giving up and trying A-witness?

---

## 5. Comparison

| Dimension                            | Idea B (sampling)                   | Idea A (LLM proof)              |
| ---                                  | ---                                 | ---                             |
| Closes by                            | z3 unsat under refined assumptions  | Verus accept of LLM-rewritten   |
| Trust level                          | medium (depends on `schema_ctx` fidelity + consistency check) | high (Verus full pipeline)     |
| Cost per case                        | 5–30 s, $0                          | 1–3 min, $0.01–0.10             |
| Parallelism                          | embarrassingly parallel             | LLM rate-limited                |
| Determinism                          | reproducible (seeded)               | non-deterministic               |
| Coverage (pilot)                     | ~25–30 % of unknown bucket          | not yet measured                |
| Coverage on `n_schemas==1`           | 0 % (no vocabulary)                 | potentially OK (LLM independent of schema) |
| Coverage on `n_schemas>200`          | poor (1 large case still unknown @ K=100) | potentially OK            |
| Failure mode                         | vacuous unsat (contradictory schemas) | LLM cheats with assume/admit  |
| Mitigation                           | consistency check, anti-contradiction sampling | lexer-level sandbox    |
| Implementation                       | wrap `run_schema_search` (2–3 d)    | prompt + sandbox + retry loop (5–7 d) |
| External deps                        | none                                | LLM provider                    |
| Onboarding for new types             | needs richer schema vocab           | LLM picks up from context       |

---

## 6. Cooperation — the proposed pipeline

```
       ┌──────────────────────────────────────┐
   R0  │ solver.check() on baseline smt2      │
       └─────┬────────────────────────────────┘
             │
   ┌─────────┴─────────┬───────────────────────┐
   │                   │                       │
   ▼                   ▼                       ▼
 unsat               sat                    unknown
   │                   │                       │
 ok_proved        ok_witness                   │
   │              + extract model              │
                                               ▼
                              ┌──────────────────────────────────┐
                              │ Idea B — deep sampling K-sweep    │
                              │ K ∈ {10, 20, 50, 100},  N=20–50    │
                              │ + consistency check on each unsat │
                              └─────┬─────────────────────────────┘
                                    │
                ┌───────────────────┼─────────────────┐
                ▼                   ▼                 ▼
            unsat              sat              unknown / vacuous
              │                  │                    │
   ok_proved_sampled    ok_witness_sampled            ▼
                                       ┌──────────────────────────────┐
                                       │ Idea A — LLM proof loop       │
                                       │ K=3 retries, sandboxed         │
                                       │ A-prove first, A-witness fallback │
                                       └──────┬───────────────────────┘
                                              │
                       ┌──────────────────────┼──────────────────────┐
                       ▼                      ▼                      ▼
                Verus accept          Verus accept           K retries failed
                (A-prove)             (A-witness)                  │
                       │                      │                    ▼
              ok_proved_llm          ok_witness_llm        ok_inconclusive
                                                          (needs_human_review)
```

### 6.1 Why this ordering

  * **B first** is cheap and parallel; closes the easy 25–30 % without
    LLM cost.
  * **B's vacuous-unsat trap** is caught by the consistency check;
    suspect cases flow into A.
  * **A picks up** the hard core (large fns, n_schemas==1, structurally
    quantified specs).
  * Anything still failing after A becomes a small auditable
    `needs_human_review` bucket — these are typically real spec gaps
    (missing axioms, opaque external types).

### 6.2 Cross-feeding signal

  * B emits a `solver.unsat_core()` on success — the minimal schema set
    that closed the goal. **Feed this to A as a prompt hint**: "here are
    the bool guards z3 found relevant; consider asserting their content
    explicitly."
  * A's LLM output, when successful and audited, gives us hand-written
    `lemma_*` calls that can be hoisted into a project-level **lemma
    library**. Next corpus run, B benefits from the broader axiom set.

---

## 7. Implementation order (recommended)

1. ✅ **T0** — landed 2026-05-15. ok_inconclusive bucket + r0_z3 persisted.
2. **B-pilot validation**: re-run the 25–30 % closure on a wider sample
   (100+ cases), add the consistency check, measure false-positive
   vacuous-unsat rate. Decide if B is worth productionising.
3. **B-impl**: wrap `run_schema_search` to call a `deep_sweep` phase
   after R0 unknown; persist `r0_z3="unknown"` but final
   `effective_z3="unsat" / "sat" / "unknown"`. Add `unsat_core` to
   trace.
4. **Audit `n_schemas==1`**: pick 3 of the 48 atmosphere cases (e.g.
   `alloc_and_map_2m::pop`, `add_io_mapping_4k`,
   `pagemap::impl0::init`) and trace `enumerate_schemas` to find the
   first opaque type. Decide if the fix is in `enumerate_schemas` or
   the view registry.
5. **A-pilot**: hand-write proof annotations for the same 5 unknowns
   from the sampling pilot (without LLM) to calibrate what's achievable
   and identify required lemma names. Outcome: yes/no go on
   productionising A.
6. **A-impl**: prompt + sandbox + retry loop; integrate as the
   B-fallback.
7. **Corpus rebuild + paper retraction**: re-run on all projects,
   publish the corrected (smaller, real) witness count.

---

## 8. What `unknown` actually means — a clarifying note

We've conflated three different reasons for `unknown` in casual
conversation. The strategies above respond to different ones:

| Sub-cause                                            | What helps    |
| ---                                                  | ---           |
| Quantifier-instantiation failure (z3 can't trigger)  | B (pin guards) > A (assert intermediate facts) |
| Missing axiom in the spec (e.g. injectivity)         | A (call/write lemma) > B (won't close) |
| Schema vocabulary gap (`n_schemas==1`)               | enumerate_schemas fix > A > B (B fails) |
| Genuine nondeterminism (which we haven't seen yet)   | A-witness > B (sat from sampling) |

This is the real reason we want both ideas; they're not redundant.

---

## 9. Decisions still pending

  * **B**: is the consistency check sufficient to trust B's `unsat`, or
    do we additionally require an unsat-core of size ≥ N to filter out
    vacuous closures?
  * **A**: full Verus run per iteration, or just z3 over the LLM-rewritten
    smt2 (skip the rust frontend)? The latter is 10× faster but cheaper
    safety.
  * **A**: model choice (proof quality vs. cost). Probably the strongest
    available; cost is dominated by Verus runtime, not tokens.
  * **scope**: do we tackle the 120 atmosphere `verus_error` codegen bugs
    (PR-F class) before or after this? They block ~9 % of atmosphere
    targets independently.
