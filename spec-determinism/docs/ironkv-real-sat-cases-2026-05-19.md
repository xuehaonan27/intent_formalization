# ironkv REAL_SAT (真·非确定性)case集

> 5 个 unique spec 函数 / 9 个 witness instances。
> z3 找到的 witness 不是 incompleteness,而是 spec **本身**就允许的非确定行为。
> 数据集: `spec-determinism/results-verusage-viewreg/ironkv/full_run.json` (May 12 viewreg 全量跑)
>
> **注**: 原 #5 `keys` 已移至 `ironkv-equal-fn-too-strict-cases-2026-05-19.md` —— spec 在 set 抽象上是确定的,non-det 来自 codegen 的 equal_fn 过严,不属于 spec 层 REAL_SAT。`retransmit_un_acked_packets` / `_for_dst`(原 #3/#4)很可能也是同类,留在本文档待二次审。

## 总览

| # | 函数 | instance 数 | 非确定性来源 |
|---|------|-------------|--------------|
| 1 | `keys_in_index_range_agree` | ×2 | spec 只在 `!ret.0` 分支约束 `ret.1`,`ret.0==true` 时 `ret.1` 自由 |
| 2 | `values_agree` | ×2 | 同上(`keys_in_index_range_agree` 内部代理) |
| 3 | `retransmit_un_acked_packets` | ×2 | spec 用 `set` 而非 `seq` 等价,Vec 顺序自由(候选迁移到 equal_fn-too-strict) |
| 4 | `retransmit_un_acked_packets_for_dst` | ×2 | 同上(同一循环体内分支)(候选迁移到 equal_fn-too-strict) |
| 5 | `sht_demarshall_data_method` | ×1 | `InvalidMessage` 分支 spec 完全静默 |

## 修复优先级建议

- **高(spec bug,容易补)**: `keys_in_index_range_agree` / `values_agree` —— 漏掉了 `ret.0==true` 分支的 `ret.1` 约束,几行 ensures 就能修。
- **中(spec 设计选择)**: `sht_demarshall_data_method` —— `InvalidMessage` 应不应被规范化看实际需求。
- **待复审(很可能是 equal_fn-too-strict)**: `retransmit_un_acked_packets` / `_for_dst` —— spec 用 set 等价是合理设计,真正的修复在 pipeline 而非 spec。

---

## #1 `keys_in_index_range_agree` (×2 instance)

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__keys_in_index_range_agree.rs`
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__keys_in_index_range_agree/`
- **z3 cost (sample)**: n_rounds=14, n_schemas=5, verus_ms=448

### 案件解释

**为什么是 REAL_SAT**: 返回类型 `(bool, bool)`。spec 只把 `ret.1` 约束在 `!ret.0` 分支里:
```
ret.0 == forall |i| lo <= i <= hi ==> self@[self.keys@[i]]@ == v@,
!ret.0 ==> (ret.1 == (... && ...))
```
当 `ret.0 == true` 时,**`ret.1` 完全无约束** —— 两个合法实现可以分别返回 `(true, true)` 和 `(true, false)`,都满足 spec。z3 找到的 witness 就是这个分支:`ret.0=true ∧ ret.1` 两个 instance 取不同值。

**修复方向**: 让 spec 在 `ret.0==true` 时也约束 `ret.1`(比如 `ret.0 ==> ret.1 == true` 或 `ret.1 == ret.0`)。

### Source 函数

```rust
fn keys_in_index_range_agree(&self, lo: usize, hi: usize, v: &ID) -> (ret:(bool, bool))
        requires 
            self.valid(),
            0 <= lo <= hi < self.keys@.len(),
        ensures 
            ret.0 == forall |i| #![auto] lo <= i <= hi ==> self@[self.keys@[i]]@ == v@,
            !ret.0 ==> (ret.1 == (self@[self.keys@[hi as int]]@ != v@ && (forall |i| #![auto] lo <= i < hi ==> self@[self.keys@[i]]@ == v@))),
    {
        assert(self.valid());
        assert(forall |i| lo <= i <= hi ==> self@[self.keys@[i]] == self.vals@[i]);
        let (agree, almost) = self.values_agree(lo, hi, v);
        
        (agree, almost)
    }
```

