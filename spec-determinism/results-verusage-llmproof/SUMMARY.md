# verusage spec-determinism — batch summary

> `ok` results are classified by the **R0** z3 verdict (initial determinism check before any schema narrowing):
>
> * **`ok_proved`** — R0 = `unsat` → function is provably deterministic.
> * **`ok_proved_llm`** — R0 was `unknown`; the LLM proof loop wrote an `assert/by`-style block that Verus accepted. Soundness preserved by the sandbox lex-allowlist.
> * **`ok_witness`** — R0 = `sat` → z3 produced a real nondeterminism counterexample.
> * **`ok_inconclusive`** — R0 = `unknown` (or legacy run without `r0_z3`) → z3 surrendered; assumes from narrowing are not a witness, just refinement attempts.

## Per-project overview

| project | n | ok_proved | ok_proved_llm | ok_witness | ok_inconclusive | search_error | verus_error | extract_error | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ironkv | 214 | 98 | 1 | 0 | 70 | 0 | 45 | 0 | 0 |
| memory-allocator | 16 | 14 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| nrkernel | 8 | 6 | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| vest | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | **240** | **120** | **1** | **0** | **71** | **0** | **48** | **0** | — |

## Real determinism witnesses (R0 = sat)

*(none — no z3-confirmed nondeterminism witnesses in this run)*

## Inconclusive targets (R0 = unknown)

These cases reached the schema-narrowing phase but z3 returned `unknown` on the baseline check; any `assumes` below are search artifacts, **not** verified witnesses.

### ironkv (70 inconclusive)

- `ironkv__verified__delegation_map_v__delegation_map_v__impl1_erase__remove`  (rounds=8, narrowed_assumes=2)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl1_erase__erase`  (rounds=14, narrowed_assumes=3)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl1_insert__insert`  (rounds=14, narrowed_assumes=3)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl1_remove__remove`  (rounds=8, narrowed_assumes=2)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl1_set__set`  (rounds=8, narrowed_assumes=2)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl3__erase__erase`  (rounds=14, narrowed_assumes=3)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__values_agree`  (rounds=19, narrowed_assumes=7)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__keys_in_index_range_agree`  (rounds=19, narrowed_assumes=7)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl3__new__new`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl3__set__insert`  (rounds=14, narrowed_assumes=3)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl3__set__set`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl3__values_agree__values_agree`  (rounds=19, narrowed_assumes=7)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl4__new__new`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl4__new__set`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl4__range_consistent_impl__keys_in_index_range_agree`  (rounds=19, narrowed_assumes=7)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl4__range_consistent_impl__greatest_lower_bound_index`  (rounds=15, narrowed_assumes=3)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__set`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__get_internal`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__clone_end_point`  (rounds=5, narrowed_assumes=4)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_delegate__set`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__get`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__clone_option_vec_u8`  (rounds=8, narrowed_assumes=7)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__clone_end_point`  (rounds=5, narrowed_assumes=4)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__send_single_cmessage`  (rounds=6, narrowed_assumes=5)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__clone_optional_value`  (rounds=8, narrowed_assumes=7)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__get`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__clone_end_point`  (rounds=5, narrowed_assumes=4)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__send_single_cmessage`  (rounds=6, narrowed_assumes=5)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__clone_vec_u8`  (rounds=5, narrowed_assumes=4)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_shard__set`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_shard__clone_end_point`  (rounds=5, narrowed_assumes=4)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_shard__send_single_cmessage`  (rounds=6, narrowed_assumes=5)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_receive_packet__host_model_receive_packet`  (rounds=487, narrowed_assumes=45)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_receive_packet__receive_impl`  (rounds=6, narrowed_assumes=5)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__host_noreceive_noclock_next__retransmit_un_acked_packets`  (rounds=5, narrowed_assumes=4)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__parse_end_points__parse_end_point`  (rounds=4, narrowed_assumes=3)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__parse_end_points__parse_end_points`  (rounds=6, narrowed_assumes=5)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__new`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__empty`  (rounds=2, narrowed_assumes=1)
- `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__clone_up_to_view`  (rounds=5, narrowed_assumes=4)
- _…and 30 more_

### memory-allocator (1 inconclusive)

- `memory-allocator__verified__commit_mask__commit_mask__impl__next_run__next_run`  (rounds=108, narrowed_assumes=15)

## Failure-mode samples

### status=`verus_error`  (48 cases)

**ironkv / ironkv__verified__delegation_map_v__delegation_map_v__impl4__range_consistent_impl__range_consistent_impl**

