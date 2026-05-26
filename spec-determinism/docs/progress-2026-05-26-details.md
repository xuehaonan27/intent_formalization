# Progress 2026-05-26 — Details (`verus_error` closeout & crash deep-dive)

Companion to [`progress-2026-05-26.md`](progress-2026-05-26.md). Two
sections that didn't fit in the short progress view:

- §1 verus_error closeout root-cause / fix tables (atmosphere /
  storage / nrkernel)
- §2 Crash example deep-dive (atmosphere `pagetable_map_4k_page`)

## 1. verus_error closeout — root cause / fix classification

Baseline had **94 `verus_error` rows** across atmosphere (49),
storage (43), and nrkernel (2). The closeout cleared 87 via
pipeline-level source rewriters:

| project    | baseline `verus_err` | post-closeout `verus_err` | newly `complete` | newly `incomplete` | newly `unknown` | dropped |
|------------|---------------------:|--------------------------:|-----------------:|-------------------:|----------------:|--------:|
| atmosphere |                   49 |                         0 |               23 |                  0 |              24 |       2 |
| storage    |                   43 |                         7 |               23 |                  2 |              11 |       0 |
| nrkernel   |                    2 |                         0 |                1 |                  0 |               1 |       0 |
| **TOTAL**  |               **94** |                     **7** |           **47** |              **2** |          **36** |   **2** |

(The 2 atmosphere "dropped" entries were extractor false-positives:
fns living inside `/* … */` block comments. The fix now skips those
regions, so the entries vanish from `total` entirely.)

### 1.1 atmosphere (49 → 0) — commit `68a2ac1e`

| bucket | count | root cause | fix |
|--------|------:|------------|-----|
| `View` trait impl missing (`String::View` etc.) | 20 | per-crate `impl View for String` lives in a sibling crate, not visible in single-file mode | `_synthesize_view_trait_impls` derives a stub `View` impl from each type's inherent `spec fn view` |
| `Dereference this mutable reference` | 16 | Verus now refuses bare `&mut` comparisons in spec context (`self == old(self)`, `*p == old(*p)`) | source-level rewriters `_rewrite_self_eq_old_self` + `_rewrite_ref_eq_ref` + `_rewrite_mut_self_in_ensures` produce `*self == *old(self)` / `final(p)` forms |
| E0308 `Tracked(p): Tracked<&mut T>` destructure loses `&mut` | 11 | extractor reset the inner-type `&mut` when normalising the destructure pattern | extractor preserves the inner `&mut`; gen_det auto-`&`-prefixes method-call args for renamed `&mut`-param idents |
| E0425 `spec_va_2m_valid` / `spec_va_1g_valid` not in scope | 2 | extractor scraped fns from inside `/* … */` block comments | extractor skip-list for block-commented regions |

Outcome: 47 of 49 compile cleanly (23 → `complete`, 24 → `unknown`);
2 drop from `total`. Full rerun:
`/tmp/atmosphere_rerun_2026-05-26.json` (`--timeout 180 s`).

### 1.2 storage (43 → 7) — commit `64b1d5fe`

