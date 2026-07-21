# vstd determinism pilot

- vstd root: `/home/xuehaonan/nanvix/toolchain/verus/vstd`
- Verus root: `/home/xuehaonan/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 34
- Status counts: `{'ok': 32, 'unsupported_mut_ref_return': 2}`
- Classification counts: `{'complete': 21, 'ok_inconclusive': 5, 'invalid_equal_fn_trivial': 6}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `array` | `array_index_get` | 76 | ok | unsat | complete | 5 | 1 | 729 |
| `array` | `array_as_slice` | 135 | ok | unsat | complete | 7 | 1 | 762 |
| `array` | `array_fill_for_copy_types` | 164 | ok | unsat | complete | 5 | 1 | 700 |
| `array` | `ref_mut_array_unsizing_coercion` | 195 | unsupported_mut_ref_return |  |  |  |  | 11 |
| `bytes` | `u16_from_le_bytes` | 79 | ok | unsat | complete | 23 | 1 | 930 |
| `bytes` | `u16_to_le_bytes` | 91 | ok | unsat | complete | 39 | 1 | 974 |
| `bytes` | `u32_from_le_bytes` | 174 | ok | unsat | complete | 23 | 1 | 978 |
| `bytes` | `u32_to_le_bytes` | 186 | ok | unsat | complete | 39 | 1 | 1005 |
| `bytes` | `u64_from_le_bytes` | 331 | ok | unsat | complete | 23 | 1 | 938 |
| `bytes` | `u64_to_le_bytes` | 343 | ok | unsat | complete | 39 | 1 | 1016 |
| `bytes` | `u128_from_le_bytes` | 518 | ok | unsat | complete | 19 | 1 | 882 |
| `bytes` | `u128_to_le_bytes` | 530 | ok | unsat | complete | 37 | 1 | 938 |
| `float` | `float_cast` | 127 | ok | unknown | ok_inconclusive | 1 | 2 | 399 |
| `layout` | `layout_for_type_is_valid` | 118 | ok | unsat | complete | 1 | 1 | 708 |
| `layout` | `layout_for_val_is_valid` | 141 | ok | unsat | complete | 1 | 1 | 651 |
| `raw_ptr` | `cast_ptr_to_thin_ptr` | 446 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 720 |
| `raw_ptr` | `cast_array_ptr_to_slice_ptr` | 468 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 725 |
| `raw_ptr` | `cast_slice_ptr_to_slice_ptr` | 492 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 755 |
| `raw_ptr` | `cast_slice_ptr_to_str_ptr` | 516 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 708 |
| `raw_ptr` | `cast_str_ptr_to_slice_ptr` | 540 | ok | unsat | invalid_equal_fn_trivial | 1 | 1 | 763 |
| `raw_ptr` | `cast_ptr_to_usize` | 560 | ok | unsat | complete | 5 | 1 | 760 |
| `raw_ptr` | `ptr_mut_write` | 579 | ok | unsat | complete | 13 | 1 | 1023 |
| `raw_ptr` | `ptr_mut_read` | 602 | ok | unsat | complete | 13 | 1 | 931 |
| `raw_ptr` | `ptr_ref` | 620 | ok | unsat | complete | 5 | 1 | 733 |
| `raw_ptr` | `ptr_mut_ref` | 636 | unsupported_mut_ref_return |  |  |  |  | 75 |
| `raw_ptr` | `expose_provenance` | 731 | ok | unsat | complete | 1 | 1 | 749 |
| `raw_ptr` | `with_exposed_provenance` | 744 | ok | unsat | invalid_equal_fn_trivial | 3 | 1 | 764 |
| `raw_ptr` | `allocate` | 908 | ok | unknown | ok_inconclusive | 5 | 15 | 696 |
| `raw_ptr` | `ptr_ref2` | 1038 | ok | unknown | ok_inconclusive | 5 | 6 | 583 |
| `slice` | `slice_index_get` | 62 | ok | unsat | complete | 5 | 1 | 678 |
| `slice` | `slice_to_vec` | 100 | ok | unsat | complete | 7 | 1 | 817 |
| `slice` | `slice_subrange` | 108 | ok | unsat | complete | 11 | 1 | 820 |
| `thread` | `spawn` | 107 | ok | unknown | ok_inconclusive | 1 | 2 | 421 |
| `thread` | `thread_id` | 200 | ok | unknown | ok_inconclusive | 1 | 2 | 429 |

## Errors

### `array::ref_mut_array_unsizing_coercion`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```

### `raw_ptr::ptr_mut_ref`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```
