# vstd determinism pilot

- vstd root: `/home/xuehaonan/verus/source/vstd`
- Verus root: `/home/xuehaonan/verus/source/target-verus/release`
- Verus version: `0.2026.07.13.cf3b5c3`
- Verus commit: `unknown`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 98
- Status counts: `{'ok': 94, 'unsupported_mut_ref_return': 4}`
- Classification counts: `{'complete': 86, 'incomplete': 7, 'incomplete_permitted': 1}`
- Audit label counts: `{'complete_tool_gap': 6, 'incomplete': 7, 'complete': 80, 'unsupported_mut_ref_return': 4, 'incomplete_permitted': 1}`

| Module | Function | Line | Status | R0 Z3 | Classification | Audit | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---|---:|---:|---:|
| `atomic` | `fetch_and` | 604 | ok | unsat | complete | complete_tool_gap | 3 | 1 | 798 |
| `atomic` | `fetch_xor` | 624 | ok | unsat | complete | complete_tool_gap | 3 | 1 | 811 |
| `atomic` | `fetch_or` | 644 | ok | unsat | complete | complete_tool_gap | 3 | 1 | 735 |
| `cell::invcell` | `new` | 105 | ok | unsat | complete | complete_tool_gap | 1 | 1 | 614 |
| `cell::invcell` | `replace` | 123 | ok | unknown | incomplete | incomplete | 1 | 2 | 434 |
| `cell::invcell` | `get` | 139 | ok | unknown | incomplete | incomplete | 1 | 2 | 474 |
| `cell::invcell` | `into_inner` | 155 | ok | unknown | incomplete | incomplete | 1 | 2 | 443 |
| `cell::pcell` | `new` | 132 | ok | unsat | complete | complete | 9 | 1 | 620 |
| `cell::pcell` | `borrow` | 145 | ok | unsat | complete | complete | 5 | 1 | 610 |
| `cell::pcell` | `borrow_mut` | 159 | unsupported_mut_ref_return |  |  | unsupported_mut_ref_return |  |  | 13 |
| `cell::pcell` | `into_inner` | 175 | ok | unsat | complete | complete | 5 | 1 | 604 |
| `cell::pcell` | `replace` | 193 | ok | unsat | complete | complete | 13 | 1 | 599 |
| `cell::pcell` | `write` | 210 | ok | unsat | complete | complete | 13 | 1 | 609 |
| `cell::pcell` | `read` | 224 | ok | unsat | complete | complete | 5 | 1 | 609 |
| `cell::pcell_maybe_uninit` | `empty` | 107 | ok | unsat | complete | complete | 9 | 1 | 664 |
| `cell::pcell_maybe_uninit` | `new` | 117 | ok | unsat | complete | complete | 9 | 1 | 644 |
| `cell::pcell_maybe_uninit` | `put` | 127 | ok | unsat | complete | complete | 13 | 1 | 620 |
| `cell::pcell_maybe_uninit` | `take` | 141 | ok | unsat | complete | complete | 13 | 1 | 771 |
| `cell::pcell_maybe_uninit` | `replace` | 158 | ok | unsat | complete | complete | 13 | 1 | 657 |
| `cell::pcell_maybe_uninit` | `borrow` | 175 | ok | unsat | complete | complete | 5 | 1 | 679 |
| `cell::pcell_maybe_uninit` | `borrow_mut` | 190 | unsupported_mut_ref_return |  |  | unsupported_mut_ref_return |  |  | 15 |
| `cell::pcell_maybe_uninit` | `into_inner` | 207 | ok | unsat | complete | complete | 5 | 1 | 620 |
| `cell::pcell_maybe_uninit` | `write` | 221 | ok | unsat | complete | complete | 13 | 1 | 753 |
| `cell::pcell_maybe_uninit` | `read` | 234 | ok | unsat | complete | complete | 5 | 1 | 657 |
| `cell` | `empty` | 168 | ok | unsat | complete | complete | 9 | 1 | 715 |
| `cell` | `new` | 178 | ok | unsat | complete | complete | 9 | 1 | 693 |
| `cell` | `put` | 188 | ok | unsat | complete | complete | 13 | 1 | 826 |
| `cell` | `take` | 203 | ok | unsat | complete | complete | 13 | 1 | 728 |
| `cell` | `replace` | 223 | ok | unsat | complete | complete | 13 | 1 | 751 |
| `cell` | `borrow` | 246 | ok | unsat | complete | complete | 5 | 1 | 831 |
| `cell` | `into_inner` | 261 | ok | unsat | complete | complete | 5 | 1 | 751 |
| `cell` | `borrow_mut` | 277 | unsupported_mut_ref_return |  |  | unsupported_mut_ref_return |  |  | 33 |
| `cell` | `write` | 297 | ok | unsat | complete | complete | 13 | 1 | 743 |
| `cell` | `new` | 344 | ok | unsat | complete | complete_tool_gap | 1 | 1 | 640 |
| `cell` | `replace` | 359 | ok | unknown | incomplete | incomplete | 1 | 2 | 439 |
| `cell` | `get` | 378 | ok | unknown | incomplete | incomplete | 1 | 2 | 459 |
| `hash_map` | `new` | 43 | ok | unsat | complete | complete | 1 | 1 | 661 |
| `hash_map` | `with_capacity` | 59 | ok | unsat | complete | complete | 3 | 1 | 655 |
| `hash_map` | `reserve` | 73 | ok | unsat | complete | complete | 3 | 1 | 659 |
| `hash_map` | `is_empty` | 82 | ok | unsat | complete | complete | 5 | 1 | 696 |
| `hash_map` | `len` | 95 | ok | unsat | complete | complete | 5 | 1 | 791 |
| `hash_map` | `insert` | 106 | ok | unsat | complete | complete | 1 | 1 | 849 |
| `hash_map` | `remove` | 118 | ok | unsat | complete | complete | 5 | 1 | 741 |
| `hash_map` | `contains_key` | 133 | ok | unsat | complete | complete | 5 | 1 | 650 |
| `hash_map` | `get` | 144 | ok | unsat | complete | complete | 5 | 1 | 722 |
| `hash_map` | `clear` | 158 | ok | unsat | complete | complete | 1 | 1 | 724 |
| `hash_map` | `union_prefer_right` | 167 | ok | unsat | complete | complete | 1 | 1 | 695 |
| `hash_map` | `new` | 209 | ok | unsat | complete | complete | 1 | 1 | 656 |
| `hash_map` | `with_capacity` | 220 | ok | unsat | complete | complete | 3 | 1 | 625 |
| `hash_map` | `reserve` | 231 | ok | unsat | complete | complete | 3 | 1 | 665 |
| `hash_map` | `is_empty` | 240 | ok | unsat | complete | complete | 5 | 1 | 659 |
| `hash_map` | `len` | 253 | ok | unsat | complete | complete | 5 | 1 | 669 |
| `hash_map` | `insert` | 264 | ok | unsat | complete | complete | 4 | 1 | 748 |
| `hash_map` | `remove` | 275 | ok | unsat | complete | complete | 4 | 1 | 719 |
| `hash_map` | `contains_key` | 286 | ok | unsat | complete | complete | 8 | 1 | 765 |
| `hash_map` | `get` | 297 | ok | unsat | complete | complete | 8 | 1 | 958 |
| `hash_map` | `clear` | 311 | ok | unsat | complete | complete | 1 | 1 | 663 |
| `hash_map` | `union_prefer_right` | 320 | ok | unsat | complete | complete | 1 | 1 | 677 |
| `hash_set` | `new` | 44 | ok | unsat | complete | complete | 1 | 1 | 736 |
| `hash_set` | `with_capacity` | 60 | ok | unsat | complete | complete | 3 | 1 | 734 |
| `hash_set` | `reserve` | 74 | ok | unsat | complete | complete | 3 | 1 | 694 |
| `hash_set` | `len` | 87 | ok | unsat | complete | complete | 5 | 1 | 645 |
| `hash_set` | `is_empty` | 96 | ok | unsat | complete | complete | 5 | 1 | 656 |
| `hash_set` | `insert` | 107 | ok | unsat | complete | complete | 5 | 1 | 682 |
| `hash_set` | `remove` | 118 | ok | unsat | complete | complete | 5 | 1 | 700 |
| `hash_set` | `contains` | 129 | ok | unsat | complete | complete | 5 | 1 | 654 |
| `hash_set` | `get` | 140 | ok | unsat | complete | complete | 5 | 1 | 688 |
| `hash_set` | `clear` | 154 | ok | unsat | complete | complete | 1 | 1 | 652 |
| `hash_set` | `new` | 195 | ok | unsat | complete | complete | 1 | 1 | 731 |
| `hash_set` | `with_capacity` | 206 | ok | unsat | complete | complete | 3 | 1 | 716 |
| `hash_set` | `reserve` | 217 | ok | unsat | complete | complete | 3 | 1 | 722 |
| `hash_set` | `is_empty` | 226 | ok | unsat | complete | complete | 5 | 1 | 656 |
| `hash_set` | `len` | 239 | ok | unsat | complete | complete | 5 | 1 | 699 |
| `hash_set` | `insert` | 250 | ok | unsat | complete | complete | 8 | 1 | 878 |
| `hash_set` | `remove` | 261 | ok | unsat | complete | complete | 8 | 1 | 950 |
| `hash_set` | `contains` | 272 | ok | unsat | complete | complete | 8 | 1 | 761 |
| `hash_set` | `get` | 283 | ok | unsat | complete | complete | 14 | 1 | 870 |
| `hash_set` | `clear` | 297 | ok | unsat | complete | complete | 1 | 1 | 643 |
| `proph` | `resolve` | 187 | ok | unsat | complete | complete | 1 | 1 | 694 |
| `rwlock` | `borrow` | 441 | ok | unsat | complete | complete | 1 | 1 | 635 |
| `rwlock` | `new` | 502 | ok | unsat | complete | complete | 1 | 1 | 674 |
| `rwlock` | `acquire_write` | 530 | ok | unknown | incomplete | incomplete | 1 | 2 | 506 |
| `rwlock` | `acquire_read` | 620 | ok | unsat | complete | complete_tool_gap | 1 | 1 | 709 |
| `rwlock` | `into_inner` | 702 | ok | unknown | incomplete | incomplete | 1 | 2 | 467 |
| `simple_pptr` | `addr` | 184 | ok | unsat | complete | complete | 5 | 1 | 613 |
| `simple_pptr` | `from_addr` | 203 | ok | unsat | complete | complete | 3 | 1 | 658 |
| `simple_pptr` | `from_usize` | 212 | ok | unsat | complete | complete | 3 | 1 | 614 |
| `simple_pptr` | `empty` | 347 | ok | unsat | complete | complete | 9 | 1 | 779 |
| `simple_pptr` | `new` | 397 | ok | unsat | complete | complete | 9 | 1 | 779 |
| `simple_pptr` | `into_inner` | 442 | ok | unsat | complete | complete | 5 | 1 | 731 |
| `simple_pptr` | `put` | 462 | ok | unsat | complete | complete | 13 | 1 | 792 |
| `simple_pptr` | `take` | 487 | ok | unsat | complete | complete | 13 | 1 | 848 |
| `simple_pptr` | `replace` | 508 | ok | unsat | complete | complete | 13 | 1 | 813 |
| `simple_pptr` | `borrow` | 530 | ok | unsat | complete | complete | 5 | 1 | 652 |
| `simple_pptr` | `borrow_mut` | 548 | unsupported_mut_ref_return |  |  | unsupported_mut_ref_return |  |  | 41 |
| `simple_pptr` | `write` | 568 | ok | unsat | complete | complete | 13 | 1 | 795 |
| `simple_pptr` | `read` | 585 | ok | unsat | complete | complete | 5 | 1 | 662 |
| `thread` | `join` | 27 | ok | unknown | incomplete_permitted | incomplete_permitted | 5 | 4 | 470 |

## Errors

### `cell::pcell::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `cell::pcell_maybe_uninit::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `cell::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `simple_pptr::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```
