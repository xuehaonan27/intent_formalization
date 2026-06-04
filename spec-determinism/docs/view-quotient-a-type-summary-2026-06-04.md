# View-quotient determinism — A 型案例小结（2026-06-04）

> 在 `complete`（Step 1 通过）的 1436 条 obligation 里，view-quotient
> determinism（Step 2）失败的 **A 型** 共两个 unique 函数：
> `StaticLinkedList::len` 和 `DelegationMap::get_internal`。
> 本文做一个高层小结，详细 witness / 公式见
> [`view-quotient-candidates-2026-06-04.en.md`](view-quotient-candidates-2026-06-04.en.md)；
> 框架定义见
> [`view-quotient-determinism-plan-2026-06-04.en.md`](view-quotient-determinism-plan-2026-06-04.en.md)。

---

## 1. 一句话回顾框架

| 检查 | 输入侧 | 输出侧 (`E_R`) | 通过含义 |
|------|--------|----------------|---------|
| Step 1（旧） | 输入完全相等 | view-aware：有 view 比 view，否则比 == | "在完全相同的具体输入下，spec 允许的所有输出仍相等" |
| Step 2（新） | view 相等 | 同上 | "对所有 view 相等的合法输入，spec 允许的所有输出也都 view 相等" |

A 型 = **Step 1 ✓，Step 2 ✗** —— spec 在具体输入下闭得住，但一旦把 hidden field 的取值放开，就会出现两次合法运行给出 view 不等的输出。

---

## 2. 两个 A 型一览

| # | 函数 | 类型 | corpus 实例 | 失败根因 | 直接修法 |
|---|------|------|-------------|-----------|----------|
| 1 | `StaticLinkedList::len` | **no-requires** A 型 | 114 (atmosphere) | ensures 直接读 hidden `value_list_len`，且没有 `requires self.wf()` | 加 `requires self.wf()` 或删掉 hidden ensures |
| 2 | `DelegationMap::get_internal` | **partial-rescue** A 型 | 1 (ironkv) | `requires self.valid()` 救得了 `id`（view-only ensures），救不了 `glb`（依赖 `lows@.dom()` 不被 valid 钉死） | 在 `valid()` 里强制 lows 为 canonical RLE，或改 ensures 让 `glb` view-derivable |

两条加起来 **115** 个 corpus 实例真实地被新检查捕获。

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
        l == self.value_list_len,            // (E1) leak：读 hidden 字段
        self.wf() ==> l == self@.len(),      // (E2) 仅在 wf 下与 view 挂钩
