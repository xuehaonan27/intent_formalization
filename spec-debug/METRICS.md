# spec-debug — Metrics Design (draft, under discussion)

Purpose: enumerate the candidate metrics for scoring an LLM-produced
spec patch, with the *reason* each is needed (grounded in a concrete
failure mode), so that `report.py` can surface the right flags and a
future iterative loop has a ranking signal.

This is design discussion, not a spec. Nothing here is implemented yet.

---

## Organising principle

A good patch must, in order:
1. Pass hard gates (compiles, impl still verifies, signature unchanged).
2. Actually close the **driving** part of the witness (not just collateral).
3. Be shaped right (touches the target function's `ensures`, helpers referenced).
4. Not cheat (no bypass of the checker, no over-specification).

Metrics below map to these layers. We use lexicographic Pareto over
axes, **not** a weighted sum — "closed one more assume" and "edit layer
is correct" are not commensurable.

---

## Axis A — Gap closure (the only positive axis)

| Metric | Question | Why it exists |
|---|---|---|
| `closed_count / total` | How many witness assumes are now ruled out | Direct signal, but case #3 (kernel::from_raw_parts) proved it insufficient alone |
| **`driving_closed / driving_total`** | Of the assumes that actually flow into `equal_fn`, how many closed | Should replace the raw count as primary. bitmap::new has 8 assumes but only 2 are driving; rewarding collateral closure incentivises over-spec |
| `new_witness_driving?` | Does the rerun produce a fresh witness, and is it driving | Catches "fix the exact old witness, leave the underlying gap" patches |
| `rounds_before → rounds_after` | Search-round delta | Spike (slab 67→99) = schema blow-up; collapse to 0 alongside `schemas→0` = bypass flag (case #3) |

**Open question raised in discussion (2026-04-24): gap *validity*
precedes gap closure.** spec-determinism is deterministic; a witness it
emits is only meaningful if the `equal_fn` used to define "same output"
is itself right. If we judge the two outputs in the witness to be
semantically equivalent (the difference is in a field that shouldn't
count), the correct response is **not** to patch the spec — it is to
feed the disagreement back to spec-determinism so it can update its
equality policy / `equal_fn`. See §A.1.

### A.1 Upstream feedback path (proposed)

Before measuring `driving_closed`, classify the witness:
- **Valid gap** — the driving assumes describe a genuinely
  observable behavioural difference under the policy. Proceed with
  normal closure metrics.
- **Policy-spurious gap** — the driving assumes only distinguish
  fields a reasonable caller shouldn't branch on (diagnostic strings,
  allocation order when result is opaque, etc.). Emit a
  `policy_suggestion` pointing back at spec-determinism
  (`errs_equivalent`, `opaque_ok`, or a new knob) and **do not**
  attempt to patch the spec.

Concrete candidate: `kernel::from_raw_parts`'s
`errs_equivalent=False` forces `Err.reason` strings to match. This
is almost certainly over-strict policy. Under this lens case #3
wasn't a spec bug at all and spec-debug's job there is to route the
finding back to spec-determinism, not to paper over it.

---

## Axis B — Structural fit (targets the dangling-helper + wrong-layer failures)

| Metric | Question | Why |
|---|---|---|
| **`edit_layer`** ∈ {target_ensures, target_requires, struct_inv, new_helper, new_assume_spec, other} | Which AST node was modified | case #1/#2/#3 each picked a different wrong layer; discrete classification is more useful than a score |
| **`referenced_from_target_ensures`** | Are newly introduced spec items reachable from the target fn's `ensures` | Direct kill for case #1's dangling helper |
| `touches_target_ensures` (bool) | Did the patch modify the target's ensures at all | Cheap sentinel; False in all three v0 cases |
| `signature_changed` | Return/param types changed | Must always be False |

`edit_layer` and `referenced_from_ensures` are orthogonal: a helper at
module scope is fine if ensures calls it; adding it unreferenced is the
dangling-helper failure.

---

## Axis C — Bypass detection (did the checker still check the same thing)

| Metric | Question | Why |
|---|---|---|
| `symbol_table_stable` | `det_spec.json.symbols` before/after equal | New `assume_specification` can re-point the instrumented symbol (case #3) |
| `equal_fn_def_stable` | `equal_fn` body unchanged when policy unchanged | If equal_fn shifted without a policy change, LLM edited a type that policy expands over |
| `schema_count_before → after` | Narrowing-dimension count | 519 → 0 is smoking gun; mild decrease is normal |
| `rounds==0 AND schemas==0` | Joint flag | Rounds=0 alone is fine (tight spec); combined with no schemas is bypass |

Theme: "changed what is being checked" and "made the thing being
checked tighter" look identical on rounds/closed. Only a structural
before/after snapshot disambiguates them.

---

## Axis D — Over-specification

| Metric | Question | Why |
|---|---|---|
| `collateral_pinned_count` | How many policy-ignored assumes did the LLM pin | Directly tests v0.1 prompt compliance |
| **`literal_bleed`** | Does new `ensures` contain literals taken from `input_narrowing` | Copying `number_of_bits == 8` makes the spec correct only for the witness; subtle but common |
| `requires_tightened` | Was `requires` strengthened | Tightening `requires` closes witnesses by rejecting inputs — turning the bug into an API restriction |

---

## Axis E — Feasibility (strongest anti-LLM-hallucination gate)

| Metric | Question | Why |
|---|---|---|
| **`impl_still_verifies`** | Does the exec impl still satisfy the new ensures via `cargo verus` | If LLM writes `ensures r is Ok` but impl can return Err, Verus rejects — this one gate kills a whole class of fake fixes |
| `ensures_consistent` | Is the new ensures internally contradictory | Largely subsumed by `impl_still_verifies` |

spec-determinism-run already invokes `cargo verus`; we just need to
surface its pass/fail as a distinct axis instead of folding it into
overall success.

---

## Axis F — Stability across samples (§5.4)

| Metric | Question | Why |
|---|---|---|
| `layer_agreement@K` | Do K samples agree on `edit_layer` | Disagreement means the prompt hasn't locked direction |
| `driving_closed_agreement@K` | Std-dev of driving closure across samples | Tests whether single-shot is sufficient |
| `char_diff_pct@K` | Text-level variance | Cheap stability probe |

---

## Proposed composite score (lexicographic)

```
tier 1 (hard gates — must all pass):
    impl_verifies ∧ signature_stable ∧ ¬bypass_flags

tier 2 (primary score — higher is better):
    (driving_closed_ratio,
     edit_layer == target_ensures,
     all_new_items_referenced)

tier 3 (tie-breakers):
    (¬new_witness_driving, ¬literal_bleed, ¬collateral_pinned)
```

"A dominates B" iff tier-1 is no worse and some tier-2 component is
strictly better with none worse — standard Pareto.

---

## Ruled out by v0 data (for record)

- ❌ `verify_pass` alone (all three patches pass)
- ❌ Patch size / minimality as primary signal (smallest was most misdirected)
- ❌ Raw `closed` count alone (case #3's 9/9 may be vacuous)
- ❌ LLM-self-reported confidence / response length