### 生成的 equal_fn

```rust
spec fn det_keys_in_index_range_agree_equal(r1: (bool, bool), r2: (bool, bool)) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_keys_in_index_range_agree<K: KeyTrait + VerusClone>(g_lo_eq: bool, k_lo_eq: int, g_lo_rng: bool, k_lo_rng_lo: int, k_lo_rng_hi: int, g_hi_eq: bool, k_hi_eq: int, g_hi_rng: bool, k_hi_rng_lo: int, k_hi_rng_hi: int, g_neq_tuple: bool, self_: StrictlyOrderedMap<K>, lo: usize, hi: usize, v: ID, r1: (bool, bool), r2: (bool, bool))
    requires (self_.valid()), (0 <= lo <= hi < self_.keys@.len()),
    ensures
        ({
            &&& (r1.0 == forall |i| #![auto] lo <= i <= hi ==> self_@[self_.keys@[i]]@ == v@)
            &&& (!r1.0 ==> (r1.1 == (self_@[self_.keys@[hi as int]]@ != v@ && (forall |i| #![auto] lo <= i < hi ==> self_@[self_.keys@[i]]@ == v@))))
            &&& (r2.0 == forall |i| #![auto] lo <= i <= hi ==> self_@[self_.keys@[i]]@ == v@)
            &&& (!r2.0 ==> (r2.1 == (self_@[self_.keys@[hi as int]]@ != v@ && (forall |i| #![auto] lo <= i < hi ==> self_@[self_.keys@[i]]@ == v@))))
        }) ==> det_keys_in_index_range_agree_equal(r1, r2),
{
    if g_lo_eq { assume(lo as int == k_lo_eq); }
    if g_lo_rng { assume(lo as int >= k_lo_rng_lo && lo as int <= k_lo_rng_hi); }
    if g_hi_eq { assume(hi as int == k_hi_eq); }
    if g_hi_rng { assume(hi as int >= k_hi_rng_lo && hi as int <= k_hi_rng_hi); }
    if g_neq_tuple { assume(!det_keys_in_index_range_agree_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__keys_in_index_range_agree`:

```
  lo == 0
  hi == 0
  !det_keys_in_index_range_agree_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__impl4__range_consistent_impl__keys_in_index_range_agree`:

```
  lo == 0
  hi == 0
  !det_keys_in_index_range_agree_equal(r1, r2)
```

### 手工构造的具体 witness

> z3 的 witness 只列出 input schema(`lo`/`hi`)的 assume,没给出 `self_`/`v`/`r1`/`r2` 的具体值 —— 当前 witness 提取器的限制(只 dump 被激活的 guard,不展开 struct/tuple 字段的 z3 model)。这里是人工补全的可读版本。

**Concrete witness:**

| 参数 | 值 |
|------|---|
| `lo` | `0usize` |
| `hi` | `0usize` |
| `self_.keys@` | `seq![K::zero_spec()]` (单 key) |
| `self_.vals@` | `seq![EndPoint { id: vec![1u8] }]` |
| `self_.m@`(spec map) | `{ K::zero_spec() ↦ AbstractEndPoint(seq![1u8]) }` |
| `v: &ID` | `&EndPoint { id: vec![1u8] }` (满足 `v@ == self_@[k0]@`) |

**两个合法实现的输出:**

```text
Impl A: r1 = (true, true)
Impl B: r2 = (true, false)
```

**两条 ensures 子句逐条检查:**

- `r1.0 == forall i. 0<=i<=0 ==> self_@[keys@[i]]@ == v@`:`i` 只能取 `0`,`self_@[k0]@ == v@` ⇔ `[1u8] == [1u8]` = true ⇒ `r1.0 = true` ✓(对 `r2` 同理)。
- `!r1.0 ==> (r1.1 == ...)`:`r1.0 = true` ⇒ 前件 false ⇒ **vacuously true**(`r1.1` 完全自由)。
- `!r2.0 ==> (r2.1 == ...)`:同上(`r2.1` 完全自由)。

**equality 检查:**

```text
det_keys_in_index_range_agree_equal(r1, r2) := (r1 == r2)
  = ((true, true) == (true, false))
  = false                                       ← witness 成立
```

