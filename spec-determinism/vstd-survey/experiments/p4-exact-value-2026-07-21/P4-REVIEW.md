# P4 决策 review：C 类真欠约束的处理（2026-07-21）

## 问题

7 个 C 类目标的 postcondition 只用**非函数性的不变式谓词**约束返回值
（`ensures self.inv(result)`），spec  genuinely 不唯一确定结果：

- `cell::{replace@359, get@378}`（弃用 `InvCell`）
- `cell::invcell::{replace@123, get@139, into_inner@155}`
- `rwlock::{acquire_write@530, into_inner@702}`

HANDOFF §13 P4 给出三个选项：① 接受并记录 possible-value 抽象；② 加
ghost 精确取值访问器；③ 改 API 弱化承诺。本次按"先②后①"完成评估。

## Phase A：机器可验证的非确定 witness（① 的证据升级）

此前 C 类标签是人工审计确立（无机器 sat witness）。本目录 3 个 witness
在**真实 vstd 模型内**证明"两个不同值同时满足 postcondition"：

| 文件 | 构造 | 验证 |
|---|---|---|
| `witness_cell_deprecated.rs` | `InvCell::new(0, Ghost(\|v\| true))` → `assert(inv(0) && inv(1) && 0≠1)` | ✅ 1 verified |
| `witness_invcell.rs` | `Pred = spec_fn 恒真`（`inv` open，委托 `predicate()`）→ 同上 | ✅ 1 verified |
| `witness_rwlock.rs` | `RwLock` 恒真谓词（`inv` open，委托 `pred().inv()`）→ 同上 | ✅ 1 verified |

这是整个研究中**第一批机器检查的 sat 反例**：谓词的非函数性不是理论
推测，而是在 Verus 里构造性地成立。C 类的 `incomplete` 标签由此从
"audit-established" 升级为 **"machine-established"**（3 个 witness 各自
覆盖同形状的全部方法：deprecated 2 个、invcell 3 个、rwlock 2 个）。

## Phase B：选项②量化——"暴露精确值即可恢复确定性"

给每个 C 类目标写反事实 det 检查：契约变为
`Q'(r) = Q(r) ∧ r == current`（`current` 建模 ghost 精确取值访问器在
pre-state 的值）。结果：

| 反事实 harness | 对应目标 | 验证 |
|---|---|---|
| `exact_cell_replace.rs` / `exact_cell_get.rs` | deprecated replace/get | ✅ |
| `exact_invcell_{replace,get,into_inner}.rs` | invcell 三个 | ✅ |
| `exact_rwlock_acquire_write.rs` | acquire_write（等号只看值分量） | ✅ |
| `exact_rwlock_into_inner.rs` | into_inner | ✅ |

**7/7 全部恢复确定性**——缺的恰好只是精确值这一条约束；修正后的契约
形状对真实 vstd 类型良构可编译。

对应的 vstd patch sketch（以可行动的 invcell 为例，rwlock 同构）：

```rust
impl<T, Pred: Predicate<T>> InvCell<T, Pred> {
    /// 当前存储的精确值（ghost 访问器）。
    /// 与现有 trusted contract 同一信任级别；实现本来就返回该值，
    /// 故 amended ensures 对实现可证。
    pub uninterp spec fn current(&self) -> T;

    pub fn replace(&self, val: T) -> (old_val: T)
        requires self.inv(val),
        ensures
            self.inv(old_val),
            old_val == old(self).current(),   // 新增一行
    { ... }
}
```

注意边界：本实验验证了修正契约**确定性**与**良构性**；"修正后的
ensures 对实现可证"未在此验证（那是上游工作；但 replace/get/into_inner
的实现都字面返回所存值，给出访问器后即可证）。

## 决策

- **① 接受并记录：正式化。** 7 个 C 类保持 `audit_label=incomplete`，
  但证据升级为机器 witness（本节 Phase A，随库提交）。
- **② 推荐为上游方向。** 已量化：7/7 恢复确定性，patch sketch 就绪；
  若要推动，拿 `witness_*` 与 `exact_*` 两组文件即可向上游说明收益。
  这是唯一能让这些 API 的 spec 完备的路径。
- **③ 拒绝。** 弱化承诺只会把欠约束合法化，且破坏这些类型以
  predicate-invariant 做信息隐藏的设计意图与下游证明。

## 产物清单

- `witness_{cell_deprecated,invcell,rwlock}.rs`：机器 witness（phase A）
- `exact_{cell,invcell,rwlock}_*.rs`（7 个）：反事实 det 检查（phase B）
- 复跑命令（每个文件）：
  ```bash
  RUSTC_BOOTSTRAP=1 ~/verus/source/target-verus/release/verus <file>.rs
  ```
