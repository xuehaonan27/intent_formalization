# vstd determinism pilot

- vstd root: `/home/chentianyu/nanvix/toolchain/verus/vstd`
- Verus root: `/home/chentianyu/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Targets: 12
- Status counts: `{'ok': 11, 'unsupported_mut_ref_return': 1}`
- Classification counts: `{'complete': 11}`

| Module | Function | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---|---|---|---:|---:|---:|
| `array` | `array_index_get` | ok | unsat | complete | 5 | 1 | 678 |
| `array` | `array_as_slice` | ok | unsat | complete | 7 | 1 | 757 |
| `array` | `array_fill_for_copy_types` | ok | unsat | complete | 5 | 1 | 668 |
| `array` | `ref_mut_array_unsizing_coercion` | unsupported_mut_ref_return |  |  |  |  | 11 |
| `bytes` | `u16_from_le_bytes` | ok | unsat | complete | 23 | 1 | 876 |
| `bytes` | `u16_to_le_bytes` | ok | unsat | complete | 39 | 1 | 946 |
| `bytes` | `u32_from_le_bytes` | ok | unsat | complete | 23 | 1 | 896 |
| `bytes` | `u32_to_le_bytes` | ok | unsat | complete | 39 | 1 | 918 |
| `bytes` | `u64_from_le_bytes` | ok | unsat | complete | 23 | 1 | 912 |
| `bytes` | `u64_to_le_bytes` | ok | unsat | complete | 39 | 1 | 897 |
| `bytes` | `u128_from_le_bytes` | ok | unsat | complete | 19 | 1 | 894 |
| `bytes` | `u128_to_le_bytes` | ok | unsat | complete | 37 | 1 | 923 |

## Errors

### `array::ref_mut_array_unsizing_coercion`

```text
current gen_det emits direct mutable-reference result projections instead of old(result)/final(result)
```
