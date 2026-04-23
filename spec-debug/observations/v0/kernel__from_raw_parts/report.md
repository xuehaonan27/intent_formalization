# spec-debug report: kernel::from_raw_parts

## Witness (before)
- rounds: 65, schemas: 519, status: ok

```text
addr == 0
size == 0
r1 is Err
r1->Err_0.code is InvalidArgument
r1->Err_0.reason == ""
r2 is Err
r2->Err_0.code is InvalidArgument
r2->Err_0.reason == "string 1"
!det_from_raw_parts_equal(r1, r2)
```

## LLM (copilot-cli)
- response: 13354 chars → `patch.spec.rs`

## Verify
- spec-determinism rerun: PASS (rc=0), rounds=0, closed=9, added=0
  - closed:
    - `!det_from_raw_parts_equal(r1, r2)`
    - `addr == 0`
    - `r1 is Err`
    - `r1->Err_0.code is InvalidArgument`
    - `r1->Err_0.reason == ""`
    - `r2 is Err`
    - `r2->Err_0.code is InvalidArgument`
    - `r2->Err_0.reason == "string 1"`
    - `size == 0`