| bucket | count | root cause | fix |
|--------|------:|------------|-----|
| `error[E0432]: unresolved import deps_hack::…` | 43 | sibling proc-macro crate `deps_hack` (provides `PmSized` derive, `pmsized_primitive!` macro, types like `crc64fast::Digest`) is unresolvable in single-file mode | new `_rewrite_deps_hack` shim — strip `use deps_hack::…`, strip `PmSized` from `#[derive(…)]`, drop `pmsized_primitive!(T);` calls, emit stub trait impls (`SpecPmSized` / `UnsafeSpecPmSized` / `PmSized` returning 0) plus `unsafe impl ConstPmSized for T` for primitives. Sound for determinism because r1/r2 resolve to the same stub. |
| `parse error: keyword fn` (10 of 43) | — | helper injection used `rfind("}")` and landed inside the last `unsafe impl ConstPmSized for [T;N]` block instead of `verus! { … }` | brace-aware `_find_verus_block_close` scanner (handles `//`, `/* */`, `"…"`, `'…'`, `r#"…"#`) replaces `rfind("}")` in both `single_file.py` and `llm_proof/prover.py` |
| `S not in scope` on synthesised det fn | — | `_prune_generics` only inspected the param list; generics referenced *only* in `ensures` (e.g. `<S>` in `ensures out as nat == S::spec_align_of()`) got dropped | `sig_for_prune` extended to `params + run1 + run2 + requires_str` |
| `T::spec_from_bytes` not in scope at det call site | — | `closed spec fn` decls inside blanket impls (`impl<T: Bound> Trait for T`) emitted `T::spec_from_bytes` reveals at module scope where `T` is unbound | `classify.closed_spec_fn_qualified_names` tracks `skipped_impl_spans` for blanket impls and drops their decls from the qual map entirely |

Outcome: 36 of 43 compile cleanly (23 → `complete`, 2 →
`incomplete` permitted, 11 → `unknown`). Full rerun:
`/tmp/storage_full_2026-05-26/full_run.json` (`--timeout 60 s`).

> The two real `incomplete` cases (documented separately in
> [`storage-incompleteness-cases-2026-05-26.en.md`](storage-incompleteness-cases-2026-05-26.en.md))
> are `write_setup_metadata` (byte-layout under-specified) and
> `read_log_variables` (`Result<_, E>` error path under-specified).
> The other two `permissive_or`-tagged entries (`serialize_and_write`
> ×2) were spurious classifier hits — z3 proved them unsat, so the
> permissive marker is overridden by the unsat verdict and they
> land in `complete`.

The **7 residual `verus_error`** are inherent source / vstd-version
incompats — not synthesiser bugs:

| residual bucket | count | description |
|-----------------|------:|-------------|
| `Box<S>: SpecEq<S>` not implemented | 4 | original body `out == true_val` with `out: Box<S>`, `true_val: S`; current Verus demands `*out == true_val` |
| `iter.end` on `VerusForLoopWrapper` | 3 | original uses `iter.end` for a named for-loop iterator; current vstd restructured to `iter.iter.end` / `iter.snapshot.end` |

Both buckets would need either a guarded textual rewrite (risky —
false positives on unrelated `.end` / `Box`-comparison sites) or
upstream source updates. Excluded from determinism numerator /
denominator.

### 1.3 nrkernel (2 → 0) — commit `38bd6d8e`

| bucket | count | root cause | fix |
|--------|------:|------------|-----|
| `repr(transparent)` + `Ghost<T>` rejected | 2 | newer rustc promotes `repr_transparent_non_zst_fields` to a hard error; Verus's `Ghost<T>` is a ZST field of an external type with private fields, blocked on structs like `#[repr(transparent)] struct PDE { entry: usize, layer: Ghost<nat> }` | `_allow_repr_transparent_lint` rewriter — when source contains `#[repr(transparent)]`, insert a crate-level `#![allow(repr_transparent_non_zst_fields)]` after BOM/shebang/inner attrs/leading comments. Layout semantics preserved; only the lint is silenced. |

Outcome: both compile cleanly (1 → `complete`, 1 → `unknown`).
Full rerun: `/tmp/nrkernel_rerun/full_run.json` (`--timeout 60 s`).

### 1.4 Pipeline files touched (closeout window)

| file | additions |
|------|-----------|
| `spec_determinism/verus/single_file.py` | `_find_verus_block_close`, `_rewrite_deps_hack` (+ helpers), `_allow_repr_transparent_lint`, `_synthesize_view_trait_impls` header cleanup |
| `spec_determinism/llm_proof/prover.py`  | `_find_verus_block_close` (mirror) |
| `spec_determinism/codegen/gen_det.py`   | `_build_template` — `sig_for_prune` includes `run1 + run2 + requires_str` |
| `spec_determinism/classify.py`          | `_IMPL_HEADER_RE` named-capture, `_impl_generic_param_names`, `closed_spec_fn_qualified_names` `skipped_impl_spans` |
| `spec_determinism/extract/extractor.py` | preserve inner `&mut` on `Tracked(...): Tracked<&mut T>` destructure; skip block-commented fns |

