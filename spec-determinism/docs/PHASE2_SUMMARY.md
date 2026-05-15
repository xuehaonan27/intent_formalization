# Phase 2 弧：View Registry → PR-G

> **目的**：spec-determinism 项目 Phase 2（A-2 false-positive 减少 + A-1/A-3
> 错误减少）阶段性总结，slides 素材。
> **覆盖**：2026-04 末到 2026-05-12，从 `type_registry` 的 SCC 工具到 PR-G 落地。
> **不覆盖**：Phase 1（Verus 单文件 invoke、equal-fn 雏形、`EqualPolicy`）。

---

## 1. 问题陈述

### 1.1 我们在做什么

把 Verus 项目里每个公开函数自动检验**确定性（determinism）** ——
即 "对相同输入，函数总是给出 spec 等价的输出"。

输入：Verus 源码 + `requires/ensures` 注解
输出：每个函数一个**原始** `status`，再从 `status=="ok"` 的结果里派生
witness bucket。也就是说，`ok_with_witness` 不是 JSON 里的独立 status，
而是 `status=="ok" && assumes != []`。

```
raw status:
ok            pipeline 跑通；可能有 witness，也可能没有
verus_error   生成的等式函数 / 注入代码过不了 Verus 类型检查
runner_crash  pipeline 内部错误

derived buckets:
ok_without_witness  status=="ok" && assumes==[]：ensures 足以推出 equal-fn
ok_with_witness     status=="ok" && assumes!=[]：schema search 保留了一组
                    反例 assumes，说明当前 equal-fn 下仍有 spec 维度没钉住
```

理想分布：**raw ok 多，其中 ok_with_witness 少，verus_error 少**。

### 1.2 三条优化轴

| 轴 | 含义 | 失败现象 |
|---|---|---|
| **A-1** | 可观测维度 / 投影识别不足 | `verus_error` / partial witness / `pass_untranslatable`：工具看不到 spec 提到的内部维度 |
| **A-2** | 等式函数过于严苛 | ok_with_witness（false positive）：把语义相等的两次执行视为不等 |
| **A-3** | 等式函数语义错误 | verus_error：嵌套结构里 Err 该 collapse 没 collapse |

Phase 1 baseline（commit `42c1248`，n=1647 跨 7 项目）：

```
ok           1455   ← raw ok 总数；目标：往上推
ok_with_witness  376   ← raw ok 的子集；A-2 主战场
verus_error   191   ← A-1 + A-3 主战场
runner_crash    1
```

### 1.3 三轴的具体例子

**前置说明 ── spec-determinism 是 incompleteness 探测器，不是 prover**

spec-determinism 给每个目标 fn **自动生成一个 equal-fn `eq(r1, r2)`**，然后让
Verus + z3 检查：在 ensures 下 `eq(r1, r2)` 是否恒成立。

**关键约束**：equal-fn **完全由返回类型决定**（外加可配置 policy，比如 PR-G 的
errs-equivalent）。它**不会**根据 ensures 的内容"挑一个能证的版本"。所以：

| verdict bucket | 含义 |
|---|---|
| `ok_without_witness` | spec（ensures）足以推出当前 equal-fn 定义下的 spec 层确定性 |
| `ok_with_witness` | raw `ok`，但 `assumes` 非空：ensures 不够强，或 equal-fn 仍有 A-2 噪音 —— 工具给出反例维度供用户判断 |
| `verus_error` / `runner_crash` | **工具坏掉**，verdict 不带信号 |

PR-F / PR-G 的目的**不是**"让更多 fn 显得 complete"，而是：

1. 把"工具坏掉"（verus_error）翻成"工具能用 + 真实信号"（ok_without_witness / ok_with_witness）
2. 在 ensures 已经紧的少数情形下顺便给出 `ok_without_witness`
3. 把 spurious witness（来自 byte-level noise，A-2 轴）变成 meaningful witness 或 `ok_without_witness`

下面 6 个例子分别展示这三种翻转。

#### A-1 例 1 ── `Ghost<Seq<u32>>` 输出（atmosphere 形态）

```rust
// 源
fn build_log() -> (r: Ghost<Seq<u32>>)
    ensures r@.len() == 5
```

