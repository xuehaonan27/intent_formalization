# Bitmap — Meta-Prompter Strategy

## Priority Ranking

1. **🔴 `new()` liveness** — new(8) permitted to return Err. No guarantee valid inputs → Ok.
2. **🔴 Error code opacity** — Every Err(_) wildcarded across all functions.
3. **🟡 `new()` error conditions one-way** — Three Err implications don't cover converse.
4. **🟡 Alloc determinism / next_free opacity** — Spec allows nondeterministic free bit choice.
5. **🟡 `alloc` liveness** — Err iff is_full(), but equivalence with exists_contiguous_free_range worth checking.
6. **🟡 `set` liveness** — Err branch is `Err(_) => true`, no constraints on when Err can occur for valid+clear bit.

## Functions to Focus On
1. `new` — liveness gap, error condition completeness
2. `alloc` / `alloc_range` — liveness ↔ is_full equivalences, frame conditions
3. `set` / `clear` — error code distinguishability

## Likely FP (inv covers)
- usage bounded, set_bits ⊆ [0, num_bits), byte consistency, number_of_bits > 0

## Key Note
Alpha flagged missing alloc frame condition risk — need to check if alloc preserves other bits.
Also flagged that `set` Err branch is `Err(_) => true` with zero constraints.