```

**没有任何 `requires`**，于是 `wf()` 这个条件型 ensures 救不到非 wf 的输入。

### 3.3 反例（最小）

让 `s1`、`s2` 的 `spec_seq@` 都是空序列，但 `value_list_len` 一个是 `0`、一个是 `7`，其他字段任意（即两者都不满足 `wf()`，所以 (E2) 退化为 `true`）。
- `pre1@ == pre2@ == ε` ✓
- 两者都满足 ensures（仅 (E1) 起作用）
- `r1 = 0, r2 = 7`，`E_R` 是 `usize` 的 `==`，崩。

### 3.4 这是真 spec 缺陷

`len` 在 spec 上承诺了它会返回 `value_list_len`，但 `value_list_len` 在非 wf 状态下完全是垃圾。任何"信 `len` 返回值"的调用方在没有 wf 假设时就在用未定义行为。补 `requires self.wf()` 是无副作用的最小修复。

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

`m@` 是逻辑函数 `K → EndPoint`；`lows` 是把它压缩成 "只在变化点存 key" 的实现。

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

`E_R`：`id@ == id'@`（`EndPoint` 有 view）∧ `glb == glb'`（`KeyIterator` **没有 view**）。

### 4.3 `valid()` 救一半

```rust
spec fn valid(self) -> bool {
    &&& self.lows.valid()
    &&& self.lows@.contains_key(K::zero)
    &&& self@.dom().is_full()
    &&& forall|k| self@[k].valid_physical_address()
    &&& forall|k,i,j|                            // (★) 共享子域上值一致
          self.lows@.contains_key(i) ∧
          self.lows.gap(KI(i), j) ∧
          KI::between(KI(i), KI(k), j)
        ⟹ self@[k] == self.lows@[i]@
}
```

| ensures | 关键字段 | 救/不救 |
|---------|----------|---------|
| (E1) `id@ == self@[*k]` | 只读 view | ✅ 直接由 `pre1@ == pre2@` 推出 |
| (E2) `greatest_lower_bound_spec(lows, ...)` | 读 `lows@.dom()` | ❌ valid 只钉值不钉 dom |

(★) 是 **structural**（"lows 上每个 entry 的值跟 m@ 一致"），不是 **representational**（"lows.dom 是 m@ 的某种函数"）。允许冗余 breakpoint —— 这正是漏洞。

### 4.4 反例（最小）

固定常函数 `m@ = K → ep_x`：

| state | `lows.keys` | `lows@` | `valid()` |
|-------|-------------|---------|:---------:|
| `s1`  | `[K::zero]` | `{K::zero ↦ ep_x}` | ✓ |
| `s2`  | `[K::zero, k₅]` | `{K::zero ↦ ep_x, k₅ ↦ ep_x}` | ✓（`k₅` 是冗余 breakpoint） |

查询 `*k = k₆`，`k₅ < k₆`：
- `glb1 = KI::new(K::zero)`
- `glb2 = KI::new(k₅)`

`id1@ = id2@ = ep_x` ✓，但 `glb1 ≠ glb2` —— `glb` 分量崩。

### 4.5 触发条件精确化

**不是** "两个 key 映到同一 endpoint"（在 `m@` 里这完全合法）；**是** "lows 里两个相邻 key 映到同一 endpoint"（在 `lows` 里出现冗余 breakpoint）。`valid()` 不禁止这种冗余，于是 `lows@.dom()` 不再被 `m@` 唯一决定。

### 4.6 修法

- **强 valid**：要求 `lows.dom = { k | k == K::zero ∨ m@[k] ≠ m@[predecessor(k)] }`（canonical RLE）。`s2` 立刻非法。
- **改 ensures**：让 `glb` 也由 `m@` 决定，例如 "`*k` 所在最大相等段的左端点"。

---

## 5. 两个 case 的对照

| 维度 | `len` | `get_internal` |
|------|-------|----------------|
| 缺陷形态 | requires 完全缺 | requires 在但不够 |
| 失败的 ensures | (E1) hidden 字段直读 | (E2) 读 hidden 字段的 dom 量词 |
| `view@` 等价后还能否被 invariant 救 | 不能（无 invariant） | 部分能（id ✓，glb ✗）|
| Audit 难度 | 一眼可见 | **必须 unfold valid 的 body** |
| 修法成本 | 加一行 `requires` | 改不变量或改返回签名 |

---

## 6. 对 audit 流程的启示

1. **`requires` 不是免死金牌。** Scan v3 把"requires 里有 wf/valid/invariant"当 rescue 是 **syntactic shortcut**；真正判定要把谓词体打开，看它是否把 ensures 用到的每个 hidden field "作为 view 的函数"钉死。
2. **区分 structural vs representational invariant。**
   - structural：值在共享子域上一致（如 `DelegationMap.valid` 的 ★）。能救 view-only ensures。
   - representational：编码本身被 view 唯一决定（canonical form）。能救读 hidden domain 的 ensures。
   - 两者在审计里要分开标记。
3. **No-requires 和 partial-rescue 是两类不同的 bug**，应分别报告（前者建议补 `requires`，后者建议强化或重写不变量）。
4. **下一步**（见 candidates 文档 §7）：把 wf-rescue 的 body unfold 机器化。`get_internal` 是手工验证的，其余 13 个 syntactically-rescued 候选还没逐一过。

---

## 7. 链接

- 详细 witness / 公式 / scan 脚本：
  [`view-quotient-candidates-2026-06-04.en.md`](view-quotient-candidates-2026-06-04.en.md)
- 框架定义（P/Q/V/E_R、Step 1/2）：
  [`view-quotient-determinism-plan-2026-06-04.en.md`](view-quotient-determinism-plan-2026-06-04.en.md)
- 源文件：
  - `verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs:42,65,82`
  - `verusage/source-projects/ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs:120-249,545-548`
