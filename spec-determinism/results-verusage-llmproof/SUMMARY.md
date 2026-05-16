# verusage spec-determinism — batch summary

> `ok` results are classified by the **R0** z3 verdict (initial determinism check before any schema narrowing):
>
> * **`ok_proved`** — R0 = `unsat` → function is provably deterministic.
> * **`ok_proved_llm`** — R0 was `unknown`; the LLM proof loop wrote an `assert/by`-style block that Verus accepted. Soundness preserved by the sandbox lex-allowlist.
> * **`ok_witness`** — R0 = `sat` → z3 produced a real nondeterminism counterexample.
> * **`ok_inconclusive`** — R0 = `unknown` (or legacy run without `r0_z3`) → z3 surrendered; assumes from narrowing are not a witness, just refinement attempts.

## Per-project overview

| project | n | ok_proved | ok_proved_llm | ok_witness | ok_inconclusive | search_error | verus_error | extract_error | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| memory-allocator | 16 | 14 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| nrkernel | 8 | 6 | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| vest | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | **26** | **22** | **0** | **0** | **1** | **0** | **3** | **0** | — |

## Real determinism witnesses (R0 = sat)

*(none — no z3-confirmed nondeterminism witnesses in this run)*

## Inconclusive targets (R0 = unknown)

These cases reached the schema-narrowing phase but z3 returned `unknown` on the baseline check; any `assumes` below are search artifacts, **not** verified witnesses.

### memory-allocator (1 inconclusive)

- `memory-allocator__verified__commit_mask__commit_mask__impl__next_run__next_run`  (rounds=108, narrowed_assumes=15)

## Failure-mode samples

### status=`verus_error`  (3 cases)

**memory-allocator / memory-allocator__verified__layout__layout__impl__calculate_page_block_at__calculate_page_block_at**

```
error: expected one of: identifier, `::`, `<`, `_`, literal, `const`, `ref`, `mut`, `&`, parentheses, square brackets, `..`, `const`
   --> /tmp/specdet_sf_calculate_page_block_at_kx8xc23s/layout__impl__calculate_page_block_at.rs:189:1040
    |
189 | ...l, page_start: usize, block_size: usize, idx: usize, ?: Ghost<PageId>, r1: usize, r2: usize)
    |                                                         ^

error: aborting due to 1 previous error
```

**nrkernel / nrkernel__verified__impl_u__l2_impl__impl_u__l2_impl__impl0__address__address**

```
error: zero-sized fields in `repr(transparent)` cannot contain external types with private fields
   --> /tmp/specdet_sf_address_ot584o0t/impl_u__l2_impl__impl0__address.rs:127:5
    |
127 |     pub layer: Ghost<nat>,
    |     ^^^^^^^^^^^^^^^^^^^^^
    |
    = warning: this was previously accepted by the compiler but is being phased out; it will become a hard error in a future release!
    = note: for more information, see issue #78586 <https://github.com/rust-lang/rust/issues/78586>
    = note: this field contains `vstd::prelude::Ghost<vstd::prelude::nat>`, which contains private fields, so it could become non-zero-sized in the future.
    = note: `#[deny(repr_transparent_non_zst_fields)]` (part of `#[deny(future_incompatible)]`) on by default

error: aborting due to 1 previous error
```

**nrkernel / nrkernel__verified__impl_u__l2_impl__impl_u__l2_impl__impl0__new_entry__new_entry**

```
error: zero-sized fields in `repr(transparent)` cannot contain external types with private fields
   --> /tmp/specdet_sf_new_entry_m__47drw/impl_u__l2_impl__impl0__new_entry.rs:129:5
    |
129 |     pub layer: Ghost<nat>,
    |     ^^^^^^^^^^^^^^^^^^^^^
    |
    = warning: this was previously accepted by the compiler but is being phased out; it will become a hard error in a future release!
    = note: for more information, see issue #78586 <https://github.com/rust-lang/rust/issues/78586>
    = note: this field contains `vstd::prelude::Ghost<vstd::prelude::nat>`, which contains private fields, so it could become non-zero-sized in the future.
    = note: `#[deny(repr_transparent_non_zst_fields)]` (part of `#[deny(future_incompatible)]`) on by default

error: aborting due to 1 previous error
```