ensures **故意只钉长度，不钉元素** —— 这是真实 atmosphere 里常见的形态。

| | 生成的 equal-fn（**由类型决定**） | Verus + z3 推理 | verdict |
|---|---|---|---|
| PRE-PR-F | `r1 == r2`（Ghost 未识别 → UNKNOWN fallback） | Verus 拒绝 Ghost wrapper 上的结构 `==`（或 z3 把 Ghost 当 opaque sort，给一个 vacuous SAT） | **verus_error** —— 工具坏掉，verdict **没有 spec 信号** |
| POST-PR-F | `((r1)@ == (r2)@)`（GHOST 分支：剥 wrapper） | Verus 接受（Seq 是 spec 类型）；z3 narrow 给 `_leneq` / `_lenrng`；ensures 给 `r1@.len()==5` `r2@.len()==5` 但元素自由 → z3 找到合法反例 `r1@=seq![0;5]`、`r2@=seq![1;5]` | **ok_with_witness** —— 工具能用了，verdict 是**真实信号**：ensures 没钉元素，请补 `forall\|i\| r@[i] == …` |

**PR-F 的胜利**：把 verdict 从"工具坏掉"翻成"工具正常 + 真实 incompleteness
信号"。如果用户后续把 ensures 紧到 `r@ == state.log@`，verdict 会进一步变成
`ok_without_witness`（z3 用 transitivity chain 过去）—— 但那是用户的事，不是 PR-F 的事。

#### A-1 例 2 ── `Tracked<PointsTo<u32>>` 输出（storage 形态）

```rust
// 源
fn split_cell(pt: Tracked<PointsTo<u32>>) -> (r: Tracked<PointsTo<u32>>)
    ensures r@.is_init() == pt@.is_init(),
            r@.addr() == pt@.addr()
```

ensures 钉了 `is_init` 和 `addr` 两个投影，**故意没钉 `value()`** —— 真实代码
里很常见，因为 storage 调用方往往不关心当前 cell 装的值。

| | 生成的 equal-fn（**由 `Tracked<PointsTo<u32>>` 类型决定**） | Verus + z3 推理 | verdict |
|---|---|---|---|
| PRE-PR-F | `r1 == r2` —— Tracked / PointsTo 是 `external_body` newtype | Verus 编译时报错：external_body 类型没有结构 `==` | **verus_error** —— 工具坏掉 |
| POST-PR-F | `(r1)@.is_init() == (r2)@.is_init() && (r1)@.addr() == (r2)@.addr() && ((r1)@.is_init() ==> (r1)@.value() == (r2)@.value())` | ensures 钉 `is_init`、`addr`；但 `value()` 在 init 分支下自由 → z3 找到合法反例 `r1@.value()=0`、`r2@.value()=42`（同 addr 同 init，但内容不同） | **ok_with_witness** —— 信号：ensures 没钉 init 时的 value，请补 `r@.is_init() ==> r@.value() == …` |

**PR-F 的胜利**：verus_error → ok_with_witness。把"工具卡在 external_body
壳上"翻成"工具拆开壳后，把 spec 的真实漏洞（value 没钉）暴露出来"。

#### A-2 例 1 ── 自定义 struct 字段是 `Vec<u8>`

```rust
// 源
pub struct AbstractEndPoint { pub id: Vec<u8> }

fn make_endpoint(bytes: Vec<u8>) -> (r: AbstractEndPoint)
    ensures r.id@ == bytes@
```

ensures 钉了 `r.id@`（即 `id` 投到 `Seq<u8>` 的视图）—— **这次 spec 是 tight 的**。

| | 生成的 equal-fn | z3 反例 | verdict |
|---|---|---|---|
| 无 view-registry | `r1 == r2` —— `Vec` 结构 `==` 比 `ptr / cap / len`，是 runtime 噪音 | `r1.cap=8, r2.cap=16, 内容都等于 bytes@` —— **byte 层的 spurious 反例**，spec 层无意义 | **ok_with_witness（spurious）** —— 信号噪比低 |
| L4-synth view | `r1.view() == r2.view()`，`view()` 投到 `Seq<u8>` —— spec 层比较 | （unsat：`r1.view().id == bytes@ == r2.view().id`） | **ok_without_witness** |

