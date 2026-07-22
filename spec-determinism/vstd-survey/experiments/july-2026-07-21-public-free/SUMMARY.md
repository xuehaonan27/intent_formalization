# vstd determinism pilot

- vstd root: `/home/xuehaonan/verus/source/vstd`
- Verus root: `/home/xuehaonan/verus/source/target-verus/release`
- Verus version: `0.2026.07.13.cf3b5c3`
- Verus commit: `unknown`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 37
- Status counts: `{'ok': 33, 'unsupported_mut_ref_return': 3, 'verus_error': 1}`
- Classification counts: `{'complete': 24, 'ok_inconclusive': 3, 'invalid_equal_fn_trivial': 6}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `array` | `array_index_get` | 76 | ok | unsat | complete | 5 | 1 | 671 |
| `array` | `array_as_slice` | 135 | ok | unsat | complete | 7 | 1 | 733 |
| `array` | `array_fill_for_copy_types` | 164 | ok | unsat | complete | 5 | 1 | 654 |
| `array` | `ref_mut_array_unsizing_coercion` | 195 | unsupported_mut_ref_return |  |  |  |  | 11 |
| `bytes` | `u16_from_le_bytes` | 79 | ok | unsat | complete | 23 | 1 | 938 |
| `bytes` | `u16_to_le_bytes` | 91 | ok | unsat | complete | 39 | 1 | 1020 |
| `bytes` | `u32_from_le_bytes` | 174 | ok | unsat | complete | 23 | 1 | 933 |
| `bytes` | `u32_to_le_bytes` | 186 | ok | unsat | complete | 39 | 1 | 950 |
| `bytes` | `u64_from_le_bytes` | 331 | ok | unsat | complete | 23 | 1 | 925 |
| `bytes` | `u64_to_le_bytes` | 343 | ok | unsat | complete | 39 | 1 | 973 |
| `bytes` | `u128_from_le_bytes` | 518 | ok | unsat | complete | 19 | 1 | 917 |
| `bytes` | `u128_to_le_bytes` | 530 | ok | unsat | complete | 37 | 1 | 911 |
| `float` | `float_cast` | 127 | ok | unknown | ok_inconclusive | 1 | 2 | 447 |
| `layout` | `layout_for_type_is_valid` | 118 | ok | unsat | complete | 1 | 1 | 711 |
| `layout` | `layout_for_val_is_valid` | 141 | ok | unsat | complete | 1 | 1 | 624 |
| `raw_ptr` | `cast_ptr_to_thin_ptr` | 446 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 654 |
| `raw_ptr` | `cast_array_ptr_to_slice_ptr` | 468 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 718 |
| `raw_ptr` | `cast_slice_ptr_to_slice_ptr` | 492 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 746 |
| `raw_ptr` | `cast_slice_ptr_to_str_ptr` | 516 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 728 |
| `raw_ptr` | `cast_str_ptr_to_slice_ptr` | 540 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 725 |
| `raw_ptr` | `cast_ptr_to_usize` | 560 | ok | unsat | complete | 5 | 1 | 694 |
| `raw_ptr` | `ptr_mut_write` | 579 | ok | unsat | complete | 13 | 1 | 881 |
| `raw_ptr` | `ptr_mut_read` | 602 | ok | unsat | complete | 13 | 1 | 890 |
| `raw_ptr` | `ptr_ref` | 620 | ok | unsat | complete | 5 | 1 | 710 |
| `raw_ptr` | `ptr_mut_ref` | 636 | unsupported_mut_ref_return |  |  |  |  | 75 |
| `raw_ptr` | `expose_provenance` | 731 | ok | unsat | complete | 1 | 1 | 734 |
| `raw_ptr` | `with_exposed_provenance` | 744 | ok | unsat | invalid_equal_fn_trivial | 3 | 1 | 680 |
| `raw_ptr` | `allocate` | 908 | ok | unknown | ok_inconclusive | 5 | 15 | 792 |
| `raw_ptr` | `ptr_ref2` | 1038 | ok | unsat | complete | 5 | 1 | 850 |
| `slice` | `slice_index_get` | 62 | ok | unsat | complete | 5 | 1 | 648 |
| `slice` | `slice_to_vec` | 100 | ok | unsat | complete | 7 | 1 | 714 |
| `slice` | `slice_subrange` | 108 | ok | unsat | complete | 11 | 1 | 811 |
| `std_specs::core` | `index_set` | 205 | verus_error |  |  | 1 |  | 447 |
| `std_specs::vec` | `vec_index` | 53 | ok | unsat | complete | 5 | 1 | 691 |
| `std_specs::vec` | `vec_index_mut` | 67 | unsupported_mut_ref_return |  |  |  |  | 58 |
| `thread` | `spawn` | 107 | ok | unknown | ok_inconclusive | 1 | 2 | 450 |
| `thread` | `thread_id` | 200 | ok | unsat | complete | 1 | 1 | 709 |

## Errors

### `array::ref_mut_array_unsizing_coercion`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `raw_ptr::ptr_mut_ref`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `std_specs::core::index_set`

```text
ex: Idx, val: E, post1_container: T, r1: (), post2_contain...
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
  --> vstd/std_specs/core.rs:191:12
help: consider borrowing here
   |
25 |             &&& (pre_container.spec_index_set_ensures(&post1_container, index, val))
   |                                                       +

error[E0308]: mismatched types
  --> vstd-survey/experiments/july-2026-07-21-public-free/artifacts/std_specs__core__index_set__L205/harness.rs:26:55
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
  --> vstd/std_specs/core.rs:191:12
help: consider borrowing here
   |
26 |             &&& (pre_container.spec_index_set_ensures(&post2_container, index, val))
   |                                                       +

error[E0277]: the size for values of type `T` cannot be known at compilation time
  --> vstd-survey/experiments/july-2026-07-21-public-free/artifacts/std_specs__core__index_set__L205/harness.rs:27:57
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

### `std_specs::vec::vec_index_mut`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```
