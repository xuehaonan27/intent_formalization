# vstd determinism pilot

- vstd root: `/home/xuehaonan/nanvix/toolchain/verus/vstd`
- Verus root: `/home/xuehaonan/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 34
- Status counts: `{'ok': 27, 'unsupported_mut_ref_return': 2, 'verus_error': 5}`
- Classification counts: `{'complete': 18, 'ok_inconclusive': 3, 'invalid_equal_fn_trivial': 6}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `array` | `array_index_get` | 76 | ok | unsat | complete | 5 | 1 | 2020 |
| `array` | `array_as_slice` | 135 | ok | unsat | complete | 7 | 1 | 1608 |
| `array` | `array_fill_for_copy_types` | 164 | ok | unsat | complete | 5 | 1 | 1607 |
| `array` | `ref_mut_array_unsizing_coercion` | 195 | unsupported_mut_ref_return |  |  |  |  | 36 |
| `bytes` | `u16_from_le_bytes` | 79 | ok | unsat | complete | 23 | 1 | 2223 |
| `bytes` | `u16_to_le_bytes` | 91 | ok | unsat | complete | 39 | 1 | 2333 |
| `bytes` | `u32_from_le_bytes` | 174 | ok | unsat | complete | 23 | 1 | 2709 |
| `bytes` | `u32_to_le_bytes` | 186 | ok | unsat | complete | 39 | 1 | 2447 |
| `bytes` | `u64_from_le_bytes` | 331 | ok | unsat | complete | 23 | 1 | 2139 |
| `bytes` | `u64_to_le_bytes` | 343 | ok | unsat | complete | 39 | 1 | 2298 |
| `bytes` | `u128_from_le_bytes` | 518 | ok | unsat | complete | 19 | 1 | 2088 |
| `bytes` | `u128_to_le_bytes` | 530 | ok | unsat | complete | 37 | 1 | 2812 |
| `float` | `float_cast` | 127 | ok | unknown | ok_inconclusive | 1 | 2 | 842 |
| `layout` | `layout_for_type_is_valid` | 118 | ok | unsat | complete | 1 | 1 | 1276 |
| `layout` | `layout_for_val_is_valid` | 141 | ok | unsat | complete | 1 | 1 | 764 |
| `raw_ptr` | `cast_ptr_to_thin_ptr` | 446 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 715 |
| `raw_ptr` | `cast_array_ptr_to_slice_ptr` | 468 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 833 |
| `raw_ptr` | `cast_slice_ptr_to_slice_ptr` | 492 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 730 |
| `raw_ptr` | `cast_slice_ptr_to_str_ptr` | 516 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 707 |
| `raw_ptr` | `cast_str_ptr_to_slice_ptr` | 540 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 752 |
| `raw_ptr` | `cast_ptr_to_usize` | 560 | ok | unsat | complete | 5 | 1 | 691 |
| `raw_ptr` | `ptr_mut_write` | 579 | verus_error |  |  | 13 |  | 571 |
| `raw_ptr` | `ptr_mut_read` | 602 | verus_error |  |  | 13 |  | 884 |
| `raw_ptr` | `ptr_ref` | 620 | verus_error |  |  | 5 |  | 1090 |
| `raw_ptr` | `ptr_mut_ref` | 636 | unsupported_mut_ref_return |  |  |  |  | 156 |
| `raw_ptr` | `expose_provenance` | 731 | ok | unsat | complete | 1 | 1 | 1881 |
| `raw_ptr` | `with_exposed_provenance` | 744 | ok | unsat | invalid_equal_fn_trivial | 3 | 1 | 2028 |
| `raw_ptr` | `allocate` | 908 | ok | unknown | ok_inconclusive | 5 | 15 | 1354 |
| `raw_ptr` | `ptr_ref2` | 1038 | verus_error |  |  | 5 |  | 491 |
| `slice` | `slice_index_get` | 62 | ok | unsat | complete | 5 | 1 | 1801 |
| `slice` | `slice_to_vec` | 100 | ok | unsat | complete | 7 | 1 | 2301 |
| `slice` | `slice_subrange` | 108 | ok | unsat | complete | 11 | 1 | 2997 |
| `thread` | `spawn` | 107 | verus_error |  |  | 1 |  | 1018 |
| `thread` | `thread_id` | 200 | ok | unknown | ok_inconclusive | 1 | 2 | 1197 |

## Errors

### `array::ref_mut_array_unsizing_coercion`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `raw_ptr::ptr_mut_write`

```text
   |
29 | ...pre_perm__addr___rng_lo && (pre_perm).addr() as int <= k__pre_perm__addr___rng_hi); }
   |                                          ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_write__L579/harness.rs:32:55
   |
32 |     if g__post1_perm__addr___eq { assume((post1_perm).addr() as int == k__post1_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_write__L579/harness.rs:33:56
   |
33 |     if g__post1_perm__addr___rng { assume((post1_perm).addr() as int >= k__post1_perm__addr___rng_lo && (post1_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_write__L579/harness.rs:33:118
   |
33 | ...1_perm__addr___rng_lo && (post1_perm).addr() as int <= k__post1_perm__addr___rng_hi); }
   |                                          ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_write__L579/harness.rs:36:55
   |
36 |     if g__post2_perm__addr___eq { assume((post2_perm).addr() as int == k__post2_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_write__L579/harness.rs:37:56
   |
37 |     if g__post2_perm__addr___rng { assume((post2_perm).addr() as int >= k__post2_perm__addr___rng_lo && (post2_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_write__L579/harness.rs:37:118
   |
37 | ...2_perm__addr___rng_lo && (post2_perm).addr() as int <= k__post2_perm__addr___rng_hi); }
   |                                          ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error: aborting due to 9 previous errors

For more information about this error, try `rustc --explain E0599`.

```

