# vstd determinism pilot

- vstd root: `/home/xuehaonan/verus/source/vstd`
- Verus root: `/home/xuehaonan/verus/source/target-verus/release`
- Verus version: `0.2026.07.13.cf3b5c3`
- Verus commit: `unknown`
- Compare raw pointers: `True`
- View registry: `True`
- Targets: 6
- Status counts: `{'ok': 6}`
- Classification counts: `{'complete': 6}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `raw_ptr` | `cast_ptr_to_thin_ptr` | 446 | ok | unsat | complete | 1 | 1 | 700 |
| `raw_ptr` | `cast_array_ptr_to_slice_ptr` | 468 | ok | unsat | complete | 1 | 1 | 775 |
| `raw_ptr` | `cast_slice_ptr_to_slice_ptr` | 492 | ok | unsat | complete | 1 | 1 | 678 |
| `raw_ptr` | `cast_slice_ptr_to_str_ptr` | 516 | ok | unsat | complete | 1 | 1 | 693 |
| `raw_ptr` | `cast_str_ptr_to_slice_ptr` | 540 | ok | unsat | complete | 1 | 1 | 695 |
| `raw_ptr` | `with_exposed_provenance` | 744 | ok | unsat | complete | 3 | 1 | 740 |

## Errors

None.