```
    found struct `KeyIterator<_>`
note: expected `&KeyIterator<K>`, found `KeyIterator<K>`
   --> /tmp/specdet_sf_range_consistent_impl_53iatx_q/delegation_map_v__impl4__range_consistent_impl.rs:674:51
    |
674 |             &&& (r2 == self_.range_consistent(lo, hi, dst))
    |                                                   ^^
    = note: expected reference `&KeyIterator<_>`
                  found struct `KeyIterator<_>`
note: method defined here
   --> /tmp/specdet_sf_range_consistent_impl_53iatx_q/delegation_map_v__impl4__range_consistent_impl.rs:238:22
    |
238 |     pub open spec fn range_consistent(self, lo: &KeyIterator<K>, hi: &KeyIterator<K>, dst: &ID) -> bool {
    |                      ^^^^^^^^^^^^^^^^       -------------------  -------------------  --------
help: consider borrowing here
    |
674 |             &&& (r2 == self_.range_consistent(&lo, hi, dst))
    |                                               +
help: consider borrowing here
    |
674 |             &&& (r2 == self_.range_consistent(lo, &hi, dst))
    |                                                   +
help: consider borrowing here
    |
674 |             &&& (r2 == self_.range_consistent(lo, hi, &dst))
    |                                                       +

error: aborting due to 2 previous errors; 13 warnings emitted

For more information about this error, try `rustc --explain E0308`.
```

**ironkv / ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__erase**

```
ted type parameter `K`, found `&K`
    |                                                                             |
    |                                                                             arguments to this method are incorrect
    |
    = note: expected type parameter `_`
                    found reference `&_`
note: method defined here
   --> vstd/map_lib.rs:32:21

error[E0308]: mismatched types
   --> /tmp/specdet_sf_erase_9zbp28ja/delegation_map_v__impl4__set.rs:625:97
    |
591 | ...et_erase<K: KeyTrait + VerusClone>(g_neq_tuple: bool, pre_self_: StrictlyOrderedMap<K>, lo: KeyIterator<K>, ...
    |             - expected this type parameter
...
625 | ...                    (hi.geq_spec(y) || hi.is_end_spec() || !post2_self_@.contains_key(hi.get())))
    |                                                                             ------------ ^^^^^^^^ expected type parameter `K`, found `&K`
    |                                                                             |
    |                                                                             arguments to this method are incorrect
    |
    = note: expected type parameter `_`
                    found reference `&_`
note: method defined here
   --> vstd/map_lib.rs:32:21

error: aborting due to 2 previous errors; 12 warnings emitted

For more information about this error, try `rustc --explain E0308`.
```

**ironkv / ironkv__verified__delegation_map_v__delegation_map_v__impl5__delegate_for_key_range_is_host_impl__range_consistent_impl**

```
or<_>`
note: expected `&KeyIterator<K>`, found `KeyIterator<K>`
   --> /tmp/specdet_sf_range_consistent_impl_bn1eztji/delegation_map_v__impl5__delegate_for_key_range_is_host_impl.rs:326:51
    |
326 |             &&& (r2 == self_.range_consistent(lo, hi, dst))
    |                                                   ^^
    = note: expected reference `&KeyIterator<_>`
                  found struct `KeyIterator<_>`
note: method defined here
   --> /tmp/specdet_sf_range_consistent_impl_bn1eztji/delegation_map_v__impl5__delegate_for_key_range_is_host_impl.rs:165:22
    |
165 |     pub open spec fn range_consistent(self, lo: &KeyIterator<K>, hi: &KeyIterator<K>, dst: &ID) -> bool {
    |                      ^^^^^^^^^^^^^^^^       -------------------  -------------------  --------
help: consider borrowing here
    |
326 |             &&& (r2 == self_.range_consistent(&lo, hi, dst))
    |                                               +
help: consider borrowing here
    |
326 |             &&& (r2 == self_.range_consistent(lo, &hi, dst))
    |                                                   +
help: consider borrowing here
    |
326 |             &&& (r2 == self_.range_consistent(lo, hi, &dst))
    |                                                       +

error: aborting due to 2 previous errors; 8 warnings emitted

For more information about this error, try `rustc --explain E0308`.
```

**ironkv / ironkv__verified__host_impl_v__host_impl_v__impl2__deliver_packet_seq__deliver_packet_seq**

```
error[E0599]: no method named `view` found for struct `vstd::seq::Seq<A>` in the current scope
    --> /tmp/specdet_sf_deliver_packet_seq_mm2kv95t/host_impl_v__impl2__deliver_packet_seq.rs:1118:35
     |
1118 |             history: self.history@@,
     |                      ------------ ^ method not found in `vstd::seq::Seq<LIoOp<AbstractEndPoint, vstd::seq::Seq<u8>>>`
     |                      |
     |                      method `view` is available on `vstd::prelude::Ghost<vstd::seq::Seq<LIoOp<AbstractEndPoint, vstd::seq::Seq<u8>>>>`

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0599`.
```

**ironkv / ironkv__verified__host_impl_v__host_impl_v__impl2__deliver_packet_seq__send_packet_seq**

```
error[E0599]: no method named `view` found for struct `vstd::seq::Seq<A>` in the current scope
    --> /tmp/specdet_sf_send_packet_seq_ulxk19_x/host_impl_v__impl2__deliver_packet_seq.rs:1118:35
     |
1118 |             history: self.history@@,
     |                      ------------ ^ method not found in `vstd::seq::Seq<LIoOp<AbstractEndPoint, vstd::seq::Seq<u8>>>`
     |                      |
     |                      method `view` is available on `vstd::prelude::Ghost<vstd::seq::Seq<LIoOp<AbstractEndPoint, vstd::seq::Seq<u8>>>>`

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0599`.
```

_...and 43 more_

