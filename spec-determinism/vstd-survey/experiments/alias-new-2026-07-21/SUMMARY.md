# vstd determinism pilot

- vstd root: `/home/xuehaonan/nanvix/toolchain/verus/vstd`
- Verus root: `/home/xuehaonan/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 26
- Status counts: `{'ok': 9, 'verus_error': 12, 'unsupported_mut_ref_return': 3, 'no_ensures': 2}`
- Classification counts: `{'ok_inconclusive': 6, 'complete': 3}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `cell::invcell` | `new` | 105 | ok | unknown | ok_inconclusive | 1 | 2 | 423 |
| `cell::invcell` | `replace` | 123 | ok | unknown | ok_inconclusive | 1 | 2 | 396 |
| `cell::invcell` | `get` | 139 | ok | unknown | ok_inconclusive | 1 | 2 | 395 |
| `cell::invcell` | `into_inner` | 155 | ok | unknown | ok_inconclusive | 1 | 2 | 393 |
| `cell::pcell` | `new` | 132 | ok | unknown | ok_inconclusive | 9 | 10 | 417 |
| `cell::pcell` | `borrow` | 145 | verus_error |  |  | 5 |  | 38 |
| `cell::pcell` | `borrow_mut` | 159 | unsupported_mut_ref_return |  |  |  |  | 11 |
| `cell::pcell` | `into_inner` | 175 | verus_error |  |  | 5 |  | 34 |
| `cell::pcell` | `replace` | 193 | verus_error |  |  | 13 |  | 42 |
| `cell::pcell` | `write` | 210 | verus_error |  |  | 13 |  | 35 |
| `cell::pcell` | `read` | 224 | no_ensures |  |  |  |  | 9 |
| `cell::pcell_maybe_uninit` | `empty` | 107 | verus_error |  |  | 9 |  | 76 |
| `cell::pcell_maybe_uninit` | `new` | 117 | verus_error |  |  | 9 |  | 83 |
| `cell::pcell_maybe_uninit` | `put` | 127 | verus_error |  |  | 13 |  | 90 |
| `cell::pcell_maybe_uninit` | `take` | 141 | verus_error |  |  | 13 |  | 93 |
| `cell::pcell_maybe_uninit` | `replace` | 158 | verus_error |  |  | 13 |  | 93 |
| `cell::pcell_maybe_uninit` | `borrow` | 175 | ok | unsat | complete | 5 | 1 | 654 |
| `cell::pcell_maybe_uninit` | `borrow_mut` | 190 | unsupported_mut_ref_return |  |  |  |  | 23 |
| `cell::pcell_maybe_uninit` | `into_inner` | 207 | ok | unsat | complete | 5 | 1 | 685 |
| `cell::pcell_maybe_uninit` | `write` | 221 | verus_error |  |  | 13 |  | 81 |
| `cell::pcell_maybe_uninit` | `read` | 234 | no_ensures |  |  |  |  | 12 |
| `std_specs::core` | `index_set` | 215 | verus_error |  |  | 1 |  | 395 |
| `std_specs::iter` | `new` | 264 | ok | unsat | complete | 3 | 1 | 647 |
| `std_specs::iter` | `next` | 287 | ok | unknown | ok_inconclusive | 5 | 4 | 740 |
| `std_specs::vec` | `vec_index` | 53 | verus_error |  |  | 5 |  | 133 |
| `std_specs::vec` | `vec_index_mut` | 67 | unsupported_mut_ref_return |  |  |  |  | 70 |

## Errors

### `cell::pcell::borrow`

