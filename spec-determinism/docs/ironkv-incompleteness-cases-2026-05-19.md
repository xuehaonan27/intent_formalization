# Ironkv 确定 incompleteness 案例汇总

**Source dataset**: `spec-determinism/results-verusage-viewreg/ironkv/full_run.json`(May 12;view-equal wiring + full funnel)

## 总览

76 个 ok-with-witness 实例 → 42 unique groups(按 function + equal_fn 哈希去重)。
- **REAL_SAT** (spec 真允许多解): 6 groups / 10 instances — **不收录在本文档**
- **UNKNOWN_INCOMPLETE** (本文档): 66 instances / 36 unique groups

## Bucket 分类

| 桶 | 性质 | 说明 |
|---|---|---|
| A-E | **Wiring-blocked** | equal_fn 里某个 leaf 类型(EndPoint / CMessage / CPacket / HashMap-ish 等)走了 structural `==` fallback,因为 view_registry quarantine。修复 = 解 quarantine(根=`CKeyHashMap`)。 |
| F | **Quantifier-wall** | spec 数学上 deterministic,但 z3 不会自动 instantiate ∀ 量词;需手写 `assert P by { ... }` 或 lemma。 |
| G | **混合** | view-equal 已部分注入,但其他字段(Vec / 元素 quarantined)仍 wiring-blocked + 量词。 |

每条 case 提供:**路径** / **Source 函数体** / **生成的 equal_fn** / **生成的 det fn** / **z3 witness assumes**。

---

## #1 `cack_state_swap` (×2 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__receive_ack_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__cack_state_swap/`
- **z3 cost**: n_rounds=26, n_schemas=9, verus_ms=857
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CAckState` 仍走 structural `==`(`CAckState.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn cack_state_swap(&mut self, src: &EndPoint, ack_state: &mut CAckState, default: CAckState)
    requires
        old(self).valid(),
        src.abstractable(),
    ensures
        HashMap::swap_spec(old(self).epmap@, self.epmap@, src@, *old(ack_state), *ack_state, default),
    {
        unimplemented!()
    }