**view-registry 的胜利**：把 spurious witness 翻成 `ok_without_witness`。等价于"剥掉 runtime
噪音后，spec 实际上够 tight，工具能 chain 出确定性"。

#### A-2 例 2 ── enum + 自递归类型

```rust
// 源
pub enum NodeEntry { Leaf(usize), Subdir(Box<PTDir>) }
pub struct PTDir { pub entries: Seq<Option<PTDir>> }

fn modify_tree(t: PTDir, k: usize) -> (r: PTDir)
    ensures r.entries.len() == t.entries.len()
```

ensures 故意只钉长度。

| | 生成的 equal-fn | z3 反例 | verdict |
|---|---|---|---|
| 无 view-registry | 递归落到 `Subdir(Box<PTDir>)` —— Verus spec 模式无 box-deref → fallback 用 box 指针 `==` | `r1.entries[0] = Subdir(Box@0x1000)`、`r2.entries[0] = Subdir(Box@0x2000)`，**指针不同但所指树同**（byte 层 spurious） | **ok_with_witness（spurious）** |
| L4-synth view + PR-E M4 lint | LLM 给 PTDir 选 Option C：`type V = Self`，view() 递归剥 Box —— equal-fn = `r1.view() == r2.view()`，在 spec 层做结构比较 | `r1.entries = seq![None, …]`、`r2.entries = seq![Some(child), …]`，长度相同但内容不同（**真正 spec 层差异**） | **ok_with_witness（meaningful）** |

**PR-E 的胜利**：**verdict 状态不变**（都是 ok_with_witness），但 witness 质量
从 spurious（指针噪音）翻成 meaningful（spec 层 underdetermined）。如果用户后续
把 ensures 紧到 `r =~= t` 之类，post 会变成 `ok_without_witness`，pre 仍是 spurious witness。

#### A-3 例 1 ── `Seq<Result<u32, MyErr>>` 输出

```rust
// 源
fn batch_lookup(keys: Vec<u32>) -> (r: Seq<Result<u32, MyErr>>)
    ensures r.len() == keys.len()

// policy: errs_equivalent = True（不同 Err 视为同一类）
```

ensures 只钉长度，不钉每位 Ok/Err 的分布也不钉 Ok 值。

| | 生成的 equal-fn（**由类型 + policy 决定**） | z3 反例 | verdict |
|---|---|---|---|
| PRE-PR-G | `r1 == r2` —— Seq 在 primitive `==` 列表里，policy 未生效 | `r1 = [Err(Foo("a"))], r2 = [Err(Foo("b"))]`：内容不同 → `==` false；MyErr 可能是 external_body，Verus 报错 | **verus_error** —— 工具被 Err 内容卡住，看不到 spec 层 |
| POST-PR-G | `r1.len() == r2.len() && forall\|i: int\| 0 <= i < r1.len() ==> ((r1[i] is Ok) == (r2[i] is Ok)) && ((r1[i] is Ok) ==> (r1[i]->Ok_0 == r2[i]->Ok_0))` | `r1 = [Ok(5)]`、`r2 = [Ok(7)]`：长度同、discriminator 同（都 Ok），但 Ok 值不同 | **ok_with_witness（meaningful）** —— 信号：ensures 没钉 per-index 的 Ok/Err 分布和 Ok 值 |

**PR-G 的胜利**：verus_error → ok_with_witness。policy（errs_equivalent）让 Err
内容差异不再阻碍工具；但 spec 没钉 Ok 值这件事被真实暴露。

#### A-3 例 2 ── `Map<Key, Result<Val, Err>>` 字段

```rust
// 源
pub struct ResultCache { pub entries: Map<Key, Result<Val, CacheErr>> }

fn populate(keys: Set<Key>) -> (r: ResultCache)
    ensures r.entries.dom() == keys
```

ensures 只钉 `dom`，不钉每个 key 上的值。

