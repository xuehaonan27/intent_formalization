# vstd determinism pilot

- vstd root: `/home/xuehaonan/verus/source/vstd`
- Verus root: `/home/xuehaonan/verus/source/target-verus/release`
- Verus version: `0.2026.07.13.cf3b5c3`
- Verus commit: `unknown`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 98
- Status counts: `{'ok': 92, 'unsupported_mut_ref_return': 4, 'no_ensures': 2}`
- Classification counts: `{'ok_inconclusive': 22, 'complete': 70}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `atomic` | `fetch_and` | 604 | ok | unknown | ok_inconclusive | 3 | 8 | 589 |
| `atomic` | `fetch_xor` | 624 | ok | unknown | ok_inconclusive | 3 | 8 | 570 |
| `atomic` | `fetch_or` | 644 | ok | unknown | ok_inconclusive | 3 | 8 | 566 |
| `cell::invcell` | `new` | 105 | ok | unknown | ok_inconclusive | 1 | 2 | 440 |
| `cell::invcell` | `replace` | 123 | ok | unknown | ok_inconclusive | 1 | 2 | 419 |
| `cell::invcell` | `get` | 139 | ok | unknown | ok_inconclusive | 1 | 2 | 417 |
| `cell::invcell` | `into_inner` | 155 | ok | unknown | ok_inconclusive | 1 | 2 | 417 |
| `cell::pcell` | `new` | 132 | ok | unknown | ok_inconclusive | 9 | 10 | 448 |
| `cell::pcell` | `borrow` | 145 | ok | unsat | complete | 5 | 1 | 600 |
| `cell::pcell` | `borrow_mut` | 159 | unsupported_mut_ref_return |  |  |  |  | 12 |
| `cell::pcell` | `into_inner` | 175 | ok | unsat | complete | 5 | 1 | 643 |
| `cell::pcell` | `replace` | 193 | ok | unsat | complete | 13 | 1 | 604 |
| `cell::pcell` | `write` | 210 | ok | unsat | complete | 13 | 1 | 615 |
| `cell::pcell` | `read` | 224 | no_ensures |  |  |  |  | 9 |
| `cell::pcell_maybe_uninit` | `empty` | 107 | ok | unknown | ok_inconclusive | 9 | 8 | 458 |
| `cell::pcell_maybe_uninit` | `new` | 117 | ok | unknown | ok_inconclusive | 9 | 10 | 462 |
| `cell::pcell_maybe_uninit` | `put` | 127 | ok | unsat | complete | 13 | 1 | 649 |
| `cell::pcell_maybe_uninit` | `take` | 141 | ok | unsat | complete | 13 | 1 | 646 |
| `cell::pcell_maybe_uninit` | `replace` | 158 | ok | unsat | complete | 13 | 1 | 675 |
| `cell::pcell_maybe_uninit` | `borrow` | 175 | ok | unsat | complete | 5 | 1 | 608 |
| `cell::pcell_maybe_uninit` | `borrow_mut` | 190 | unsupported_mut_ref_return |  |  |  |  | 15 |
| `cell::pcell_maybe_uninit` | `into_inner` | 207 | ok | unsat | complete | 5 | 1 | 585 |
| `cell::pcell_maybe_uninit` | `write` | 221 | ok | unsat | complete | 13 | 1 | 706 |
| `cell::pcell_maybe_uninit` | `read` | 234 | no_ensures |  |  |  |  | 12 |
| `cell` | `empty` | 168 | ok | unknown | ok_inconclusive | 9 | 8 | 465 |
| `cell` | `new` | 178 | ok | unknown | ok_inconclusive | 9 | 10 | 501 |
| `cell` | `put` | 188 | ok | unsat | complete | 13 | 1 | 692 |
| `cell` | `take` | 203 | ok | unsat | complete | 13 | 1 | 664 |
| `cell` | `replace` | 223 | ok | unsat | complete | 13 | 1 | 684 |
| `cell` | `borrow` | 246 | ok | unsat | complete | 5 | 1 | 650 |
| `cell` | `into_inner` | 261 | ok | unsat | complete | 5 | 1 | 666 |
| `cell` | `borrow_mut` | 277 | unsupported_mut_ref_return |  |  |  |  | 30 |
| `cell` | `write` | 297 | ok | unsat | complete | 13 | 1 | 649 |
| `cell` | `new` | 344 | ok | unknown | ok_inconclusive | 1 | 2 | 477 |
| `cell` | `replace` | 359 | ok | unknown | ok_inconclusive | 1 | 2 | 433 |
| `cell` | `get` | 378 | ok | unknown | ok_inconclusive | 1 | 2 | 454 |
| `hash_map` | `new` | 43 | ok | unsat | complete | 1 | 1 | 676 |
| `hash_map` | `with_capacity` | 59 | ok | unsat | complete | 3 | 1 | 659 |
| `hash_map` | `reserve` | 73 | ok | unsat | complete | 3 | 1 | 637 |
| `hash_map` | `is_empty` | 82 | ok | unsat | complete | 5 | 1 | 644 |
| `hash_map` | `len` | 95 | ok | unsat | complete | 5 | 1 | 643 |
| `hash_map` | `insert` | 106 | ok | unsat | complete | 1 | 1 | 666 |
| `hash_map` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 714 |
| `hash_map` | `contains_key` | 133 | ok | unsat | complete | 5 | 1 | 657 |
| `hash_map` | `get` | 144 | ok | unsat | complete | 5 | 1 | 691 |
| `hash_map` | `clear` | 158 | ok | unsat | complete | 1 | 1 | 653 |
| `hash_map` | `union_prefer_right` | 167 | ok | unsat | complete | 1 | 1 | 644 |
| `hash_map` | `new` | 209 | ok | unsat | complete | 1 | 1 | 661 |
| `hash_map` | `with_capacity` | 220 | ok | unsat | complete | 3 | 1 | 627 |
| `hash_map` | `reserve` | 231 | ok | unsat | complete | 3 | 1 | 635 |
| `hash_map` | `is_empty` | 240 | ok | unsat | complete | 5 | 1 | 626 |
| `hash_map` | `len` | 253 | ok | unsat | complete | 5 | 1 | 643 |
| `hash_map` | `insert` | 264 | ok | unsat | complete | 4 | 1 | 662 |
| `hash_map` | `remove` | 275 | ok | unsat | complete | 4 | 1 | 662 |
| `hash_map` | `contains_key` | 286 | ok | unsat | complete | 8 | 1 | 781 |
| `hash_map` | `get` | 297 | ok | unsat | complete | 8 | 1 | 749 |
| `hash_map` | `clear` | 311 | ok | unsat | complete | 1 | 1 | 732 |
| `hash_map` | `union_prefer_right` | 320 | ok | unsat | complete | 1 | 1 | 633 |
| `hash_set` | `new` | 44 | ok | unsat | complete | 1 | 1 | 643 |
| `hash_set` | `with_capacity` | 60 | ok | unsat | complete | 3 | 1 | 630 |
| `hash_set` | `reserve` | 74 | ok | unsat | complete | 3 | 1 | 620 |
| `hash_set` | `len` | 87 | ok | unsat | complete | 5 | 1 | 639 |
| `hash_set` | `is_empty` | 96 | ok | unsat | complete | 5 | 1 | 646 |
| `hash_set` | `insert` | 107 | ok | unsat | complete | 5 | 1 | 640 |
| `hash_set` | `remove` | 118 | ok | unsat | complete | 5 | 1 | 659 |
| `hash_set` | `contains` | 129 | ok | unsat | complete | 5 | 1 | 629 |
| `hash_set` | `get` | 140 | ok | unsat | complete | 5 | 1 | 653 |
| `hash_set` | `clear` | 154 | ok | unsat | complete | 1 | 1 | 620 |
| `hash_set` | `new` | 195 | ok | unsat | complete | 1 | 1 | 614 |
| `hash_set` | `with_capacity` | 206 | ok | unsat | complete | 3 | 1 | 649 |
| `hash_set` | `reserve` | 217 | ok | unsat | complete | 3 | 1 | 619 |
| `hash_set` | `is_empty` | 226 | ok | unsat | complete | 5 | 1 | 631 |
| `hash_set` | `len` | 239 | ok | unsat | complete | 5 | 1 | 646 |
| `hash_set` | `insert` | 250 | ok | unsat | complete | 8 | 1 | 722 |
| `hash_set` | `remove` | 261 | ok | unsat | complete | 8 | 1 | 756 |
| `hash_set` | `contains` | 272 | ok | unsat | complete | 8 | 1 | 736 |
| `hash_set` | `get` | 283 | ok | unsat | complete | 14 | 1 | 823 |
| `hash_set` | `clear` | 297 | ok | unsat | complete | 1 | 1 | 701 |
| `proph` | `resolve` | 187 | ok | unsat | complete | 1 | 1 | 633 |
| `rwlock` | `borrow` | 441 | ok | unsat | complete | 1 | 1 | 617 |
| `rwlock` | `new` | 502 | ok | unknown | ok_inconclusive | 1 | 2 | 490 |
| `rwlock` | `acquire_write` | 530 | ok | unknown | ok_inconclusive | 1 | 2 | 498 |
| `rwlock` | `acquire_read` | 620 | ok | unknown | ok_inconclusive | 1 | 2 | 510 |
| `rwlock` | `into_inner` | 702 | ok | unknown | ok_inconclusive | 1 | 2 | 487 |
| `simple_pptr` | `addr` | 184 | ok | unsat | complete | 5 | 1 | 604 |
| `simple_pptr` | `from_addr` | 203 | ok | unsat | complete | 3 | 1 | 641 |
| `simple_pptr` | `from_usize` | 212 | ok | unsat | complete | 3 | 1 | 606 |
| `simple_pptr` | `empty` | 347 | ok | unknown | ok_inconclusive | 9 | 17 | 612 |
| `simple_pptr` | `new` | 397 | ok | unknown | ok_inconclusive | 9 | 19 | 671 |
| `simple_pptr` | `into_inner` | 442 | ok | unsat | complete | 5 | 1 | 637 |
| `simple_pptr` | `put` | 462 | ok | unsat | complete | 13 | 1 | 782 |
| `simple_pptr` | `take` | 487 | ok | unsat | complete | 13 | 1 | 817 |
| `simple_pptr` | `replace` | 508 | ok | unsat | complete | 13 | 1 | 839 |
| `simple_pptr` | `borrow` | 530 | ok | unsat | complete | 5 | 1 | 742 |
| `simple_pptr` | `borrow_mut` | 548 | unsupported_mut_ref_return |  |  |  |  | 49 |
| `simple_pptr` | `write` | 568 | ok | unsat | complete | 13 | 1 | 872 |
| `simple_pptr` | `read` | 585 | ok | unsat | complete | 5 | 1 | 633 |
| `thread` | `join` | 27 | ok | unknown | ok_inconclusive | 5 | 4 | 463 |

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