**一行 spec 修复:**

```rust
ensures
    ret.0 == forall |i| lo <= i <= hi ==> self@[self.keys@[i]]@ == v@,
+   ret.0 ==> !ret.1,                           // 或 ret.1 == ret.0,看 caller 期望
    !ret.0 ==> (ret.1 == (...)),
```

---

## #2 `values_agree` (×2 instance)

- **Source**: `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl3__values_agree.rs`
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__values_agree/`
- **z3 cost (sample)**: n_rounds=14, n_schemas=5, verus_ms=436

### 案件解释

**为什么是 REAL_SAT**: 与 `keys_in_index_range_agree` 是同一个模式 —— 返回 `(bool, bool)`,只在 `!ret.0` 分支里约束 `ret.1`:
```
ret.0 == forall |i| lo <= i <= hi ==> self.vals@[i]@ == v@,
!ret.0 ==> (ret.1 == (self.vals@[hi as int]@ != v@ && ...))
```
`ret.0 == true` 时 `ret.1` 完全自由 → 真正的 non-determinism。`keys_in_index_range_agree` 在内部直接调用 `values_agree` 并把元组转手返回,所以两边的 REAL_SAT 是同源的。

**修复方向**: 同上 —— 补 `ret.0 ==> ret.1 == ???` 的 spec 约束。

### Source 函数

```rust
fn values_agree(&self, lo: usize, hi: usize, v: &ID) -> (ret:(bool, bool))
        requires 
            self.valid(),
            0 <= lo <= hi < self.keys@.len(),
        ensures 
            ret.0 == forall |i| #![auto] lo <= i <= hi ==> self.vals@[i]@ == v@,
            !ret.0 ==> (ret.1 == (self.vals@[hi as int]@ != v@ && forall |i| #![auto] lo <= i < hi ==> self.vals@[i]@ == v@)),
    {
        let mut i = lo;
        while i <= hi
            invariant 
                lo <= i,
                self.keys@.len() <= usize::MAX,
                hi < self.keys@.len() as usize == self.vals@.len(),
                forall |j| #![auto] lo <= j < i ==> self.vals@[j]@ == v@,
            decreases
                self.keys@.len() - i
        {
            let eq = do_end_points_match(&self.vals[i], v);
            if  !eq {
                if i == hi {
                    return (false, true);
                } else {
                    return (false, false);
                }
            } else {
                proof {
                    //K::cmp_properties();
                }
            }
            i = i + 1;
        }
        (true, true)
    }
```

### 生成的 equal_fn

```rust
spec fn det_values_agree_equal(r1: (bool, bool), r2: (bool, bool)) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_values_agree<K: KeyTrait + VerusClone>(g_lo_eq: bool, k_lo_eq: int, g_lo_rng: bool, k_lo_rng_lo: int, k_lo_rng_hi: int, g_hi_eq: bool, k_hi_eq: int, g_hi_rng: bool, k_hi_rng_lo: int, k_hi_rng_hi: int, g_neq_tuple: bool, self_: StrictlyOrderedMap<K>, lo: usize, hi: usize, v: ID, r1: (bool, bool), r2: (bool, bool))
    requires (self_.valid()), (0 <= lo <= hi < self_.keys@.len()),
    ensures
        ({
            &&& (r1.0 == forall |i| #![auto] lo <= i <= hi ==> self_.vals@[i]@ == v@)
            &&& (!r1.0 ==> (r1.1 == (self_.vals@[hi as int]@ != v@ && forall |i| #![auto] lo <= i < hi ==> self_.vals@[i]@ == v@)))
            &&& (r2.0 == forall |i| #![auto] lo <= i <= hi ==> self_.vals@[i]@ == v@)
            &&& (!r2.0 ==> (r2.1 == (self_.vals@[hi as int]@ != v@ && forall |i| #![auto] lo <= i < hi ==> self_.vals@[i]@ == v@)))
        }) ==> det_values_agree_equal(r1, r2),
{
    if g_lo_eq { assume(lo as int == k_lo_eq); }
    if g_lo_rng { assume(lo as int >= k_lo_rng_lo && lo as int <= k_lo_rng_hi); }
    if g_hi_eq { assume(hi as int == k_hi_eq); }
    if g_hi_rng { assume(hi as int >= k_hi_rng_lo && hi as int <= k_hi_rng_hi); }
    if g_neq_tuple { assume(!det_values_agree_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__keys_in_index_range_agree__values_agree`:

```
  lo == 0
  hi == 0
  !det_values_agree_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__delegation_map_v__delegation_map_v__impl3__values_agree__values_agree`:

```
  lo == 0
  hi == 0
  !det_values_agree_equal(r1, r2)
```

### 手工构造的具体 witness

> 与 case #1 同源 —— `keys_in_index_range_agree` 函数体内 `let (agree, almost) = self.values_agree(lo, hi, v); (agree, almost)` 直接把这个 `(bool, bool)` 元组转手返回。

**Concrete witness:**

| 参数 | 值 |
|------|---|
| `lo` | `0usize` |
| `hi` | `0usize` |
| `self_.vals@` | `seq![EndPoint { id: vec![1u8] }]` (长度 1) |
| `self_.keys@` | `seq![K::zero_spec()]` (长度 1,与 `vals` 等长以满足 `valid()`) |
| `v: &ID` | `&EndPoint { id: vec![1u8] }` (满足 `v@ == self_.vals@[0]@`) |

**两个合法实现:**

```text
Impl A: r1 = (true, true)
Impl B: r2 = (true, false)
```

**ensures 检查:**

- `r1.0 == forall i. 0<=i<=0 ==> self_.vals@[i]@ == v@`:`i=0` 时 `EndPoint{id:[1]}@ == EndPoint{id:[1]}@` = true ⇒ `r1.0 = true` ✓(`r2.0` 同理)。
- `!r1.0 ==> ...`:`r1.0 = true` ⇒ vacuously true(`r1.1` 自由)。
- `!r2.0 ==> ...`:同上(`r2.1` 自由)。

**equality:**

```text
(true, true) == (true, false)  →  false  →  witness 成立
```

**注意**: 修 `values_agree` 的 spec 等价于一并修 `keys_in_index_range_agree`(它把 `values_agree` 的输出原样吐出来),不用两边都改。

---

## #3 `retransmit_un_acked_packets` (×2 instance)

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__retransmit_un_acked_packets.rs`
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__host_impl_v__host_impl_v__impl2__host_noreceive_noclock_next__retransmit_un_acked_packets/`
- **z3 cost (sample)**: n_rounds=2, n_schemas=1, verus_ms=1346

### 案件解释

**为什么是 REAL_SAT**: 返回 `Vec<CPacket>`,spec 只约束 `packets@` 经 `.map_values(...).to_set()` 后等于一个抽象 set:
```
abstractify_seq_of_cpackets_to_set_of_sht_packets(packets@) == self@.un_acked_messages(src@),
self@.un_acked_messages(src@) == packets@.map_values(|p| p@).to_set(),
```
spec 用的是 **set** 而不是 **seq** —— 排列顺序完全自由。两个不同顺序的 `Vec<CPacket>`(或两次循环按 hash 不同顺序 traverse 出来的结果)都满足 spec,但 equal_fn 走的是 `Vec` 的 structural `==`(因为 `CPacket` quarantined),自然 SAT。
即使 wiring 把 `Vec<CPacket>` 改成 view-equal,只要 view-equal 还是 seq-level(`s1 =~= s2`),依然 SAT —— 因为 spec 本身只到 set 级别。

**修复方向**: 这条 spec 在算法层就是不确定的;真要给它确定性,得给 ack_state 引入显式的 ordering(比如按 seq_no 排序),并在 ensures 里加 `packets@.map_values(p@) == ack_state.un_acked@.map_values(...)`(seq 等价而非 set 等价)。

### Source 函数

```rust
pub fn retransmit_un_acked_packets_for_dst(&self, src: &EndPoint, dst: &EndPoint, packets: &mut Vec<CPacket>)
    requires
        self.valid(),
        src.abstractable(),
        outbound_packet_seq_is_valid(old(packets)@),
        outbound_packet_seq_has_correct_srcs(old(packets)@, src@),
        self.send_state@.contains_key(dst@),
        Self::packets_are_valid_messages(old(packets)@),
    ensures
        packets@.map_values(|p: CPacket| p@).to_set() ==
            old(packets)@.map_values(|p: CPacket| p@).to_set() + self@.un_acked_messages_for_dest(src@, dst@),
        outbound_packet_seq_is_valid(packets@),
        outbound_packet_seq_has_correct_srcs(packets@, src@),
        Self::packets_are_valid_messages(packets@),
	{
		unimplemented!()
	}
```

### 生成的 equal_fn

```rust
spec fn det_retransmit_un_acked_packets_equal(r1: Vec<CPacket>, r2: Vec<CPacket>) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_retransmit_un_acked_packets(g_neq_tuple: bool, self_: CSingleDelivery, src: EndPoint, r1: Vec<CPacket>, r2: Vec<CPacket>)
    requires (self_.valid()), (src.abstractable()),
    ensures
        ({
            &&& (abstractify_seq_of_cpackets_to_set_of_sht_packets(r1@) == self_@.un_acked_messages(src@))
            &&& (outbound_packet_seq_is_valid(r1@))
            &&& (outbound_packet_seq_has_correct_srcs(r1@, src@))
            &&& (self_@.un_acked_messages(src@) == r1@.map_values(|p: CPacket| p@).to_set())
            &&& (CSingleDelivery::packets_are_valid_messages(r1@))
            &&& (abstractify_seq_of_cpackets_to_set_of_sht_packets(r2@) == self_@.un_acked_messages(src@))
            &&& (outbound_packet_seq_is_valid(r2@))
            &&& (outbound_packet_seq_has_correct_srcs(r2@, src@))
            &&& (self_@.un_acked_messages(src@) == r2@.map_values(|p: CPacket| p@).to_set())
            &&& (CSingleDelivery::packets_are_valid_messages(r2@))
        }) ==> det_retransmit_un_acked_packets_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_retransmit_un_acked_packets_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__host_impl_v__host_impl_v__impl2__host_noreceive_noclock_next__retransmit_un_acked_packets`:

```
  !det_retransmit_un_acked_packets_equal(r1, r2)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets__retransmit_un_acked_packets`:

```
  !det_retransmit_un_acked_packets_equal(r1, r2)
```

---

## #4 `retransmit_un_acked_packets_for_dst` (×2 instance)

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__retransmit_un_acked_packets_for_dst.rs`
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets__retransmit_un_acked_packets_for_dst/`
- **z3 cost (sample)**: n_rounds=2, n_schemas=1, verus_ms=899

### 案件解释

**为什么是 REAL_SAT**: in-place 累积版,与 `retransmit_un_acked_packets` 同源:
```
packets@.map_values(|p| p@).to_set() ==
    old(packets)@.map_values(|p| p@).to_set() + self@.un_acked_messages_for_dest(src@, dst@),
```
依然是 **set 等价**,seq 顺序自由 → 两个 instance 可以按不同顺序把同一组 packet 推到 `packets` 后端,equal_fn 见到的 `Vec<CPacket>` 结构不同 → SAT。注意这个函数是 `retransmit_un_acked_packets` 的循环体内调用,所以两个 case 的 witness 形态完全平行。

**修复方向**: 同上 —— 提升 spec 到 seq 等价(并把 set 等价作为后续 corollary)。

### Source 函数

```rust
pub fn retransmit_un_acked_packets_for_dst(&self, src: &EndPoint, dst: &EndPoint, packets: &mut Vec<CPacket>)
    requires
        self.valid(),
        src.abstractable(),
        outbound_packet_seq_is_valid(old(packets)@),
        outbound_packet_seq_has_correct_srcs(old(packets)@, src@),
        self.send_state@.contains_key(dst@),
        Self::packets_are_valid_messages(old(packets)@),
    ensures
        packets@.map_values(|p: CPacket| p@).to_set() ==
            old(packets)@.map_values(|p: CPacket| p@).to_set() + self@.un_acked_messages_for_dest(src@, dst@),
        outbound_packet_seq_is_valid(packets@),
        outbound_packet_seq_has_correct_srcs(packets@, src@),
        Self::packets_are_valid_messages(packets@),
    {
        proof {
            assert_sets_equal!(
                packets@.map_values(|p: CPacket| p@).to_set(),
                    old(packets)@.map_values(|p: CPacket| p@).to_set() + self@.un_acked_messages_for_dest_up_to(src@, dst@, 0 as nat),
            );
        }

        match self.send_state.epmap.get(dst) {
            Some(ack_state) => {
                let mut i=0;

                while i < ack_state.un_acked.len()
                  invariant
                    0 <= i <= ack_state.un_acked.len(),
                    self.valid(),   // Everybody hates having to carry everything through here. :v(
                    src.abstractable(),
                    outbound_packet_seq_is_valid(packets@),
                    outbound_packet_seq_has_correct_srcs(packets@, src@),
                    self.send_state@.contains_key(dst@),
                    ack_state == self.send_state.epmap[dst],
                    packets@.map_values(|p: CPacket| p@).to_set() ==
                        old(packets)@.map_values(|p: CPacket| p@).to_set() + self@.un_acked_messages_for_dest_up_to(src@, dst@, i as nat),
                    Self::packets_are_valid_messages(packets@),
                  decreases
                    ack_state.un_acked.len() - i
                {
                    let ghost packets0_view = packets@;

                    assert( CAckState::un_acked_valid(&ack_state.un_acked@[i as int]) );    // trigger

                    let sm = &ack_state.un_acked[i];
                    let dst = match sm {
                        CSingleMessage::Message{dst, .. } => dst,
                        _ => { proof {assert(false); } unreached() },
                    };

                    let cpacket = CPacket{dst: dst.clone_up_to_view(), src: src.clone_up_to_view(), msg: sm.clone_up_to_view()};
                    packets.push(cpacket);

                    i = i + 1;

                    proof{
                        same_view_same_marshalable( &cpacket.msg, &sm );

                        lemma_seq_push_to_set(packets0_view, cpacket);

                        assert_seqs_equal!(packets@.map_values(|p: CPacket| p@),
                                           packets0_view.map_values(|p: CPacket| p@).push(cpacket@));

                        lemma_seq_push_to_set(packets0_view.map_values(|p: CPacket| p@), cpacket@);
                        self.un_acked_messages_extend(src@, dst@, (i-1) as nat);

                        assert_sets_equal!(
                            packets@.map_values(|p: CPacket| p@).to_set(),
                            old(packets)@.map_values(|p: CPacket| p@).to_set() + self@.un_acked_messages_for_dest_up_to(src@, dst@, i as nat)
                        );
                    }
            
/* … truncated … */
```

### 生成的 equal_fn

```rust
spec fn det_retransmit_un_acked_packets_for_dst_equal(r1: (), r2: (), post1_packets: Vec<CPacket>, post2_packets: Vec<CPacket>) -> bool {
    (r1 == r2)
    && (post1_packets == post2_packets)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_retransmit_un_acked_packets_for_dst(g_neq_tuple: bool, self_: CSingleDelivery, src: EndPoint, dst: EndPoint, pre_packets: Vec<CPacket>, post1_packets: Vec<CPacket>, r1: (), post2_packets: Vec<CPacket>, r2: ())
    requires (self_.valid()), (src.abstractable()), (outbound_packet_seq_is_valid(pre_packets@)), (outbound_packet_seq_has_correct_srcs(pre_packets@, src@)), (self_.send_state@.contains_key(dst@)), (CSingleDelivery::packets_are_valid_messages(pre_packets@)),
    ensures
        ({
            &&& (post1_packets@.map_values(|p: CPacket| p@).to_set() ==
            pre_packets@.map_values(|p: CPacket| p@).to_set() + self_@.un_acked_messages_for_dest(src@, dst@))
            &&& (outbound_packet_seq_is_valid(post1_packets@))
            &&& (outbound_packet_seq_has_correct_srcs(post1_packets@, src@))
            &&& (CSingleDelivery::packets_are_valid_messages(post1_packets@))
            &&& (post2_packets@.map_values(|p: CPacket| p@).to_set() ==
            pre_packets@.map_values(|p: CPacket| p@).to_set() + self_@.un_acked_messages_for_dest(src@, dst@))
            &&& (outbound_packet_seq_is_valid(post2_packets@))
            &&& (outbound_packet_seq_has_correct_srcs(post2_packets@, src@))
            &&& (CSingleDelivery::packets_are_valid_messages(post2_packets@))
        }) ==> det_retransmit_un_acked_packets_for_dst_equal(r1, r2, post1_packets, post2_packets),
{
    if g_neq_tuple { assume(!det_retransmit_un_acked_packets_for_dst_equal(r1, r2, post1_packets, post2_packets)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets__retransmit_un_acked_packets_for_dst`:

```
  !det_retransmit_un_acked_packets_for_dst_equal(r1, r2, post1_packets, post2_packets)
```

**Instance 2** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets_for_dst__retransmit_un_acked_packets_for_dst`:

```
  !det_retransmit_un_acked_packets_for_dst_equal(r1, r2, post1_packets, post2_packets)
```

---

> **case `keys`(原 #5)已移至 `ironkv-equal-fn-too-strict-cases-2026-05-19.md`**

---

## #5 `sht_demarshall_data_method` (×1 instance)

- **Source**: `verusage/source-projects/ironkv/verified/net_sht_v/net_sht_v__receive_with_demarshal.rs`
- **Artifact (sample)**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__net_sht_v__net_sht_v__receive_with_demarshal__sht_demarshall_data_method/`
- **z3 cost (sample)**: n_rounds=2, n_schemas=1, verus_ms=713

### 案件解释

**为什么是 REAL_SAT**: trusted(`unimplemented!()`),返回 `CSingleMessage`。ensures 用的是含蓄式 `!(out is InvalidMessage) ==> ...`:
```
ensures
    !(out is InvalidMessage) ==> {
        &&& out.is_marshalable()
        &&& out@ == sht_demarshal_data(buffer@)@
        &&& out.abstractable()
    }
```
当 demarshal **失败**时(`out is InvalidMessage`),spec **完全没约束** `out` 的具体内容 —— InvalidMessage 变体里如果有 payload 字段(seq_no、文本等),两次 demarshal 失败可以返回不同的 InvalidMessage 实例,equal_fn 上看到的就是结构不等 → SAT。

即使 demarshal **成功**,spec 也只锁 `out@`(投影到 `SingleMessage` abstract),而 `CSingleMessage` 的具体 byte-level layout(payload、Vec<u8> 顺序、CMessage 包装等)在 quarantined wiring 下 fallback 到 structural `==`,也允许不等。

**修复方向**:
- 给 `InvalidMessage` 变体规定唯一形态(比如要求它的 payload 必须等于 input buffer 的某个 prefix,或者强制 `InvalidMessage{}` 不带 payload);
- 把 `out` 的概念性等价从 `out@` 提升到 `out`(结构等价) —— 但这要求 quarantine 解除,本质上和 wiring-blocked 是耦合的。

### Source 函数

```rust
pub fn sht_demarshall_data_method(buffer: &Vec<u8>) -> (out: CSingleMessage)
ensures
    !(out is InvalidMessage) ==> {
        &&& out.is_marshalable()
        &&& out@ == sht_demarshal_data(buffer@)@
        &&& out.abstractable()
    }
```

### 生成的 equal_fn

```rust
spec fn det_sht_demarshall_data_method_equal(r1: CSingleMessage, r2: CSingleMessage) -> bool {
    (r1 == r2)
}
```

### 生成的 det fn (synthetic proof obligation)

```rust
proof fn det_sht_demarshall_data_method(g_neq_tuple: bool, buffer: Vec<u8>, r1: CSingleMessage, r2: CSingleMessage)
    ensures
        ({
            &&& (!(r1 is InvalidMessage) ==> {
        &&& r1.is_marshalable()
        &&& r1@ == sht_demarshal_data(buffer@)@
        &&& r1.abstractable()
    })
            &&& (!(r2 is InvalidMessage) ==> {
        &&& r2.is_marshalable()
        &&& r2@ == sht_demarshal_data(buffer@)@
        &&& r2.abstractable()
    })
        }) ==> det_sht_demarshall_data_method_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_sht_demarshall_data_method_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__net_sht_v__net_sht_v__receive_with_demarshal__sht_demarshall_data_method`:

```
  !det_sht_demarshall_data_method_equal(r1, r2)
```

---
