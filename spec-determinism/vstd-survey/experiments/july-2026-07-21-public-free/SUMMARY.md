# vstd determinism pilot

- vstd root: `/home/xuehaonan/verus/source/vstd`
- Verus root: `/home/xuehaonan/verus/source/target-verus/release`
- Verus version: `0.2026.07.13.cf3b5c3`
- Verus commit: `unknown`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 37
- Status counts: `{'ok': 33, 'unsupported_mut_ref_return': 3, 'verus_error': 1}`
- Classification counts: `{'complete': 22, 'ok_inconclusive': 5, 'invalid_equal_fn_trivial': 6}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `array` | `array_index_get` | 76 | ok | unsat | complete | 5 | 1 | 668 |
| `array` | `array_as_slice` | 135 | ok | unsat | complete | 7 | 1 | 738 |
| `array` | `array_fill_for_copy_types` | 164 | ok | unsat | complete | 5 | 1 | 663 |
| `array` | `ref_mut_array_unsizing_coercion` | 195 | unsupported_mut_ref_return |  |  |  |  | 11 |
| `bytes` | `u16_from_le_bytes` | 79 | ok | unsat | complete | 23 | 1 | 908 |
| `bytes` | `u16_to_le_bytes` | 91 | ok | unsat | complete | 39 | 1 | 947 |
| `bytes` | `u32_from_le_bytes` | 174 | ok | unsat | complete | 23 | 1 | 906 |
| `bytes` | `u32_to_le_bytes` | 186 | ok | unsat | complete | 39 | 1 | 925 |
| `bytes` | `u64_from_le_bytes` | 331 | ok | unsat | complete | 23 | 1 | 924 |
| `bytes` | `u64_to_le_bytes` | 343 | ok | unsat | complete | 39 | 1 | 945 |
| `bytes` | `u128_from_le_bytes` | 518 | ok | unsat | complete | 19 | 1 | 897 |
| `bytes` | `u128_to_le_bytes` | 530 | ok | unsat | complete | 37 | 1 | 1005 |
| `float` | `float_cast` | 127 | ok | unknown | ok_inconclusive | 1 | 2 | 474 |
| `layout` | `layout_for_type_is_valid` | 118 | ok | unsat | complete | 1 | 1 | 723 |
| `layout` | `layout_for_val_is_valid` | 141 | ok | unsat | complete | 1 | 1 | 618 |
| `raw_ptr` | `cast_ptr_to_thin_ptr` | 446 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 683 |
| `raw_ptr` | `cast_array_ptr_to_slice_ptr` | 468 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 708 |
| `raw_ptr` | `cast_slice_ptr_to_slice_ptr` | 492 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 709 |
| `raw_ptr` | `cast_slice_ptr_to_str_ptr` | 516 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 705 |
| `raw_ptr` | `cast_str_ptr_to_slice_ptr` | 540 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 693 |
| `raw_ptr` | `cast_ptr_to_usize` | 560 | ok | unsat | complete | 5 | 1 | 669 |
| `raw_ptr` | `ptr_mut_write` | 579 | ok | unsat | complete | 13 | 1 | 895 |
| `raw_ptr` | `ptr_mut_read` | 602 | ok | unsat | complete | 13 | 1 | 877 |
| `raw_ptr` | `ptr_ref` | 620 | ok | unsat | complete | 5 | 1 | 837 |
| `raw_ptr` | `ptr_mut_ref` | 636 | unsupported_mut_ref_return |  |  |  |  | 74 |
| `raw_ptr` | `expose_provenance` | 731 | ok | unsat | complete | 1 | 1 | 684 |
| `raw_ptr` | `with_exposed_provenance` | 744 | ok | unsat | invalid_equal_fn_trivial | 3 | 1 | 700 |
| `raw_ptr` | `allocate` | 908 | ok | unknown | ok_inconclusive | 5 | 15 | 766 |
| `raw_ptr` | `ptr_ref2` | 1038 | ok | unknown | ok_inconclusive | 5 | 6 | 640 |
| `slice` | `slice_index_get` | 62 | ok | unsat | complete | 5 | 1 | 624 |
| `slice` | `slice_to_vec` | 100 | ok | unsat | complete | 7 | 1 | 723 |
| `slice` | `slice_subrange` | 108 | ok | unsat | complete | 11 | 1 | 858 |
| `std_specs::core` | `index_set` | 205 | verus_error |  |  | 1 |  | 428 |
| `std_specs::vec` | `vec_index` | 53 | ok | unsat | complete | 5 | 1 | 684 |
| `std_specs::vec` | `vec_index_mut` | 67 | unsupported_mut_ref_return |  |  |  |  | 62 |
| `thread` | `spawn` | 107 | ok | unknown | ok_inconclusive | 1 | 2 | 429 |
| `thread` | `thread_id` | 200 | ok | unknown | ok_inconclusive | 1 | 2 | 432 |

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