All 3 self-test suites (`extractor`, `gen_det`, `classify`) pass on
the final tree.

## 2. crash example — `atmosphere::pagetable_map_4k_page`

Raw entry in `/tmp/corpus_baseline/atmosphere/full_run.json`:

```json
{
  "project":     "atmosphere",
  "file":        ".../verified/kernel/kernel__create_and_map_pages__impl0__alloc_and_map.rs",
  "function":    "pagetable_map_4k_page",
  "artifact_key": "atmosphere__verified__kernel__kernel__create_and_map_pages__impl0__alloc_and_map__pagetable_map_4k_page",
  "status":      "runner_crash",
  "error":       "subprocess wall timeout 300s",
  "wall_ms":     300035
}
```

Probed with `--keep-tmp` to recover the on-disk artefacts:

| where | value |
|---|---:|
| source ensures (lines 1741–1816) | **76 lines** |
| closed spec fns called from ensures | 8 (`wf`, `get_pagetable_by_pcid`, `get_pagetable_mapping_by_pcid`, `page_closure`, `mapping_4k/2m/1g`, `kernel_entries`) |
| synthesised det fn parameters | **340** |
| synthesised det fn signature size | 56 544 chars |
| synthesised det fn `assume(...)` count | **566** |
| synthesised det fn `forall` count | 12 |
| `reveal(...)` injected | **0** |
| Verus → z3 query (`root.smt2`) | **29.5 MB / 85 292 lines** |
| ↳ `(declare-fun …)` | 851 |
| ↳ `(assert …)` | **2 501** |
| ↳ `(forall …)` instances | **1 481** |
| ↳ `(check-sat)` | 3 |

A typical Verus query is in the tens-of-kB range with a few hundred
quantifier instances. This one is **30 MB / 1 481 forall** — z3 falls
into a matching loop on the shared `get_pagetable_by_pcid(_).mapping_4k()`
trigger heads and never returns from one of the three `(check-sat)`
queries before the 300 s outer wall fires.

The Python driver (`verusage_run`) has **no child subprocess** during
synthesis — gen_det's schema enumeration runs in-process and finishes
quickly; the wall is consumed entirely by the spawned `verus` → `z3`
invocation. The 30 MB `root.smt2` is fully written to disk before
z3 hangs, confirming the bottleneck is downstream of synthesis.

### 2.1 Why atmosphere upstream "verifies" this function

The source declares:

```rust
#[verifier::external_body]
pub fn pagetable_map_4k_page(&mut self, …) -> …
    requires …
    ensures …   // 76 lines
{
    unimplemented!()
}
```

**Upstream atmosphere never proves this function.**
`#[verifier::external_body]` instructs Verus to trust the body and
expose only the ensures as an axiom to callers; the body is literally
`unimplemented!()`. The 76-line ensures was authored as a *spec
axiom*, not as something the atmosphere authors expected Verus to
discharge.

Our determinism pipeline strips `external_body` (it has to — we
want to validate the *spec*, not skip it) and asks z3: "given these
ensures, is the output uniquely determined?" That requires unfolding
the full `wf()`-rooted closed-spec-fn cone — which is exactly the
work atmosphere chose to externalise. The crash isn't a regression;
it surfaces the fact that the spec is too heavy for z3 to discharge
directly.

Auditing the 40 unique crash functions against the source: **17/40
(43 %) of unique fns** and **37/65 (57 %) of crash instances** carry
`#[verifier::external_body]` upstream — i.e. the majority of the
crash *workload* comes from functions atmosphere itself never asked
z3 to verify. The remaining 23 unique fns (28 instances) have real
bodies, but they sit on the same `wf()`-axiom cone, so the
quantifier-instantiation pressure is the same.