### `raw_ptr::ptr_mut_read`

```text
1:110
   |
31 | ...pre_perm__addr___rng_lo && (pre_perm).addr() as int <= k__pre_perm__addr___rng_hi); }
   |                                          ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_read__L602/harness.rs:34:55
   |
34 |     if g__post1_perm__addr___eq { assume((post1_perm).addr() as int == k__post1_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_read__L602/harness.rs:35:56
   |
35 |     if g__post1_perm__addr___rng { assume((post1_perm).addr() as int >= k__post1_perm__addr___rng_lo && (post1_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_read__L602/harness.rs:35:118
   |
35 | ...1_perm__addr___rng_lo && (post1_perm).addr() as int <= k__post1_perm__addr___rng_hi); }
   |                                          ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_read__L602/harness.rs:38:55
   |
38 |     if g__post2_perm__addr___eq { assume((post2_perm).addr() as int == k__post2_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_read__L602/harness.rs:39:56
   |
39 |     if g__post2_perm__addr___rng { assume((post2_perm).addr() as int >= k__post2_perm__addr___rng_lo && (post2_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for struct `vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_mut_read__L602/harness.rs:39:118
   |
39 | ...2_perm__addr___rng_lo && (post2_perm).addr() as int <= k__post2_perm__addr___rng_hi); }
   |                                          ^^^^ method not found in `vstd::raw_ptr::PointsTo<T>`

error: aborting due to 9 previous errors

For more information about this error, try `rustc --explain E0599`.

```

### `raw_ptr::ptr_ref`

```text
error[E0599]: no method named `addr` found for reference `&vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_ref__L620/harness.rs:25:43
   |
25 |     if g__perm__addr___eq { assume((perm).addr() as int == k__perm__addr___eq); }
   |                                           ^^^^ method not found in `&vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for reference `&vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_ref__L620/harness.rs:26:44
   |
26 |     if g__perm__addr___rng { assume((perm).addr() as int >= k__perm__addr___rng_lo && (perm).addr() as int <= k__perm__addr___rng_hi...
   |                                            ^^^^ method not found in `&vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for reference `&vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_ref__L620/harness.rs:26:94
   |
26 | ... >= k__perm__addr___rng_lo && (perm).addr() as int <= k__perm__addr___rng_hi); }
   |                                         ^^^^ method not found in `&vstd::raw_ptr::PointsTo<T>`

error: aborting due to 3 previous errors

For more information about this error, try `rustc --explain E0599`.

```

### `raw_ptr::ptr_mut_ref`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `raw_ptr::ptr_ref2`

```text
error[E0599]: no method named `addr` found for reference `&vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_ref2__L1038/harness.rs:41:43
   |
41 |     if g__perm__addr___eq { assume((perm).addr() as int == k__perm__addr___eq); }
   |                                           ^^^^ method not found in `&vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for reference `&vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_ref2__L1038/harness.rs:42:44
   |
42 |     if g__perm__addr___rng { assume((perm).addr() as int >= k__perm__addr___rng_lo && (perm).addr() as int <= k__perm__addr___rng_hi...
   |                                            ^^^^ method not found in `&vstd::raw_ptr::PointsTo<T>`

error[E0599]: no method named `addr` found for reference `&vstd::raw_ptr::PointsTo<T>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/raw_ptr__ptr_ref2__L1038/harness.rs:42:94
   |
42 | ... >= k__perm__addr___rng_lo && (perm).addr() as int <= k__perm__addr___rng_hi); }
   |                                         ^^^^ method not found in `&vstd::raw_ptr::PointsTo<T>`

error: aborting due to 3 previous errors

For more information about this error, try `rustc --explain E0599`.

```

### `thread::spawn`

```text
error[E0283]: type annotations needed
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/thread__spawn__L107/harness.rs:26:30
   |
26 |     if g_neq_tuple { assume(!det_spawn_equal(r1, r2)); }
   |                              ^^^^^^^^^^^^^^^ cannot infer type of the type parameter `F` declared on the function `det_spawn_equal`
   |
   = note: cannot satisfy `_: FnOnce()`
note: required by a bound in `det_spawn_equal`
  --> vstd-survey/experiments/repro-2026-07-21-public-free/artifacts/thread__spawn__L107/harness.rs:11:14
   |
10 | spec fn det_spawn_equal<F, Ret>(r1: JoinHandle<Ret>, r2: JoinHandle<Ret>) -> bool
   |         --------------- required by a bound in this function
11 |     where F: FnOnce() -> Ret, F: Send + 'static, Ret: Send + 'static {
   |              ^^^^^^^^^^^^^^^ required by this bound in `det_spawn_equal`
help: consider specifying the generic arguments
   |
26 |     if g_neq_tuple { assume(!det_spawn_equal::<F, Ret>(r1, r2)); }
   |                                             ++++++++++

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0283`.

```
