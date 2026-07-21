# vstd determinism pilot

- vstd root: `/home/xuehaonan/nanvix/toolchain/verus/vstd`
- Verus root: `/home/xuehaonan/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 77
- Status counts: `{'ok': 75, 'unsupported_mut_ref_return': 2}`
- Classification counts: `{'ok_inconclusive': 15, 'complete': 60}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `atomic` | `fetch_and` | 610 | ok | unknown | ok_inconclusive | 3 | 8 | 578 |
| `atomic` | `fetch_xor` | 630 | ok | unknown | ok_inconclusive | 3 | 8 | 727 |
| `atomic` | `fetch_or` | 650 | ok | unknown | ok_inconclusive | 3 | 8 | 591 |
| `cell` | `empty` | 168 | ok | unknown | ok_inconclusive | 9 | 8 | 564 |
| `cell` | `new` | 178 | ok | unknown | ok_inconclusive | 9 | 10 | 461 |
| `cell` | `put` | 188 | ok | unsat | complete | 13 | 1 | 725 |
| `cell` | `take` | 203 | ok | unsat | complete | 13 | 1 | 688 |
| `cell` | `replace` | 223 | ok | unsat | complete | 13 | 1 | 681 |
| `cell` | `borrow` | 246 | ok | unsat | complete | 5 | 1 | 630 |
| `cell` | `into_inner` | 261 | ok | unsat | complete | 5 | 1 | 616 |
| `cell` | `borrow_mut` | 277 | unsupported_mut_ref_return |  |  |  |  | 30 |
| `cell` | `write` | 297 | ok | unsat | complete | 13 | 1 | 664 |
| `cell` | `new` | 344 | ok | unknown | ok_inconclusive | 1 | 2 | 438 |
| `cell` | `replace` | 359 | ok | unknown | ok_inconclusive | 1 | 2 | 417 |
| `cell` | `get` | 378 | ok | unknown | ok_inconclusive | 1 | 2 | 414 |
| `hash_map` | `new` | 43 | ok | unsat | complete | 1 | 1 | 694 |
| `hash_map` | `with_capacity` | 59 | ok | unsat | complete | 3 | 1 | 701 |
| `hash_map` | `reserve` | 73 | ok | unsat | complete | 3 | 1 | 673 |
| `hash_map` | `is_empty` | 82 | ok | unsat | complete | 5 | 1 | 674 |
| `hash_map` | `len` | 95 | ok | unsat | complete | 5 | 1 | 686 |
| `hash_map` | `insert` | 106 | ok | unsat | complete | 1 | 1 | 660 |
| `hash_map` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 772 |
| `hash_map` | `contains_key` | 133 | ok | unsat | complete | 5 | 1 | 651 |
| `hash_map` | `get` | 144 | ok | unsat | complete | 5 | 1 | 717 |
| `hash_map` | `clear` | 158 | ok | unsat | complete | 1 | 1 | 665 |
| `hash_map` | `union_prefer_right` | 167 | ok | unsat | complete | 1 | 1 | 651 |
| `hash_map` | `new` | 209 | ok | unsat | complete | 1 | 1 | 646 |
| `hash_map` | `with_capacity` | 220 | ok | unsat | complete | 3 | 1 | 665 |
| `hash_map` | `reserve` | 231 | ok | unsat | complete | 3 | 1 | 669 |
| `hash_map` | `is_empty` | 240 | ok | unsat | complete | 5 | 1 | 679 |
| `hash_map` | `len` | 253 | ok | unsat | complete | 5 | 1 | 666 |
| `hash_map` | `insert` | 264 | ok | unsat | complete | 4 | 1 | 678 |
| `hash_map` | `remove` | 275 | ok | unsat | complete | 4 | 1 | 695 |
| `hash_map` | `contains_key` | 286 | ok | unsat | complete | 8 | 1 | 771 |
| `hash_map` | `get` | 297 | ok | unsat | complete | 8 | 1 | 801 |
| `hash_map` | `clear` | 311 | ok | unsat | complete | 1 | 1 | 633 |
| `hash_map` | `union_prefer_right` | 320 | ok | unsat | complete | 1 | 1 | 652 |
| `hash_set` | `new` | 44 | ok | unsat | complete | 1 | 1 | 633 |
| `hash_set` | `with_capacity` | 60 | ok | unsat | complete | 3 | 1 | 653 |
| `hash_set` | `reserve` | 74 | ok | unsat | complete | 3 | 1 | 647 |
| `hash_set` | `len` | 87 | ok | unsat | complete | 5 | 1 | 646 |
| `hash_set` | `is_empty` | 96 | ok | unsat | complete | 5 | 1 | 705 |
| `hash_set` | `insert` | 107 | ok | unsat | complete | 5 | 1 | 724 |
| `hash_set` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 672 |
| `hash_set` | `contains` | 129 | ok | unsat | complete | 5 | 1 | 635 |
| `hash_set` | `get` | 140 | ok | unsat | complete | 5 | 1 | 692 |
| `hash_set` | `clear` | 154 | ok | unsat | complete | 1 | 1 | 635 |
| `hash_set` | `new` | 195 | ok | unsat | complete | 1 | 1 | 644 |
| `hash_set` | `with_capacity` | 206 | ok | unsat | complete | 3 | 1 | 623 |
| `hash_set` | `reserve` | 217 | ok | unsat | complete | 3 | 1 | 635 |
| `hash_set` | `is_empty` | 226 | ok | unsat | complete | 5 | 1 | 646 |
| `hash_set` | `len` | 239 | ok | unsat | complete | 5 | 1 | 635 |
| `hash_set` | `insert` | 250 | ok | unsat | complete | 8 | 1 | 748 |
| `hash_set` | `remove` | 261 | ok | unsat | complete | 8 | 1 | 754 |
| `hash_set` | `contains` | 272 | ok | unsat | complete | 8 | 1 | 749 |
| `hash_set` | `get` | 283 | ok | unsat | complete | 14 | 1 | 861 |
| `hash_set` | `clear` | 297 | ok | unsat | complete | 1 | 1 | 620 |
| `proph` | `resolve` | 187 | ok | unsat | complete | 1 | 1 | 591 |
| `rwlock` | `borrow` | 441 | ok | unsat | complete | 1 | 1 | 643 |
| `rwlock` | `new` | 502 | ok | unknown | ok_inconclusive | 1 | 2 | 443 |
| `rwlock` | `acquire_write` | 530 | ok | unknown | ok_inconclusive | 1 | 2 | 480 |
| `rwlock` | `acquire_read` | 620 | ok | unknown | ok_inconclusive | 1 | 2 | 530 |
| `rwlock` | `into_inner` | 702 | ok | unknown | ok_inconclusive | 1 | 2 | 436 |
| `simple_pptr` | `addr` | 184 | ok | unsat | complete | 5 | 1 | 651 |
| `simple_pptr` | `from_addr` | 203 | ok | unsat | complete | 3 | 1 | 610 |
| `simple_pptr` | `from_usize` | 212 | ok | unsat | complete | 3 | 1 | 626 |
| `simple_pptr` | `empty` | 347 | ok | unknown | ok_inconclusive | 9 | 17 | 606 |
| `simple_pptr` | `new` | 386 | ok | unknown | ok_inconclusive | 9 | 19 | 600 |
| `simple_pptr` | `into_inner` | 431 | ok | unsat | complete | 5 | 1 | 651 |
| `simple_pptr` | `put` | 451 | ok | unsat | complete | 13 | 1 | 780 |
| `simple_pptr` | `take` | 476 | ok | unsat | complete | 13 | 1 | 877 |
| `simple_pptr` | `replace` | 497 | ok | unsat | complete | 13 | 1 | 815 |
| `simple_pptr` | `borrow` | 519 | ok | unsat | complete | 5 | 1 | 654 |
| `simple_pptr` | `borrow_mut` | 537 | unsupported_mut_ref_return |  |  |  |  | 39 |
| `simple_pptr` | `write` | 557 | ok | unsat | complete | 13 | 1 | 840 |
| `simple_pptr` | `read` | 574 | ok | unsat | complete | 5 | 1 | 653 |
| `thread` | `join` | 27 | ok | unknown | ok_inconclusive | 5 | 4 | 411 |

## Errors

### `cell::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `simple_pptr::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```