| | 生成的 equal-fn 片段 | z3 反例 | verdict |
|---|---|---|---|
| PRE-PR-G | `r1.entries == r2.entries` —— Map 落到 UNKNOWN 的 `==` 回退 | 两个 `Err` 内容不同 → false；CacheErr external_body | **verus_error** |
| POST-PR-G | `r1.entries.dom() == r2.entries.dom() && forall\|k: Key\| r1.entries.dom().contains(k) ==> ((r1.entries[k] is Ok) == (r2.entries[k] is Ok)) && ((r1.entries[k] is Ok) ==> (r1.entries[k]->Ok_0 == r2.entries[k]->Ok_0))` | `dom={k0}`、`r1.entries[k0]=Ok(v1)`、`r2.entries[k0]=Ok(v2)`：dom 同、discriminator 同（都 Ok）、Ok 值不同 | **ok_with_witness（meaningful）** —— 信号：ensures 没钉每个 key 上的 Result 内容 |

**PR-G 的胜利**：同 A-3 例 1，verus_error → meaningful witness。

---

## 2. 解法：View Registry（视图注册表）

### 2.1 核心 idea

Verus 里 `impl View for T` 是一种"从 runtime struct 投影到 spec struct"
的 trait。如果给每个类型都备好 `View`，等式函数就可以：

```rust
fn equal_fn(r1: T, r2: T) -> bool {
    r1.view() == r2.view()    // spec 层比较，避开 Vec/字节级 noise
}
```

z3 只在 spec 层推理 → witness 减少（A-2）+ narrow 维度增多（A-1）。

### 2.2 View 来源 —— 4 层解析器（L1–L4）

| 层 | 来源 | 例子 |
|---|---|---|
| **L1** | Verus prelude（hand-coded） | `Vec → Seq`, `HashMap → Map` |
| **L2** | Type alias 展开 | `Pcid = usize` → 透明 |
| **L3** | 项目源里现成的 `impl View for T` | scan 出 atmosphere 自带的 ~50 个 View |
| **L4** | **LLM-synth**（Copilot CLI） | 没人写过的类型，让模型现编 |

L1+L2+L3 是机械层；L4 是新东西，把 spec 工程"剩下的活" off-load 给模型。

---

## 3. 建造过程（commit 时间线）

```
view/ 子包搭骨架          8dc1c20  2026-04-30
L3 scan                  5ea750b  → audit per-project
L1+L2+L3 resolver        b65d37f  PR-B
gen_det 接入 registry    5a67804  PR-C
L4 LLM synth (offline)   f094843  PR-D1
L4 缓存接入 gen_det      1f7a245  PR-D2
跨子包 refactor          226d93f  → 后来 1751dc1 修了 import bug
LLM backend 抽出         ab5f5d6  → 给 codegen/policy_llm 复用
codex critic pass        f47125f  → 给 L4 加事后检查
prefill 批跑工具         aaa4059
critic_reject 状态        aa0744e
wait-for-prefill chain   7531eeb  scripts/auto_chain.sh
M1/M2/M3 lint sketch     ad691cd  static lint：view body must reference self
quarantine 14 broken     a71ff15  + M1/M2/M3 detector spec
PR-D4 final              4cd29b4  11 wins / 0 regress / -10 witness
PR-D5: M1/M2/M3 impl     e61a504  retroactive scan → +4 quarantines
PR-E: M4 + 自递归 prompt 513d8d9
PR-F + PR-G              4eb7376  Tracked/Ghost/PointsTo + 嵌套-Err
```

---

## 4. 四个最近 PR（Phase 2 收官）

### 4.1 PR-D5 — M1/M2/M3 lint 实装

**问题**：L4 LLM 合成的 view 偶尔静默错误（比如 `field@` 投影到一个根本没
`View` impl 的类型上 → Verus 后期才报错或干脆产出错的 spec）。

**对策**：三个 tree-sitter-based 静态 lint，在 L4 cache 时拒收：

| 规则 | 拒掉什么 |
|---|---|
| **M1** | `field@` 或 `<Inner as View>::V` 调用在**无 registered View** 的类型上 |
| **M2** | `field@@` 过度投影穿过 `Ghost<…>` 进入 `Set`/`Map` 等无变身类型 |
| **M3** | view body 使用 `self.<field>`，但 parent 是 `external_body` / opaque 类型 |

**关键 deviation（实装时发现）**:

