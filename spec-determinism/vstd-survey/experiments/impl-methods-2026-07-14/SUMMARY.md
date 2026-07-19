# vstd determinism pilot

- vstd root: `/home/chentianyu/nanvix/toolchain/verus/vstd`
- Verus root: `/home/chentianyu/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 77
- Status counts: `{'ok': 75, 'unsupported_mut_ref_return': 2}`
- Classification counts: `{'ok_inconclusive': 15, 'complete': 60}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `atomic` | `fetch_and` | 610 | ok | unknown | ok_inconclusive | 3 | 8 | 534 |
| `atomic` | `fetch_xor` | 630 | ok | unknown | ok_inconclusive | 3 | 8 | 525 |
| `atomic` | `fetch_or` | 650 | ok | unknown | ok_inconclusive | 3 | 8 | 503 |
| `cell` | `empty` | 168 | ok | unknown | ok_inconclusive | 9 | 16 | 434 |
| `cell` | `new` | 178 | ok | unknown | ok_inconclusive | 9 | 18 | 441 |
| `cell` | `put` | 188 | ok | unsat | complete | 13 | 1 | 754 |
| `cell` | `take` | 203 | ok | unsat | complete | 13 | 1 | 705 |
| `cell` | `replace` | 223 | ok | unsat | complete | 13 | 1 | 710 |
| `cell` | `borrow` | 246 | ok | unsat | complete | 5 | 1 | 689 |
| `cell` | `into_inner` | 261 | ok | unsat | complete | 5 | 1 | 664 |
| `cell` | `borrow_mut` | 277 | unsupported_mut_ref_return |  |  |  |  | 20 |
| `cell` | `write` | 297 | ok | unsat | complete | 13 | 1 | 628 |
| `cell` | `new` | 344 | ok | unknown | ok_inconclusive | 1 | 2 | 397 |
| `cell` | `replace` | 359 | ok | unknown | ok_inconclusive | 1 | 2 | 383 |
| `cell` | `get` | 378 | ok | unknown | ok_inconclusive | 1 | 2 | 442 |
| `hash_map` | `new` | 43 | ok | unsat | complete | 1 | 1 | 692 |
| `hash_map` | `with_capacity` | 59 | ok | unsat | complete | 3 | 1 | 697 |
| `hash_map` | `reserve` | 73 | ok | unsat | complete | 3 | 1 | 686 |
| `hash_map` | `is_empty` | 82 | ok | unsat | complete | 5 | 1 | 648 |
| `hash_map` | `len` | 95 | ok | unsat | complete | 5 | 1 | 727 |
| `hash_map` | `insert` | 106 | ok | unsat | complete | 1 | 1 | 700 |
| `hash_map` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 749 |
| `hash_map` | `contains_key` | 133 | ok | unsat | complete | 5 | 1 | 688 |
| `hash_map` | `get` | 144 | ok | unsat | complete | 5 | 1 | 736 |
| `hash_map` | `clear` | 158 | ok | unsat | complete | 1 | 1 | 684 |
| `hash_map` | `union_prefer_right` | 167 | ok | unsat | complete | 1 | 1 | 615 |
| `hash_map` | `new` | 209 | ok | unsat | complete | 1 | 1 | 700 |
| `hash_map` | `with_capacity` | 220 | ok | unsat | complete | 3 | 1 | 610 |
| `hash_map` | `reserve` | 231 | ok | unsat | complete | 3 | 1 | 619 |
| `hash_map` | `is_empty` | 240 | ok | unsat | complete | 5 | 1 | 615 |
| `hash_map` | `len` | 253 | ok | unsat | complete | 5 | 1 | 706 |
| `hash_map` | `insert` | 264 | ok | unsat | complete | 4 | 1 | 696 |
| `hash_map` | `remove` | 275 | ok | unsat | complete | 4 | 1 | 692 |
| `hash_map` | `contains_key` | 286 | ok | unsat | complete | 8 | 1 | 744 |
| `hash_map` | `get` | 297 | ok | unsat | complete | 8 | 1 | 715 |
| `hash_map` | `clear` | 311 | ok | unsat | complete | 1 | 1 | 607 |
| `hash_map` | `union_prefer_right` | 320 | ok | unsat | complete | 1 | 1 | 611 |
| `hash_set` | `new` | 44 | ok | unsat | complete | 1 | 1 | 663 |
| `hash_set` | `with_capacity` | 60 | ok | unsat | complete | 3 | 1 | 620 |
| `hash_set` | `reserve` | 74 | ok | unsat | complete | 3 | 1 | 597 |
| `hash_set` | `len` | 87 | ok | unsat | complete | 5 | 1 | 604 |
| `hash_set` | `is_empty` | 96 | ok | unsat | complete | 5 | 1 | 639 |
| `hash_set` | `insert` | 107 | ok | unsat | complete | 5 | 1 | 654 |
| `hash_set` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 611 |
| `hash_set` | `contains` | 129 | ok | unsat | complete | 5 | 1 | 599 |
| `hash_set` | `get` | 140 | ok | unsat | complete | 5 | 1 | 619 |
| `hash_set` | `clear` | 154 | ok | unsat | complete | 1 | 1 | 620 |
| `hash_set` | `new` | 195 | ok | unsat | complete | 1 | 1 | 589 |
| `hash_set` | `with_capacity` | 206 | ok | unsat | complete | 3 | 1 | 672 |
| `hash_set` | `reserve` | 217 | ok | unsat | complete | 3 | 1 | 626 |
| `hash_set` | `is_empty` | 226 | ok | unsat | complete | 5 | 1 | 634 |
| `hash_set` | `len` | 239 | ok | unsat | complete | 5 | 1 | 601 |
| `hash_set` | `insert` | 250 | ok | unsat | complete | 8 | 1 | 695 |
| `hash_set` | `remove` | 261 | ok | unsat | complete | 8 | 1 | 709 |
| `hash_set` | `contains` | 272 | ok | unsat | complete | 8 | 1 | 688 |
| `hash_set` | `get` | 283 | ok | unsat | complete | 14 | 1 | 777 |
| `hash_set` | `clear` | 297 | ok | unsat | complete | 1 | 1 | 591 |
| `proph` | `resolve` | 187 | ok | unsat | complete | 1 | 1 | 558 |
| `rwlock` | `borrow` | 441 | ok | unsat | complete | 1 | 1 | 598 |
| `rwlock` | `new` | 502 | ok | unknown | ok_inconclusive | 1 | 2 | 412 |
| `rwlock` | `acquire_write` | 530 | ok | unknown | ok_inconclusive | 1 | 2 | 438 |
| `rwlock` | `acquire_read` | 620 | ok | unknown | ok_inconclusive | 1 | 2 | 421 |
| `rwlock` | `into_inner` | 702 | ok | unknown | ok_inconclusive | 1 | 2 | 400 |
| `simple_pptr` | `addr` | 184 | ok | unsat | complete | 5 | 1 | 583 |
| `simple_pptr` | `from_addr` | 203 | ok | unsat | complete | 3 | 1 | 590 |
| `simple_pptr` | `from_usize` | 212 | ok | unsat | complete | 3 | 1 | 644 |
| `simple_pptr` | `empty` | 347 | ok | unknown | ok_inconclusive | 9 | 17 | 541 |
| `simple_pptr` | `new` | 386 | ok | unknown | ok_inconclusive | 9 | 19 | 563 |
| `simple_pptr` | `into_inner` | 431 | ok | unsat | complete | 5 | 1 | 665 |
| `simple_pptr` | `put` | 451 | ok | unsat | complete | 13 | 1 | 775 |
| `simple_pptr` | `take` | 476 | ok | unsat | complete | 13 | 1 | 783 |
| `simple_pptr` | `replace` | 497 | ok | unsat | complete | 13 | 1 | 783 |
| `simple_pptr` | `borrow` | 519 | ok | unsat | complete | 5 | 1 | 632 |
| `simple_pptr` | `borrow_mut` | 537 | unsupported_mut_ref_return |  |  |  |  | 25 |
| `simple_pptr` | `write` | 557 | ok | unsat | complete | 13 | 1 | 755 |
| `simple_pptr` | `read` | 574 | ok | unsat | complete | 5 | 1 | 635 |
| `thread` | `join` | 27 | ok | unknown | ok_inconclusive | 5 | 4 | 384 |

## Errors

### `cell::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `simple_pptr::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```