```

### 生成的 equal_fn

```rust
spec fn det_cack_state_swap_equal(r1: (), r2: (), post1_self_: CSendState, post2_self_: CSendState, post1_ack_state: CAckState, post2_ack_state: CAckState) -> bool {
    (r1 == r2)
    && ((post1_self_.epmap == post2_self_.epmap))
    && ((post1_ack_state.num_packets_acked == post2_ack_state.num_packets_acked) && (post1_ack_state.un_acked == post2_ack_state.un_acked))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_cack_state_swap(g_pre_ack_state_num_packets_acked_eq: bool, k_pre_ack_state_num_packets_acked_eq: int, g_pre_ack_state_num_packets_acked_rng: bool, k_pre_ack_state_num_packets_acked_rng_lo: int, k_pre_ack_state_num_packets_acked_rng_hi: int, g_default_num_packets_acked_eq: bool, k_default_num_packets_acked_eq: int, g_default_num_packets_acked_rng: bool, k_default_num_packets_acked_rng_lo: int, k_default_num_packets_acked_rng_hi: int, g_post1_ack_state_num_packets_acked_eq: bool, k_post1_ack_state_num_packets_acked_eq: int, g_post1_ack_state_num_packets_acked_rng: bool, k_post1_ack_state_num_packets_acked_rng_lo: int, k_post1_ack_state_num_packets_acked_rng_hi: int, g_post2_ack_state_num_packets_acked_eq: bool, k_post2_ack_state_num_packets_acked_eq: int, g_post2_ack_state_num_packets_acked_rng: bool, k_post2_ack_state_num_packets_acked_rng_lo: int, k_post2_ack_state_num_packets_acked_rng_hi: int, g_neq_tuple: bool, pre_self_: CSendState, src: EndPoint, pre_ack_state: CAckState, default: CAckState, post1_self_: CSendState, post1_ack_state: CAckState, r1: (), post2_self_: CSendState, post2_ack_state: CAckState, r2: ())
    requires (pre_self_.valid()), (src.abstractable()),
    ensures
        ({
            &&& (HashMap::swap_spec(pre_self_.epmap@, post1_self_.epmap@, src@, pre_ack_state, post1_ack_state, default))
            &&& (HashMap::swap_spec(pre_self_.epmap@, post2_self_.epmap@, src@, pre_ack_state, post2_ack_state, default))
        }) ==> det_cack_state_swap_equal(r1, r2, post1_self_, post2_self_, post1_ack_state, post2_ack_state),
{
    if g_pre_ack_state_num_packets_acked_eq { assume(pre_ack_state.num_packets_acked as int == k_pre_ack_state_num_packets_acked_eq); }
    if g_pre_ack_state_num_packets_acked_rng { assume(pre_ack_state.num_packets_acked as int >= k_pre_ack_state_num_packets_acked_rng_lo && pre_ack_state.num_packets_acked as int <= k_pre_ack_state_num_packets_acked_rng_hi); }
    if g_default_num_packets_acked_eq { assume(default.num_packets_acked as int == k_default_num_packets_acked_eq); }
    if g_default_num_packets_acked_rng { assume(default.num_packets_acked as int >= k_default_num_packets_acked_rng_lo && default.num_packets_acked as int <= k_default_num_packets_acked_rng_hi); }
    if g_post1_ack_state_num_packets_acked_eq { assume(post1_ack_state.num_packets_acked as int == k_post1_ack_state_num_packets_acked_eq); }
    if g_post1_ack_state_num_packets_acked_rng { assume(post1_ack_state.num_packets_acked as int >= k_post1_ack_state_num_packets_acked_rng_lo && post1_ack_state.num_packets_acked as int <= k_post1_ack_state_num_packets_acked_rng_hi); }
    if g_post2_ack_state_num_packets_acked_eq { assume(post2_ack_state.num_packets_acked as int == k_post2_ack_state_num_packets_acked_eq); }
    if g_post2_ack_state_num_packets_acked_rng { assume(post2_ack_state.num_packets_acked as int >= k_post2_ack_state_num_packets_acked_rng_lo && post2_ack_state.num_packets_acked as int <= k_post2_ack_state_num_packet
/* … (truncated — full body in injected.rs) … */
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__cack_state_swap`:

```
  pre_ack_state.num_packets_acked == 0
  default.num_packets_acked == 0
  post1_ack_state.num_packets_acked == 0
  post2_ack_state.num_packets_acked == 0
  !det_cack_state_swap_equal(r1, r2, post1_self_, post2_self_, post1_ack_state, post2_ack_state)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__send_single_cmessage__cack_state_swap`:

```
  pre_ack_state.num_packets_acked == 0
  default.num_packets_acked == 0
  post1_ack_state.num_packets_acked == 0
  post2_ack_state.num_packets_acked == 0
  !det_cack_state_swap_equal(r1, r2, post1_self_, post2_self_, post1_ack_state, post2_ack_state)
```

---

## #2 `clone_end_point` (×4 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__clone_end_point/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=995
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `EndPoint` 仍走 structural `==`(`EndPoint.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn clone_end_point(ep: &EndPoint) -> (cloned_ep: EndPoint)
        ensures
            cloned_ep@ == ep@
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_clone_end_point_equal(r1: EndPoint, r2: EndPoint) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_clone_end_point(g_neq_tuple: bool, ep: EndPoint, r1: EndPoint, r2: EndPoint)
    ensures
        ({
            &&& (r1@ == ep@)
            &&& (r2@ == ep@)
        }) ==> det_clone_end_point_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_clone_end_point_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__clone_end_point`:

```
  !det_clone_end_point_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__clone_end_point`:

```
  !det_clone_end_point_equal(r1, r2)
```

**Instance 3** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__clone_end_point`:

```
  !det_clone_end_point_equal(r1, r2)
```

**Instance 4** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_shard__clone_end_point`:

```
  !det_clone_end_point_equal(r1, r2)
```

---

## #3 `clone_option_vec_u8` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_get_request.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__clone_option_vec_u8/`
- **z3 cost**: n_rounds=5, n_schemas=7, verus_ms=1270
- **Incompleteness 性质**: Wiring-blocked: Vec<u8> 走 structural — Vec wrapper opaque

### Source 函数(摘取)

```rust
pub fn clone_option_vec_u8(ov: Option<&Vec<u8>>) -> (res: Option<Vec<u8>>)
        ensures
            match ov {
                Some(e1) => res.is_some() && e1@ == res.get_Some_0()@,
                None => res.is_None(),
            }
```

### 生成的 equal_fn

```rust
spec fn det_clone_option_vec_u8_equal(r1: Option<Vec<u8>>, r2: Option<Vec<u8>>) -> bool {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0)))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_clone_option_vec_u8(g_ov_is_Some: bool, g_ov_is_None: bool, g_r1_is_Some: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2_is_None: bool, g_neq_tuple: bool, ov: Option<&Vec<u8>>, r1: Option<Vec<u8>>, r2: Option<Vec<u8>>)
    ensures
        ({
            &&& (match ov {
                Some(e1) => r1.is_some() && e1@ == r1.get_Some_0()@,
                None => r1.is_None(),
            })
            &&& (match ov {
                Some(e1) => r2.is_some() && e1@ == r2.get_Some_0()@,
                None => r2.is_None(),
            })
        }) ==> det_clone_option_vec_u8_equal(r1, r2),
{
    if g_ov_is_Some { assume(ov is Some); }
    if g_ov_is_None { assume(ov is None); }
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_clone_option_vec_u8_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__clone_option_vec_u8`:

```
  ov is Some
  r1 is Some
  r2 is Some
  !det_clone_option_vec_u8_equal(r1, r2)
```

---

## #4 `clone_optional_value` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_set_request.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__clone_optional_value/`
- **z3 cost**: n_rounds=5, n_schemas=7, verus_ms=1479
- **Incompleteness 性质**: Wiring-blocked: Vec<u8> 走 structural — Vec wrapper opaque

### Source 函数(摘取)

```rust
pub fn clone_optional_value(ov: &Option::<Vec::<u8>>) -> (res: Option::<Vec::<u8>>)
    ensures optional_value_view(*ov) == optional_value_view(res)
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_clone_optional_value_equal(r1: Option::<Vec::<u8>>, r2: Option::<Vec::<u8>>) -> bool {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0)))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_clone_optional_value(g_ov_is_Some: bool, g_ov_is_None: bool, g_r1_is_Some: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2_is_None: bool, g_neq_tuple: bool, ov: Option::<Vec::<u8>>, r1: Option::<Vec::<u8>>, r2: Option::<Vec::<u8>>)
    ensures
        ({
            &&& (optional_value_view(ov) == optional_value_view(r1))
            &&& (optional_value_view(ov) == optional_value_view(r2))
        }) ==> det_clone_optional_value_equal(r1, r2),
{
    if g_ov_is_Some { assume(ov is Some); }
    if g_ov_is_None { assume(ov is None); }
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_clone_optional_value_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__clone_optional_value`:

```
  ov is Some
  r1 is Some
  r2 is Some
  !det_clone_optional_value_equal(r1, r2)
```

---

## #5 `clone_up_to_view` (×4 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__real_init_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__clone_up_to_view/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=811
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `EndPoint` 仍走 structural `==`(`EndPoint.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn clone_up_to_view(&self) -> (res: EndPoint)
        ensures res@ == self@
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_clone_up_to_view_equal(r1: EndPoint, r2: EndPoint) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_clone_up_to_view(g_neq_tuple: bool, self_: EndPoint, r1: EndPoint, r2: EndPoint)
    ensures
        ({
            &&& (r1@ == self_@)
            &&& (r2@ == self_@)
        }) ==> det_clone_up_to_view_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_clone_up_to_view_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__clone_up_to_view`:

```
  !det_clone_up_to_view_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__net_sht_v__net_sht_v__receive_with_demarshal__clone_up_to_view`:

```
  !det_clone_up_to_view_equal(r1, r2)
```

**Instance 3** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__maybe_ack_packet_impl__clone_up_to_view`:

```
  !det_clone_up_to_view_equal(r1, r2)
```

**Instance 4** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__clone_up_to_view`:

```
  !det_clone_up_to_view_equal(r1, r2)
```

---

## #6 `clone_up_to_view` (×3 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__retransmit_un_acked_packets_for_dst.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets_for_dst__clone_up_to_view/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=818
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CSingleMessage` 仍走 structural `==`(`CSingleMessage.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn clone_up_to_view(&self) -> (c: Self)
  ensures
    c@ == self@
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_clone_up_to_view_equal(r1: CSingleMessage, r2: CSingleMessage) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_clone_up_to_view(g_neq_tuple: bool, self_: CSingleMessage, r1: CSingleMessage, r2: CSingleMessage)
    ensures
        ({
            &&& (r1@ == self_@)
            &&& (r2@ == self_@)
        }) ==> det_clone_up_to_view_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_clone_up_to_view_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets_for_dst__clone_up_to_view`:

```
  !det_clone_up_to_view_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__single_delivery_state_v__single_delivery_state_v__impl0__clone_up_to_view__clone_up_to_view`:

```
  self_ is Message
  !det_clone_up_to_view_equal(r1, r2)
```

**Instance 3** — `ironkv__verified__single_delivery_state_v__single_delivery_state_v__impl0__lemma_seqno_in_un_acked_list__clone_up_to_view`:

```
  !det_clone_up_to_view_equal(r1, r2)
```

---

## #7 `clone_up_to_view` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__send_single_cmessage.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__send_single_cmessage__clone_up_to_view/`
- **z3 cost**: n_rounds=4, n_schemas=7, verus_ms=2443
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CMessage` 仍走 structural `==`(`CMessage.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn clone_up_to_view(&self) -> (c: Self)
  ensures
    c@ == self@
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_clone_up_to_view_equal(r1: CMessage, r2: CMessage) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_clone_up_to_view(g_self__is_GetRequest: bool, g_self__is_SetRequest: bool, g_self__is_Reply: bool, g_self__is_Redirect: bool, g_self__is_Shard: bool, g_self__is_Delegate: bool, g_neq_tuple: bool, self_: CMessage, r1: CMessage, r2: CMessage)
    ensures
        ({
            &&& (r1@ == self_@)
            &&& (r2@ == self_@)
        }) ==> det_clone_up_to_view_equal(r1, r2),
{
    if g_self__is_GetRequest { assume(self_ is GetRequest); }
    if g_self__is_SetRequest { assume(self_ is SetRequest); }
    if g_self__is_Reply { assume(self_ is Reply); }
    if g_self__is_Redirect { assume(self_ is Redirect); }
    if g_self__is_Shard { assume(self_ is Shard); }
    if g_self__is_Delegate { assume(self_ is Delegate); }
    if g_neq_tuple { assume(!det_clone_up_to_view_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__send_single_cmessage__clone_up_to_view`:

```
  self_ is SetRequest
  !det_clone_up_to_view_equal(r1, r2)
```

---

## #8 `clone_vec_u8` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_set_request.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__clone_vec_u8/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=1475
- **Incompleteness 性质**: Wiring-blocked: Vec<u8> 走 structural — Vec wrapper opaque

### Source 函数(摘取)

```rust
pub fn clone_vec_u8(v: &Vec<u8>) -> (out: Vec<u8>)
ensures
    out@ == v@
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_clone_vec_u8_equal(r1: Vec<u8>, r2: Vec<u8>) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_clone_vec_u8(g_neq_tuple: bool, v: Vec<u8>, r1: Vec<u8>, r2: Vec<u8>)
    ensures
        ({
            &&& (r1@ == v@)
            &&& (r2@ == v@)
        }) ==> det_clone_vec_u8_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_clone_vec_u8_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__clone_vec_u8`:

```
  !det_clone_vec_u8_equal(r1, r2)
```

---

## #9 `empty` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__real_init_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__empty/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=794
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CSingleDelivery` 仍走 structural `==`(`CSingleDelivery.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn empty() -> (out:Self)
    ensures out@ == SingleDelivery::<Message>::init()
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_empty_equal(r1: CSingleDelivery, r2: CSingleDelivery) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_empty(g_neq_tuple: bool, r1: CSingleDelivery, r2: CSingleDelivery)
    ensures
        ({
            &&& (r1@ == SingleDelivery::<Message>::init())
            &&& (r2@ == SingleDelivery::<Message>::init())
        }) ==> det_empty_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_empty_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__empty`:

```
  !det_empty_equal(r1, r2)
```

---

## #10 `erase` (×2 instances) — Bucket E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl1_erase.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl1_erase__erase/`
- **z3 cost**: n_rounds=14, n_schemas=5, verus_ms=502
- **Incompleteness 性质**: Wiring-blocked: StrictlyOrdered* 通过 `K: VerusClone` 间接卡 cascade(K 实例化时挂上 quarantined 类型)

### Source 函数(摘取)

```rust
fn erase(&mut self, start: usize, end: usize)
        requires
            old(self).valid(),
            start <= end <= old(self)@.len(),
        ensures
            self.valid(),
            self@ == old(self)@.subrange(0, start as int) + old(self)@.subrange(end as int, old(self)@.len() as int),
            // TODO: We might want to strengthen this further to say that the two sets on the RHS
            //       are disjoint
            old(self)@.to_set() == self@.to_set() + old(self)@.subrange(start as int, end as int).to_set(),
    {
        let mut deleted = 0;

        proof {
            assert(self@ == old(self)@.subrange(0, start as int) + old(self)@.subrange(start as int + deleted as int, old(self)@.len() as int));
            assert(old(self)@.to_set() == self@.to_set() + old(self)@.subrange(start as int, start + deleted).to_set());
        }
        while deleted < end - start
            invariant
                start <= end <= old(self)@.len(),
                self@.len() == old(self)@.len() - deleted,
                0 <= deleted <= end - start,
                old(self).valid(),
                self.valid(),
                self@ == old(self)@.subrange(0, start as int) + old(self)@.subrange(start as int + deleted as int, old(self)@.len() as int),
                old(self)@.to_set() == self@.to_set() + old(self)@.subrange(start as int, start + deleted).to_set(),
            decreases
                end - start - deleted,
        {
            self.remove(start);
            deleted = deleted + 1;
            proof {
                assert(self@ == old(self)@.subrange(0, start as int) + old(self)@.subrange(start as int + deleted as int, old(self)@.len() as int));

                assert(old(self)@.to_set() == self@.to_set() + old(self)@.subrange(start as int, start + deleted).to_set()) by {
                    assert(old(self)@ =~= old(self)@.subrange(0, start as int) 
                                                + old(self)@.subrange(start as int, start + deleted)
                                                + old(self)@.subrange(start as int + deleted as int, old(self)@.len() as int));
                    seq_to_set_distributes_over_add::<K>(old(self)@.subrange(0, start as int), 
                                    old(self)@.subrange(start as int + deleted as int, old(self)@.len() as int));
                    assert(old(self)@.to_set() =~= old(self)@.subrange(0, start as int).to_set()
                                            
/* … (truncated) … */
```

### 生成的 equal_fn

```rust
spec fn det_erase_equal<K: KeyTrait + VerusClone>(r1: (), r2: (), post1_self_: StrictlyOrderedVec<K>, post2_self_: StrictlyOrderedVec<K>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_erase<K: KeyTrait + VerusClone>(g_start_eq: bool, k_start_eq: int, g_start_rng: bool, k_start_rng_lo: int, k_start_rng_hi: int, g_end_eq: bool, k_end_eq: int, g_end_rng: bool, k_end_rng_lo: int, k_end_rng_hi: int, g_neq_tuple: bool, pre_self_: StrictlyOrderedVec<K>, start: usize, end: usize, post1_self_: StrictlyOrderedVec<K>, r1: (), post2_self_: StrictlyOrderedVec<K>, r2: ())
    requires (pre_self_.valid()), (start <= end <= pre_self_@.len()),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (post1_self_@ == pre_self_@.subrange(0, start as int) + pre_self_@.subrange(end as int, pre_self_@.len() as int))
            &&& (pre_self_@.to_set() == post1_self_@.to_set() + pre_self_@.subrange(start as int, end as int).to_set())
            &&& (post2_self_.valid())
            &&& (post2_self_@ == pre_self_@.subrange(0, start as int) + pre_self_@.subrange(end as int, pre_self_@.len() as int))
            &&& (pre_self_@.to_set() == post2_self_@.to_set() + pre_self_@.subrange(start as int, end as int).to_set())
        }) ==> det_erase_equal(r1, r2, post1_self_, post2_self_),
{
    if g_start_eq { assume(start as int == k_start_eq); }
    if g_start_rng { assume(start as int >= k_start_rng_lo && start as int <= k_start_rng_hi); }
    if g_end_eq { assume(end as int == k_end_eq); }
    if g_end_rng { assume(end as int >= k_end_rng_lo && end as int <= k_end_rng_hi); }
    if g_neq_tuple { assume(!det_erase_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl1_erase__erase`:

```
  start == 0
  end == 0
  !det_erase_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__erase__erase`:

```
  start == 0
  end == 0
  !det_erase_equal(r1, r2, post1_self_, post2_self_)
```

---

## #11 `extract_range_impl` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_shard.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_shard__extract_range_impl/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=1260
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CKeyHashMap` 仍走 structural `==`(`CKeyHashMap.json.quarantine` 标记)

### Source 函数(摘取)

```rust
fn extract_range_impl(h: &CKeyHashMap, kr: &KeyRange<CKey>) -> (ext: CKeyHashMap)
requires
    //h@.valid_key_range() // (See Distributed/Services/SHT/AppInterface.i.dfy: ValidKey() == true)
    forall |k| h@.contains_key(k) ==> /*#[trigger] valid_key(k) &&*/ #[trigger] valid_value(h@[k]),
ensures
    ext@ =~= extract_range(h@, *kr),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_extract_range_impl_equal(r1: CKeyHashMap, r2: CKeyHashMap) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_extract_range_impl(g_neq_tuple: bool, h: CKeyHashMap, kr: KeyRange<CKey>, r1: CKeyHashMap, r2: CKeyHashMap)
    requires (forall |k| h@.contains_key(k) ==> /*#[trigger] valid_key(k) &&*/ #[trigger] valid_value(h@[k])),
    ensures
        ({
            &&& (r1@ =~= extract_range(h@, kr))
            &&& (r2@ =~= extract_range(h@, kr))
        }) ==> det_extract_range_impl_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_extract_range_impl_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_shard__extract_range_impl`:

```
  !det_extract_range_impl_equal(r1, r2)
```

---

## #12 `get` (×2 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_get_request.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__get/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=1313
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `ID` 仍走 structural `==`(`ID.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn get(&self, k: &K) -> (id: ID)
        requires
            self.valid(),
        ensures
            id@ == self@[*k],
            id@.valid_physical_address(),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_get_equal(r1: ID, r2: ID) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_get<K: KeyTrait + VerusClone>(g_neq_tuple: bool, self_: DelegationMap<K>, k: K, r1: ID, r2: ID)
    requires (self_.valid()),
    ensures
        ({
            &&& (r1@ == self_@[k])
            &&& (r1@.valid_physical_address())
            &&& (r2@ == self_@[k])
            &&& (r2@.valid_physical_address())
        }) ==> det_get_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_get_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__get`:

```
  !det_get_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__get`:

```
  !det_get_equal(r1, r2)
```

---

## #13 `get_internal` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__get_internal/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=1005
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `ID` 仍走 structural `==`(`ID.json.quarantine` 标记)

### Source 函数(摘取)

```rust
fn get_internal(&self, k: &K) -> (res: (ID, Ghost<KeyIterator<K>>))
        requires
            self.valid(),
        ensures ({
            let (id, glb) = res;
            &&& id@ == self@[*k]
            &&& self.lows.greatest_lower_bound_spec(KeyIterator::new_spec(*k), glb@)
            &&& id@.valid_physical_address()
    }
```

### 生成的 equal_fn

```rust
spec fn det_get_internal_equal<K: KeyTrait + VerusClone>(r1: (ID, Ghost<KeyIterator<K>>), r2: (ID, Ghost<KeyIterator<K>>)) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_get_internal<K: KeyTrait + VerusClone>(g_neq_tuple: bool, self_: DelegationMap<K>, k: K, r1: (ID, Ghost<KeyIterator<K>>), r2: (ID, Ghost<KeyIterator<K>>))
    requires (self_.valid()),
    ensures
        ({
            &&& (({
            let (id, glb) = r1;
            &&& id@ == self_@[k]
            &&& self_.lows.greatest_lower_bound_spec(KeyIterator::new_spec(k), glb@)
            &&& id@.valid_physical_address()
    }))
            &&& (({
            let (id, glb) = r2;
            &&& id@ == self_@[k]
            &&& self_.lows.greatest_lower_bound_spec(KeyIterator::new_spec(k), glb@)
            &&& id@.valid_physical_address()
    }))
        }) ==> det_get_internal_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_get_internal_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__get_internal`:

```
  !det_get_internal_equal(r1, r2)
```

---

## #14 `get_my_end_point` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__real_init_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__get_my_end_point/`
- **z3 cost**: n_rounds=3, n_schemas=4, verus_ms=795
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `EndPoint` 仍走 structural `==`(`EndPoint.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn get_my_end_point(&self) -> (ep: EndPoint)
        ensures
            ep@ == self.my_end_point()
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_get_my_end_point_equal(r1: EndPoint, r2: EndPoint) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_get_my_end_point(g__self__state___is_Receiving: bool, g__self__state___is_Sending: bool, g__self__state___is_Error: bool, g_neq_tuple: bool, self_: NetClient, r1: EndPoint, r2: EndPoint)
    ensures
        ({
            &&& (r1@ == self_.my_end_point())
            &&& (r2@ == self_.my_end_point())
        }) ==> det_get_my_end_point_equal(r1, r2),
{
    if g__self__state___is_Receiving { assume((self_.state)@ is Receiving); }
    if g__self__state___is_Sending { assume((self_.state)@ is Sending); }
    if g__self__state___is_Error { assume((self_.state)@ is Error); }
    if g_neq_tuple { assume(!det_get_my_end_point_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__get_my_end_point`:

```
  (self_.state)@ is Receiving
  !det_get_my_end_point_equal(r1, r2)
```

---

## #15 `greatest_lower_bound_index` (×2 instances) — Bucket F

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__greatest_lower_bound_index.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl3__greatest_lower_bound_index__greatest_lower_bound_index/`
- **z3 cost**: n_rounds=15, n_schemas=5, verus_ms=551
- **Incompleteness 性质**: Quantifier-wall: GLB 唯一性需要 hand-instantiate ∀k(已被 LLM proof loop 在 inline `assert by` 里证掉)

### Source 函数(摘取)

```rust
fn greatest_lower_bound_index(&self, iter: &KeyIterator<K>) -> (index: usize)
        requires
            self.valid(),
            self@.contains_key(K::zero_spec()),
        ensures
            0 <= index < self.keys@.len(),
            self.greatest_lower_bound_spec(*iter, KeyIterator::new_spec(self.keys@[index as int])),
    {
        let mut bound = 0;
        let mut i = 1;

        // Prove the initial starting condition
        assert forall |j:nat| j < i implies iter.geq_K(#[trigger]self.keys@.index(j as int)) by {
            let z = K::zero_spec();
            assert(self.keys@.contains(z));
            let n = choose |n: int| 0 <= n < self.keys@.len() && self.keys@[n] == z;
            K::zero_properties();
            assert_by_contradiction!(n == 0, {
                assert(self.keys@[0].cmp_spec(self.keys@[n]).lt());
                K::cmp_properties();
            });
            assert(self.keys@[0] == z);
            K::cmp_properties();
        }

        // Find the glb's index (bound)
        while i < self.keys.len()
            invariant
                1 <= i <= self.keys@.len(),
                bound == i - 1,
                forall |j:nat| j < i ==> iter.geq_K(#[trigger]self.keys@.index(j as int)),
            ensures
                bound == i - 1,
                (i == self.keys@.len() &&
                 forall |j:nat| j < i ==> iter.geq_K(#[trigger]self.keys@.index(j as int)))
             || (i < self.keys@.len() &&
                 !iter.geq_K(self.keys@.index(i as int)) &&
                 forall |j:nat| j < i ==> iter.geq_K(#[trigger]self.keys@.index(j as int))),
            decreases
                self.keys@.len() - i
        {
            if iter.lt(&KeyIterator::new(self.keys.index(i))) {
                // Reached a key that's too large
                break;
            }
            bound = i;
            i = i + 1;
        }

        let glb = KeyIterator::new(self.keys.index(bound));

        assert forall |k|
               KeyIterator::new_spec(k) != glb
            && #[trigger] self@.contains_key(k)
            && iter.above(k)
            implies glb.above(k) by {
            K::cmp_properties();
        }

        proof {
            if !iter.is_end_spec() {
                if i == self.keys@.len() {
                    let hi = KeyIterator::end();
                    // Prove self.gap(glb, hi)
                    assert forall |ki| glb.lt_spec(ki) && ki.lt_spec(hi) implies !(#[trigger] self@.contains_key(
/* … (truncated) … */
```

### 生成的 equal_fn

```rust
spec fn det_greatest_lower_bound_index_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_greatest_lower_bound_index<K: KeyTrait + VerusClone>(g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, self_: StrictlyOrderedMap<K>, iter: KeyIterator<K>, r1: usize, r2: usize)
    requires (self_.valid()), (self_@.contains_key(K::zero_spec())),
    ensures
        ({
            &&& (0 <= r1 < self_.keys@.len())
            &&& (self_.greatest_lower_bound_spec(iter, KeyIterator::new_spec(self_.keys@[r1 as int])))
            &&& (0 <= r2 < self_.keys@.len())
            &&& (self_.greatest_lower_bound_spec(iter, KeyIterator::new_spec(self_.keys@[r2 as int])))
        }) ==> det_greatest_lower_bound_index_equal(r1, r2),
{
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_greatest_lower_bound_index_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__greatest_lower_bound_index__greatest_lower_bound_index`:

```
  r1 == 0
  r2 == 1
  !det_greatest_lower_bound_index_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__impl4__range_consistent_impl__greatest_lower_bound_index`:

```
  r1 == 0
  r2 == 1
  !det_greatest_lower_bound_index_equal(r1, r2)
```

---

## #16 `host_model_receive_packet` (×1 instances) — Bucket G

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_receive_packet.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_receive_packet__host_model_receive_packet/`
- **z3 cost**: n_rounds=464, n_schemas=91, verus_ms=2003
- **Incompleteness 性质**: View-equal 已部分注入,但 `Vec<CPacket>` 残留 quantifier-wall(CPacket quarantined,Vec 顺序约束需量词)

### Source 函数(摘取)

```rust
fn host_model_receive_packet(&mut self, cpacket: CPacket) -> (rc: (Vec<CPacket>, Ghost<CPacket>))
    requires
        old(self).valid(),
        old(self).host_state_packet_preconditions(cpacket),
        !(cpacket.msg is InvalidMessage),
        cpacket.dst@ == old(self).constants.me@,
    ensures ({
        let (sent_packets, ack) = rc;
        &&& outbound_packet_seq_is_valid(sent_packets@)
        &&& receive_packet(old(self)@, self@, cpacket@, abstractify_seq_of_cpackets_to_set_of_sht_packets(sent_packets@), ack@@)
        // The Dafny Ironfleet "common preconditions" take an explicit cpacket, but we need to talk
        // about
        &&& self.host_state_common_postconditions(*old(self), cpacket, sent_packets@)
        }
```

### 生成的 equal_fn

```rust
spec fn det_host_model_receive_packet_equal(r1: (Vec<CPacket>, Ghost<CPacket>), r2: (Vec<CPacket>, Ghost<CPacket>), post1_self_: HostState, post2_self_: HostState) -> bool {
    (r1 == r2)
    && (((post1_self_).view() == (post2_self_).view()))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_host_model_receive_packet(g_pre_self__next_action_index_eq: bool, k_pre_self__next_action_index_eq: int, g_pre_self__next_action_index_rng: bool, k_pre_self__next_action_index_rng_lo: int, k_pre_self__next_action_index_rng_hi: int, g_pre_self__resend_count_eq: bool, k_pre_self__resend_count_eq: int, g_pre_self__resend_count_rng: bool, k_pre_self__resend_count_rng_lo: int, k_pre_self__resend_count_rng_hi: int, g_pre_self__constants_params_max_seqno_eq: bool, k_pre_self__constants_params_max_seqno_eq: int, g_pre_self__constants_params_max_seqno_rng: bool, k_pre_self__constants_params_max_seqno_rng_lo: int, k_pre_self__constants_params_max_seqno_rng_hi: int, g_pre_self__constants_params_max_delegations_eq: bool, k_pre_self__constants_params_max_delegations_eq: int, g_pre_self__constants_params_max_delegations_rng: bool, k_pre_self__constants_params_max_delegations_rng_lo: int, k_pre_self__constants_params_max_delegations_rng_hi: int, g_pre_self__received_packet_is_Some: bool, g_pre_self__received_packet_is_None: bool, g_pre_self__num_delegations_eq: bool, k_pre_self__num_delegations_eq: int, g_pre_self__num_delegations_rng: bool, k_pre_self__num_delegations_rng_lo: int, k_pre_self__num_delegations_rng_hi: int, g__pre_self__received_requests___leneq: bool, k__pre_self__received_requests___leneq: nat, g__pre_self__received_requests___lenrng: bool, k__pre_self__received_requests___lenrng_lo: nat, k__pre_self__received_requests___lenrng_hi: nat, g__pre_self__received_requests___0__is_AppGetRequest: bool, g__pre_self__received_requests___0__is_AppSetRequest: bool, g__pre_self__received_requests___1__is_AppGetRequest: bool, g__pre_self__received_requests___1__is_AppSetRequest: bool, g__pre_self__received_requests___2__is_AppGetRequest: bool, g__pre_self__received_requests___2__is_AppSetRequest: bool, g__pre_self__received_requests___3__is_AppGetRequest: bool, g__pre_self__received_requests___3__is_AppSetRequest: bool, g__pre_self__received_requests___4__is_AppGetRequest: bool, g__pre_self__received_requests___4__is_AppSetRequest: bool, g__pre_self__received_requests___5__is_AppGetRequest: bool, g__pre_self__received_requests___5__is_AppSetRequest: bool, g__pre_self__received_requests___6__is_AppGetRequest: bool, g__pre_self__received_requests___6__is_AppSetRequest: bool, g__pre_self__received_requests___7__is_AppGetRequest: bool, g__pre_self__received_requests___7__is_AppSetRequest: bool, g_post1_self__next_action_index_eq: bool, k_post1_self__next_action_index_eq: int, g_post1_self__next_action_index_rng: bool, k_post1_self__next_action_index_rng_lo: int, k_post1_self__next_action_index_rng_hi: int, g_post1_self__resend_count_eq: bool, k_post1_self__resend_count_eq: int, g_post1_self__resend_count_rng: bool, k_post1_self__resend_count_rng_lo: int, k_post1_self__resend_count_rng_hi: int, g_post1_self__constants_params_max_seqno_eq: bool, k_post1_self__constants_params_max_seqno_eq: int, g_post1_self__constants_params_max_seqno_rng: bool, k_po
/* … (truncated — full body in injected.rs) … */
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_receive_packet__host_model_receive_packet`:

```
  pre_self_.next_action_index == 0
  pre_self_.resend_count == 0
  pre_self_.constants.params.max_seqno == 18446744073709551615
  pre_self_.constants.params.max_delegations == 9223372036854775807
  pre_self_.received_packet is Some
  pre_self_.num_delegations == 0
  (pre_self_.received_requests)@.len() == 0
  post1_self_.next_action_index == 0
  post1_self_.resend_count == 0
  post1_self_.constants.params.max_seqno == 18446744073709551615
  post1_self_.constants.params.max_delegations == 9223372036854775807
  post1_self_.received_packet is Some
  post1_self_.num_delegations == 0
  (post1_self_.received_requests)@.len() == 0
  post2_self_.next_action_index == 0
  post2_self_.resend_count == 0
  post2_self_.constants.params.max_seqno == 18446744073709551615
  post2_self_.constants.params.max_delegations == 9223372036854775807
  post2_self_.received_packet is Some
  post2_self_.num_delegations == 0
  (post2_self_.received_requests)@.len() == 0
  !det_host_model_receive_packet_equal(r1, r2, post1_self_, post2_self_)
```

---

## #17 `insert` (×2 instances) — Bucket E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl1_insert.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl1_insert__insert/`
- **z3 cost**: n_rounds=14, n_schemas=5, verus_ms=485
- **Incompleteness 性质**: Wiring-blocked: StrictlyOrdered* 通过 `K: VerusClone` 间接卡 cascade(K 实例化时挂上 quarantined 类型)

### Source 函数(摘取)

```rust
fn insert(&mut self, k: K) -> (i: usize)
        requires
            old(self).valid(),
            !old(self)@.contains(k),
        ensures self.valid(),
            self@.len() == old(self)@.len() + 1,
            0 <= i < self@.len(),
            self@ == old(self)@.insert(i as int, k),
            self@.to_set() == old(self)@.to_set().insert(k),
    {
        // Find the index where we should insert k
        let mut index: usize = 0;
        while index < self.v.len() && self.v[index].cmp(&k).is_lt()
            invariant
                0 <= index <= self@.len(),
                forall |i| 0 <= i < index ==> (#[trigger] self@.index(i).cmp_spec(k)).lt()
            decreases
               self@.len() - index
        {
            index = index + 1;
        }
        self.v.insert(index, k);
        assert forall |m, n| 0 <= m < n < self@.len() implies #[trigger](self@[m].cmp_spec(self@[n]).lt()) by {
            K::cmp_properties();
        }
        assert(self@.to_set() == old(self)@.to_set().insert(k)) by {
            let new_s = self@.to_set();
            let old_s = old(self)@.to_set().insert(k);
            assert(self@[index as int] == k);   // OBSERVE
            assert forall |e| old_s.contains(e) implies new_s.contains(e) by {
                if e == k {
                } else {
                    let i = choose |i: int| 0 <= i < old(self)@.len() && old(self)@[i] == e;
                    if i < index {
                        assert(self@[i] == e);      // OBSERVE
                    } else {
                        assert(self@[i+1] == e);    // OBSERVE
                    }
                }
            };
            assert_sets_equal!(new_s, old_s);
        };
        return index;
    }
```

### 生成的 equal_fn

```rust
spec fn det_insert_equal<K: KeyTrait + VerusClone>(r1: usize, r2: usize, post1_self_: StrictlyOrderedVec<K>, post2_self_: StrictlyOrderedVec<K>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_insert<K: KeyTrait + VerusClone>(g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, pre_self_: StrictlyOrderedVec<K>, k: K, post1_self_: StrictlyOrderedVec<K>, r1: usize, post2_self_: StrictlyOrderedVec<K>, r2: usize)
    requires (pre_self_.valid()), (!pre_self_@.contains(k)),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (post1_self_@.len() == pre_self_@.len() + 1)
            &&& (0 <= r1 < post1_self_@.len())
            &&& (post1_self_@ == pre_self_@.insert(r1 as int, k))
            &&& (post1_self_@.to_set() == pre_self_@.to_set().insert(k))
            &&& (post2_self_.valid())
            &&& (post2_self_@.len() == pre_self_@.len() + 1)
            &&& (0 <= r2 < post2_self_@.len())
            &&& (post2_self_@ == pre_self_@.insert(r2 as int, k))
            &&& (post2_self_@.to_set() == pre_self_@.to_set().insert(k))
        }) ==> det_insert_equal(r1, r2, post1_self_, post2_self_),
{
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_insert_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl1_insert__insert`:

```
  r1 == 0
  r2 == 0
  !det_insert_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__set__insert`:

```
  r1 == 0
  r2 == 0
  !det_insert_equal(r1, r2, post1_self_, post2_self_)
```

---

## #18 `insert` (×4 instances) — Bucket D

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__maybe_ack_packet_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__maybe_ack_packet_impl__insert/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=815
- **Incompleteness 性质**: Wiring-blocked: HashMap 字段(基于 `CKeyHashMap`)未 resolve

### Source 函数(摘取)

```rust
pub fn insert(&mut self, key: &EndPoint, value: V)
      ensures self@ == old(self)@.insert(key@, value)
        {
                unimplemented!()
        }
```

### 生成的 equal_fn

```rust
spec fn det_insert_equal<V>(r1: (), r2: (), post1_self_: HashMap<V>, post2_self_: HashMap<V>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_insert<V>(g_neq_tuple: bool, pre_self_: HashMap<V>, key: EndPoint, value: V, post1_self_: HashMap<V>, r1: (), post2_self_: HashMap<V>, r2: ())
    ensures
        ({
            &&& (post1_self_@ == pre_self_@.insert(key@, value))
            &&& (post2_self_@ == pre_self_@.insert(key@, value))
        }) ==> det_insert_equal(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_insert_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__maybe_ack_packet_impl__insert`:

```
  !det_insert_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__insert`:

```
  !det_insert_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 3** — `ironkv__verified__single_delivery_state_v__single_delivery_state_v__impl1__insert__insert`:

```
  !det_insert_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 4** — `ironkv__verified__single_delivery_state_v__single_delivery_state_v__impl3__un_acked_messages_extend__insert`:

```
  !det_insert_equal(r1, r2, post1_self_, post2_self_)
```

---

## #19 `maybe_ack_packet_impl` (×2 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__maybe_ack_packet_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__maybe_ack_packet_impl__maybe_ack_packet_impl/`
- **z3 cost**: n_rounds=4, n_schemas=5, verus_ms=894
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CPacket` 仍走 structural `==`(`CPacket.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn maybe_ack_packet_impl(&self, pkt: &CPacket) -> (opt_ack: Option<CPacket>)
    requires
        self.valid(),
        pkt.abstractable(),
        pkt.msg is Message,
    ensures
        SingleDelivery::maybe_ack_packet(self@, pkt@, opt_ack.unwrap()@, Self::option_cpacket_to_set_packet(opt_ack)),
        opt_ack is Some ==> valid_ack(opt_ack.unwrap(), *pkt),
    {
        // jonh inlined ShouldAckSingleMessageImpl and SendAckImpl.
        // I feel like we could inline a LOT of these methods; they're
        // very much consequences of the painful Dafny break-everything-into-
        // two-line-methods lifestyle.
        match pkt.msg {
            CSingleMessage::Message{seqno, ..} => {
                if seqno <= self.receive_state.lookup(&pkt.src) {
                    let m_ack = CSingleMessage::Ack{ack_seqno: seqno};
                    assert(m_ack.is_marshalable()) by {
                        vstd::bytes::lemma_auto_spec_u64_to_from_le_bytes();
                    }
                    let p_ack = CPacket{
                        dst: pkt.src.clone_up_to_view(),
                        src: pkt.dst.clone_up_to_view(),
                        msg: m_ack
                    };
                    Some(p_ack) // Fresh or Duplicate
                } else {
                    None
                }
            },
            _ => { assert(false); unreached() }
        }

        // When ReceiveSingleMessageImpl calls MaybeAckPacketImpl(acct'), the returned b must be true,
        // because acct' came from ReceiveRealPacketImpl.
        //
        // The "weird" case is receiving a duplicate message; here's the call stack:
        // HMRP / ReceiveSingleMessageImpl / ReceiveRealPacketImpl / NewSingleMessageImpl returns false
        // HMRP / ReceiveSingleMessageImpl / MaybeAckPacketImpl(acct') returns true
        // HMRP / NewSingleMessageImpl(acct0) returns false
    }
```

### 生成的 equal_fn

```rust
spec fn det_maybe_ack_packet_impl_equal(r1: Option<CPacket>, r2: Option<CPacket>) -> bool {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> (((r1->Some_0.dst.id == r2->Some_0.dst.id)) && ((r1->Some_0.src.id == r2->Some_0.src.id)) && (r1->Some_0.msg == r2->Some_0.msg))))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_maybe_ack_packet_impl(g_r1_is_Some: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2_is_None: bool, g_neq_tuple: bool, self_: CSingleDelivery, pkt: CPacket, r1: Option<CPacket>, r2: Option<CPacket>)
    requires (self_.valid()), (pkt.abstractable()), (pkt.msg is Message),
    ensures
        ({
            &&& (SingleDelivery::maybe_ack_packet(self_@, pkt@, r1.unwrap()@, CSingleDelivery::option_cpacket_to_set_packet(r1)))
            &&& (r1 is Some ==> valid_ack(r1.unwrap(), pkt))
            &&& (SingleDelivery::maybe_ack_packet(self_@, pkt@, r2.unwrap()@, CSingleDelivery::option_cpacket_to_set_packet(r2)))
            &&& (r2 is Some ==> valid_ack(r2.unwrap(), pkt))
        }) ==> det_maybe_ack_packet_impl_equal(r1, r2),
{
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_maybe_ack_packet_impl_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__maybe_ack_packet_impl__maybe_ack_packet_impl`:

```
  r1 is Some
  r2 is Some
  !det_maybe_ack_packet_impl_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__receive_impl__maybe_ack_packet_impl`:

```
  r1 is Some
  r2 is Some
  !det_maybe_ack_packet_impl_equal(r1, r2)
```

---

## #20 `new` (×1 instances) — Bucket E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__new.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl3__new__new/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=365
- **Incompleteness 性质**: Wiring-blocked: StrictlyOrdered* 通过 `K: VerusClone` 间接卡 cascade(K 实例化时挂上 quarantined 类型)

### Source 函数(摘取)

```rust
fn new() -> (v: Self)
        ensures v@ == Seq::<K>::empty(),
                v.valid(),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_new_equal<K: KeyTrait + VerusClone>(r1: StrictlyOrderedVec<K>, r2: StrictlyOrderedVec<K>) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_new<K: KeyTrait + VerusClone>(g_neq_tuple: bool, r1: StrictlyOrderedVec<K>, r2: StrictlyOrderedVec<K>)
    ensures
        ({
            &&& (r1@ == Seq::<K>::empty())
            &&& (r1.valid())
            &&& (r2@ == Seq::<K>::empty())
            &&& (r2.valid())
        }) ==> det_new_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__new__new`:

```
  !det_new_equal(r1, r2)
```

---

## #21 `new` (×1 instances) — Bucket E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__new.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl4__new__new/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=442
- **Incompleteness 性质**: Wiring-blocked: StrictlyOrdered* 通过 `K: VerusClone` 间接卡 cascade(K 实例化时挂上 quarantined 类型)

### Source 函数(摘取)

```rust
fn new() -> (s: Self)
        ensures
            s.valid(),
            s@ == Map::<K,ID>::empty(),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_new_equal<K: KeyTrait + VerusClone>(r1: StrictlyOrderedMap<K>, r2: StrictlyOrderedMap<K>) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_new<K: KeyTrait + VerusClone>(g_neq_tuple: bool, r1: StrictlyOrderedMap<K>, r2: StrictlyOrderedMap<K>)
    ensures
        ({
            &&& (r1.valid())
            &&& (r1@ == Map::<K,ID>::empty())
            &&& (r2.valid())
            &&& (r2@ == Map::<K,ID>::empty())
        }) ==> det_new_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl4__new__new`:

```
  !det_new_equal(r1, r2)
```

---

## #22 `new` (×1 instances) — Bucket E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__real_init_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__new/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=802
- **Incompleteness 性质**: Wiring-blocked: StrictlyOrdered* 通过 `K: VerusClone` 间接卡 cascade(K 实例化时挂上 quarantined 类型)

### Source 函数(摘取)

```rust
pub fn new(k_zero: K, id_zero: ID) -> (s: Self)
        requires
            k_zero == K::zero_spec(),
            id_zero@.valid_physical_address(),
        ensures
            s.valid(),
            s@ == Map::total(|k: K| id_zero@),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_new_equal<K: KeyTrait + VerusClone>(r1: DelegationMap<K>, r2: DelegationMap<K>) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_new<K: KeyTrait + VerusClone>(g_neq_tuple: bool, k_zero: K, id_zero: ID, r1: DelegationMap<K>, r2: DelegationMap<K>)
    requires (k_zero == K::zero_spec()), (id_zero@.valid_physical_address()),
    ensures
        ({
            &&& (r1.valid())
            &&& (r1@ == Map::total(|k: K| id_zero@))
            &&& (r2.valid())
            &&& (r2@ == Map::total(|k: K| id_zero@))
        }) ==> det_new_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__real_init_impl__new`:

```
  !det_new_equal(r1, r2)
```

---

## #23 `new` (×3 instances) — Bucket D

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__maybe_ack_packet_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__maybe_ack_packet_impl__new/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=765
- **Incompleteness 性质**: Wiring-blocked: HashMap 字段(基于 `CKeyHashMap`)未 resolve

### Source 函数(摘取)

```rust
pub fn new() -> (out: Self)
        ensures out@ == Map::<AbstractEndPoint, V>::empty()
    {
      HashMap { m: collections::HashMap::new() }
    }
```

### 生成的 equal_fn

```rust
spec fn det_new_equal<V>(r1: HashMap<V>, r2: HashMap<V>) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_new<V>(g_neq_tuple: bool, r1: HashMap<V>, r2: HashMap<V>)
    ensures
        ({
            &&& (r1@ == Map::<AbstractEndPoint, V>::empty())
            &&& (r2@ == Map::<AbstractEndPoint, V>::empty())
        }) ==> det_new_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__maybe_ack_packet_impl__new`:

```
  !det_new_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__new`:

```
  !det_new_equal(r1, r2)
```

**Instance 3** — `ironkv__verified__single_delivery_state_v__single_delivery_state_v__impl3__un_acked_messages_extend__new`:

```
  !det_new_equal(r1, r2)
```

---

## #24 `new` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__send_single_cmessage.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__send_single_cmessage__new/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=2425
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CAckState` 仍走 structural `==`(`CAckState.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn new() -> (e: CAckState)
    ensures
        e.num_packets_acked == 0,
        e.un_acked.len() == 0,
        e@ =~= AckState::new(),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_new_equal(r1: CAckState, r2: CAckState) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_new(g_neq_tuple: bool, r1: CAckState, r2: CAckState)
    ensures
        ({
            &&& (r1.num_packets_acked == 0)
            &&& (r1.un_acked.len() == 0)
            &&& (r1@ =~= AckState::new())
            &&& (r2.num_packets_acked == 0)
            &&& (r2.un_acked.len() == 0)
            &&& (r2@ =~= AckState::new())
        }) ==> det_new_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__send_single_cmessage__new`:

```
  !det_new_equal(r1, r2)
```

---

## #25 `parse_end_point` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__parse_end_points.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__parse_end_points__parse_end_point/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=480
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `EndPoint` 仍走 structural `==`(`EndPoint.json.quarantine` 标记)

### Source 函数(摘取)

```rust
fn parse_end_point(arg: &Arg) -> (out: EndPoint)
    ensures
        out@ == parse_arg_as_end_point(arg@),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_parse_end_point_equal(r1: EndPoint, r2: EndPoint) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_parse_end_point(g_neq_tuple: bool, arg: Arg, r1: EndPoint, r2: EndPoint)
    ensures
        ({
            &&& (r1@ == parse_arg_as_end_point(arg@))
            &&& (r2@ == parse_arg_as_end_point(arg@))
        }) ==> det_parse_end_point_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_parse_end_point_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__parse_end_points__parse_end_point`:

```
  !det_parse_end_point_equal(r1, r2)
```

---

## #26 `parse_end_points` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__parse_end_points.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__parse_end_points__parse_end_points/`
- **z3 cost**: n_rounds=4, n_schemas=5, verus_ms=486
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `EndPoint` 仍走 structural `==`(`EndPoint.json.quarantine` 标记)

### Source 函数(摘取)

```rust
fn parse_end_points(args: &Args) -> (out: Option<Vec<EndPoint>>)
    ensures
        match out {
            None => parse_args(abstractify_args(*args)) is None,
            Some(vec) => {
                &&& parse_args(abstractify_args(*args)) is Some
                &&& abstractify_end_points(vec) == parse_args(abstractify_args(*args)).unwrap()
            },
        }
```

### 生成的 equal_fn

```rust
spec fn det_parse_end_points_equal(r1: Option<Vec<EndPoint>>, r2: Option<Vec<EndPoint>>) -> bool {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0)))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_parse_end_points(g_r1_is_Some: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2_is_None: bool, g_neq_tuple: bool, args: Args, r1: Option<Vec<EndPoint>>, r2: Option<Vec<EndPoint>>)
    ensures
        ({
            &&& (match r1 {
            None => parse_args(abstractify_args(args)) is None,
            Some(vec) => {
                &&& parse_args(abstractify_args(args)) is Some
                &&& abstractify_end_points(vec) == parse_args(abstractify_args(args)).unwrap()
            },
        })
            &&& (match r2 {
            None => parse_args(abstractify_args(args)) is None,
            Some(vec) => {
                &&& parse_args(abstractify_args(args)) is Some
                &&& abstractify_end_points(vec) == parse_args(abstractify_args(args)).unwrap()
            },
        })
        }) ==> det_parse_end_points_equal(r1, r2),
{
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_parse_end_points_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__parse_end_points__parse_end_points`:

```
  r1 is Some
  r2 is Some
  !det_parse_end_points_equal(r1, r2)
```

---

## #27 `put` (×2 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__receive_ack_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__put/`
- **z3 cost**: n_rounds=8, n_schemas=3, verus_ms=879
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CSendState` 仍走 structural `==`(`CSendState.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn put(&mut self, src: &EndPoint, value: CAckState)
    ensures
        HashMap::put_spec(old(self).epmap@, self.epmap@, src@, value),
    {
        unimplemented!()
    }
```

### 生成的 equal_fn

```rust
spec fn det_put_equal(r1: (), r2: (), post1_self_: CSendState, post2_self_: CSendState) -> bool {
    (r1 == r2)
    && ((post1_self_.epmap == post2_self_.epmap))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_put(g_value_num_packets_acked_eq: bool, k_value_num_packets_acked_eq: int, g_value_num_packets_acked_rng: bool, k_value_num_packets_acked_rng_lo: int, k_value_num_packets_acked_rng_hi: int, g_neq_tuple: bool, pre_self_: CSendState, src: EndPoint, value: CAckState, post1_self_: CSendState, r1: (), post2_self_: CSendState, r2: ())
    ensures
        ({
            &&& (HashMap::put_spec(pre_self_.epmap@, post1_self_.epmap@, src@, value))
            &&& (HashMap::put_spec(pre_self_.epmap@, post2_self_.epmap@, src@, value))
        }) ==> det_put_equal(r1, r2, post1_self_, post2_self_),
{
    if g_value_num_packets_acked_eq { assume(value.num_packets_acked as int == k_value_num_packets_acked_eq); }
    if g_value_num_packets_acked_rng { assume(value.num_packets_acked as int >= k_value_num_packets_acked_rng_lo && value.num_packets_acked as int <= k_value_num_packets_acked_rng_hi); }
    if g_neq_tuple { assume(!det_put_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__put`:

```
  value.num_packets_acked == 0
  !det_put_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__send_single_cmessage__put`:

```
  value.num_packets_acked == 0
  !det_put_equal(r1, r2, post1_self_, post2_self_)
```

---

## #28 `receive_ack_impl` (×2 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_impl2__receive_ack_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__receive_ack_impl/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=848
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CSingleDelivery` 仍走 structural `==`(`CSingleDelivery.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn receive_ack_impl(&mut self, pkt: &CPacket)
    requires
        old(self).valid(),
       // self.abstractable(),
        pkt.abstractable(),
        pkt.msg is Ack,
    ensures
        self.valid(),
        SingleDelivery::receive_ack(old(self)@, self@, pkt@, set!{}
```

### 生成的 equal_fn

```rust
spec fn det_receive_ack_impl_equal(r1: (), r2: (), post1_self_: CSingleDelivery, post2_self_: CSingleDelivery) -> bool {
    (r1 == r2)
    && (((post1_self_.receive_state.epmap == post2_self_.receive_state.epmap)) && ((post1_self_.send_state.epmap == post2_self_.send_state.epmap)))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_receive_ack_impl(g_neq_tuple: bool, pre_self_: CSingleDelivery, pkt: CPacket, post1_self_: CSingleDelivery, r1: (), post2_self_: CSingleDelivery, r2: ())
    requires (pre_self_.valid()), (pkt.abstractable()), (pkt.msg is Ack),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (SingleDelivery::receive_ack(pre_self_@, post1_self_@, pkt@, set!{}))
            &&& (post2_self_.valid())
            &&& (SingleDelivery::receive_ack(pre_self_@, post2_self_@, pkt@, set!{}))
        }) ==> det_receive_ack_impl_equal(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_receive_ack_impl_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_impl2__receive_ack_impl__receive_ack_impl`:

```
  !det_receive_ack_impl_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__receive_impl__receive_ack_impl`:

```
  !det_receive_ack_impl_equal(r1, r2, post1_self_, post2_self_)
```

---

## #29 `receive_impl` (×2 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_receive_packet.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_receive_packet__receive_impl/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=965
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CSingleDelivery` 仍走 structural `==`(`CSingleDelivery.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn receive_impl(&mut self, pkt: &CPacket) -> (rr: ReceiveImplResult)
    requires
        old(self).valid(),
        old(self).abstractable(),
        pkt.abstractable(),
    ensures
        self.valid(),
        rr.valid_ack(*pkt),
        SingleDelivery::receive(old(self)@, self@, pkt@, rr.get_ack()@, rr.get_abstracted_ack_set()),
        rr is FreshPacket ==> SingleDelivery::new_single_message(old(self)@, pkt@),
        rr is DuplicatePacket ==> !SingleDelivery::new_single_message(old(self)@, pkt@),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_receive_impl_equal(r1: ReceiveImplResult, r2: ReceiveImplResult, post1_self_: CSingleDelivery, post2_self_: CSingleDelivery) -> bool {
    (r1 == r2)
    && (((post1_self_.receive_state.epmap == post2_self_.receive_state.epmap)) && ((post1_self_.send_state.epmap == post2_self_.send_state.epmap)))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_receive_impl(g_neq_tuple: bool, pre_self_: CSingleDelivery, pkt: CPacket, post1_self_: CSingleDelivery, r1: ReceiveImplResult, post2_self_: CSingleDelivery, r2: ReceiveImplResult)
    requires (pre_self_.valid()), (pre_self_.abstractable()), (pkt.abstractable()),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (r1.valid_ack(pkt))
            &&& (SingleDelivery::receive(pre_self_@, post1_self_@, pkt@, r1.get_ack()@, r1.get_abstracted_ack_set()))
            &&& (r1 is FreshPacket ==> SingleDelivery::new_single_message(pre_self_@, pkt@))
            &&& (r1 is DuplicatePacket ==> !SingleDelivery::new_single_message(pre_self_@, pkt@))
            &&& (post2_self_.valid())
            &&& (r2.valid_ack(pkt))
            &&& (SingleDelivery::receive(pre_self_@, post2_self_@, pkt@, r2.get_ack()@, r2.get_abstracted_ack_set()))
            &&& (r2 is FreshPacket ==> SingleDelivery::new_single_message(pre_self_@, pkt@))
            &&& (r2 is DuplicatePacket ==> !SingleDelivery::new_single_message(pre_self_@, pkt@))
        }) ==> det_receive_impl_equal(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_receive_impl_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_receive_packet__receive_impl`:

```
  !det_receive_impl_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__receive_impl__receive_impl`:

```
  !det_receive_impl_equal(r1, r2, post1_self_, post2_self_)
```

---

## #30 `receive_real_packet_impl` (×1 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__receive_impl.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__receive_impl__receive_real_packet_impl/`
- **z3 cost**: n_rounds=4, n_schemas=5, verus_ms=791
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CSingleDelivery` 仍走 structural `==`(`CSingleDelivery.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn receive_real_packet_impl(&mut self, pkt: &CPacket) -> (packet_is_fresh: bool)
    requires
        old(self).valid(),
        pkt.abstractable(),
        pkt.msg is Message,
    ensures
        self.valid(),
        SingleDelivery::receive_real_packet(old(self)@, self@, pkt@),
        packet_is_fresh == SingleDelivery::new_single_message(old(self)@, pkt@),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_receive_real_packet_impl_equal(r1: bool, r2: bool, post1_self_: CSingleDelivery, post2_self_: CSingleDelivery) -> bool {
    (r1 == r2)
    && (((post1_self_.receive_state.epmap == post2_self_.receive_state.epmap)) && ((post1_self_.send_state.epmap == post2_self_.send_state.epmap)))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_receive_real_packet_impl(g_r1_is_true: bool, g_r1_is_false: bool, g_r2_is_true: bool, g_r2_is_false: bool, g_neq_tuple: bool, pre_self_: CSingleDelivery, pkt: CPacket, post1_self_: CSingleDelivery, r1: bool, post2_self_: CSingleDelivery, r2: bool)
    requires (pre_self_.valid()), (pkt.abstractable()), (pkt.msg is Message),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (SingleDelivery::receive_real_packet(pre_self_@, post1_self_@, pkt@))
            &&& (r1 == SingleDelivery::new_single_message(pre_self_@, pkt@))
            &&& (post2_self_.valid())
            &&& (SingleDelivery::receive_real_packet(pre_self_@, post2_self_@, pkt@))
            &&& (r2 == SingleDelivery::new_single_message(pre_self_@, pkt@))
        }) ==> det_receive_real_packet_impl_equal(r1, r2, post1_self_, post2_self_),
{
    if g_r1_is_true { assume(r1 == true); }
    if g_r1_is_false { assume(r1 == false); }
    if g_r2_is_true { assume(r2 == true); }
    if g_r2_is_false { assume(r2 == false); }
    if g_neq_tuple { assume(!det_receive_real_packet_impl_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__receive_impl__receive_real_packet_impl`:

```
  r1 == true
  r2 == true
  !det_receive_real_packet_impl_equal(r1, r2, post1_self_, post2_self_)
```

---

## #31 `remove` (×2 instances) — Bucket E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl1_erase.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl1_erase__remove/`
- **z3 cost**: n_rounds=8, n_schemas=3, verus_ms=512
- **Incompleteness 性质**: Wiring-blocked: StrictlyOrdered* 通过 `K: VerusClone` 间接卡 cascade(K 实例化时挂上 quarantined 类型)

### Source 函数(摘取)

```rust
fn remove(&mut self, i: usize) -> (k: K)
        requires
            old(self).valid(),
            i < old(self)@.len(),
        ensures
            self.valid(),
            k == old(self)@.index(i as int),
            self@ == old(self)@.remove(i as int),
            self@.to_set() == old(self)@.to_set().remove(k),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_remove_equal<K: KeyTrait + VerusClone>(r1: K, r2: K, post1_self_: StrictlyOrderedVec<K>, post2_self_: StrictlyOrderedVec<K>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_remove<K: KeyTrait + VerusClone>(g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_neq_tuple: bool, pre_self_: StrictlyOrderedVec<K>, i: usize, post1_self_: StrictlyOrderedVec<K>, r1: K, post2_self_: StrictlyOrderedVec<K>, r2: K)
    requires (pre_self_.valid()), (i < pre_self_@.len()),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (r1 == pre_self_@.index(i as int))
            &&& (post1_self_@ == pre_self_@.remove(i as int))
            &&& (post1_self_@.to_set() == pre_self_@.to_set().remove(r1))
            &&& (post2_self_.valid())
            &&& (r2 == pre_self_@.index(i as int))
            &&& (post2_self_@ == pre_self_@.remove(i as int))
            &&& (post2_self_@.to_set() == pre_self_@.to_set().remove(r2))
        }) ==> det_remove_equal(r1, r2, post1_self_, post2_self_),
{
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_neq_tuple { assume(!det_remove_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl1_erase__remove`:

```
  i == 0
  !det_remove_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__impl1_remove__remove`:

```
  i == 0
  !det_remove_equal(r1, r2, post1_self_, post2_self_)
```

---

## #32 `send_single_cmessage` (×4 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_get_request.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__send_single_cmessage/`
- **z3 cost**: n_rounds=5, n_schemas=11, verus_ms=1399
- **Incompleteness 性质**: Wiring-blocked: equal_fn 里 `CSingleMessage` 仍走 structural `==`(`CSingleMessage.json.quarantine` 标记)

### Source 函数(摘取)

```rust
pub fn send_single_cmessage(&mut self, m: &CMessage, dst: &EndPoint) -> (sm: Option<CSingleMessage>)
        requires
            old(self).valid(),
            old(self).abstractable(),
            m.abstractable(),
            m.message_marshallable(),
            m.is_marshalable(),
            dst@.valid_physical_address(),
        ensures
            self.valid(),
            match sm {
                Some(sm) => {
                    &&& sm.abstractable()
                    &&& sm is Message
                    &&& sm.arrow_Message_dst()@ == dst@
                    &&& SingleDelivery::send_single_message(old(self)@, self@, m@, dst@, Some(sm@), AbstractParameters::static_params())
                    &&& sm.is_marshalable()
                },
                None =>
                    SingleDelivery::send_single_message(old(self)@, self@, m@, dst@, None, AbstractParameters::static_params()),
            }
```

### 生成的 equal_fn

```rust
spec fn det_send_single_cmessage_equal(r1: Option<CSingleMessage>, r2: Option<CSingleMessage>, post1_self_: CSingleDelivery, post2_self_: CSingleDelivery) -> bool {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0)))
    && (((post1_self_.receive_state.epmap == post2_self_.receive_state.epmap)) && ((post1_self_.send_state.epmap == post2_self_.send_state.epmap)))
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_send_single_cmessage(g_m_is_GetRequest: bool, g_m_is_SetRequest: bool, g_m_is_Reply: bool, g_m_is_Redirect: bool, g_m_is_Shard: bool, g_m_is_Delegate: bool, g_r1_is_Some: bool, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2_is_None: bool, g_neq_tuple: bool, pre_self_: CSingleDelivery, m: CMessage, dst: EndPoint, post1_self_: CSingleDelivery, r1: Option<CSingleMessage>, post2_self_: CSingleDelivery, r2: Option<CSingleMessage>)
    requires (pre_self_.valid()), (pre_self_.abstractable()), (m.abstractable()), (m.message_marshallable()), (m.is_marshalable()), (dst@.valid_physical_address()),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (match r1 {
                Some(r1) => {
                    &&& r1.abstractable()
                    &&& r1 is Message
                    &&& r1.arrow_Message_dst()@ == dst@
                    &&& SingleDelivery::send_single_message(pre_self_@, post1_self_@, m@, dst@, Some(r1@), AbstractParameters::static_params())
                    &&& r1.is_marshalable()
                },
                None =>
                    SingleDelivery::send_single_message(pre_self_@, post1_self_@, m@, dst@, None, AbstractParameters::static_params()),
            })
            &&& (post2_self_.valid())
            &&& (match r2 {
                Some(r2) => {
                    &&& r2.abstractable()
                    &&& r2 is Message
                    &&& r2.arrow_Message_dst()@ == dst@
                    &&& SingleDelivery::send_single_message(pre_self_@, post2_self_@, m@, dst@, Some(r2@), AbstractParameters::static_params())
                    &&& r2.is_marshalable()
                },
                None =>
                    SingleDelivery::send_single_message(pre_self_@, post2_self_@, m@, dst@, None, AbstractParameters::static_params()),
            })
        }) ==> det_send_single_cmessage_equal(r1, r2, post1_self_, post2_self_),
{
    if g_m_is_GetRequest { assume(m is GetRequest); }
    if g_m_is_SetRequest { assume(m is SetRequest); }
    if g_m_is_Reply { assume(m is Reply); }
    if g_m_is_Redirect { assume(m is Redirect); }
    if g_m_is_Shard { assume(m is Shard); }
    if g_m_is_Delegate { assume(m is Delegate); }
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_send_single_cmessage_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_get_request__send_single_cmessage`:

```
  m is GetRequest
  r1 is Some
  r2 is Some
  !det_send_single_cmessage_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_set_request__send_single_cmessage`:

```
  m is GetRequest
  r1 is Some
  r2 is Some
  !det_send_single_cmessage_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 3** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_shard__send_single_cmessage`:

```
  m is GetRequest
  r1 is Some
  r2 is Some
  !det_send_single_cmessage_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 4** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__send_single_cmessage__send_single_cmessage`:

```
  m is GetRequest
  r1 is Some
  r2 is Some
  !det_send_single_cmessage_equal(r1, r2, post1_self_, post2_self_)
```

---

## #33 `set` (×1 instances) — Bucket E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl1_set.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl1_set__set/`
- **z3 cost**: n_rounds=8, n_schemas=3, verus_ms=405
- **Incompleteness 性质**: Wiring-blocked: StrictlyOrdered* 通过 `K: VerusClone` 间接卡 cascade(K 实例化时挂上 quarantined 类型)

### Source 函数(摘取)

```rust
fn set(&mut self, i: usize, k: K)
        requires old(self).valid(),
                 i < old(self)@.len(),
                 i > 0 ==> old(self)@[i as int - 1].cmp_spec(k).lt(),
                 i < old(self)@.len() - 1 ==> k.cmp_spec(old(self)@[i as int + 1]).lt(),
        ensures
            self.valid(),
            self@ == old(self)@.update(i as int, k),
    {
        self.v.set(i, k);

        assert forall |m, n| 0 <= m < n < self@.len() implies #[trigger](self@[m].cmp_spec(self@[n]).lt()) by {
            K::cmp_properties();
        }

        assert forall |i, j| 0 <= i < self@.len() && 0 <= j < self@.len() && i != j implies self@[i] != self@[j] by {
            K::cmp_properties();
        }

    }
```

### 生成的 equal_fn

```rust
spec fn det_set_equal<K: KeyTrait + VerusClone>(r1: (), r2: (), post1_self_: StrictlyOrderedVec<K>, post2_self_: StrictlyOrderedVec<K>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_set<K: KeyTrait + VerusClone>(g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_neq_tuple: bool, pre_self_: StrictlyOrderedVec<K>, i: usize, k: K, post1_self_: StrictlyOrderedVec<K>, r1: (), post2_self_: StrictlyOrderedVec<K>, r2: ())
    requires (pre_self_.valid()), (i < pre_self_@.len()), (i > 0 ==> pre_self_@[i as int - 1].cmp_spec(k).lt()), (i < pre_self_@.len() - 1 ==> k.cmp_spec(pre_self_@[i as int + 1]).lt()),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (post1_self_@ == pre_self_@.update(i as int, k))
            &&& (post2_self_.valid())
            &&& (post2_self_@ == pre_self_@.update(i as int, k))
        }) ==> det_set_equal(r1, r2, post1_self_, post2_self_),
{
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_neq_tuple { assume(!det_set_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl1_set__set`:

```
  i == 0
  !det_set_equal(r1, r2, post1_self_, post2_self_)
```

---

## #34 `set` (×3 instances) — Bucket E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__set.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl3__set__set/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=544
- **Incompleteness 性质**: Wiring-blocked: StrictlyOrdered* 通过 `K: VerusClone` 间接卡 cascade(K 实例化时挂上 quarantined 类型)

### Source 函数(摘取)

```rust
fn set(&mut self, k: K, v: ID)
        requires
            old(self).valid(),
        ensures
            self.valid(),
            self@ == old(self)@.insert(k, v),
            forall |lo, hi| self.gap(lo, hi) <==>
                            old(self).gap(lo, hi)
                        && !(lo.lt_spec(KeyIterator::new_spec(k))
                          && KeyIterator::new_spec(k).lt_spec(hi)),
    {
        match self.find_key(&k) {
            Some(i) => {
                self.vals.set(i, v);
                self.m = Ghost(self.m@.insert(k, v));
                proof {
                    assert_sets_equal!(self.m@.dom() == self.keys@.to_set());
                }
            },
            None => {
                let index = self.keys.insert(k.clone());
                self.vals.insert(index, v);
                self.m = Ghost(self.m@.insert(k, v));
            }
        }
        assert forall |lo, hi| self.gap(lo, hi) <==>
                            old(self).gap(lo, hi)
                        && !(lo.lt_spec(KeyIterator::new_spec(k))
                          && KeyIterator::new_spec(k).lt_spec(hi)) by {
            self.mind_the_gap();
            old(self).mind_the_gap();
            if old(self).gap(lo, hi) && !(lo.lt_spec(KeyIterator::new_spec(k)) && KeyIterator::new_spec(k).lt_spec(hi)) {
                assert forall |ki| lo.lt_spec(ki) && ki.lt_spec(hi) implies !(#[trigger] self@.contains_key(*ki.get())) by {
                    // TODO: This was the previous (flaky) proof:
                    // K::cmp_properties();
                    //
                    assert_by_contradiction!(!old(self)@.contains_key(*ki.get()), {
                        old(self).gap_means_empty(lo, hi, ki);
                    });
                };
                assert(self.gap(lo, hi));
            }

            if self.gap(lo, hi) {
                assert forall |ki| lo.lt_spec(ki) && ki.lt_spec(hi) implies !(#[trigger] old(self)@.contains_key(*ki.get())) by {
                    assert_by_contradiction!(!(old(self)@.contains_key(*ki.get())), {
                        assert(self@.contains_key(*ki.get()));
                        K::cmp_properties();
                    });
                };
                assert(old(self).gap(lo, hi));
                assert_by_contradiction!(!(lo.lt_spec(KeyIterator::new_spec(k)) && KeyIterator::new_spec(k).lt_spec(hi)), {
                    assert(self@.contains_key(k));
                    self.gap_means_empty(lo, 
/* … (truncated) … */
```

### 生成的 equal_fn

```rust
spec fn det_set_equal<K: KeyTrait + VerusClone>(r1: (), r2: (), post1_self_: StrictlyOrderedMap<K>, post2_self_: StrictlyOrderedMap<K>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_set<K: KeyTrait + VerusClone>(g_neq_tuple: bool, pre_self_: StrictlyOrderedMap<K>, k: K, v: ID, post1_self_: StrictlyOrderedMap<K>, r1: (), post2_self_: StrictlyOrderedMap<K>, r2: ())
    requires (pre_self_.valid()),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (post1_self_@ == pre_self_@.insert(k, v))
            &&& (forall |lo, hi| post1_self_.gap(lo, hi) <==>
                            pre_self_.gap(lo, hi)
                        && !(lo.lt_spec(KeyIterator::new_spec(k))
                          && KeyIterator::new_spec(k).lt_spec(hi)))
            &&& (post2_self_.valid())
            &&& (post2_self_@ == pre_self_@.insert(k, v))
            &&& (forall |lo, hi| post2_self_.gap(lo, hi) <==>
                            pre_self_.gap(lo, hi)
                        && !(lo.lt_spec(KeyIterator::new_spec(k))
                          && KeyIterator::new_spec(k).lt_spec(hi)))
        }) ==> det_set_equal(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_set_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__set__set`:

```
  !det_set_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__impl4__new__set`:

```
  !det_set_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 3** — `ironkv__verified__delegation_map_v__delegation_map_v__impl4__set__set`:

```
  !det_set_equal(r1, r2, post1_self_, post2_self_)
```

---

## #35 `set` (×2 instances) — Bucket E

- **Source**: `verusage/source-projects/ironkv/verified/host_impl_v/host_impl_v__impl2__host_model_next_delegate.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_delegate__set/`
- **z3 cost**: n_rounds=2, n_schemas=1, verus_ms=1038
- **Incompleteness 性质**: Wiring-blocked: StrictlyOrdered* 通过 `K: VerusClone` 间接卡 cascade(K 实例化时挂上 quarantined 类型)

### Source 函数(摘取)

```rust
pub fn set(&mut self, lo: &KeyIterator<K>, hi: &KeyIterator<K>, dst: &ID)
        requires
            old(self).valid(),
            dst@.valid_physical_address(),
        ensures
            self.valid(),
            forall |ki:KeyIterator<K>| #[trigger] KeyIterator::between(*lo, ki, *hi) ==> self@[*ki.get()] == dst@,
            forall |ki:KeyIterator<K>| !ki.is_end_spec() && !(#[trigger] KeyIterator::between(*lo, ki, *hi)) ==> self@[*ki.get()] == old(self)@[*ki.get()],
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_set_equal<K: KeyTrait + VerusClone>(r1: (), r2: (), post1_self_: DelegationMap<K>, post2_self_: DelegationMap<K>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_set<K: KeyTrait + VerusClone>(g_neq_tuple: bool, pre_self_: DelegationMap<K>, lo: KeyIterator<K>, hi: KeyIterator<K>, dst: ID, post1_self_: DelegationMap<K>, r1: (), post2_self_: DelegationMap<K>, r2: ())
    requires (pre_self_.valid()), (dst@.valid_physical_address()),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (forall |ki:KeyIterator<K>| #[trigger] KeyIterator::between(lo, ki, hi) ==> post1_self_@[*ki.get()] == dst@)
            &&& (forall |ki:KeyIterator<K>| !ki.is_end_spec() && !(#[trigger] KeyIterator::between(lo, ki, hi)) ==> post1_self_@[*ki.get()] == pre_self_@[*ki.get()])
            &&& (post2_self_.valid())
            &&& (forall |ki:KeyIterator<K>| #[trigger] KeyIterator::between(lo, ki, hi) ==> post2_self_@[*ki.get()] == dst@)
            &&& (forall |ki:KeyIterator<K>| !ki.is_end_spec() && !(#[trigger] KeyIterator::between(lo, ki, hi)) ==> post2_self_@[*ki.get()] == pre_self_@[*ki.get()])
        }) ==> det_set_equal(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_set_equal(r1, r2, post1_self_, post2_self_)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_delegate__set`:

```
  !det_set_equal(r1, r2, post1_self_, post2_self_)
```

**Instance 2** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_model_next_shard__set`:

```
  !det_set_equal(r1, r2, post1_self_, post2_self_)
```

---

## #36 `vec_erase` (×2 instances) — Bucket A-E

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__erase.rs`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl3__erase__vec_erase/`
- **z3 cost**: n_rounds=14, n_schemas=5, verus_ms=825
- **Incompleteness 性质**: Wiring-blocked: Vec 元素类型不在 view registry 里

### Source 函数(摘取)

```rust
pub fn vec_erase<A>(v: &mut Vec<A>, start: usize, end: usize)
    requires
        start <= end <= old(v).len(),
    ensures
        true,
        v@ == old(v)@.subrange(0, start as int) + old(v)@.subrange(end as int, old(v)@.len() as int),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_vec_erase_equal<A>(r1: (), r2: (), post1_v: Vec<A>, post2_v: Vec<A>) -> bool {
    (r1 == r2)
    && (post1_v == post2_v)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_vec_erase<A>(g_start_eq: bool, k_start_eq: int, g_start_rng: bool, k_start_rng_lo: int, k_start_rng_hi: int, g_end_eq: bool, k_end_eq: int, g_end_rng: bool, k_end_rng_lo: int, k_end_rng_hi: int, g_neq_tuple: bool, pre_v: Vec<A>, start: usize, end: usize, post1_v: Vec<A>, r1: (), post2_v: Vec<A>, r2: ())
    requires (start <= end <= pre_v.len()),
    ensures
        ({
            &&& (true)
            &&& (post1_v@ == pre_v@.subrange(0, start as int) + pre_v@.subrange(end as int, pre_v@.len() as int))
            &&& (true)
            &&& (post2_v@ == pre_v@.subrange(0, start as int) + pre_v@.subrange(end as int, pre_v@.len() as int))
        }) ==> det_vec_erase_equal(r1, r2, post1_v, post2_v),
{
    if g_start_eq { assume(start as int == k_start_eq); }
    if g_start_rng { assume(start as int >= k_start_rng_lo && start as int <= k_start_rng_hi); }
    if g_end_eq { assume(end as int == k_end_eq); }
    if g_end_rng { assume(end as int >= k_end_rng_lo && end as int <= k_end_rng_hi); }
    if g_neq_tuple { assume(!det_vec_erase_equal(r1, r2, post1_v, post2_v)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__erase__vec_erase`:

```
  start == 0
  end == 0
  !det_vec_erase_equal(r1, r2, post1_v, post2_v)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__vec_erase__vec_erase`:

```
  start == 0
  end == 0
  !det_vec_erase_equal(r1, r2, post1_v, post2_v)
```

---