```text
error: unexpected closing delimiter: `}`
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell__borrow__L145/harness.rs:25:1
   |
22 |     if g__perm__is_init___is_true { assume(true) == true); }
   |                                   -                     - missing open `(` for this delimiter
   |                                   |
   |                                   the nearest open delimiter
23 |     if g__perm__is_init___is_false { assume(true) == false); }
   |                                    -                      - missing open `(` for this delimiter
   |                                    |
   |                                    the nearest open delimiter
24 |     if g_neq_tuple { assume(!det_borrow_equal::<T>(r1, r2)); }
25 | }
   | ^ unexpected closing delimiter

error: aborting due to 1 previous error


```

### `cell::pcell::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `cell::pcell::into_inner`

```text
error: unexpected closing delimiter: `}`
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell__into_inner__L175/harness.rs:27:1
   |
24 |     if g__perm__is_init___is_true { assume(true) == true); }
   |                                   -                     - missing open `(` for this delimiter
   |                                   |
   |                                   the nearest open delimiter
25 |     if g__perm__is_init___is_false { assume(true) == false); }
   |                                    -                      - missing open `(` for this delimiter
   |                                    |
   |                                    the nearest open delimiter
26 |     if g_neq_tuple { assume(!det_into_inner_equal::<T>(r1, r2)); }
27 | }
   | ^ unexpected closing delimiter

error: aborting due to 1 previous error


```

### `cell::pcell::replace`

```text
error: unexpected closing delimiter: `}`
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell__replace__L193/harness.rs:14:1
   |
 7 | verus! {
   |        - the nearest open delimiter
...
11 |     where T: Sized {
   |                    - the nearest open delimiter
12 |     (r1 == r2)
13 |     && ((true) == (true)) && ((post1_perm).id() == (post2_perm).id()) && (true) ==> ((post1_perm).value() == (post2_perm).value())))
   |                                                                                                                                   -- missing open `(` for this delimiter
   |                                                                                                                                   |
   |                                                                                                                                   missing open `(` for this delimiter
14 | }
   | ^ unexpected closing delimiter

error: aborting due to 1 previous error


```

### `cell::pcell::write`

```text
error: unexpected closing delimiter: `}`
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell__write__L210/harness.rs:14:1
   |
 7 | verus! {
   |        - the nearest open delimiter
...
11 |     where T: Sized {
   |                    - the nearest open delimiter
12 |     (r1 == r2)
13 |     && ((true) == (true)) && ((post1_perm).id() == (post2_perm).id()) && (true) ==> ((post1_perm).value() == (post2_perm).value())))
   |                                                                                                                                   -- missing open `(` for this delimiter
   |                                                                                                                                   |
   |                                                                                                                                   missing open `(` for this delimiter
14 | }
   | ^ unexpected closing delimiter

error: aborting due to 1 previous error


```

### `cell::pcell::read`

```text
no_ensures
```

### `cell::pcell_maybe_uninit::empty`

```text
error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__empty__L107/harness.rs:18:42
   |
18 |             &&& (r1.1@.mem_contents() == MemContents::Uninit)
   |                                          ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__empty__L107/harness.rs:20:42
   |
20 |             &&& (r2.1@.mem_contents() == MemContents::Uninit)
   |                                          ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error: aborting due to 2 previous errors

For more information about this error, try `rustc --explain E0433`.

```

### `cell::pcell_maybe_uninit::new`

```text
error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__new__L117/harness.rs:18:42
   |
18 |             &&& (r1.1@.mem_contents() == MemContents::Init(v))
   |                                          ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__new__L117/harness.rs:20:42
   |
20 |             &&& (r2.1@.mem_contents() == MemContents::Init(v))
   |                                          ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error: aborting due to 2 previous errors

For more information about this error, try `rustc --explain E0433`.

```

### `cell::pcell_maybe_uninit::put`

```text
error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__put__L127/harness.rs:16:73
   |
16 |     requires (pre_perm.id() == self_.id()), (pre_perm.mem_contents() == MemContents::Uninit),
   |                                                                         ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__put__L127/harness.rs:20:47
   |
20 |             &&& (post1_perm.mem_contents() == MemContents::Init(in_v))
   |                                               ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__put__L127/harness.rs:22:47
   |
22 |             &&& (post2_perm.mem_contents() == MemContents::Init(in_v))
   |                                               ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error: aborting due to 3 previous errors

For more information about this error, try `rustc --explain E0433`.

```

### `cell::pcell_maybe_uninit::take`

```text
error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__take__L141/harness.rs:20:47
   |
20 |             &&& (post1_perm.mem_contents() == MemContents::Uninit)
   |                                               ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__take__L141/harness.rs:23:47
   |
23 |             &&& (post2_perm.mem_contents() == MemContents::Uninit)
   |                                               ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error: aborting due to 2 previous errors

For more information about this error, try `rustc --explain E0433`.

```

### `cell::pcell_maybe_uninit::replace`

```text
error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__replace__L158/harness.rs:20:47
   |
20 |             &&& (post1_perm.mem_contents() == MemContents::Init(in_v))
   |                                               ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__replace__L158/harness.rs:23:47
   |
23 |             &&& (post2_perm.mem_contents() == MemContents::Init(in_v))
   |                                               ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error: aborting due to 2 previous errors

For more information about this error, try `rustc --explain E0433`.

```

### `cell::pcell_maybe_uninit::borrow_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `cell::pcell_maybe_uninit::write`

```text
error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__write__L221/harness.rs:20:47
   |
20 |             &&& (post1_perm.mem_contents() == MemContents::Init(in_v))
   |                                               ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error[E0433]: cannot find type `MemContents` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/cell__pcell_maybe_uninit__write__L221/harness.rs:22:47
   |
22 |             &&& (post2_perm.mem_contents() == MemContents::Init(in_v))
   |                                               ^^^^^^^^^^^ use of undeclared type `MemContents`
   |
help: consider importing this enum
   |
 3 + use vstd::simple_pptr::MemContents;
   |

error: aborting due to 2 previous errors

For more information about this error, try `rustc --explain E0433`.

```

### `cell::pcell_maybe_uninit::read`

```text
no_ensures
```

### `std_specs::core::index_set`

```text
tainer: T, index: Idx, val: E, post1_container: T, r1: (), post2_contain...
   |                        - found this type parameter
...
25 |             &&& (pre_container.spec_index_set_ensures(post1_container, index, val))
   |                                ---------------------- ^^^^^^^^^^^^^^^ expected `&T`, found type parameter `T`
   |                                |
   |                                arguments to this method are incorrect
   |
   = note:   expected reference `&_`
           found type parameter `_`
note: method defined here
  --> vstd/std_specs/core.rs:201:12
help: consider borrowing here
   |
25 |             &&& (pre_container.spec_index_set_ensures(&post1_container, index, val))
   |                                                       +

error[E0308]: mismatched types
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/std_specs__core__index_set__L215/harness.rs:26:55
   |
18 | proof fn det_index_set<T, Idx, E>(g_neq_tuple: bool, pre_container: T, index: Idx, val: E, post1_container: T, r1: (), post2_contain...
   |                        - found this type parameter
...
26 |             &&& (pre_container.spec_index_set_ensures(post2_container, index, val))
   |                                ---------------------- ^^^^^^^^^^^^^^^ expected `&T`, found type parameter `T`
   |                                |
   |                                arguments to this method are incorrect
   |
   = note:   expected reference `&_`
           found type parameter `_`
note: method defined here
  --> vstd/std_specs/core.rs:201:12
help: consider borrowing here
   |
26 |             &&& (pre_container.spec_index_set_ensures(&post2_container, index, val))
   |                                                       +

error[E0277]: the size for values of type `T` cannot be known at compilation time
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/std_specs__core__index_set__L215/harness.rs:27:57
   |
18 | proof fn det_index_set<T, Idx, E>(g_neq_tuple: bool, pre_container: T, index: Idx, val: E, post1_container: T, r1: (), post2_contain...
   |                        - this type parameter needs to be `Sized`
...
27 |         }) ==> det_index_set_equal::<T, Idx, E>(r1, r2, post1_container, post2_container),
   |                                                         ^^^^^^^^^^^^^^^ doesn't have a size known at compile-time
   |
   = note: all function arguments must have a statically known size
   = help: unsized fn params are gated as an unstable feature
help: consider removing the `?Sized` bound to make the type parameter `Sized`
   |
19 -     where T: ?Sized + core::ops::IndexMut<Idx> + core::ops::Index<Idx, Output = E> + IndexSetTrustedSpec<
19 +     where T: core::ops::IndexMut<Idx> + core::ops::Index<Idx, Output = E> + IndexSetTrustedSpec<
   |

error: aborting due to 10 previous errors

Some errors have detailed explanations: E0277, E0308.
For more information about an error, try `rustc --explain E0277`.

```

### `std_specs::vec::vec_index`

```text
error[E0405]: cannot find trait `Allocator` in this scope
  --> vstd-survey/experiments/alias-new-2026-07-21/artifacts/std_specs__vec__vec_index__L53/harness.rs:14:30
   |
14 | proof fn det_vec_index<T, A: Allocator>(g_vec_leneq: bool, k_vec_leneq: nat, g_vec_lenrng: bool, k_vec_lenrng_lo: nat, k_vec_lenrng_...
   |                              ^^^^^^^^^ not found in this scope
   |
help: consider importing one of these traits
   |
 3 + use std::alloc::Allocator;
   |
 3 + use alloc::alloc::Allocator;
   |

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0405`.

```

### `std_specs::vec::vec_index_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```
