# vstd determinism pilot

- vstd root: `/home/xuehaonan/nanvix/toolchain/verus/vstd`
- Verus root: `/home/xuehaonan/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 5
- Status counts: `{'ok': 5}`
- Classification counts: `{'complete': 3, 'ok_inconclusive': 2}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `raw_ptr` | `ptr_mut_read` | 602 | ok | unsat | complete | 13 | 1 | 911 |
| `raw_ptr` | `ptr_mut_write` | 579 | ok | unsat | complete | 13 | 1 | 981 |
| `raw_ptr` | `ptr_ref2` | 1038 | ok | unknown | ok_inconclusive | 5 | 6 | 575 |
| `raw_ptr` | `ptr_ref` | 620 | ok | unsat | complete | 5 | 1 | 723 |
| `thread` | `spawn` | 107 | ok | unknown | ok_inconclusive | 1 | 2 | 412 |

## Errors

None.