- M2 实际上只对 `FnSpec` 这种"non-viewable head"敏感；其他情况大多是合法递归
- M3 给"unit-V"（`type V = ()`）开了豁免
- M1 honour `impl<G>` 的泛型参数（不能把 `T@` 当 "T 无 View" 处理）

**Retroactive scan**：把 lint 跑过**所有**已缓存的 view（包括没被
quarantine 的）→ 又抓出 4 个隐藏错误，新增 quarantine。

---

### 4.2 PR-E — M4 lint + 递归视图 prompt 引导

**Pivot**：原计划是 "整 SCC 一起 prompt"（强连通分量整组喂给 LLM）。
跑了 `discover_sccs.py` 后发现：9 个项目里**只有 1 个**多类型 SCC
（nrkernel 的 `{Directory, NodeEntry}`，且 L4 cache 已覆盖）。
所以 PR-E 没真目标 → 转向另一个剩下的问题。

**新目标**：自递归（`T` 在自己的字段里 wrap-recursive 出现）。
典型 bug：PTDir 类型 `pub struct PTDir { pub entries: Seq<Option<PTDir>>, ... }`
LLM 倾向于写：

```rust
pub struct PTDirView { entries: Seq<Option<PTDirView>>, ... }  // V 里递归位置换成 View
impl View for PTDir {
    type V = PTDirView;
    fn view(&self) -> PTDirView {
        PTDirView { entries: self.entries@, ... }              // bare @ 不会 descend
    }
}
```

但 `<Seq<Option<T>> as View>::V = Seq<Option<T>>`（identity） →
`self.entries@` 仍是 `Seq<Option<PTDir>>`，不会自动变成
`Seq<Option<PTDirView>>`。这会让 V 声明和 body 类型不匹配；如果用别的
绕法把类型凑过去，也容易留下结构比较 / 错误抽象的 silent bug。

**M4 lint**：catch 这一类 —— V 的递归位置里出现 `TView`，但 body 写 bare
`self.f@`。`lint_view_decl` priority: **M3 > M2 > M4 > M1**。

**Prompt 改造**：`view/llm.py` 的 `_VIEW_SCHEMA_DOC` 加了 80 行
"Self-recursive types" 章节，列三条路：

- **Option A**：递归 lift（`PTDirView { entries: Seq<Option<PTDirView>> }`）+
  显式 `Seq::new` / `match` lifting，最贵
- **Option B**：V mirror concrete inner（`PTDirView { entries: Seq<Option<PTDir>> }`），
  body 直接复制 `self.entries`，中等
- **Option C**：`type V = Self` + body `*self`，最便宜

且 `build_view_prompt` 在检测到自递归类型时，在 schema doc 之前**显式插入一段
告警**，把 offending field 名字 callout 出来（不是只让 LLM 自己读出问题）。

`_FEW_SHOT` 加了一个 Tree（Option C）的样例。

---

### 4.3 PR-F — A-1: Tracked/Ghost/PointsTo

**问题**：Verus 里 `Tracked<T>` / `Ghost<T>` / `PointsTo<V>` 是常见的
permission/ghost wrapper。Extractor 之前把它们都归到 `TypeKind.UNKNOWN`，
导致：

1. **Schema enumeration**: 0 个维度 emit（z3 没有 narrow 入口）
2. **Equal-fn**：fallback `r1 == r2`，对结构来说语义对，但 z3 看不到内部
3. **Narrow strategies**: 走 `narrow_unknown`，部分 witness

更糟糕：full-path `vstd::pcell::Tracked<T>` 因为 tree-sitter 把它的名字节点
当成 `scoped_type_identifier`（不是 `type_identifier`），extractor
直接把整串 `vstd::pcell::Tracked<T>` 当类型名 → 永远 match 不上 generics 表。

**修复**（4 个文件）：

| 文件 | 改动 |
|---|---|
| `extract/types.py` | 新增 `TypeKind.TRACKED / GHOST / POINTS_TO` |
| `extract/extractor.py` | `_KNOWN_GENERICS` 加 3 项；`_parse_type_node` 接受 `scoped_type_identifier`、剥掉 `vstd::pcell::` 前缀 |
| `extract/narrow.py` | `narrow_tracked_or_ghost`（`@` 投影后递归）；`narrow_points_to`（探 `is_init()` / `value()` / `addr()`） |
| `codegen/gen_det.py build_equal_expr` | TRACKED/GHOST → `({lhs})@` 递归；POINTS_TO → 三个探针 conjunction |
| `schema_search/schemas.py _emit` | 同三个新 kind 出 schema（否则 narrow 的 assume 都 `pass_untranslatable`） |

