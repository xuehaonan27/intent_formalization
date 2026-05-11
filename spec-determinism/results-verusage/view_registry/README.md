# view_registry — Phase 2 L3 impl scan + audit artifacts

This directory holds the Phase 2 view-resolver artifacts. One
subdirectory per project:

```
view_registry/
  <project>/
    _l3_scan.json         # all `impl View` / `impl PartialEq` / `impl Eq` found in raw source
    _audit.json           # roll-up of the L3 scan vs. type_registry
    _resolver_audit.json  # full L1+L2+L3 resolver coverage per defined short name
```

Regenerate with:

```
python -m spec_determinism.view.impl_scanner audit verusage/source-projects/<project>
python -m spec_determinism.view.registry     audit verusage/source-projects/<project>
```

## Corpus-wide L3 coverage (raw `impl View` scan)

| project | defined types | View impls found | targets w/ View | L1+L2+L3 uncovered |
|---|---:|---:|---:|---:|
| atmosphere | 56 | 0 | 0 | 36 |
| ironkv | 64 | 0 | 0 | 44 |
| anvil-library | 4 | 0 | 0 | 2 |
| memory-allocator | 6 | 0 | 0 | 6 |
| nrkernel | 39 | 0 | 0 | 39 |
| storage | 20 | 0 | 0 | 20 |
| vest | 4 | 30 | 3 | 0 |
| **total** | **193** | **30** | **3** | **147** |

(L2 "free" = alias types resolved transparently by the registry,
already subtracted from the uncovered column.)

## Corpus-wide resolver coverage (L1 + L2 + L3 combined)

| project | covered | total | L1 | L2 | L3 | uncovered |
|---|---:|---:|---:|---:|---:|---:|
| atmosphere | 17 | 56 | 0 | 17 | 0 | 39 |
| ironkv | 12 | 64 | 0 | 12 | 0 | 52 |
| anvil-library | 0 | 4 | 0 | 0 | 0 | 4 |
| memory-allocator | 0 | 6 | 0 | 0 | 0 | 6 |
| nrkernel | 0 | 39 | 0 | 0 | 0 | 39 |
| storage | 0 | 20 | 0 | 0 | 0 | 20 |
| vest | 4 | 4 | 0 | 1 | 3 | 0 |
| **total** | **33** | **193** | **0** | **30** | **3** | **160** |

L1=0 in the table only because the audit synthesizes leaf
`TypeExpr`s for the defined short names — none of which *are*
prelude containers themselves. L1 fires when target ensures
projection drills *into* a container (e.g. `post.queue@`), and that
distribution will be measured in PR-C against the 1647 target
ensures.

## What this means for A-2

The corpus uses explicit `impl View for X` almost exclusively in
**vest** (parser combinators — `Repeat`, `RepeatN`,
`UnsignedLEB128`). The other six projects have *zero* user-defined
View impls in raw source — they either:

1. Operate purely on container Views (`Vec<X>@` gives `Seq<X>` and
   the inner `X` is then compared structurally — L1 handles this).
2. Generate View impls via `state_machine!` /
   `tokenized_state_machine!` macros, which tree-sitter does not
   expand.
3. Genuinely don't need view-based equal because their ensures
   never reaches `.@` on the type in question.

So **L3 alone contributes very little** outside vest. The A-2 fix
relies on:

- **L1 prelude rules** for the common container patterns (`Vec`,
  `Option`, `Map`, `Seq`, `&T`, `&mut T`, `Ghost`, `Tracked`,
  `Box`, `Arc`, …) — see `spec_determinism/view/prelude.py`
- **L4 LLM generation** for user types that *are* referenced under
  `@` in the ensures of our synthesised functions.

The 160 "uncovered" types in the resolver table are an *upper
bound* on L4 calls; the actual cost is far lower because PR-C will
filter to "types reachable under `@` from the ensures of one of
our 1647 targets" before invoking L4.

## Fallback path (not in PR-A / PR-B)

If LLM cost or reliability proves a problem, an alternative is to
run `cargo expand` per project and re-scan the macro-expanded
source — that would surface `state_machine!`-generated View impls
and push L3 coverage up substantially. Estimated impact: ~80 % of
atmosphere / nrkernel types are state-machine-generated and would
gain View impls this way.

## Files

* `<project>/_l3_scan.json` — raw scan: every `impl View` / `impl
  PartialEq` / `impl Eq` block as a `ViewImpl` / `EqImpl`
  dataclass dump. Keyed by short target type name; one entry per
  discovered impl. Useful for grepping or LLM context retrieval.
* `<project>/_audit.json` — roll-up stats of the L3 scan.
* `<project>/_resolver_audit.json` — bucket of defined short names
  by resolver layer (primitive / unit / L1 / L2 / L3 / uncovered),
  with examples + needs list.

Regenerate with the one-shot commands at the top of this README.

