# View-quotient determinism — 失败案例小结（2026-06-04）


## 2. 一览

| # | 函数 | 失败原因（一句话） | 修法方向 |
|---|------|-------------------|---------|
| 1 | `StaticLinkedList::len`（atmosphere） | ensures 直读 hidden 字段 `value_list_len`，且没有任何 `requires` 限定调用前提 | 补 `requires self.wf()`，或去掉读 hidden 字段的 ensures |
| 2 | `DelegationMap::get_internal`（ironkv） | ensures 里 `glb` 一项依赖 hidden 字段 `lows` 的内部结构，而 `valid()` 没把这一结构钉死 | 强化 `valid()` 让 `lows` 唯一，或改 ensures 让 `glb` 也由 view 决定 |

合计 **115** 个 corpus 实例被新检查命中（114 + 1）。

---

## 3. Case 1：`StaticLinkedList::len`

### 3.1 结构

```rust
struct StaticLinkedList<T, N> {
    spec_seq:       Ghost<Seq<T>>,   // view fields = {spec_seq}
    value_list_len: usize,           // hidden
    head, tail, free_head, ...       // hidden
}
spec fn view(self) -> Seq<T> { self.spec_seq@ }
```

### 3.2 函数

```rust
fn len(&self) -> (l: usize)
    ensures
        l == self.value_list_len,            // (E1) 直接暴露 hidden 字段
        self.wf() ==> l == self@.len(),      // (E2) 条件化，仅在 wf 下与 view 对齐
```

函数**没有 `requires`**。(E2) 是条件式的：一旦输入不满足 `wf()`，它退化成 `true`，剩下的 (E1) 又只约束 hidden 字段，view 这一边什么都不剩。

### 3.3 反例（最小）

取 `s1`、`s2` 的 `spec_seq@` 都为空序列，`value_list_len` 分别置为 `0` 与 `7`，其余字段任意。两者都**不**满足 `wf()`，但因为没有 pre-condition 强制 `wf()`，这两次调用都是合法输入。
- `pre1@ == pre2@ == ε` ✓
- 两者都满足 ensures（只有 (E1) 起作用，(E2) trivially holds）
- `r1 = 0`，`r2 = 7`；`usize` 没有 view，直接比 `==`，失败。

### 3.4 这是真 spec 缺陷

`len` 在 spec 上承诺返回 `value_list_len`，但该字段在非 wf 状态下完全是垃圾值。任何相信 `len` 返回值的调用方，若没有事先证 `self.wf()`，都在依赖未定义行为。最小修复是补一行 `requires self.wf()`：无副作用，且让 (E1) 和 (E2) 同时收紧。

---

## 4. Case 2：`DelegationMap::get_internal`

### 4.1 结构

```rust
struct DelegationMap<K> {
    lows: StrictlyOrderedMap<K>,        // hidden：实际游程编码
    m:    Ghost<Map<K, AbstractEndPoint>>,
}
spec fn view(self) -> Map<K, AbstractEndPoint> { self.m@ }
```

`m@` 是逻辑层面的函数 `K → EndPoint`；`lows` 是它的高效实现，把连续相同值压成 "只在变化点存 key"。view 只看 `m@`，`lows` 对外不可见。

### 4.2 函数

```rust
fn get_internal(&self, k: &K) -> (res: (ID, Ghost<KeyIterator<K>>))
    requires self.valid(),
    ensures ({
        let (id, glb) = res;
        &&& id@ == self@[*k]                                          // (E1) view-only
        &&& self.lows.greatest_lower_bound_spec(KI(*k), glb@)         // (E2) reads lows
        &&& id@.valid_physical_address()
    })
```

返回值比较时，`id` 有 view，比较 `id@`；`glb` 包了一层 `Ghost`，内部的 `KeyIterator` **没有 view**，回落到结构 `==`。

### 4.3 `valid()` 救一半

关键漏洞：`valid()` **没有禁止 `lows` 里两个不同的 key 映到同一个 endpoint**。也就是说，同一个逻辑值可以在 `lows` 里被拆成任意多段表示。

逐条对照两条 ensures：

| ensures | 关键字段 | 是否被 `valid()` 救 |
|---------|----------|--------------------|
| (E1) `id@ == self@[*k]` | 只读 view (`self@`) | ✅ 直接由 `pre1@ == pre2@` 推出 |
| (E2) `greatest_lower_bound_spec(lows, ...)` | 读 `lows@.dom()` | ❌ 两个 view 相等的状态可以有不同的 `lows@.dom()` |

`id` 这一边不依赖 `lows`，自然安全；`glb` 这一边在 `lows@.dom()` 上做"最大下界"运算，而 `valid()` 没把 `lows@.dom()` 钉成 `m@` 的函数 —— 漏洞由此而生。

### 4.4 反例（最小）

固定常函数 `m@ = K → ep_x`：

| state | `lows.keys` | `lows@` | `valid()` |
|-------|-------------|---------|:---------:|
| `s1`  | `[K::zero]` | `{K::zero ↦ ep_x}` | ✓ |
| `s2`  | `[K::zero, k₅]` | `{K::zero ↦ ep_x, k₅ ↦ ep_x}` | ✓ |

`s2` 里 `K::zero` 和 `k₅` 是不同的 key，却都映到 `ep_x` —— 正是 §4.3 描述的漏洞。

查询 `*k = k₆`，且 `k₅ < k₆`：
- `glb1 = KI::new(K::zero)`（`s1.lows@.dom()` 里 < `k₆` 的最大 key）
- `glb2 = KI::new(k₅)`（`s2.lows@.dom()` 里 < `k₆` 的最大 key）

`id1@ = id2@ = ep_x` ✓，但 `glb1 ≠ glb2` —— `glb` 分量崩。

### 4.5 修法

- **强 valid**：补一条"`lows` 里相邻 key 必须映到不同 endpoint"（等价于 `lows.dom` 是 `m@` 的 canonical RLE）。`s2` 立刻非法，反例消失。
- **改 ensures**：让 `glb` 也由 `m@` 决定，例如返回 "`*k` 所在最大相等段的左端点"，绕开 `lows` 的内部结构。
