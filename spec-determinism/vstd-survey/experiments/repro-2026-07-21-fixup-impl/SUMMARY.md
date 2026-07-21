# vstd determinism pilot

- vstd root: `/home/xuehaonan/nanvix/toolchain/verus/vstd`
- Verus root: `/home/xuehaonan/nanvix/toolchain/verus`
- Verus version: `0.2026.05.17.e479cce`
- Verus commit: `e479cce36490b8fa4b0fd7755aa742aec354372c`
- Compare raw pointers: `False`
- View registry: `True`
- Targets: 8
- Status counts: `{'ok': 8}`
- Classification counts: `{'complete': 6, 'ok_inconclusive': 2}`

| Module | Function | Line | Status | R0 Z3 | Classification | Schemas | Rounds | Wall ms |
|---|---|---:|---|---|---|---:|---:|---:|
| `cell` | `borrow` | 246 | ok | unsat | complete | 5 | 1 | 644 |
| `cell` | `empty` | 168 | ok | unknown | ok_inconclusive | 9 | 8 | 478 |
| `cell` | `into_inner` | 261 | ok | unsat | complete | 5 | 1 | 640 |
| `cell` | `new` | 178 | ok | unknown | ok_inconclusive | 9 | 10 | 455 |
| `cell` | `put` | 188 | ok | unsat | complete | 13 | 1 | 760 |
| `cell` | `replace` | 223 | ok | unsat | complete | 13 | 1 | 680 |
| `cell` | `take` | 203 | ok | unsat | complete | 13 | 1 | 751 |
| `cell` | `write` | 297 | ok | unsat | complete | 13 | 1 | 682 |

## Errors

None.
