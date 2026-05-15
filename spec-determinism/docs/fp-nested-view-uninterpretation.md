# FP-B: Nested-Container View Uninterpretation

A specific class of false-positive witness our pipeline produces. The
witness looks valid in z3 (the search engine accepts it) and Verus
also rejects the corresponding proof obligation, but the spec is
**semantically deterministic** on the slice — we only see a witness
because `gen_det` rendered the wrong equality at the inner position.

## TL;DR

The chain (using `ironkv::clone_option_vec_u8` as the running example,
ensures `Some(e1) => res.is_some() && e1@ == res.get_Some_0()@`):

1. **Initial search** — z3 evaluates `!det_equal(Some(v1), Some(v2))`
   where the equal-fn unfolds to `v1 == v2` (structural `Vec<u8> ==
   Vec<u8>`). Verus declares this with `assume_specification` (no
   body) at `vstd/std_specs/vec.rs:334`. From z3's POV the predicate
   `<Vec<u8> as PartialEq>::eq` is an uninterpreted function — it
   freely picks a model where `v1 ≠ v2` while their views can be
   anything. → **SAT, witness emitted.**
2. **Narrow refinement** — narrow tightens to `r1@.len()==0,
   r2@.len()==0` (and similarly on the input `ov`). z3 still **SAT**.
   The length narrows constrain the *Seq view*; they do not
   constrain the uninterpreted `Vec == Vec`. Two `Vec<u8>` with the
   same empty view but distinct allocator state stay structurally
   unequal in z3's model.
3. **Hypothetical "instantiation to Vec"** — if codegen had emitted
   the inner comparison as `r1->Some_0@ == r2->Some_0@` (Seq view
   instead of structural Vec), Verus's Seq equality is total and
   decidable. Then under ensures the inner views are forced equal to
   `ov@` on both sides, so transitively `r1->Some_0@ == r2->Some_0@`
   holds, `det_equal` is true, the goal `!det_equal` is **UNSAT**,
   and the witness vanishes. **The "FP" tag means: a sound
   transformation that we control could turn this from SAT into
   UNSAT.**

## Why z3 can't bridge it on its own

Verus exposes view-bridging lemmas in `vstd/std_specs/vec.rs`:

```rust
// line 486
pub broadcast proof fn lemma_vec_obeys_eq_spec<T: PartialEq>(...) {...}
// line 496
pub broadcast proof fn lemma_vec_obeys_view_eq<T: PartialEq + View>(...) {...}
// line 510
pub broadcast proof fn lemma_vec_obeys_deep_eq<T: PartialEq + DeepView>(...) {...}
```

But the default `broadcast use group_vec_axioms` group at line 536–542
includes only `axiom_spec_len`, `axiom_vec_index_decreases`,
`vec_clone_deep_view_proof`, `axiom_spec_into_iter`, and
`axiom_vec_has_resolved`. **None of the obeys_* lemmas are in the
default group.** A user would have to explicitly write `broadcast use
lemma_vec_obeys_view_eq;` at the proof-fn scope to activate the
bridge. Our injected proof fn does not — and even if it did, that
would only paper over the codegen choice rather than fix it.

So the path z3 needs — `Vec eq ⇔ view eq` — is sitting in vstd but
never gets activated under standard scope. From z3's POV the model
freely splits structural and view equality.

## What "实例化" actually means here (purely a typing operation)

The user's intuition: "we should instantiate down to `Vec<u8>` so z3
sees the concrete inner type". The catch is that *the extractor
already knows* `r1->Some_0: Vec<u8>` — typing isn't the problem.
What's missing is that **codegen doesn't carry the
`TypeInfo.spec_view` annotation through nested generic arguments**:

```text
TypeInfo Option<Vec<u8>>
├── kind = OPTION
├── spec_view = None              ← Option itself has no view
└── type_args[0] = TypeInfo Vec<u8>
    ├── kind = SEQ                ← extractor mapped Vec → SEQ
    └── spec_view = Seq<u8>       ← ISSUES #14a set this, but…
```

`gen_det._typeinfo_to_typeexpr` walks the outer kind, sees `OPTION`,
emits `Option<…>`, then recurses on `type_args[0]` by **name**
(`"Vec<u8>"`) — losing the `spec_view` annotation. The recursive
version we plan would walk the *TypeInfo* itself and emit `Seq<u8>`
whenever a child carries `spec_view`. The "instantiation" you want is
just this one structural recursion — no value-level concretisation,
no extra model search. It's a syntactic rewrite of the equal-fn
signature plus a `r.map(|v| v@)` projection at the call site.