**关键洞察 1：组合性**
PR-F 的 `({lhs})@` 递归到内层 `EventResults`（UNKNOWN+View）后，
自动接上 PR-D2 的 `.view()` 投影 → equal-fn 一行串起来：

```rust
spec fn equal(r1: Ghost<EventResults>, r2: Ghost<EventResults>) -> bool {
    ((((r1)@).view() == ((r2)@).view()))     // PR-F outer @, PR-D2 inner .view()
}
```

**关键洞察 2：schema 必须同步扩展**
narrow 写 `(g)@.recvs.len() == k`，但如果 `_emit` 没 emit 对应 schema，
search 看不懂这个 assume → 退回 `pass_untranslatable` → narrow 失败。
所以 narrow + schema **必须**一起改。

---

### 4.4 PR-G — A-3: 嵌套 Err 策略

**问题**：`EqualPolicy.errs_equivalent=True` 让 `Result<T, Err>` 把所有
`Err` 收成一类，但只在**最外层 Result** 工作。

```rust
// ❌ 失效场景
fn foo() -> Seq<Result<u32, MyErr>>;
// equal-fn 自动生成：
fn equal(r1, r2) -> bool { r1 == r2 }    // Seq 在原代码里是 primitive == 列表
// → 两条 Seq 里 Err 内容不同就 false，policy 完全没生效
```

**修复**（一个文件 `gen_det.py`）：

```python
# 1. 新增 _contains_result(ty) —— 递归扫 type_args + fields；id() 防自引用环
# 2. 新增 _container_needs_elementwise(ty, policy) —— 当 collapse-err && 内有 Result 才 true
# 3. TypeKind.SEQ 从 primitive == 列表里抽出来：
#    elementwise needed → forall|i: int| 0 <= i < len ==> elem_eq
#    否则 → 老 fast path == 
# 4. TypeKind.MAP 同上：dom == + forall|k| dom.contains(k) ==> val_eq
# 5. TypeKind.SET 留 ==（不能 lift —— Set 没 positional 索引，
#    要 lift 得自定义 set 等价关系；记入 known limitation）
```

---

## 5. 工程实践

### 5.1 Quarantine 体系

`.quarantine` 后缀文件 = 已知坏 view，跳过加载。L4 prefill 的失败 case
还会写进 `_rejected.jsonl`（durable log，下次重试可读）。

`view/llm.py --include-quarantined` 控制是否重试 quarantine。

### 5.2 Critic pass

L4 缓存前先过一道 **codex critic**（独立 LLM 调用）：

```
prompt → "下面这段 view 看起来对吗？请 verdict accept / revise / reject"
```

- `accept` → 缓存
- `revise` → **仍然缓存**；把 critic 的意见记录到 `critic_issues`，供人工后续审
  （当前实现不会自动触发重生成）
- `reject` → 写 `_rejected.jsonl`

Critic 的 acceptance criteria 写在 `docs/critic-criteria.md`，被 prompt 引用，
也是给未来 LLM caller 的契约。

### 5.3 Lint pipeline 演进

```
PR-D5  → M1 (无 View 类型上的 field@)
        M2 (Ghost 穿透到 Set/Map)
        M3 (external_body 上的 self.field)
PR-E  → M4 (自递归类型的 bare self.f@)

priority: M3 > M2 > M4 > M1
```

每条规则都有 acceptance fixtures = 对应的 quarantined view（reject）+ 4 个
winning view（accept controls）。

### 5.4 Compare 框架

`scripts/compare_runs.py` 拿 baseline vs candidate 出 transition table：

```
fixed         witness → ok          (脚本原文；含义是 ok_without_witness，真 win)
witness → verus_error              (view 编译但阻塞，不算 win)
regressed     clean ok → verus_error  (脚本原文；无 witness 的 raw ok，必须 ≈ 0 才能 land)
```

