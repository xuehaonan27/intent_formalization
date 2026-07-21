# vstd determinism pilot

- vstd root: `/home/xuehaonan/nanvix/toolchain/verus/vstd`
- Verus root: `/home/xuehaonan/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 77
- Status counts: `{'ok': 67, 'verus_error': 8, 'unsupported_mut_ref_return': 2}`
- Classification counts: `{'ok_inconclusive': 13, 'complete': 54}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `atomic` | `fetch_and` | 610 | ok | unknown | ok_inconclusive | 3 | 8 | 1860 |
| `atomic` | `fetch_xor` | 630 | ok | unknown | ok_inconclusive | 3 | 8 | 1312 |
| `atomic` | `fetch_or` | 650 | ok | unknown | ok_inconclusive | 3 | 8 | 1283 |
| `cell` | `empty` | 168 | verus_error |  |  | 9 |  | 1131 |
| `cell` | `new` | 178 | verus_error |  |  | 9 |  | 929 |
| `cell` | `put` | 188 | verus_error |  |  | 13 |  | 652 |
| `cell` | `take` | 203 | verus_error |  |  | 13 |  | 474 |
| `cell` | `replace` | 223 | verus_error |  |  | 13 |  | 1099 |
| `cell` | `borrow` | 246 | verus_error |  |  | 5 |  | 1191 |
| `cell` | `into_inner` | 261 | verus_error |  |  | 5 |  | 970 |
| `cell` | `borrow_mut` | 277 | unsupported_mut_ref_return |  |  |  |  | 55 |
| `cell` | `write` | 297 | verus_error |  |  | 13 |  | 979 |
| `cell` | `new` | 344 | ok | unknown | ok_inconclusive | 1 | 2 | 1138 |
| `cell` | `replace` | 359 | ok | unknown | ok_inconclusive | 1 | 2 | 1508 |
| `cell` | `get` | 378 | ok | unknown | ok_inconclusive | 1 | 2 | 1381 |
| `hash_map` | `new` | 43 | ok | unsat | complete | 1 | 1 | 1360 |
| `hash_map` | `with_capacity` | 59 | ok | unsat | complete | 3 | 1 | 860 |
| `hash_map` | `reserve` | 73 | ok | unsat | complete | 3 | 1 | 651 |
| `hash_map` | `is_empty` | 82 | ok | unsat | complete | 5 | 1 | 1088 |
| `hash_map` | `len` | 95 | ok | unsat | complete | 5 | 1 | 885 |
| `hash_map` | `insert` | 106 | ok | unsat | complete | 1 | 1 | 723 |
| `hash_map` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 789 |
| `hash_map` | `contains_key` | 133 | ok | unsat | complete | 5 | 1 | 706 |
| `hash_map` | `get` | 144 | ok | unsat | complete | 5 | 1 | 926 |
| `hash_map` | `clear` | 158 | ok | unsat | complete | 1 | 1 | 965 |
| `hash_map` | `union_prefer_right` | 167 | ok | unsat | complete | 1 | 1 | 721 |
| `hash_map` | `new` | 209 | ok | unsat | complete | 1 | 1 | 666 |
| `hash_map` | `with_capacity` | 220 | ok | unsat | complete | 3 | 1 | 709 |
| `hash_map` | `reserve` | 231 | ok | unsat | complete | 3 | 1 | 704 |
| `hash_map` | `is_empty` | 240 | ok | unsat | complete | 5 | 1 | 1462 |
| `hash_map` | `len` | 253 | ok | unsat | complete | 5 | 1 | 1078 |
| `hash_map` | `insert` | 264 | ok | unsat | complete | 4 | 1 | 1592 |
| `hash_map` | `remove` | 275 | ok | unsat | complete | 4 | 1 | 2158 |
| `hash_map` | `contains_key` | 286 | ok | unsat | complete | 8 | 1 | 2212 |
| `hash_map` | `get` | 297 | ok | unsat | complete | 8 | 1 | 2482 |
| `hash_map` | `clear` | 311 | ok | unsat | complete | 1 | 1 | 913 |
| `hash_map` | `union_prefer_right` | 320 | ok | unsat | complete | 1 | 1 | 688 |
| `hash_set` | `new` | 44 | ok | unsat | complete | 1 | 1 | 714 |
| `hash_set` | `with_capacity` | 60 | ok | unsat | complete | 3 | 1 | 664 |
| `hash_set` | `reserve` | 74 | ok | unsat | complete | 3 | 1 | 677 |
| `hash_set` | `len` | 87 | ok | unsat | complete | 5 | 1 | 630 |
| `hash_set` | `is_empty` | 96 | ok | unsat | complete | 5 | 1 | 683 |
| `hash_set` | `insert` | 107 | ok | unsat | complete | 5 | 1 | 1454 |
| `hash_set` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 1512 |
| `hash_set` | `contains` | 129 | ok | unsat | complete | 5 | 1 | 1801 |
| `hash_set` | `get` | 140 | ok | unsat | complete | 5 | 1 | 1987 |
| `hash_set` | `clear` | 154 | ok | unsat | complete | 1 | 1 | 1686 |
| `hash_set` | `new` | 195 | ok | unsat | complete | 1 | 1 | 756 |
| `hash_set` | `with_capacity` | 206 | ok | unsat | complete | 3 | 1 | 757 |
| `hash_set` | `reserve` | 217 | ok | unsat | complete | 3 | 1 | 689 |
| `hash_set` | `is_empty` | 226 | ok | unsat | complete | 5 | 1 | 707 |
| `hash_set` | `len` | 239 | ok | unsat | complete | 5 | 1 | 694 |
| `hash_set` | `insert` | 250 | ok | unsat | complete | 8 | 1 | 796 |
| `hash_set` | `remove` | 261 | ok | unsat | complete | 8 | 1 | 805 |
| `hash_set` | `contains` | 272 | ok | unsat | complete | 8 | 1 | 759 |
| `hash_set` | `get` | 283 | ok | unsat | complete | 14 | 1 | 875 |
| `hash_set` | `clear` | 297 | ok | unsat | complete | 1 | 1 | 711 |
| `proph` | `resolve` | 187 | ok | unsat | complete | 1 | 1 | 995 |
| `rwlock` | `borrow` | 441 | ok | unsat | complete | 1 | 1 | 1321 |
| `rwlock` | `new` | 502 | ok | unknown | ok_inconclusive | 1 | 2 | 843 |
| `rwlock` | `acquire_write` | 530 | ok | unknown | ok_inconclusive | 1 | 2 | 1003 |
| `rwlock` | `acquire_read` | 620 | ok | unknown | ok_inconclusive | 1 | 2 | 902 |
| `rwlock` | `into_inner` | 702 | ok | unknown | ok_inconclusive | 1 | 2 | 813 |
| `simple_pptr` | `addr` | 184 | ok | unsat | complete | 5 | 1 | 1378 |
| `simple_pptr` | `from_addr` | 203 | ok | unsat | complete | 3 | 1 | 1430 |
| `simple_pptr` | `from_usize` | 212 | ok | unsat | complete | 3 | 1 | 1501 |
| `simple_pptr` | `empty` | 347 | ok | unknown | ok_inconclusive | 9 | 17 | 1399 |
| `simple_pptr` | `new` | 386 | ok | unknown | ok_inconclusive | 9 | 19 | 1489 |
| `simple_pptr` | `into_inner` | 431 | ok | unsat | complete | 5 | 1 | 1420 |
| `simple_pptr` | `put` | 451 | ok | unsat | complete | 13 | 1 | 2200 |
| `simple_pptr` | `take` | 476 | ok | unsat | complete | 13 | 1 | 1902 |
| `simple_pptr` | `replace` | 497 | ok | unsat | complete | 13 | 1 | 925 |
| `simple_pptr` | `borrow` | 519 | ok | unsat | complete | 5 | 1 | 641 |
| `simple_pptr` | `borrow_mut` | 537 | unsupported_mut_ref_return |  |  |  |  | 38 |
| `simple_pptr` | `write` | 557 | ok | unsat | complete | 13 | 1 | 860 |
| `simple_pptr` | `read` | 574 | ok | unsat | complete | 5 | 1 | 650 |
| `thread` | `join` | 27 | ok | unknown | ok_inconclusive | 5 | 4 | 453 |

