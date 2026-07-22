# vstd determinism pilot

- vstd root: `/home/xuehaonan/verus/source/vstd`
- Verus root: `/home/xuehaonan/verus/source/target-verus/release`
- Verus version: `0.2026.07.13.cf3b5c3`
- Verus commit: `unknown`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 98
- Status counts: `{'ok': 92, 'unsupported_mut_ref_return': 4, 'no_ensures': 2}`
- Classification counts: `{'complete': 84, 'ok_inconclusive': 7, 'incomplete_permitted': 1}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `atomic` | `fetch_and` | 604 | ok | unsat | complete | 3 | 1 | 733 |
| `atomic` | `fetch_xor` | 624 | ok | unsat | complete | 3 | 1 | 833 |
| `atomic` | `fetch_or` | 644 | ok | unsat | complete | 3 | 1 | 727 |
| `cell::invcell` | `new` | 105 | ok | unsat | complete | 1 | 1 | 623 |
| `cell::invcell` | `replace` | 123 | ok | unknown | ok_inconclusive | 1 | 2 | 420 |
| `cell::invcell` | `get` | 139 | ok | unknown | ok_inconclusive | 1 | 2 | 422 |
| `cell::invcell` | `into_inner` | 155 | ok | unknown | ok_inconclusive | 1 | 2 | 430 |
| `cell::pcell` | `new` | 132 | ok | unsat | complete | 9 | 1 | 597 |
| `cell::pcell` | `borrow` | 145 | ok | unsat | complete | 5 | 1 | 612 |
| `cell::pcell` | `borrow_mut` | 159 | unsupported_mut_ref_return |  |  |  |  | 11 |
| `cell::pcell` | `into_inner` | 175 | ok | unsat | complete | 5 | 1 | 611 |
| `cell::pcell` | `replace` | 193 | ok | unsat | complete | 13 | 1 | 602 |
| `cell::pcell` | `write` | 210 | ok | unsat | complete | 13 | 1 | 608 |
| `cell::pcell` | `read` | 224 | no_ensures |  |  |  |  | 9 |
| `cell::pcell_maybe_uninit` | `empty` | 107 | ok | unsat | complete | 9 | 1 | 619 |
| `cell::pcell_maybe_uninit` | `new` | 117 | ok | unsat | complete | 9 | 1 | 651 |
| `cell::pcell_maybe_uninit` | `put` | 127 | ok | unsat | complete | 13 | 1 | 636 |
| `cell::pcell_maybe_uninit` | `take` | 141 | ok | unsat | complete | 13 | 1 | 656 |
| `cell::pcell_maybe_uninit` | `replace` | 158 | ok | unsat | complete | 13 | 1 | 708 |
| `cell::pcell_maybe_uninit` | `borrow` | 175 | ok | unsat | complete | 5 | 1 | 624 |
| `cell::pcell_maybe_uninit` | `borrow_mut` | 190 | unsupported_mut_ref_return |  |  |  |  | 17 |
| `cell::pcell_maybe_uninit` | `into_inner` | 207 | ok | unsat | complete | 5 | 1 | 653 |
| `cell::pcell_maybe_uninit` | `write` | 221 | ok | unsat | complete | 13 | 1 | 695 |
| `cell::pcell_maybe_uninit` | `read` | 234 | no_ensures |  |  |  |  | 12 |
| `cell` | `empty` | 168 | ok | unsat | complete | 9 | 1 | 653 |
| `cell` | `new` | 178 | ok | unsat | complete | 9 | 1 | 625 |
| `cell` | `put` | 188 | ok | unsat | complete | 13 | 1 | 724 |
| `cell` | `take` | 203 | ok | unsat | complete | 13 | 1 | 680 |
| `cell` | `replace` | 223 | ok | unsat | complete | 13 | 1 | 776 |
| `cell` | `borrow` | 246 | ok | unsat | complete | 5 | 1 | 620 |
| `cell` | `into_inner` | 261 | ok | unsat | complete | 5 | 1 | 612 |
| `cell` | `borrow_mut` | 277 | unsupported_mut_ref_return |  |  |  |  | 36 |
| `cell` | `write` | 297 | ok | unsat | complete | 13 | 1 | 743 |
| `cell` | `new` | 344 | ok | unsat | complete | 1 | 1 | 638 |
| `cell` | `replace` | 359 | ok | unknown | ok_inconclusive | 1 | 2 | 454 |
| `cell` | `get` | 378 | ok | unknown | ok_inconclusive | 1 | 2 | 455 |
| `hash_map` | `new` | 43 | ok | unsat | complete | 1 | 1 | 660 |
| `hash_map` | `with_capacity` | 59 | ok | unsat | complete | 3 | 1 | 671 |
| `hash_map` | `reserve` | 73 | ok | unsat | complete | 3 | 1 | 694 |
| `hash_map` | `is_empty` | 82 | ok | unsat | complete | 5 | 1 | 670 |
| `hash_map` | `len` | 95 | ok | unsat | complete | 5 | 1 | 655 |
| `hash_map` | `insert` | 106 | ok | unsat | complete | 1 | 1 | 657 |
| `hash_map` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 716 |
| `hash_map` | `contains_key` | 133 | ok | unsat | complete | 5 | 1 | 653 |
| `hash_map` | `get` | 144 | ok | unsat | complete | 5 | 1 | 696 |
| `hash_map` | `clear` | 158 | ok | unsat | complete | 1 | 1 | 638 |
| `hash_map` | `union_prefer_right` | 167 | ok | unsat | complete | 1 | 1 | 652 |
| `hash_map` | `new` | 209 | ok | unsat | complete | 1 | 1 | 642 |
| `hash_map` | `with_capacity` | 220 | ok | unsat | complete | 3 | 1 | 652 |
| `hash_map` | `reserve` | 231 | ok | unsat | complete | 3 | 1 | 643 |
| `hash_map` | `is_empty` | 240 | ok | unsat | complete | 5 | 1 | 658 |
| `hash_map` | `len` | 253 | ok | unsat | complete | 5 | 1 | 628 |
| `hash_map` | `insert` | 264 | ok | unsat | complete | 4 | 1 | 681 |
| `hash_map` | `remove` | 275 | ok | unsat | complete | 4 | 1 | 671 |
| `hash_map` | `contains_key` | 286 | ok | unsat | complete | 8 | 1 | 805 |
| `hash_map` | `get` | 297 | ok | unsat | complete | 8 | 1 | 783 |
| `hash_map` | `clear` | 311 | ok | unsat | complete | 1 | 1 | 667 |
| `hash_map` | `union_prefer_right` | 320 | ok | unsat | complete | 1 | 1 | 640 |
| `hash_set` | `new` | 44 | ok | unsat | complete | 1 | 1 | 631 |
| `hash_set` | `with_capacity` | 60 | ok | unsat | complete | 3 | 1 | 647 |
| `hash_set` | `reserve` | 74 | ok | unsat | complete | 3 | 1 | 621 |
| `hash_set` | `len` | 87 | ok | unsat | complete | 5 | 1 | 656 |
| `hash_set` | `is_empty` | 96 | ok | unsat | complete | 5 | 1 | 628 |
| `hash_set` | `insert` | 107 | ok | unsat | complete | 5 | 1 | 668 |
| `hash_set` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 666 |
| `hash_set` | `contains` | 129 | ok | unsat | complete | 5 | 1 | 656 |
| `hash_set` | `get` | 140 | ok | unsat | complete | 5 | 1 | 643 |
| `hash_set` | `clear` | 154 | ok | unsat | complete | 1 | 1 | 649 |
| `hash_set` | `new` | 195 | ok | unsat | complete | 1 | 1 | 612 |
| `hash_set` | `with_capacity` | 206 | ok | unsat | complete | 3 | 1 | 661 |
| `hash_set` | `reserve` | 217 | ok | unsat | complete | 3 | 1 | 651 |
| `hash_set` | `is_empty` | 226 | ok | unsat | complete | 5 | 1 | 624 |
| `hash_set` | `len` | 239 | ok | unsat | complete | 5 | 1 | 668 |
| `hash_set` | `insert` | 250 | ok | unsat | complete | 8 | 1 | 744 |
| `hash_set` | `remove` | 261 | ok | unsat | complete | 8 | 1 | 762 |
| `hash_set` | `contains` | 272 | ok | unsat | complete | 8 | 1 | 724 |
| `hash_set` | `get` | 283 | ok | unsat | complete | 14 | 1 | 836 |
| `hash_set` | `clear` | 297 | ok | unsat | complete | 1 | 1 | 678 |
| `proph` | `resolve` | 187 | ok | unsat | complete | 1 | 1 | 625 |
| `rwlock` | `borrow` | 441 | ok | unsat | complete | 1 | 1 | 635 |
| `rwlock` | `new` | 502 | ok | unsat | complete | 1 | 1 | 666 |
| `rwlock` | `acquire_write` | 530 | ok | unknown | ok_inconclusive | 1 | 2 | 498 |
| `rwlock` | `acquire_read` | 620 | ok | unsat | complete | 1 | 1 | 683 |
| `rwlock` | `into_inner` | 702 | ok | unknown | ok_inconclusive | 1 | 2 | 450 |
| `simple_pptr` | `addr` | 184 | ok | unsat | complete | 5 | 1 | 658 |
| `simple_pptr` | `from_addr` | 203 | ok | unsat | complete | 3 | 1 | 632 |
| `simple_pptr` | `from_usize` | 212 | ok | unsat | complete | 3 | 1 | 613 |
| `simple_pptr` | `empty` | 347 | ok | unsat | complete | 9 | 1 | 754 |
| `simple_pptr` | `new` | 397 | ok | unsat | complete | 9 | 1 | 788 |
| `simple_pptr` | `into_inner` | 442 | ok | unsat | complete | 5 | 1 | 669 |
| `simple_pptr` | `put` | 462 | ok | unsat | complete | 13 | 1 | 843 |
| `simple_pptr` | `take` | 487 | ok | unsat | complete | 13 | 1 | 834 |
| `simple_pptr` | `replace` | 508 | ok | unsat | complete | 13 | 1 | 816 |
| `simple_pptr` | `borrow` | 530 | ok | unsat | complete | 5 | 1 | 645 |
| `simple_pptr` | `borrow_mut` | 548 | unsupported_mut_ref_return |  |  |  |  | 50 |
| `simple_pptr` | `write` | 568 | ok | unsat | complete | 13 | 1 | 799 |
| `simple_pptr` | `read` | 585 | ok | unsat | complete | 5 | 1 | 642 |
| `thread` | `join` | 27 | ok | unknown | incomplete_permitted | 5 | 4 | 443 |

## Errors

### `cell::pcell::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `cell::pcell::read`

```text
no_ensures
```

### `cell::pcell_maybe_uninit::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `cell::pcell_maybe_uninit::read`

```text
no_ensures
```

### `cell::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `simple_pptr::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```