## Empirical z3 probe

Run on the `clone_option_vec_u8` smt2 (verus log at
`/tmp/specdet_sf_clone_option_vec_u8_*/verus_log/root.smt2`):

```
   sat     [bare]: ov is Some, r1 is Some, r2 is Some, !equal(r1, r2)
   sat     +ov@.len=0
   sat     +ov@.len=0  +r1@.len=0  +r2@.len=0       ← maximally narrowed witness
   sat     +ov@.len=1  +r1@.len=1  +r2@.len=1
   sat     +ov@.len=3  +r1@.len=3  +r2@.len=3
  unsat    +r1@.len=0  +r2@.len=1                   ← ensures forbids view mismatch
```

Two things to read off:

* Every view-aligned narrowing stays **SAT** — confirming the
  structural inequality is genuinely free in z3's model under the
  current equal-fn.
* Any view-misaligned narrowing (`r1@.len ≠ r2@.len`) is immediately
  **UNSAT** — confirming ensures already forces `r1@ == r2@`.

The second bullet is the crucial bit: **r1 and r2 *cannot* differ in
any spec-observable way**. The only thing the SAT model wiggles is
the spec-unobservable Vec internals — i.e. exactly the gap that the
view-lift codegen fix collapses.

## Litmus test for "real A-2 vs FP-B"

Given any new "A-2"-flagged witness involving a nested `Vec<T>`
(`Option<Vec<T>>`, `Result<…, Vec<T>>`, `Struct{f: Vec<T>}`, …):

1. Locate the position where the equal-fn does structural `==` on
   the nested `Vec<T>`.
2. Probe z3 (or by hand): does ensures force `<inner>@` to be equal
   on both sides? Concretely: try a narrowing where the two outputs'
   `@.len()` differ. If z3 returns **unsat**, every legal witness is
   view-equal at that position, so the surviving inequality is only
   the codegen artefact → **FP-B**.
3. If z3 stays **sat** even with mismatched views, ensures genuinely
   under-constrains the view → **real A-2** (or possibly A-1 on
   re-read).

## Fix plan (deferred — capturing the design)

1. **`gen_det._typeinfo_to_typeexpr`** — make it recursive on
   `TypeInfo`, not flat on `ty.name`. When `child.spec_view is not
   None`, emit the spec-view name instead of the source-level name.
   Cover OPTION/RESULT/MAP/SEQ/TUPLE/STRUCT — wherever
   `_typeinfo_to_typeexpr` recurses today.
2. **Call-site projection** in `build_equal_expr` — when a parameter's
   type has been view-lifted by step 1, emit the corresponding `.map`
   chain or `@` projection so the call passes the lifted form.
   * `Option<Vec<u8>>` → `r.map(|v| v@)` (gives `Option<Seq<u8>>`)
   * `Result<T, Vec<u8>>` → `r.map_err(|e| e@)`
   * `Vec<u8>` (already lifted) → `r@`
3. **Schema regen** — schemas under that position already use the
   `accessor` path (post-#14c), so no schema-side change needed.
4. **Selftest** — extend `narrow.py`'s selftest with a
   `Option<Vec<u8>>` case asserting the projection chain ends in
   `Seq<u8>` comparison.
5. **Corpus rerun** — expect ironkv `clone_option_vec_u8`,
   `clone_optional_value`, and similar to go from `ok_with_witness`
   to plain `ok`. Watch for new regressions where ensures actually
   only pins view (the lift would correctly clear) vs ensures that
   pins structural state (rare; would need an opt-out).

## Cross-references

* `docs/incompleteness-examples.md` §3 (clone_option_vec_u8) — the
  per-case writeup of this FP.
* `spec_determinism/extract/extractor.py:_KNOWN_GENERICS` — where
  `Vec<T>.spec_view = Seq<T>` gets tagged (ISSUES #14a/b).
* `spec_determinism/codegen/gen_det.py:_typeinfo_to_typeexpr` —
  fix site for the recursive view-lift.
* `spec_determinism/schema_search/schemas.py` (post-#14c) — schemas
  already emit `var@` accessor when `ty.spec_view` is set; the
  matching narrow predicate uses the same path so witnesses no longer
  get silently dropped as "pass_untranslatable".
* `vstd/std_specs/vec.rs:334` — `assume_specification` for Vec `==`.
* `vstd/std_specs/vec.rs:496` — `lemma_vec_obeys_view_eq` (the
  bridge that exists but isn't in default scope).
