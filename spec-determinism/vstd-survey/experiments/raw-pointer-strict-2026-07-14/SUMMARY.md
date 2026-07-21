# vstd determinism pilot

- vstd root: `/home/xuehaonan/nanvix/toolchain/verus/vstd`
- Verus root: `/home/xuehaonan/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Compare raw pointers: `True`
- View registry: `True`
- Targets: 6
- Status counts: `{'ok': 6}`
- Classification counts: `{'complete': 6}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `raw_ptr` | `cast_ptr_to_thin_ptr` | 446 | ok | unsat | complete | 1 | 1 | 695 |
| `raw_ptr` | `cast_array_ptr_to_slice_ptr` | 468 | ok | unsat | complete | 1 | 1 | 682 |
| `raw_ptr` | `cast_slice_ptr_to_slice_ptr` | 492 | ok | unsat | complete | 1 | 1 | 677 |
| `raw_ptr` | `cast_slice_ptr_to_str_ptr` | 516 | ok | unsat | complete | 1 | 1 | 627 |
| `raw_ptr` | `cast_str_ptr_to_slice_ptr` | 540 | ok | unsat | complete | 1 | 1 | 634 |
| `raw_ptr` | `with_exposed_provenance` | 744 | ok | unsat | complete | 3 | 1 | 690 |

## Errors

None.
