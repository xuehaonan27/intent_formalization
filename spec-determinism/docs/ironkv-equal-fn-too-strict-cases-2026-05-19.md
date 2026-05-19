# ironkv equal_fn 口径过严 case 集

> **不是 REAL_SAT,也不是 incompleteness**:spec 在它自己选定的抽象层上是确定的(canonical equivalence 就是 `set`/`multiset` 上的等);但 determinism pipeline codegen 出来的 equal_fn 走的是 `Vec` / 结构 `==`,口径比 spec 更严,于是 z3 找到 witness。
>
> 修复方向不在 spec,而在 **determinism pipeline 的 equal_fn 选型**:让 equal_fn 接入 spec ensures 里现成的等价关系。
>
> 数据集: `spec-determinism/results-verusage-viewreg/ironkv/full_run.json` (May 12 viewreg 全量跑)

## 核心区分

| 分类 | spec 本身 | equal_fn | 修复位置 |
|------|---------|---------|---------|
| Incompleteness | 确定 | 正确 | z3 / proof helper |
| **本文档(equal_fn 口径过严)** | 确定(用 set/multiset 抽象) | 过严(用结构 `==`) | pipeline equal_fn 选型 |
| REAL_SAT(spec bug) | 漏写约束,真有非确定 | 任意 | 补 spec ensures |

判别准则:把 spec 里 ensures 等号右侧的抽象层当 equivalence 套上去,如果 z3 立刻能证 ≡,就属于本文档类别。

---

## #1 `keys` (×1 instance)

- **Source**: `verusage/source-projects/ironkv/verified/single_delivery_model_v/single_delivery_model_v__impl2__retransmit_un_acked_packets.rs:677`
- **Artifact**: `spec-determinism/results-verusage-viewreg/ironkv/artifacts/ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets__keys/`
- **z3 cost (sample)**: n_rounds=2, n_schemas=1, verus_ms=869

### 案件解释

spec:

```rust
pub fn keys(&self) -> (out: Vec<EndPoint>)
    ensures out@.map_values(|e: EndPoint| e@).to_set() == self@.dom()
```

`CKeyHashMap::view()` 返回 `Map<AbstractKey, Seq<u8>>`,所以 `self@.dom() : Set<AbstractEndPoint>`。

**为什么 spec 没问题**:`keys()` 这个函数在概念上就是"返回 map 的 domain"。Map 的 dom 天然是 `Set`,**`set 等价 ≡ map 等价(在 dom 这一层)**。
- 如果硬要在 spec 上加 ordering,例如 `out@ == self@.dom().to_seq_in_canonical_order()`,这要求 HashMap 实现暴露内部 hash 顺序或重新做排序 —— **既给实现强加无谓的约束,又破坏 hashmap 抽象**。
- 上层调用者 `retransmit_un_acked_packets` 也是用 `dests@.map_values(...).to_set()` 在 invariant 里使用,从不依赖顺序。

所以"输出 `Vec` 顺序自由 + `EndPoint.id: Vec<u8>` byte 表示自由"这两层维度,在 spec 的视角下**根本不在 equivalence 里**。这条 spec 已经是 strongest possible。

### 为什么 pipeline 仍报 SAT

codegen 看的是返回**类型** `Vec<EndPoint>`,不读 ensures。`EndPoint` 在 ironkv 是 quarantined(M1 cascade),`Vec<EndPoint>` 没法用 view-equal 替换,fallback 到结构 `==`:

```rust
spec fn det_keys_equal(r1: Vec<EndPoint>, r2: Vec<EndPoint>) -> bool {
    (r1 == r2)
}
```

注意:**即使 EndPoint 解除 quarantine,wiring 走到 view-equal,equal_fn 也只是变成 `r1@ =~= r2@`(seq 级)** —— 还是过严,顺序自由依然过不去。真正贴合 spec 的 equal_fn 应该是:

```rust
spec fn det_keys_equal(r1: Vec<EndPoint>, r2: Vec<EndPoint>) -> bool {
    r1@.map_values(|e: EndPoint| e@).to_set() == r2@.map_values(|e: EndPoint| e@).to_set()
}
```

把它喂给 z3,从 spec 的 ensures 两次实例化即可立刻 unsat(`r1.set == self@.dom() ∧ r2.set == self@.dom() ⇒ r1.set == r2.set`)。

### Source 函数

```rust
pub fn keys(&self) -> (out: Vec<EndPoint>)
    ensures out@.map_values(|e: EndPoint| e@).to_set() == self@.dom()
{
    unimplemented!()
}
```

### 当前生成的 equal_fn(过严)

```rust
spec fn det_keys_equal(r1: Vec<EndPoint>, r2: Vec<EndPoint>) -> bool {
    (r1 == r2)
}
```

### 当前生成的 det fn

```rust
proof fn det_keys<V>(g_neq_tuple: bool, self_: HashMap<V>, r1: Vec<EndPoint>, r2: Vec<EndPoint>)
    ensures
        ({
            &&& (r1@.map_values(|e: EndPoint| e@).to_set() == self_@.dom())
            &&& (r2@.map_values(|e: EndPoint| e@).to_set() == self_@.dom())
        }) ==> det_keys_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_keys_equal(r1, r2)); }
}
```

### z3 找到的 witness

**Instance 1** — `ironkv__verified__single_delivery_model_v__single_delivery_model_v__impl2__retransmit_un_acked_packets__keys`:

```
  !det_keys_equal(r1, r2)
```

(witness extractor 只 dump 了 guard;具体 `r1` / `r2` / `self_` 没展开。手工构造:两个不同 byte 表示但 `@` 后映射到同一抽象端点的 `EndPoint`,组成不同顺序的 `Vec`,即可让 `r1 == r2` 为 false 而 ensures 都成立。)

### Pipeline 修复方向

candidate 实现思路:

1. **Per-function equal_fn 覆写**(轻量):在 codegen 时检测 ensures 形如 `out@.map_values(F).to_set() == X`,把 equal_fn 替换为 `r1@.map_values(F).to_set() == r2@.map_values(F).to_set()`。
2. **类型级"as set"注册**(系统化):允许返回类型上附标记 `#[equiv_as_set(EndPoint, |e| e@)]`,让 view_registry 在生成 equal_fn 时优先用此 equivalence。
3. **从 ensures 自动抽 equal_fn**(最一般):对纯函数式的 ensures(`out@.SOMETHING == EXPR_not_mentioning_out`),把它当作 implicit equal_fn。需要 ensures shape 分析。

短期最实用的是 #1。

---

## 候选(待确认是否归入本文档)

如果你确认 #3 `retransmit_un_acked_packets` / #4 `retransmit_un_acked_packets_for_dst` 也是同类情况(spec 用 `to_set()` 是 right level,equal_fn 过严),可以从 `ironkv-real-sat-cases-2026-05-19.md` 一并迁过来。它们的形态完全平行:

```rust
// retransmit_un_acked_packets
ensures
    abstractify_seq_of_cpackets_to_set_of_sht_packets(packets@) == self@.un_acked_messages(src@),
    self@.un_acked_messages(src@) == packets@.map_values(|p: CPacket| p@).to_set(),

// retransmit_un_acked_packets_for_dst
ensures
    packets@.map_values(|p: CPacket| p@).to_set() ==
        old(packets)@.map_values(|p: CPacket| p@).to_set() + self@.un_acked_messages_for_dest(src@, dst@),
```

两条都把抽象到 `to_set()` 一层,跟 #1 `keys` 同源 —— 上层 `retransmit_un_acked_packets` 的 invariant 也只用 set 等价。