## Errors

### `cell::empty`

```text
cell::pcell::PCell` or `vstd::cell::pcell_maybe_uninit::PCell` instead
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__empty__L168/harness.rs:18:48
   |
18 |             &&& (r2.1@@ == pcell_points![ r2.0.id() => MemContents::Uninit ])
   |                                                ^^

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__empty__L168/harness.rs:23:49
   |
23 |     if g___r1_1____addr___eq { assume(((r1.1)@).addr() as int == k___r1_1____addr___eq); }
   |                                                 ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__empty__L168/harness.rs:24:50
   |
24 |     if g___r1_1____addr___rng { assume(((r1.1)@).addr() as int >= k___r1_1____addr___rng_lo && ((r1.1)@).addr() as int <= k___r1_1__...
   |                                                  ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__empty__L168/harness.rs:24:106
   |
24 | ...k___r1_1____addr___rng_lo && ((r1.1)@).addr() as int <= k___r1_1____addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__empty__L168/harness.rs:27:49
   |
27 |     if g___r2_1____addr___eq { assume(((r2.1)@).addr() as int == k___r2_1____addr___eq); }
   |                                                 ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__empty__L168/harness.rs:28:50
   |
28 |     if g___r2_1____addr___rng { assume(((r2.1)@).addr() as int >= k___r2_1____addr___rng_lo && ((r2.1)@).addr() as int <= k___r2_1__...
   |                                                  ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__empty__L168/harness.rs:28:106
   |
28 | ...k___r2_1____addr___rng_lo && ((r2.1)@).addr() as int <= k___r2_1____addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error: aborting due to 6 previous errors; 2 warnings emitted

For more information about this error, try `rustc --explain E0599`.

```

### `cell::new`

```text
use `vstd::cell::pcell::PCell` or `vstd::cell::pcell_maybe_uninit::PCell` instead
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__new__L178/harness.rs:18:49
   |
18 |             &&& (r2.1@@ == pcell_points! [ r2.0.id() => MemContents::Init(v) ])
   |                                                 ^^

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__new__L178/harness.rs:23:49
   |
23 |     if g___r1_1____addr___eq { assume(((r1.1)@).addr() as int == k___r1_1____addr___eq); }
   |                                                 ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__new__L178/harness.rs:24:50
   |
24 |     if g___r1_1____addr___rng { assume(((r1.1)@).addr() as int >= k___r1_1____addr___rng_lo && ((r1.1)@).addr() as int <= k___r1_1__...
   |                                                  ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__new__L178/harness.rs:24:106
   |
24 | ...k___r1_1____addr___rng_lo && ((r1.1)@).addr() as int <= k___r1_1____addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__new__L178/harness.rs:27:49
   |
27 |     if g___r2_1____addr___eq { assume(((r2.1)@).addr() as int == k___r2_1____addr___eq); }
   |                                                 ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__new__L178/harness.rs:28:50
   |
28 |     if g___r2_1____addr___rng { assume(((r2.1)@).addr() as int >= k___r2_1____addr___rng_lo && ((r2.1)@).addr() as int <= k___r2_1__...
   |                                                  ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__new__L178/harness.rs:28:106
   |
28 | ...k___r2_1____addr___rng_lo && ((r2.1)@).addr() as int <= k___r2_1____addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error: aborting due to 6 previous errors; 2 warnings emitted

For more information about this error, try `rustc --explain E0599`.

```

### `cell::put`

```text
xperiments/repro-2026-07-21-impl-methods/artifacts/cell__put__L188/harness.rs:26:110
   |
26 | ..._pre_perm__addr___rng_lo && (pre_perm).addr() as int <= k__pre_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__put__L188/harness.rs:29:55
   |
29 |     if g__post1_perm__addr___eq { assume((post1_perm).addr() as int == k__post1_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__put__L188/harness.rs:30:56
   |
30 |     if g__post1_perm__addr___rng { assume((post1_perm).addr() as int >= k__post1_perm__addr___rng_lo && (post1_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__put__L188/harness.rs:30:118
   |
30 | ...t1_perm__addr___rng_lo && (post1_perm).addr() as int <= k__post1_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__put__L188/harness.rs:33:55
   |
33 |     if g__post2_perm__addr___eq { assume((post2_perm).addr() as int == k__post2_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__put__L188/harness.rs:34:56
   |
34 |     if g__post2_perm__addr___rng { assume((post2_perm).addr() as int >= k__post2_perm__addr___rng_lo && (post2_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__put__L188/harness.rs:34:118
   |
34 | ...t2_perm__addr___rng_lo && (post2_perm).addr() as int <= k__post2_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error: aborting due to 9 previous errors; 3 warnings emitted

For more information about this error, try `rustc --explain E0599`.

```

### `cell::take`

```text
ents/repro-2026-07-21-impl-methods/artifacts/cell__take__L203/harness.rs:30:110
   |
30 | ..._pre_perm__addr___rng_lo && (pre_perm).addr() as int <= k__pre_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__take__L203/harness.rs:33:55
   |
33 |     if g__post1_perm__addr___eq { assume((post1_perm).addr() as int == k__post1_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__take__L203/harness.rs:34:56
   |
34 |     if g__post1_perm__addr___rng { assume((post1_perm).addr() as int >= k__post1_perm__addr___rng_lo && (post1_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__take__L203/harness.rs:34:118
   |
34 | ...t1_perm__addr___rng_lo && (post1_perm).addr() as int <= k__post1_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__take__L203/harness.rs:37:55
   |
37 |     if g__post2_perm__addr___eq { assume((post2_perm).addr() as int == k__post2_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__take__L203/harness.rs:38:56
   |
38 |     if g__post2_perm__addr___rng { assume((post2_perm).addr() as int >= k__post2_perm__addr___rng_lo && (post2_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__take__L203/harness.rs:38:118
   |
38 | ...t2_perm__addr___rng_lo && (post2_perm).addr() as int <= k__post2_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error: aborting due to 9 previous errors; 1 warning emitted

For more information about this error, try `rustc --explain E0599`.

```

### `cell::replace`

```text
-impl-methods/artifacts/cell__replace__L223/harness.rs:30:110
   |
30 | ..._pre_perm__addr___rng_lo && (pre_perm).addr() as int <= k__pre_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__replace__L223/harness.rs:33:55
   |
33 |     if g__post1_perm__addr___eq { assume((post1_perm).addr() as int == k__post1_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__replace__L223/harness.rs:34:56
   |
34 |     if g__post1_perm__addr___rng { assume((post1_perm).addr() as int >= k__post1_perm__addr___rng_lo && (post1_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__replace__L223/harness.rs:34:118
   |
34 | ...t1_perm__addr___rng_lo && (post1_perm).addr() as int <= k__post1_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__replace__L223/harness.rs:37:55
   |
37 |     if g__post2_perm__addr___eq { assume((post2_perm).addr() as int == k__post2_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__replace__L223/harness.rs:38:56
   |
38 |     if g__post2_perm__addr___rng { assume((post2_perm).addr() as int >= k__post2_perm__addr___rng_lo && (post2_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__replace__L223/harness.rs:38:118
   |
38 | ...t2_perm__addr___rng_lo && (post2_perm).addr() as int <= k__post2_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error: aborting due to 9 previous errors; 1 warning emitted

For more information about this error, try `rustc --explain E0599`.

```

### `cell::borrow`

```text
warning: use of deprecated method `vstd::cell::PCell::<V>::id`: use `vstd::cell::pcell::PCell` or `vstd::cell::pcell_maybe_uninit::PCell` instead
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__borrow__L246/harness.rs:15:21
   |
15 |     requires (self_.id() == perm@.pcell), (perm.is_init()),
   |                     ^^
   |
   = note: `#[warn(deprecated)]` on by default

error[E0599]: no method named `addr` found for reference `&vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__borrow__L246/harness.rs:24:43
   |
24 |     if g__perm__addr___eq { assume((perm).addr() as int == k__perm__addr___eq); }
   |                                           ^^^^ method not found in `&vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for reference `&vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__borrow__L246/harness.rs:25:44
   |
25 |     if g__perm__addr___rng { assume((perm).addr() as int >= k__perm__addr___rng_lo && (perm).addr() as int <= k__perm__addr___rng_hi...
   |                                            ^^^^ method not found in `&vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for reference `&vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__borrow__L246/harness.rs:25:94
   |
25 | ...nt >= k__perm__addr___rng_lo && (perm).addr() as int <= k__perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `&vstd::cell::PointsTo<V>`

error: aborting due to 3 previous errors; 1 warning emitted

For more information about this error, try `rustc --explain E0599`.

```

### `cell::into_inner`

```text
warning: use of deprecated method `vstd::cell::PCell::<V>::id`: use `vstd::cell::pcell::PCell` or `vstd::cell::pcell_maybe_uninit::PCell` instead
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__into_inner__L261/harness.rs:15:21
   |
15 |     requires (self_.id() == perm@.pcell), (perm.is_init()),
   |                     ^^
   |
   = note: `#[warn(deprecated)]` on by default

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__into_inner__L261/harness.rs:24:43
   |
24 |     if g__perm__addr___eq { assume((perm).addr() as int == k__perm__addr___eq); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__into_inner__L261/harness.rs:25:44
   |
25 |     if g__perm__addr___rng { assume((perm).addr() as int >= k__perm__addr___rng_lo && (perm).addr() as int <= k__perm__addr___rng_hi...
   |                                            ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__into_inner__L261/harness.rs:25:94
   |
25 | ...nt >= k__perm__addr___rng_lo && (perm).addr() as int <= k__perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error: aborting due to 3 previous errors; 1 warning emitted

For more information about this error, try `rustc --explain E0599`.

```

### `cell::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `cell::write`

```text
pro-2026-07-21-impl-methods/artifacts/cell__write__L297/harness.rs:28:110
   |
28 | ..._pre_perm__addr___rng_lo && (pre_perm).addr() as int <= k__pre_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__write__L297/harness.rs:31:55
   |
31 |     if g__post1_perm__addr___eq { assume((post1_perm).addr() as int == k__post1_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__write__L297/harness.rs:32:56
   |
32 |     if g__post1_perm__addr___rng { assume((post1_perm).addr() as int >= k__post1_perm__addr___rng_lo && (post1_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__write__L297/harness.rs:32:118
   |
32 | ...t1_perm__addr___rng_lo && (post1_perm).addr() as int <= k__post1_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__write__L297/harness.rs:35:55
   |
35 |     if g__post2_perm__addr___eq { assume((post2_perm).addr() as int == k__post2_perm__addr___eq); }
   |                                                       ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__write__L297/harness.rs:36:56
   |
36 |     if g__post2_perm__addr___rng { assume((post2_perm).addr() as int >= k__post2_perm__addr___rng_lo && (post2_perm).addr() as int <...
   |                                                        ^^^^ method not found in `vstd::cell::PointsTo<V>`

error[E0599]: no method named `addr` found for struct `vstd::cell::PointsTo<V>` in the current scope
  --> vstd-survey/experiments/repro-2026-07-21-impl-methods/artifacts/cell__write__L297/harness.rs:36:118
   |
36 | ...t2_perm__addr___rng_lo && (post2_perm).addr() as int <= k__post2_perm__addr___rng_hi); }
   |                                           ^^^^ method not found in `vstd::cell::PointsTo<V>`

error: aborting due to 9 previous errors; 1 warning emitted

For more information about this error, try `rustc --explain E0599`.

```

### `simple_pptr::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```
