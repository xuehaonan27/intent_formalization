# spec-determinism × vstd 研究教程

> 面向刚接手本项目的人。目标：读完这一篇，你能说清楚这个 research 在解决什么问题、
> 用什么方法、做到哪一步、坑在哪里、下一步是什么。
> 细节随时回链到原始文档；本文不替代它们，只是地图。
>
> 撰写日期：2026-07-21（xuehaonan 机器环境就绪后）。

---

## 1. 一句话概括

**用 SMT 自动检查"规范（specification）是否唯一确定了输出"，以此发现规范的不完备
（underconstraint）**——并把这套方法系统地应用到 Verus 标准库 `vstd` 上，盘点它的
规范全貌、实测它的 trusted contracts。

---

## 2. 背景：Verus 与"规范是信任基座"

[Verus](https://github.com/verus-lang/verus) 是 Rust 的形式化验证器。你在 Rust 函数上写：

```rust
fn insert(&mut self, k: Key, v: Value)
    requires ...              // 前置条件 P
    ensures  self@ == old(self)@.insert(k, v)   // 后置条件 Q
```

Verus 把函数体和 spec 翻译成 SMT，用 Z3 证明"实现满足 spec"。

关键问题在于：**验证通过只能保证"实现满足 spec"，不能保证 spec 本身写对了。**

- spec 是 TCB（trusted computing base）的一部分。`ensures true` 永远能验证通过，
  但它什么都没说。
- 下游证明（crash consistency、状态机精化……） implicitly 假设上游 spec 把 post-state
  钉死了。spec 欠约束时，这些证明在不知不觉中建立在空地上。
- `vstd` 里的 `std_specs/*` 尤其要害：它们是 Rust 标准库的 **trusted contracts**
  （`assume_specification`），全 Verus 生态的每个项目都信任它们。它们写弱了，
  所有下游证明都被稀释。

所以需要一个**自动化的 spec 质量审计工具**。这就是 spec-determinism。

---

## 3. 核心思想：完备性 ⇔ 确定性

一个完备的规范，对每个合法输入只允许**一个**（可观测意义上唯一的）输出：

```text
∀x. P(x) → ∃!y. Q(x, y)                          — 完备（确定）

∃x. P(x) ∧ ∃y₁,y₂. Q(x,y₁) ∧ Q(x,y₂) ∧ y₁≠y₂     — 不完备（存在两个合法但不同的输出）
```

对 spec 做检查，不需要跑实现，直接把上面的否定形式写成一个 proof 义务：

```rust
proof fn det_foo(x: InputType, y1: OutputType, y2: OutputType)
    requires P(x),
    ensures  Q(x, y1) && Q(x, y2) ==> equal(y1, y2)
{
    // 空函数体，交给 SMT 判定
}
```

- Verus/Z3 证得动（`unsat`）→ 不存在反例 → spec 在该语义输出上是**确定的**；
- 证不动且能构造出具体 `(x, y1, y2)`（`sat`）→ **规范不完备的 witness**，
  它能精确定位"哪个字段/哪一位/哪个元素没被约束住"。

三个要点：

1. **查的是 spec，不是实现。** 实现几乎是确定的（Rust exec 代码），有意思的是
   spec 是否把 post-state 刻画到只剩一种可能。
2. **"输出"不只是返回值。** 对 `fn f(&mut self, ...) -> r`，输出 = `(最终 self, r)`；
   每个 `&mut` 参数都拆成 pre（输入）和 post（输出）两个变量。
3. **`equal` 不是结构相等。** 两个 `HashMap` 内部 bucket 布局不同但内容相同，
   语义上应判等；两个 raw pointer 地址不同可能是"有意非确定"而不是 spec 漏洞。
   所以 equal-fn 是按类型的**语义等价**——优先比较 `view`（`@`）、`mem_contents()`、
   permission 的可观测投影，而不是内存表示。equal-fn 的合成是本 pipeline 最核心的
   工程问题之一。

---

## 4. 结果词汇与"漏斗"：unknown 不是结论

每次检查，Z3 基线（称 **R0**）给出三种结果，但它们**不是三个平行结局**：

| R0 | 含义 | 性质 |
|---|---|---|
| `unsat` | 规范确定输出 | **终局判定**（complete） |
| `sat` | 有具体反例 witness | **终局判定**（确认不完备） |
| `unknown` | 求解器没判定 | **不是判定**——公式仍然是 sat 或 unsat，只是没解出来 |

整条 pipeline 的下半段就是在**消减 unknown 桶**（详见
`docs/determinism-funnel-framework.md`）：

```text
extract → gen_det → R0 基线
                        │
        ┌───────────────┼────────────────┐
     unsat            sat             unknown
     终局             终局              │
                              unsat 侧漏斗（单调向 unsat，不会翻案）：
                                view-equal 修正（PR-N / C-patch / L1/L3）
                                Tier 1.5  LLM 类型补全
                                Tier 2    equal-fn 放宽
                                Tier 3    LLM proof 引理标注
                                深度 schema narrowing
                                        │
                                 UNKNOWN_RESIDUAL
                                        │
                              sat 侧漏斗：portfolio solver / sat 采样 / 人工 witness
                                        │
                     ┌──────────────────┼──────────────────┐
                   sat(witness)      presumed_sat      residual_unknown
```

血泪教训（`docs/unknown-handling-strategy-2026-05-15.md`）：早期 corpus 里上报的
几百个"nondeterminism witness"，2026-05-13/14 复跑发现 **100% 是 z3 unknown，
0 个真 sat**。所以纪律是：

> 永远不要把 `unknown` 当成 complete 或 incomplete 上报。

vstd 实验同样 `0 sat`，但**人工语义审计**在 unknown 里确认了 4 个真不完备（见 §8）。

---

## 5. Pipeline 怎么跑（阶段速览）

完整参考：`docs/pipeline-2026-06-02.en.md`（1539 行长文）。vstd runner
（`run_determinism.py`）对每个目标依次：

1. **extract_spec**：tree-sitter-verus 解析源码 → `FunctionSpec`（requires/ensures/
   类型/泛型边界）。支持 `module:fn@line` 行号消歧同名 impl 方法。
2. **View 解析（L1–L4）**：确定每个类型的语义投影（`View::V`、inherent `spec fn view`、
   registry 里 LLM 预填的 impl 块）。
3. **equal-fn 合成**：按类型结构递归生成 `det_<f>_equal(r1, r2)`；view 优先于
   `#[verifier::ext_equal]`；opaque 类型（如 `PointsToRaw`）整体坍缩为 `true`（不可观测）；
   `Tracked<T>`/`Ghost<T>` 有内层 spec view 时比 `@@`。
4. **gen_det**：把后置条件按 `(r1, r2)` 双份展开，渲染带 guard 的模板：
   ```rust
   proof fn det_f(g_neq_tuple: bool, g_schema_1: bool, ..., inputs, r1: T, r2: T)
       requires Q(inputs, r1) && Q(inputs, r2),
       ensures  (Q展开合取) ==> det_f_equal(r1, r2),
   {
       if g_schema_1 { assume(<schema_1>); }   // 引理/外延性等"精化词汇"
       if g_neq_tuple { assume(!det_f_equal(r1, r2)); }
   }
   ```
5. **Verus 编译**，`--log-all` 留下 SMT2。
6. **schema search**：把 SMT2 重新载入 z3-py，用布尔 guard 在**同一份大 SMT2**里开关
   不同精化组合（不用反复重跑 Verus），找能让 z3 判定的最窄切片。
7. **classify**：`unsat` → complete；`sat` → witness；`unknown` → inconclusive，
   绝不误判。

vstd 实验只用了上述**纯 SMT 子集**（未启用 Tier 1.5/3 的 LLM 工具），
unknown 的归因审计是人工做的（`experiments/UNKNOWN-AUDIT-2026-07-15.md`）。

---

## 6. 这个方法能发现什么、不能发现什么

**能发现**：spec 欠约束——某个输出维度没有被 ensures 钉住，witness 直接指出在哪里。

**不能发现**（说给你自己听三遍）：

1. **"确定但错误"的过强 spec。** 例如 `std_specs::num` 某条 ensures 把结果唯一钉死
   但语义写错了——确定性检查照样 `unsat` 通过。本方法只量"唯一性"，不量"正确性"。
2. **`assume_specification` 与真实 Rust 实现是否一致。** 那是 trusted axiom，
   Verus 无法对 rustc/标准库实现求证。本方法能指出"这条 trusted contract 弱到
   允许两个输出"，但不能证明"强的那条真的成立"。
3. **有意非确定**（fresh 地址/handle、float cast 关系、线程调度）会被 flagged，
   需要显式的 permitted 规则或商等号（忽略 identity、只看内容/谓词）才能区分
   "设计如此"与"真的漏了"。

---

## 7. 为什么拿 vstd 做，以及盘点了什么

vstd 是 Verus 生态的地基库；它的 spec 质量是所有下游项目的上限。
`vstd-survey/README.md` 给出完整盘点（上游 `cf3b5c3`，2026-07-13）：

- 125 个 module、52,715 行、**3,367 个 spec 相关声明点**；
- 其中真正面向 API 使用者的 **contract sites 只有 515 个**：
  185 个 exec/trait 后置条件 + 330 个带后置条件的 `assume_specification`；
- vstd 分八层（数学基础 / std_specs / 运行时容器 / 内存所有权 / 并发 prophecy /
  resource algebra / 实验性 exec_spec / 基础设施）。**`std_specs/*` 一家占 58.8%
  的 contract surface**；47 个 critical/high module 覆盖 85.4%。
  → 不需要平均处理 125 个 module，按 README 的推荐顺序来。

计数口径（重要，免得以后误读数字）：

- 全部是**源码声明点**：宏模板只计一次，不按类型展开重复计数；
- `spec fn` / `proof fn` 不计入 exec；
- "无显式 postcondition" ≠ 缺 spec（可能继承自 trait、是 compiler intrinsic、
  或有意非确定，如 `Prophecy::new`）；
- 扫描器目前不进 `verus_! { ... }` 别名宏（已知缺口，见 §11）。

---

## 8. vstd 实验与三类 unknown

在与编译产物严格匹配的 2026-05-17 快照（`0.2026.05.17.e479cce`）上，对
**111 个 AST 可见、带显式后置条件的 public exec definitions**（34 自由函数 +
77 impl 方法）跑完确定性检查：

| 结果 | 数量 | 含义 |
|---|---:|---|
| complete | 87 | R0=unsat，equal-fn 经人工确认非平凡 |
| unknown | 20 | 求解器未判定 |
| unsupported | 4 | 返回 `&mut T`（`old(result)`/`final(result)` 替换未实现） |
| sat witness | 0 | 无机器确认的反例 |

对 unknown 的**人工语义审计**（`experiments/UNKNOWN-AUDIT-2026-07-15.md`）分成三类，
这是整个研究最有信息量的产出：

- **A 类（7 个）：本应 complete，是工具缺口。**
  例：`atomic::fetch_and/xor/or` 的权限类型是宏生成的，源码级 view 发现看不到它，
  equal-fn 退化成裸结构相等；手工改成比较 `.view()` 字段后即验证通过。
  → 修工具，不是修 spec。
- **B 类（9 个）：有意/被允许的非确定。**
  例：`raw_ptr::allocate` 的地址与 provenance、`PCell::new` 的 fresh `CellId`、
  `float_cast` 的非确定转换关系。
  → 应标记 `incomplete_permitted`；或在"忽略 identity 的商等号"下判 complete。
  不是 bug，但必须显式记录，不能默默吞掉。
- **C 类（4 个）：真正的语义欠约束。**
  例：弃用版 `InvCell::{replace, get}` 与 `RwLock::{acquire_write, into_inner}`
  的后置条件只有 `inv(result)`——一个任意不变式谓词。谓词不是函数：
  `inv(0) ∧ inv(1)` 可以同时成立，返回值确实不被唯一确定。
  → 可能是故意的信息隐藏设计，但形式上就是 spec 不完备；如何处理是 API 决策
  （接受并记录 / 加 ghost 精确取值访问器 / 改 API），见 HANDOFF §13 P4。

**结论形态**：vstd 的常规容器/字节/字符串 spec 质量很好（87/111 自动通过）；
剩下的难点集中在并发、权限、身份这类"本来就想隐藏"的 API 上。

---

## 9. 已设计的第二步：抽象确定性（view-quotient）

`docs/abstract-determinism-plan-2026-06-04.en.md`：在第一步（固定具体输入 → 输出唯一）
通过后，再问第二步——**输入在 view 层相等，输出是否也在 view 层相等**：

```text
view(o₁) == view(o₂)  ∧  P(o₁) ∧ P(o₂)  ∧  Q(o₁,r₁) ∧ Q(o₂,r₂)
  ⟹  view(r₁) == view(r₂)
```

它分离两种缺陷：spec 欠约束（第一步抓）与"结果泄漏具体表示细节"（第二步抓）。
尚未在 vstd 上实施。

---

## 10. 本机环境与复现（2026-07-21 起）

| 组件 | 位置 | 版本 |
|---|---|---|
| 仓库 | `/home/xuehaonan/intent_formalization` | — |
| 上游盘点源码 | `~/verus` | `cf3b5c3`（2026-07-13） |
| 实验快照（源码+编译产物匹配） | `~/nanvix/toolchain/verus` | `0.2026.05.17.e479cce` |
| Rust 工具链（release shim 需要） | rustup | `1.95.0-x86_64-unknown-linux-gnu` |
| Python 环境 | conda env `specdet` | Python 3.11，`pip install -e .` |
| tree-sitter-verus | pip git 安装 | **0.23.2**（⚠ 文档数字由 0.21.0 生成，见 §11） |

冒烟验证（已通过）：`bytes:u16_from_le_bytes@79` 与 `hash_map:insert@106`
均 `r0=unsat class=complete`。

跑一个目标：

```bash
cd /home/xuehaonan/intent_formalization/spec-determinism
/opt/conda/envs/specdet/bin/python vstd-survey/run_determinism.py \
  --vstd-root /home/xuehaonan/nanvix/toolchain/verus/vstd \
  --verus-root /home/xuehaonan/nanvix/toolchain/verus \
  --out /tmp/vstd-one --target hash_map:insert@106 \
  --timeout 240 --rlimit 60
```

全量复现命令见 HANDOFF §11。

---

## 11. 已知局限（详单见 HANDOFF §12）

1. **扫描器不进 `verus_!{...}` 别名宏** → 漏掉非弃用版 `cell::invcell`/`pcell`/
   `pcell_maybe_uninit` 与部分 `std_specs`。所以**"111 目标"不是完整 vstd
   exec surface**，对外表述时绝不能省略这个限定。
2. tree-sitter-verus 已换成 0.23.2（旧文档数字基于 0.21.0）。自测与冒烟均过，
   但重新生成 inventory 后数字可能变化（预期 parse recovery 减少）——这本身是
   P0 工作的一部分。
3. 返回 `&mut T` 的 4 个目标暂不支持。
4. `assume_specification` 只做了词法盘点，未做确定性实测。
5. `unknown` 永不等于判定；runner 的 permitted 标记目前恒为 False，
   A/B/C 标签还在 Markdown 里，没进结构化结果。

---

## 12. 下一步（详单见 HANDOFF §13 P0–P5 与 §15）

- **P0** 修 `verus_!` 别名解析（配合新 grammar 0.23.2），重新生成两套 inventory；
- 本机全量复跑 111 目标，确认 87/20/4 在新环境可复现；
- **P1** 为七月快照 `~/verus@cf3b5c3` 从源码构建匹配工具链，停止混用五/七月快照；
- **P2–P5**：自动化 A 类（宏生成 view、投影策略、引理提示）→ 编码 B 类 permitted
  规则 → 决策 C 类 API → 把审计标签结构化进结果元数据。

---

## 附录 A. 名词表

| 术语 | 含义 |
|---|---|
| `exec fn` | 可执行 Rust 函数（验证对象是它的实现） |
| `spec fn` | 纯数学函数，只活在 spec/证明里 |
| `proof fn` | 引理/证明，编译后不留代码 |
| `axiom fn` | trusted 公理，无证明 |
| `assume_specification` | 给外部（如 std）函数挂 trusted contract 的声明 |
| `View` / `@` / `view()` | 从具体表示到数学对象的投影（`Seq`/`Set`/`Map`…） |
| `tracked` / `Ghost` | ghost 状态组件，运行时不存在但参与证明 |
| R0 | 不加任何精化的 z3 基线检查 |
| equal-fn | pipeline 为输出类型合成的语义等价谓词 |
| schema / guard | 精化词汇（引理、外延性…）及其布尔开关；复用同一份 SMT2 |
| witness | 满足 spec 但互不相同的具体 `(x, y1, y2)`，不完备的证据 |
| permitted incompleteness | 有意非确定（fresh identity 等），需显式规则记录 |
| TCB | trusted computing base，验证中"必须信"的部分 |

## 附录 B. 文档地图

| 文档 | 读它是为了什么 |
|---|---|
| `skills/spec-determinism/SKILL.md` | 方法核心（det 检查 + 类型引导 witness 搜索） |
| `docs/pipeline-2026-06-02.en.md` | pipeline 全阶段长文参考 |
| `docs/determinism-funnel-framework.md` | 桶生命周期/漏斗语义 |
| `docs/unknown-handling-strategy-2026-05-15.md` | unknown 处理纪律的来源 |
| `docs/abstract-determinism-plan-2026-06-04.en.md` | 第二步（view-quotient）设计 |
| `vstd-survey/README.md` | vstd 盘点全景 + 推荐审计顺序 |
| `vstd-survey/HANDOFF.md` | 交接主文档：环境、代码改动、实验、复现、下一步 |
| `vstd-survey/experiments/REVIEW-2026-07-14.md` | 111 目标实验综合结论 |
| `vstd-survey/experiments/UNKNOWN-AUDIT-2026-07-15.md` | 27 个 unknown 的逐项审计 |
