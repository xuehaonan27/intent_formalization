# spec-debug report: slab::from_raw_parts

## Witness (before)
- rounds: 67, schemas: 291, status: ok

```text
len == 1
block_size == 1
r1 is Ok
r1->Ok_0@.block_size == 1
r1->Ok_0@.start_addr == 0
r1->Ok_0@.end_addr == 1
r1->Ok_0@.allocated_addrs == Set::<usize>::empty()
r1->Ok_0@.free_addrs == Set::<usize>::empty()
r2 is Ok
r2->Ok_0@.block_size == 1
r2->Ok_0@.start_addr == 0
r2->Ok_0@.end_addr == 1
r2->Ok_0@.allocated_addrs == Set::<usize>::empty()
r2->Ok_0@.free_addrs.len() > 0
r2->Ok_0@.free_addrs.len() == 1
r2->Ok_0@.free_addrs.contains(0)
!det_from_raw_parts_equal(r1, r2)
```

## LLM (copilot-cli)
- response: 3742 chars → `patch.spec.rs`

## Verify
- spec-determinism rerun: PASS (rc=0), rounds=99, closed=1, added=0
  - closed:
    - `r2->Ok_0@.free_addrs.contains(0)`