`scripts/auto_chain.sh` 把 "等 prefill → rerun → compare" 串成一条链。

---

## 6. 数字

口径：下面的 `witness` 都指派生 bucket `ok_with_witness`，是 raw `ok`
的子集；所以 `ok + witness + verus_error` 不能相加等于 `n`。

### 6.1 Baseline (`42c1248`, 2026-04-29)

```
n=1647  ok=1455  witness=376  verus_error=191  runner_crash=1
```

### 6.2 Post-quarantine + PR-D5 + PR-E (`33bd09a`, 2026-05-11)

```
ok=1456 (+1)  witness=366 (-10)  verus_error=190 (-1)
```

**11 真 wins**（quarantine cascade 误伤 1 个，所以净 10 witness 修复 + 0 regress）

### 6.3 Post-PR-F + PR-G (`4eb7376`, atmosphere rerun 进行中)

预测：A-1 (~29) + A-3 (~30) cohort 应该 drop verus_error 到 ~130
区间。Atmosphere 进度 69%（2026-05-12 较新快照：944/1363），ETA ~30 分钟。

**Per-target cost +62%**（4.89s → 7.93s/target，schema 增多导致 SMT 文件
更大）。属于 expected tradeoff。

---

## 7. 关键技术 take-away

1. **L4 LLM synth + critic + lint** —— 把"生成"和"验证"解耦。LLM 负责
   提议，static lint + critic 负责守门。**Retroactive scan** 是
   defense-in-depth：一旦发现新 bug class，扫所有历史 cache 看有没有
   同形态隐藏 bug。

2. **Schema / narrow / equal-fn 三者必须同步演进**。PR-F 任何一个
   单独改都会出现"narrow 写出 z3 看不懂的 assume" 或 "equal-fn
   引用一个 z3 不认识的投影"。这条贯穿所有 axis 优化。

3. **Quarantine 而非删除**。坏 view 留在磁盘但加后缀 → 可审计、可
   重试、可对比。`_rejected.jsonl` durability 让失败也是数据。

4. **Compose-by-recursion 是干净 abstraction**。PR-F 的 `({lhs})@`
   一行不知道也不关心 inner 是什么，PR-D2 的 `.view()` 同样。两个独立
   PR 在 atmosphere/ironkv 的 Ghost 字段上自动复合出 `((r1)@).view()`，
   零额外代码。

5. **预测 → quarantine → 再 rerun** 循环是 debuggable 的。PR-D4 final
   预测 "11 wins / 0 regress / -10 witness" → 实际 "10 wins / 0 regress /
   -10 witness"（1 个被 cascade 误伤）。误差小 = 模型对 → 下次可以更
   confident。

---

## 8. 未关项 / 下一步

- 🟡 **integration smoketest**（ISSUES.md #5）—— 单 target end-to-end，
   wired into `make check`。会拦截类似 `1751dc1` 的 cross-subpackage
   import regression（之前手动 rerun 才发现）。
- 🟡 **`results-verusage/view_registry/` 的版本管理决策** —— git
   vs DVC vs S3。当前 untracked（112 entries + 23 quarantine + audit JSONs）。
- ⏳ **Newtype-of-`usize` unwrap**（如 `struct ProcPtr(pub usize)`）—— A-1
   follow-up，需要 cross-file type resolution。
- ⏳ **Atmosphere rerun 完成后** —— 写 final `COMPARE.md` 落数字到 STATUS.md。
- ⏳ **4 个 `_rejected.jsonl` 类型重试** —— CrcDigest / PTDir / LoadResult /
   MaybeCorruptedBytes。M1-M4 + critic 现在 strict enough 可以放心 retry。

---

## 9. 一句话 abstract

> Phase 2 给 spec-determinism 装上了一套**多层 view 解析器**（机械 L1-L3
> + LLM L4），并通过四条 static lint + critic + quarantine 把 LLM 引入
> 的不可靠性约束在可审计的范围内。在不改 baseline 工具链的前提下，
> 376 witness 已减到 366（10 真 wins / 0 regress），191 verus_error
> 在 PR-F+PR-G 后预计进一步减少 ~50。
