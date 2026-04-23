# spec-debug report: bitmap::new

## Witness (before)
- rounds: 20, schemas: 271, status: ok

```text
number_of_bits == 8
r1 is Ok
r1->Ok_0@.num_bits == 8
r1->Ok_0@.set_bits == Set::<int>::empty()
r2 is Err
r2->Err_0.code is OperationNotPermitted
r2->Err_0.reason == ""
!det_new_equal(r1, r2)
```

## LLM (copilot-cli)
- response: 17647 chars → `patch.spec.rs`

## Verify
- spec-determinism rerun: PASS (rc=0), rounds=20, closed=0, added=0
