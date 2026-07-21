# vstd specification survey

本目录给出 Verus `vstd` 的 module 级规范全景，并保留可重复运行的扫描器与结构化数据。

接手本工作的首要入口是 [`HANDOFF.md`](HANDOFF.md)。其中包含方法、代码改动、
实验结果、已知覆盖缺口、复现命令和下一步优先级。如果你刚接触这个 research，
建议先读 [`TUTORIAL.md`](TUTORIAL.md)——从问题动机到当前结论的教学式讲解。

当前快照：

- Repository: `verus-lang/verus`
- Commit: `cf3b5c3fb937b9effa9478d4735b49743d8646eb`
- Commit date: 2026-07-13
- Scope: 完整的 `source/vstd`，不排除 `std_specs`、`contrib` 或任何其他 module
- `build.rs` 不计入 Rust module；其余共 125 个 module、52,715 行源码

## 一页结论

`vstd` 不是单纯的“标准库函数 specs 集合”，而是由八层内容组成：

1. 数学语义基础：`Seq`、`Set`、`Map`、`View`、关系与算术定理；
2. Rust 标准库 trusted contracts：`std_specs/*`；
3. 可执行容器和数据类型：`HashMap`、`HashSet`、字符串、数组和字节；
4. 内存与所有权模型：raw pointer、cell、permission 和 invariant；
5. 并发、prophecy 与异步模型；
6. resource algebra 与状态协议；
7. 实验性的 `contrib::exec_spec`；
8. prelude、宏和 verifier encoding 基础设施。

源码中共有 **3,367 个 specification-related declaration sites**：

| 类型 | 数量 | 含义 |
|---|---:|---|
| API contract sites | 515 | 185 个 exec/trait 后置条件，加上 330 个带后置条件的 `assume_specification` |
| Mathematical `spec fn` | 1,375 | 状态模型、view、抽象操作和辅助谓词 |
| `proof fn` | 1,319 | 可验证引理和 proof automation |
| `axiom fn` | 158 | trusted axioms 或编译器/标准库桥接 |

对 spec-determinism 最重要的是 **515 个 contract sites**，而不是全部 3,367 个声明：

- 64.1% 的 contract surface 来自 trusted `assume_specification`；
- 35.9% 来自 exec function 或 trait method 的后置条件；
- 47 个 `critical`/`high` module 已覆盖 440/515，即 **85.4%** 的 contract surface。

因此不需要一开始平均处理全部 125 个 module。

## 完整 vstd exec fn 统计

下面只统计 exec function/method；`spec fn`、`proof fn` 和 `axiom fn` 均不计入。

| 源码级口径 | 全部 | Public |
|---|---:|---:|
| 有函数体的 exec definitions | 220 | 126 |
| 其中有明确 postcondition | 177 | 111 |
| 只有 `requires`、没有 postcondition | 6 | 6 |
| `requires` 和 postcondition 都没有 | 37 | 9 |
| 没有 postcondition合计 | 43 | 15 |
| 只有 trait/signature、没有函数体的 exec declarations | 66 | 64 |

因此，“exec fn 没有 spec”有两个常用口径：

- 如果指既没有 `requires`，也没有 `ensures`、`returns` 或 `default_ensures`：
  **全部 37 个，public 9 个**；
- 如果只要求“没有 postcondition”，即允许存在 `requires`：
  **全部 43 个，public 15 个**。

15 个没有 postcondition 的 public exec definitions 主要是：

| 类别 | 数量 | 例子 |
|---|---:|---|
| invariant/compiler encoding | 5 | `open_atomic_invariant_begin`、`open_invariant_end` |
| pervasive runtime/internal helpers | 5 | `runtime_assert`、`print_u64`、panic helpers |
| intentional prophecy nondeterminism | 1 | `Prophecy::new` |
| linear resource-consuming operations | 4 | `deallocate`、`free`、`release_read`、`release_write` |

这些项目目前没有明显属于“普通 public API 遗漏 postcondition”的案例。trait
signature 不与有函数体的 definition 混算，因为其语义可能由实现、external trait
specification 或 `exec_spec` 宏提供。

## 计数口径

扫描器把不同性质的内容分开统计：

- **Exec body/signature**：区分有函数体的 `function_item` 与只有声明的 trait method；
- **Exec post**：普通函数或 trait method 上的 `ensures`、`returns`、`default_ensures`；
- **Assume post/all**：带后置条件的 `assume_specification` / 所有 `assume_specification`；
- **Model spec fn**：`spec fn`、`open spec fn`、`closed spec fn`、`uninterp spec fn`；
- **Proof/Axiom**：证明引理和 trusted axioms；
- **Total spec sites**：以上四类声明点之和。

这些数字是**源码声明点数量**：

- 宏模板只计一次，不按整数类型等实际展开次数重复计算；
- 数字表示规范密度，不直接表示覆盖率、正确性或完整性；
- `no explicit postcondition` 不自动等于缺失 spec，它可能来自 trait 继承、compiler intrinsic 或有意非确定性。

## 总体结构

| 层次 | Modules | Lines | Contract sites | Total spec sites | 主要作用 |
|---|---:|---:|---:|---:|---|
| Mathematical foundations | 36 | 19,954 | 0 | 1,111 | 定义抽象语义和证明库 |
| Rust standard-library specs | 26 | 9,115 | 303 | 869 | Rust/core/alloc/std 的 trusted contracts |
| Runtime collections and data | 11 | 5,075 | 97 | 388 | vstd 自身的可执行数据结构 |
| Memory and ownership | 6 | 2,701 | 51 | 142 | pointer、cell 和 ownership permissions |
| Concurrency and prophecy | 9 | 3,497 | 13 | 96 | atomic、invariant、thread、future、prophecy |
| Resources and protocols | 23 | 9,349 | 0 | 635 | separation-style resource algebra |
| Experimental exec-spec | 8 | 1,637 | 48 | 51 | executable/spec 双表示实验 |
| Infrastructure | 6 | 1,387 | 3 | 75 | prelude、宏和 verifier encoding |

最明显的结构性结论是：

- 数学基础与 resource/protocol 占据大量源码和 proof，但几乎没有直接 API contract；
- `std_specs/*` 单独承载 303/515，即 **58.8%** 的 contract surface；
- `std_specs/*`、runtime data、memory/ownership 三层合计承载 **87.6%** 的 contract surface。

## 重要 module

### 1. 语义基础：决定“什么叫相等”

| Module | 作用 | 对 determinism 的意义 |
|---|---|---|
| `view` | 从 exec representation 投影到数学对象 | equal-fn 应优先比较 view，而不是内存表示 |
| `seq`, `set`, `map`, `multiset` | 核心数学容器 | 大量 std/runtime contracts 的共同语义 |
| `*_lib` | 容器引理、extensionality、自动证明 | 决定 SMT 能否完成确定性证明 |
| `function` | closure 的 `requires`/`ensures` 模型 | 高阶 API 是否确定取决于 closure contract |
| `laws_eq`, `laws_cmp`, `relations` | equality/order/relation laws | trait specs 的逻辑基础 |

这些 module 本身不应作为第一批 API completeness corpus，但必须先理解，否则容易把 representation difference 当作 spec gap。

### 2. Trusted Rust contracts：最核心的审计对象

contract site 最多的稳定 module：

| Module | Contract sites | 重点 |
|---|---:|---|
| `std_specs::hash` | 45 | HashMap/HashSet、iterator order、hasher model |
| `std_specs::num` | 34 | checked/wrapping/saturating integer operations |
| `std_specs::vec` | 29 | `Vec` 的 mutation、capacity-independent view |
| `std_specs::btree` | 24 | BTreeMap/BTreeSet 与 entry API |
| `std_specs::option` | 20 | Option methods 与 comparison trait specs |
| `std_specs::vecdeque` | 19 | 双端序列及其 view |
| `std_specs::range` | 18 | range 与 iterator semantics |
| `std_specs::bits` | 16 | primitive bit operations |
| `std_specs::cmp` | 14 | `PartialEq`/`Ord` external trait specs |
| `std_specs::slice` | 13 | slice access、mutation 和 range indexing |

这一层的 spec 是 trusted axioms：determinism 可以检查它是否过弱，但不能证明真实 Rust 实现满足该 spec。

### 3. 可执行数据结构：最容易先跑通

| Module | Contract sites | 特点 |
|---|---:|---|
| `string` | 26 | 10 个 exec post，加上 16 个 assumed std contracts |
| `hash_map` | 22 | 直接实现，抽象语义应使用 `Map` view |
| `hash_set` | 20 | 直接实现，抽象语义应使用 `Set` view |
| `array` | 5 | 小而清晰，适合作为第一个 smoke corpus |
| `bytes` | 8 | first-order API 较多，语义歧义较少 |

`array`、`bytes` 和简单的 `string` API 是最适合验证新 runner 的第一批目标。

### 4. 内存与所有权：高价值但语义困难

| Module | Contract sites | 风险 |
|---|---:|---|
| `raw_ptr` | 25 | address/provenance/allocator identity 可能有意非确定 |
| `simple_pptr` | 14 | pointer identity 与 tracked permission 必须一起解释 |
| `cell` | 12 | value 与 ownership token 的关系 |
| `cell::pcell*` | 少量 | freshness、uninitialized state、exclusive permissions |

这一层不能默认使用 raw structural equality。应优先比较 view、`mem_contents()` 或 permission observable projections。

### 5. Specialized proof systems

`resource::*`、`tokens`、`atomic`、`invariant`、`proph`、`future`、`thread` 和 `logatom` 很重要，但主要用于：

- resource algebra；
- linear/tracked ownership；
- prophecy/final-state reasoning；
- atomic invariant 和 concurrent protocol。

它们包含大量 spec/proof 声明，却不是第一批单函数 determinism audit 的最佳目标。很多非唯一值是设计语义，而非缺失后置条件。

## 推荐审计顺序

1. **Runner smoke**：`array`、`bytes`、简单 `string` API；
2. **低歧义 trusted specs**：`std_specs::option`、`result`、`range`、`slice`、`vecdeque`；
3. **高影响 trusted specs**：`vec`、`btree`、`hash`；
4. **边界条件专项**：`std_specs::num`；
5. **语义困难层**：`raw_ptr`、`cell`、`atomic`、`invariant`、`proph`；
6. **证明库/协议层**：使用不同于单函数 determinism 的 obligation 再审计。

需要特别注意：

- `std_specs::hash` 的迭代顺序常常是有意非确定；
- `std_specs::num` 可能出现“确定但错误”的过强 spec，determinism 无法发现；
- `raw_ptr` 和 allocator API 的地址不同不应自动判为 spec gap；
- closure-based API 需要先明确 closure 是否要求 pure/deterministic。

## 数据质量说明

当前安装的 `tree-sitter-verus` 落后于最新 vstd 语法，125 个 module 中有 54 个触发 parse recovery，主要涉及：

- `default_ensures`；
- 宏模板；
- 新的 trait/external-spec syntax。

此外，scanner 目前不会进入 `verus_! { ... }` 这种 `verus!` 的别名宏。
因此 `cell::invcell`、`cell::pcell`、`cell::pcell_maybe_uninit` 以及部分
`std_specs` module 在表格中可能显示 `Parse error` 为空、exec 数量为 0，
但这表示“宏体未被解析”，不表示模块真的没有 exec/spec surface。完整列表、
影响和修复优先级见 [`HANDOFF.md`](HANDOFF.md)。

扫描器对 `assume_specification`、`returns` 和 `default_ensures` 使用 lexical fallback，因此 contract 总数仍可用于总体规划；但对 parse-error module 的精确 function-level 列表必须在后续升级 grammar 后重新生成。

另有 385 个 `assume_specification` 源码声明点，其中 55 个没有显式 postcondition。这 55 个必须逐项区分：

- trait-level contract 已经提供语义；
- compiler intrinsic 或 verifier encoding；
- 有意非确定；
- 真正缺失的 spec。

## 目录内容

- `TUTORIAL.md`：教学文档——这个 research 在解决什么问题、方法、结果与下一步（新人先读这里）；
- `README.md`：唯一的阅读文档，包含总体说明和全部 125 个 module 的逐项表格；
- `generated/inventory.json`：完整结构化 inventory；
- `generated/modules.csv`：每个 module 一行；
- `generated/groups.csv`：按层次聚合；
- `generated/exec_functions.csv`：全部 exec definitions/signatures，包含 module、行号和 contract 状态；
- `scan_vstd.py`：可重复运行的扫描器。
- `run_determinism.py`：复用现有 spec-determinism pipeline 的 vstd determinism runner。
- `experiments/pilot-2026-07-14/SUMMARY.md`：首批 `array`/`bytes` determinism 结果。
- `experiments/REVIEW-2026-07-14.md`：全部 111 个 public exec definitions 的综合实验结论。
- `experiments/UNKNOWN-AUDIT-2026-07-15.md`：原 27 个 unknown 的逐项语义审计。
- `experiments/impl-methods-2026-07-14/SUMMARY.md`：77 个 line-qualified impl methods 的逐项结果。

## Regenerate

```bash
python vstd-survey/scan_vstd.py \
  --vstd-root /path/to/verus/source/vstd \
  --commit <verus-commit> \
  --snapshot-date YYYY-MM-DD \
  --source verus-lang/verus:source/vstd \
  --out-dir vstd-survey/generated
```

<!-- BEGIN GENERATED MODULE INVENTORY -->

## Appendix: generated module inventory

- Snapshot: `verus-lang/verus:source/vstd`
- Commit: `cf3b5c3fb937b9effa9478d4735b49743d8646eb`
- Snapshot date: `2026-07-13`
- Counting unit: source declaration sites; macro templates count once.
- `Total spec sites` = exec postconditions + assume specs with postconditions + model spec fns + proof fns + axiom fns.

## Group summary

| Group | Modules | Lines | Exec bodies | Public exec | Public no-post | Signature-only | Contract sites | Total spec sites | Parse errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Mathematical foundations | 36 | 19954 | 0 | 0 | 0 | 0 | 0 | 1111 | 14 |
| Rust standard-library specs | 26 | 9115 | 0 | 0 | 0 | 8 | 303 | 869 | 10 |
| Runtime collections and data | 11 | 5075 | 72 | 60 | 0 | 13 | 97 | 388 | 8 |
| Memory and ownership | 6 | 2701 | 47 | 41 | 2 | 0 | 51 | 142 | 3 |
| Concurrency and prophecy | 9 | 3497 | 23 | 20 | 8 | 0 | 13 | 96 | 6 |
| Resources and protocols | 23 | 9349 | 0 | 0 | 0 | 0 | 0 | 635 | 6 |
| Experimental exec-spec | 8 | 1637 | 70 | 0 | 0 | 43 | 48 | 51 | 3 |
| Infrastructure | 6 | 1387 | 8 | 5 | 5 | 2 | 3 | 75 | 4 |

## Per-module inventory

| Module | Group | Importance | Lines | Exec bodies | Public exec | Public post | Public requires-only | Public no-contract | Signature-only | Assume post/all | Model spec fn | Proof+axiom | Parse error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `function` | Mathematical foundations | critical | 164 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 2 | 5 | yes |
| `map` | Mathematical foundations | critical | 491 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 11 | 22 |  |
| `map_lib` | Mathematical foundations | critical | 837 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 24 | 27 | yes |
| `multiset` | Mathematical foundations | critical | 727 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 21 | 32 | yes |
| `multiset_lib` | Mathematical foundations | critical | 68 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 2 | 3 |  |
| `seq` | Mathematical foundations | critical | 1154 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 21 | 47 | yes |
| `seq_lib` | Mathematical foundations | critical | 3761 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 52 | 141 | yes |
| `set` | Mathematical foundations | critical | 641 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 27 | 26 | yes |
| `set_lib` | Mathematical foundations | critical | 1433 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 30 | 64 | yes |
| `view` | Mathematical foundations | critical | 344 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 24 | 0 | yes |
| `arithmetic` | Mathematical foundations | medium | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `arithmetic::div_mod` | Mathematical foundations | medium | 1664 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 76 | yes |
| `arithmetic::internals` | Mathematical foundations | medium | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `arithmetic::internals::div_internals` | Mathematical foundations | medium | 348 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 5 | 6 |  |
| `arithmetic::internals::div_internals_nonlinear` | Mathematical foundations | medium | 47 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 3 |  |
| `arithmetic::internals::general_internals` | Mathematical foundations | medium | 116 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1 | 3 |  |
| `arithmetic::internals::mod_internals` | Mathematical foundations | medium | 535 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 4 | 12 |  |
| `arithmetic::internals::mod_internals_nonlinear` | Mathematical foundations | medium | 79 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1 | 5 |  |
| `arithmetic::internals::mul_internals` | Mathematical foundations | medium | 235 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 8 |  |
| `arithmetic::internals::mul_internals_nonlinear` | Mathematical foundations | medium | 87 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 6 |  |
| `arithmetic::logarithm` | Mathematical foundations | medium | 159 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1 | 5 | yes |
| `arithmetic::mul` | Mathematical foundations | medium | 461 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 32 |  |
| `arithmetic::overflow` | Mathematical foundations | medium | 307 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 4 | 0 |  |
| `arithmetic::power` | Mathematical foundations | medium | 558 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1 | 20 | yes |
| `arithmetic::power2` | Mathematical foundations | medium | 343 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 11 |  |
| `bits` | Mathematical foundations | medium | 484 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1 | 10 |  |
| `compute` | Mathematical foundations | medium | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 1 |  |
| `imap` | Mathematical foundations | medium | 495 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 10 | 20 |  |
| `imap_lib` | Mathematical foundations | medium | 831 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 24 | 26 | yes |
| `iset` | Mathematical foundations | medium | 1081 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 30 | 42 | yes |
| `iset_lib` | Mathematical foundations | medium | 1541 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 22 | 60 | yes |
| `laws_cmp` | Mathematical foundations | medium | 286 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 5 | 7 |  |
| `laws_eq` | Mathematical foundations | medium | 413 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 6 | 22 |  |
| `math` | Mathematical foundations | medium | 76 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 8 | 0 |  |
| `predicate` | Mathematical foundations | medium | 18 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 2 | 0 |  |
| `relations` | Mathematical foundations | medium | 113 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 17 | 1 |  |
| `std_specs::cmp` | Rust standard-library specs | critical | 527 | 0 | 0 | 0 | 0 | 0 | 0 | 14/24 | 39 | 0 |  |
| `std_specs::hash` | Rust standard-library specs | critical | 1553 | 0 | 0 | 0 | 0 | 0 | 0 | 45/45 | 64 | 43 | yes |
| `std_specs::iter` | Rust standard-library specs | critical | 540 | 0 | 0 | 0 | 0 | 0 | 0 | 1/1 | 39 | 2 |  |
| `std_specs::num` | Rust standard-library specs | critical | 474 | 0 | 0 | 0 | 0 | 0 | 0 | 34/50 | 13 | 0 |  |
| `std_specs::ops` | Rust standard-library specs | critical | 514 | 0 | 0 | 0 | 0 | 0 | 0 | 10/12 | 17 | 0 | yes |
| `std_specs::option` | Rust standard-library specs | critical | 412 | 0 | 0 | 0 | 0 | 0 | 0 | 20/23 | 22 | 8 | yes |
| `std_specs::range` | Rust standard-library specs | critical | 658 | 0 | 0 | 0 | 0 | 0 | 2 | 18/18 | 61 | 2 | yes |
| `std_specs::result` | Rust standard-library specs | critical | 284 | 0 | 0 | 0 | 0 | 0 | 0 | 10/10 | 19 | 8 | yes |
| `std_specs::slice` | Rust standard-library specs | critical | 265 | 0 | 0 | 0 | 0 | 0 | 0 | 13/15 | 17 | 1 |  |
| `std_specs::vec` | Rust standard-library specs | critical | 535 | 0 | 0 | 0 | 0 | 0 | 0 | 29/30 | 20 | 10 |  |
| `std_specs::alloc` | Rust standard-library specs | high | 41 | 0 | 0 | 0 | 0 | 0 | 0 | 1/3 | 0 | 0 |  |
| `std_specs::atomic` | Rust standard-library specs | high | 105 | 0 | 0 | 0 | 0 | 0 | 0 | 0/14 | 0 | 0 |  |
| `std_specs::bits` | Rust standard-library specs | high | 726 | 0 | 0 | 0 | 0 | 0 | 0 | 16/16 | 16 | 16 |  |
| `std_specs::btree` | Rust standard-library specs | high | 977 | 0 | 0 | 0 | 0 | 0 | 0 | 24/24 | 49 | 26 | yes |
| `std_specs::clone` | Rust standard-library specs | high | 73 | 0 | 0 | 0 | 0 | 0 | 1 | 5/6 | 0 | 0 |  |
| `std_specs::convert` | Rust standard-library specs | high | 182 | 0 | 0 | 0 | 0 | 0 | 4 | 3/5 | 16 | 0 |  |
| `std_specs::default` | Rust standard-library specs | high | 83 | 0 | 0 | 0 | 0 | 0 | 1 | 6/6 | 0 | 0 |  |
| `std_specs::maybe_uninit` | Rust standard-library specs | high | 59 | 0 | 0 | 0 | 0 | 0 | 0 | 5/5 | 4 | 0 |  |
| `std_specs::smart_ptrs` | Rust standard-library specs | high | 78 | 0 | 0 | 0 | 0 | 0 | 0 | 10/10 | 0 | 0 |  |
| `std_specs::vecdeque` | Rust standard-library specs | high | 342 | 0 | 0 | 0 | 0 | 0 | 0 | 19/19 | 16 | 3 | yes |
| `std_specs` | Rust standard-library specs | medium | 44 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `std_specs::borrow` | Rust standard-library specs | medium | 103 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 6 | 0 |  |
| `std_specs::control_flow` | Rust standard-library specs | medium | 74 | 0 | 0 | 0 | 0 | 0 | 0 | 4/4 | 1 | 1 | yes |
| `std_specs::core` | Rust standard-library specs | medium | 224 | 0 | 0 | 0 | 0 | 0 | 0 | 4/4 | 3 | 0 |  |
| `std_specs::manually_drop` | Rust standard-library specs | medium | 65 | 0 | 0 | 0 | 0 | 0 | 0 | 4/4 | 3 | 1 | yes |
| `std_specs::nonzero` | Rust standard-library specs | medium | 177 | 0 | 0 | 0 | 0 | 0 | 0 | 4/4 | 17 | 3 | yes |
| `array` | Runtime collections and data | high | 216 | 5 | 4 | 4 | 0 | 0 | 1 | 0/2 | 9 | 8 | yes |
| `bytes` | Runtime collections and data | high | 538 | 8 | 8 | 8 | 0 | 0 | 0 | 0/0 | 9 | 5 |  |
| `hash_map` | Runtime collections and data | high | 338 | 22 | 22 | 22 | 0 | 0 | 0 | 0/0 | 4 | 2 | yes |
| `hash_set` | Runtime collections and data | high | 315 | 20 | 20 | 20 | 0 | 0 | 0 | 0/0 | 4 | 2 | yes |
| `layout` | Runtime collections and data | high | 397 | 2 | 2 | 2 | 0 | 0 | 0 | 4/4 | 10 | 14 | yes |
| `slice` | Runtime collections and data | high | 190 | 4 | 3 | 3 | 0 | 0 | 2 | 3/3 | 10 | 6 | yes |
| `string` | Runtime collections and data | high | 489 | 10 | 0 | 0 | 0 | 0 | 10 | 16/16 | 17 | 6 | yes |
| `utf8` | Runtime collections and data | high | 1129 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 46 | 33 |  |
| `endian` | Runtime collections and data | medium | 1209 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 44 | 29 | yes |
| `float` | Runtime collections and data | medium | 136 | 1 | 1 | 1 | 0 | 0 | 0 | 2/2 | 20 | 0 | yes |
| `wrapping` | Runtime collections and data | medium | 118 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 13 | 0 |  |
| `raw_ptr` | Memory and ownership | critical | 1055 | 20 | 15 | 14 | 1 | 0 | 0 | 6/6 | 39 | 14 | yes |
| `cell` | Memory and ownership | high | 393 | 12 | 12 | 12 | 0 | 0 | 0 | 0/0 | 10 | 0 | yes |
| `cell::invcell` | Memory and ownership | high | 168 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 4 | 0 |  |
| `cell::pcell` | Memory and ownership | high | 237 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 1 |  |
| `cell::pcell_maybe_uninit` | Memory and ownership | high | 248 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 6 | 1 |  |
| `simple_pptr` | Memory and ownership | high | 600 | 15 | 14 | 13 | 1 | 0 | 0 | 0/0 | 9 | 4 | yes |
| `atomic` | Concurrency and prophecy | high | 660 | 3 | 3 | 3 | 0 | 0 | 0 | 0/0 | 11 | 0 | yes |
| `invariant` | Concurrency and prophecy | high | 651 | 5 | 5 | 0 | 0 | 5 | 0 | 0/0 | 4 | 3 | yes |
| `rwlock` | Concurrency and prophecy | high | 711 | 7 | 7 | 5 | 1 | 1 | 0 | 0/0 | 11 | 1 |  |
| `atomic_ghost` | Concurrency and prophecy | specialized | 644 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 7 | 0 |  |
| `future` | Concurrency and prophecy | specialized | 45 | 1 | 0 | 0 | 0 | 0 | 0 | 0/0 | 4 | 0 | yes |
| `logatom` | Concurrency and prophecy | specialized | 140 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 13 | 4 | yes |
| `proph` | Concurrency and prophecy | specialized | 295 | 2 | 2 | 1 | 0 | 1 | 0 | 0/0 | 3 | 8 | yes |
| `shared` | Concurrency and prophecy | specialized | 78 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1 | 3 |  |
| `thread` | Concurrency and prophecy | specialized | 273 | 5 | 3 | 3 | 0 | 0 | 0 | 0/0 | 4 | 6 | yes |
| `resource` | Resources and protocols | specialized | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `resource::algebra` | Resources and protocols | specialized | 352 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 5 | 18 |  |
| `resource::combinators` | Resources and protocols | specialized | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `resource::combinators::agree` | Resources and protocols | specialized | 61 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 4 |  |
| `resource::combinators::auth` | Resources and protocols | specialized | 93 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 6 |  |
| `resource::combinators::exclusive` | Resources and protocols | specialized | 33 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 2 | 3 |  |
| `resource::combinators::frac` | Resources and protocols | specialized | 335 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 9 | 14 | yes |
| `resource::combinators::option` | Resources and protocols | specialized | 111 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 8 |  |
| `resource::combinators::product` | Resources and protocols | specialized | 54 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 5 |  |
| `resource::combinators::sum` | Resources and protocols | specialized | 55 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 2 | 3 |  |
| `resource::impls` | Resources and protocols | specialized | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `resource::impls::frac_opt` | Resources and protocols | specialized | 349 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 10 | 15 | yes |
| `resource::impls::ghost_var` | Resources and protocols | specialized | 122 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 6 | 3 |  |
| `resource::impls::imap` | Resources and protocols | specialized | 1710 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 35 | 65 | yes |
| `resource::impls::iset` | Resources and protocols | specialized | 886 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 12 | 47 |  |
| `resource::impls::map` | Resources and protocols | specialized | 1694 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 35 | 65 | yes |
| `resource::impls::seq` | Resources and protocols | specialized | 409 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 15 | 13 |  |
| `resource::impls::set` | Resources and protocols | specialized | 882 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 12 | 47 |  |
| `resource::lib` | Resources and protocols | specialized | 517 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1 | 15 |  |
| `resource::pcm` | Resources and protocols | specialized | 309 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 3 | 17 | yes |
| `resource::relations` | Resources and protocols | specialized | 99 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 7 | 3 |  |
| `resource::storage_protocol` | Resources and protocols | specialized | 379 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 13 | 20 | yes |
| `tokens` | Resources and protocols | specialized | 851 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 42 | 43 |  |
| `contrib` | Experimental exec-spec | support | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `contrib::exec_spec` | Experimental exec-spec | support | 207 | 0 | 0 | 0 | 0 | 0 | 6 | 0/0 | 0 | 0 |  |
| `contrib::exec_spec::map` | Experimental exec-spec | support | 266 | 11 | 0 | 0 | 0 | 0 | 6 | 0/0 | 0 | 0 | yes |
| `contrib::exec_spec::multiset` | Experimental exec-spec | support | 246 | 10 | 0 | 0 | 0 | 0 | 5 | 0/0 | 1 | 0 | yes |
| `contrib::exec_spec::option` | Experimental exec-spec | support | 75 | 5 | 0 | 0 | 0 | 0 | 1 | 0/0 | 2 | 0 |  |
| `contrib::exec_spec::seq` | Experimental exec-spec | support | 519 | 25 | 0 | 0 | 0 | 0 | 18 | 0/0 | 0 | 0 |  |
| `contrib::exec_spec::set` | Experimental exec-spec | support | 237 | 12 | 0 | 0 | 0 | 0 | 7 | 0/0 | 0 | 0 | yes |
| `contrib::exec_spec::string` | Experimental exec-spec | support | 83 | 7 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `calc_macro` | Infrastructure | support | 58 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `modes` | Infrastructure | support | 32 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 3 | yes |
| `pervasive` | Infrastructure | support | 476 | 8 | 5 | 0 | 3 | 2 | 2 | 0/0 | 17 | 5 | yes |
| `prelude` | Infrastructure | support | 88 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |  |
| `state_machine_internal` | Infrastructure | support | 572 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 9 | 38 | yes |
| `vstd` | Infrastructure | support | 161 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 | yes |

## Exec function list grouped by module

This list includes every source-level exec definition and signature found by the scanner.
`definition` has a function body; `signature` is a trait/declaration-only item.

### `std_specs::range`

- Definitions: 0
- Signature-only declarations: 2

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 396 | signature | `start_bound` | `trait ExRangeBounds` | public | no-contract |  |
| 398 | signature | `end_bound` | `trait ExRangeBounds` | public | no-contract |  |
### `std_specs::clone`

- Definitions: 0
- Signature-only declarations: 1

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 10 | signature | `clone` | `trait ExClone` | public | no-contract |  |
### `std_specs::convert`

- Definitions: 0
- Signature-only declarations: 4

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 17 | signature | `from` | `trait ExFrom` | public | post (ensures) |  |
| 32 | signature | `into` | `trait ExInto` | public | post (ensures) |  |
| 68 | signature | `try_from` | `trait ExTryFrom` | public | post (ensures) |  |
| 85 | signature | `try_into` | `trait ExTryInto` | public | post (ensures) |  |
### `std_specs::default`

- Definitions: 0
- Signature-only declarations: 1

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 10 | signature | `default` | `trait ExDefault` | public | no-contract |  |
### `array`

- Definitions: 5
- Signature-only declarations: 1

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 42 | signature | `set` | `free` | private | no-contract |  |
| 64 | definition | `set` | `impl<T, const N: usize> ArrayAdditionalExecFns<T> for [T; N]` | private | post (ensures) | external_body |
| 76 | definition | `array_index_get` | `free` | public | post (ensures) |  |
| 135 | definition | `array_as_slice` | `free` | public | post (ensures) |  |
| 164 | definition | `array_fill_for_copy_types` | `free` | public | post (ensures) |  |
| 195 | definition | `ref_mut_array_unsizing_coercion` | `free` | public | post (ensures) |  |
### `bytes`

- Definitions: 8
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 79 | definition | `u16_from_le_bytes` | `free` | public | post (ensures) | external_body |
| 91 | definition | `u16_to_le_bytes` | `free` | public | post (ensures) | external_body |
| 174 | definition | `u32_from_le_bytes` | `free` | public | post (ensures) | external_body |
| 186 | definition | `u32_to_le_bytes` | `free` | public | post (ensures) | external_body |
| 331 | definition | `u64_from_le_bytes` | `free` | public | post (ensures) | external_body |
| 343 | definition | `u64_to_le_bytes` | `free` | public | post (ensures) | external_body |
| 518 | definition | `u128_from_le_bytes` | `free` | public | post (ensures) | external_body |
| 530 | definition | `u128_to_le_bytes` | `free` | public | post (ensures) | external_body |
### `hash_map`

- Definitions: 22
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 43 | definition | `new` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 59 | definition | `with_capacity` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 73 | definition | `reserve` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 82 | definition | `is_empty` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 95 | definition | `len` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body+when_used_as_spec |
| 106 | definition | `insert` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 118 | definition | `remove` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 133 | definition | `contains_key` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 144 | definition | `get` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 158 | definition | `clear` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 167 | definition | `union_prefer_right` | `impl<Key, Value> HashMapWithView<Key, Value> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 209 | definition | `new` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
| 220 | definition | `with_capacity` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
| 231 | definition | `reserve` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
| 240 | definition | `is_empty` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
| 253 | definition | `len` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body+when_used_as_spec |
| 264 | definition | `insert` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
| 275 | definition | `remove` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
| 286 | definition | `contains_key` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
| 297 | definition | `get` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
| 311 | definition | `clear` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
| 320 | definition | `union_prefer_right` | `impl<Value> StringHashMap<Value>` | public | post (ensures) | external_body |
### `hash_set`

- Definitions: 20
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 44 | definition | `new` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 60 | definition | `with_capacity` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 74 | definition | `reserve` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 87 | definition | `len` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body+when_used_as_spec |
| 96 | definition | `is_empty` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 107 | definition | `insert` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 118 | definition | `remove` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 129 | definition | `contains` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 140 | definition | `get` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 154 | definition | `clear` | `impl<Key> HashSetWithView<Key> where Key: View + Eq + Hash` | public | post (ensures) | external_body |
| 195 | definition | `new` | `impl StringHashSet` | public | post (ensures) | external_body |
| 206 | definition | `with_capacity` | `impl StringHashSet` | public | post (ensures) | external_body |
| 217 | definition | `reserve` | `impl StringHashSet` | public | post (ensures) | external_body |
| 226 | definition | `is_empty` | `impl StringHashSet` | public | post (ensures) | external_body |
| 239 | definition | `len` | `impl StringHashSet` | public | post (ensures) | external_body+when_used_as_spec |
| 250 | definition | `insert` | `impl StringHashSet` | public | post (ensures) | external_body |
| 261 | definition | `remove` | `impl StringHashSet` | public | post (ensures) | external_body |
| 272 | definition | `contains` | `impl StringHashSet` | public | post (ensures) | external_body |
| 283 | definition | `get` | `impl StringHashSet` | public | post (ensures) | external_body |
| 297 | definition | `clear` | `impl StringHashSet` | public | post (ensures) | external_body |
### `layout`

- Definitions: 2
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 118 | definition | `layout_for_type_is_valid` | `free` | public | post (ensures) | external_body |
| 141 | definition | `layout_for_val_is_valid` | `free` | public | post (ensures) | external_body |
### `slice`

- Definitions: 4
- Signature-only declarations: 2

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 45 | signature | `set` | `free` | private | no-contract |  |
| 50 | definition | `set` | `impl<T> SliceAdditionalExecFns<T> for [T]` | private | post (ensures) | external_body |
| 62 | definition | `slice_index_get` | `free` | public | post (ensures) |  |
| 100 | definition | `slice_to_vec` | `free` | public | post (ensures) | external_body |
| 108 | definition | `slice_subrange` | `free` | public | post (ensures) | external_body |
| 127 | signature | `index` | `trait ExSliceIndex` | public | requires-only |  |
### `string`

- Definitions: 10
- Signature-only declarations: 10

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 168 | signature | `unicode_len` | `trait StrSliceExecFns` | public | no-contract |  |
| 170 | signature | `get_char` | `trait StrSliceExecFns` | public | no-contract |  |
| 172 | signature | `substring_ascii` | `trait StrSliceExecFns` | public | no-contract |  |
| 174 | signature | `substring_char` | `trait StrSliceExecFns` | public | no-contract |  |
| 176 | signature | `get_ascii` | `trait StrSliceExecFns` | public | no-contract |  |
| 179 | signature | `as_bytes_vec` | `trait StrSliceExecFns` | public | no-contract |  |
| 189 | definition | `unicode_len` | `impl StrSliceExecFns for str` | private | post (ensures) | external_body |
| 198 | definition | `get_char` | `impl StrSliceExecFns for str` | private | post (ensures) | external_body |
| 208 | definition | `substring_ascii` | `impl StrSliceExecFns for str` | private | post (ensures) | external_body |
| 221 | definition | `substring_char` | `impl StrSliceExecFns for str` | private | post (ensures) | external_body |
| 253 | definition | `get_ascii` | `impl StrSliceExecFns for str` | private | post (ensures) |  |
| 267 | definition | `as_bytes_vec` | `impl StrSliceExecFns for str` | private | post (ensures) |  |
| 370 | signature | `is_ascii` | `trait StringExecFnsIsAscii` | public | no-contract |  |
| 377 | definition | `is_ascii` | `impl StringExecFnsIsAscii for String` | private | post (ensures) | when_used_as_spec |
| 388 | signature | `from_str` | `trait StringExecFns` | public | no-contract |  |
| 390 | signature | `append` | `trait StringExecFns` | public | no-contract |  |
| 392 | signature | `concat` | `trait StringExecFns` | public | no-contract |  |
| 398 | definition | `from_str` | `impl StringExecFns for String` | private | post (ensures) | external_body |
| 406 | definition | `append` | `impl StringExecFns for String` | private | post (ensures) | external_body |
| 414 | definition | `concat` | `impl StringExecFns for String` | private | post (ensures) | external_body |
### `float`

- Definitions: 1
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 127 | definition | `float_cast` | `free` | public | post (ensures) |  |
### `raw_ptr`

- Definitions: 20
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 446 | definition | `cast_ptr_to_thin_ptr` | `free` | public | post (ensures) |  |
| 468 | definition | `cast_array_ptr_to_slice_ptr` | `free` | public | post (ensures) |  |
| 492 | definition | `cast_slice_ptr_to_slice_ptr` | `free` | public | post (ensures) |  |
| 516 | definition | `cast_slice_ptr_to_str_ptr` | `free` | public | post (ensures) |  |
| 540 | definition | `cast_str_ptr_to_slice_ptr` | `free` | public | post (ensures) |  |
| 560 | definition | `cast_ptr_to_usize` | `free` | public | post (ensures) |  |
| 579 | definition | `ptr_mut_write` | `free` | public | post (ensures) | external_body |
| 602 | definition | `ptr_mut_read` | `free` | public | post (ensures) | external_body |
| 620 | definition | `ptr_ref` | `free` | public | post (ensures) | external_body |
| 636 | definition | `ptr_mut_ref` | `free` | public | post (ensures) | external_body |
| 701 | definition | `clone` | `impl Clone for IsExposed` | private | post (ensures) | external_body |
| 731 | definition | `expose_provenance` | `free` | public | post (ensures) | external_body |
| 744 | definition | `with_exposed_provenance` | `free` | public | post (ensures) | external_body |
| 908 | definition | `allocate` | `free` | public | post (ensures) | external_body |
| 948 | definition | `deallocate` | `free` | public | requires-only | external_body |
| 982 | definition | `clone` | `impl<'a, T> Clone for SharedReference<'a, T>` | private | post (ensures) | external_body |
| 1000 | definition | `new` | `impl<'a, T> SharedReference<'a, T>` | private | post (ensures) | external_body |
| 1008 | definition | `as_ref` | `impl<'a, T> SharedReference<'a, T>` | private | post (ensures) | external_body |
| 1016 | definition | `as_ptr` | `impl<'a, T> SharedReference<'a, T>` | private | post (ensures) | external_body |
| 1038 | definition | `ptr_ref2` | `free` | public | post (ensures) | external_body |
### `cell`

- Definitions: 12
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 168 | definition | `empty` | `impl<V> PCell<V>` | public | post (ensures) | external_body |
| 178 | definition | `new` | `impl<V> PCell<V>` | public | post (ensures) | external_body |
| 188 | definition | `put` | `impl<V> PCell<V>` | public | post (ensures) | external_body |
| 203 | definition | `take` | `impl<V> PCell<V>` | public | post (ensures) | external_body |
| 223 | definition | `replace` | `impl<V> PCell<V>` | public | post (ensures) | external_body |
| 246 | definition | `borrow` | `impl<V> PCell<V>` | public | post (ensures) | external_body |
| 261 | definition | `into_inner` | `impl<V> PCell<V>` | public | post (ensures) |  |
| 277 | definition | `borrow_mut` | `impl<V> PCell<V>` | public | post (ensures) | external_body+hidden |
| 297 | definition | `write` | `impl<V: Copy> PCell<V>` | public | post (ensures) | external_body |
| 344 | definition | `new` | `impl<T> InvCell<T>` | public | post (ensures) |  |
| 359 | definition | `replace` | `impl<T> InvCell<T>` | public | post (ensures) |  |
| 378 | definition | `get` | `impl<T: Copy> InvCell<T>` | public | post (ensures) |  |
### `simple_pptr`

- Definitions: 15
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 184 | definition | `addr` | `impl<V> PPtr<V>` | public | post (ensures) | when_used_as_spec |
| 203 | definition | `from_addr` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 212 | definition | `from_usize` | `impl<V> PPtr<V>` | public | post (ensures) | hidden |
| 332 | definition | `clone` | `impl<V> Clone for PPtr<V>` | private | post (ensures) |  |
| 347 | definition | `empty` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 397 | definition | `new` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 413 | definition | `free` | `impl<V> PPtr<V>` | public | requires-only |  |
| 442 | definition | `into_inner` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 462 | definition | `put` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 487 | definition | `take` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 508 | definition | `replace` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 530 | definition | `borrow` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 548 | definition | `borrow_mut` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 568 | definition | `write` | `impl<V> PPtr<V>` | public | post (ensures) |  |
| 585 | definition | `read` | `impl<V> PPtr<V>` | public | post (ensures) |  |
### `atomic`

- Definitions: 3
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 604 | definition | `fetch_and` | `impl<T> PAtomicPtr<T>` | public | post (ensures) | external_body |
| 624 | definition | `fetch_xor` | `impl<T> PAtomicPtr<T>` | public | post (ensures) | external_body |
| 644 | definition | `fetch_or` | `impl<T> PAtomicPtr<T>` | public | post (ensures) | external_body |
### `invariant`

- Definitions: 5
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 320 | definition | `create_open_invariant_credit` | `free` | public | no-contract | external_body |
| 337 | definition | `spend_open_invariant_credit` | `free` | public | no-contract | hidden |
| 372 | definition | `open_atomic_invariant_begin` | `free` | public | no-contract | external+hidden |
| 382 | definition | `open_local_invariant_begin` | `free` | public | no-contract | external+hidden |
| 392 | definition | `open_invariant_end` | `free` | public | no-contract | external+hidden |
### `rwlock`

- Definitions: 7
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 403 | definition | `release_write` | `impl<'a, V, Pred: RwLockPredicate<V>> WriteHandle<'a, V, Pred>` | public | requires-only |  |
| 441 | definition | `borrow` | `impl<'a, V, Pred: RwLockPredicate<V>> ReadHandle<'a, V, Pred>` | public | post (ensures) |  |
| 474 | definition | `release_read` | `impl<'a, V, Pred: RwLockPredicate<V>> ReadHandle<'a, V, Pred>` | public | no-contract |  |
| 502 | definition | `new` | `impl<V, Pred: RwLockPredicate<V>> RwLock<V, Pred>` | public | post (ensures) |  |
| 530 | definition | `acquire_write` | `impl<V, Pred: RwLockPredicate<V>> RwLock<V, Pred>` | public | post (ensures) |  |
| 620 | definition | `acquire_read` | `impl<V, Pred: RwLockPredicate<V>> RwLock<V, Pred>` | public | post (ensures) |  |
| 702 | definition | `into_inner` | `impl<V, Pred: RwLockPredicate<V>> RwLock<V, Pred>` | public | post (ensures) |  |
### `future`

- Definitions: 1
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 33 | definition | `exec_await` | `free` | private | post (ensures) | external_body |
### `proph`

- Definitions: 2
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 179 | definition | `new` | `impl<T> Prophecy<T> where T: Structural` | public | no-contract | external_body |
| 187 | definition | `resolve` | `impl<T> Prophecy<T> where T: Structural` | public | post (ensures) | external_body |
### `thread`

- Definitions: 5
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 27 | definition | `join` | `impl<Ret> JoinHandle<Ret>` | public | post (ensures) | external_body |
| 107 | definition | `spawn` | `free` | public | post (ensures) | external_body |
| 183 | definition | `clone` | `impl Clone for IsThread` | private | no-contract |  |
| 188 | definition | `clone` | `impl Clone for IsThread` | private | no-contract |  |
| 200 | definition | `thread_id` | `free` | public | post (ensures) | external_body |
### `contrib::exec_spec`

- Definitions: 0
- Signature-only declarations: 6

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 31 | signature | `get_ref` | `trait ToRef` | public | post (ensures) |  |
| 38 | signature | `get_owned` | `trait ToOwned` | public | post (ensures) |  |
| 46 | signature | `deep_clone` | `trait DeepViewClone` | public | post (ensures) |  |
| 70 | signature | `exec_eq` | `trait ExecSpecEq` | public | post (ensures) |  |
| 80 | signature | `exec_index` | `trait ExecSpecIndex` | public | requires-only |  |
| 88 | signature | `exec_len` | `trait ExecSpecLen` | public | no-contract |  |
### `contrib::exec_spec::map`

- Definitions: 11
- Signature-only declarations: 6

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 24 | definition | `get_ref` | `impl< 'a, K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, V: DeepView + DeepViewClone, > ToRef<&'a HashMap<K, V>> for &'a HashMap<K, V>` | private | no-contract |  |
| 36 | definition | `get_owned` | `impl< 'a, K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, V: DeepView + DeepViewClone, > ToOwned<HashMap<K, V>> for &'a HashMap<K, V>` | private | no-contract | external_body |
| 51 | definition | `deep_clone` | `impl< K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, V: DeepView + DeepViewClone, > DeepViewClone for HashMap<K, V>` | private | no-contract | external_body |
| 72 | definition | `exec_eq` | `impl< 'a, K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, V: DeepView + DeepViewClone, > ExecSpecEq<'a> for &'a HashMap<K, V> where &'a K: ExecSpe...` | private | no-contract | external_body |
| 97 | definition | `exec_len` | `impl< 'a, K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, V: DeepView + DeepViewClone, > ExecSpecLen for &'a HashMap<K, V>` | private | post (ensures) | external_body |
| 108 | signature | `exec_empty` | `trait ExecSpecMapEmpty` | public | no-contract |  |
| 120 | signature | `exec_index` | `trait ExecSpecMapIndex` | public | requires-only |  |
| 132 | signature | `exec_insert` | `trait ExecSpecMapInsert` | public | no-contract |  |
| 139 | signature | `exec_remove` | `trait ExecSpecMapRemove` | public | no-contract |  |
| 146 | signature | `exec_dom` | `trait ExecSpecMapDom` | public | no-contract |  |
| 155 | signature | `exec_get` | `trait ExecSpecMapGet` | public | no-contract |  |
| 161 | definition | `exec_empty` | `impl<K: DeepView + std::hash::Hash + std::cmp::Eq, V: DeepView> ExecSpecMapEmpty for HashMap<K, V>` | private | post (ensures) |  |
| 178 | definition | `exec_index` | `impl<'a, K: DeepView + std::hash::Hash + std::cmp::Eq, V: DeepView> ExecSpecMapIndex< 'a, > for &'a HashMap<K, V>` | private | post (ensures) | external_body |
| 196 | definition | `exec_insert` | `impl<'a, K, V> ExecSpecMapInsert<'a, HashMap<K, V>> for &'a HashMap<K, V> where K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, V: DeepView + Deep...` | private | post (ensures) | external_body |
| 214 | definition | `exec_remove` | `impl<'a, K, V> ExecSpecMapRemove<'a, HashMap<K, V>> for &'a HashMap<K, V> where K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, V: DeepView + Deep...` | private | post (ensures) | external_body |
| 232 | definition | `exec_dom` | `impl<'a, K, V> ExecSpecMapDom<'a> for &'a HashMap<K, V> where K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, V: DeepView + DeepViewClone,` | private | post (ensures) | external_body |
| 254 | definition | `exec_get` | `impl<'a, K, V> ExecSpecMapGet<'a> for &'a HashMap<K, V> where K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, V: DeepView + DeepViewClone,` | private | post (ensures) | external_body |
### `contrib::exec_spec::multiset`

- Definitions: 10
- Signature-only declarations: 5

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 42 | definition | `get_ref` | `impl<'a, T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> ToRef< &'a ExecMultiset<T>, > for &'a ExecMultiset<T>` | private | no-contract |  |
| 52 | definition | `get_owned` | `impl<'a, T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> ToOwned< ExecMultiset<T>, > for &'a ExecMultiset<T>` | private | no-contract | external_body |
| 66 | definition | `deep_clone` | `impl<T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> DeepViewClone for ExecMultiset< T, >` | private | no-contract | external_body |
| 82 | definition | `exec_eq` | `impl<'a, T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> ExecSpecEq< 'a, > for &'a ExecMultiset<T> where &'a T: ExecSpecEq<'a, Other = &'a T>` | private | no-contract | external_body |
| 106 | definition | `exec_len` | `impl< 'a, T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, > ExecSpecLen for &'a ExecMultiset<T>` | private | post (ensures) | external_body |
| 125 | signature | `exec_count` | `trait ExecSpecMultisetCount` | public | no-contract |  |
| 130 | signature | `exec_empty` | `trait ExecSpecMultisetEmpty` | public | no-contract |  |
| 137 | signature | `exec_singleton` | `trait ExecSpecMultisetSingleton` | public | no-contract |  |
| 142 | signature | `exec_add` | `trait ExecSpecMultisetAdd` | public | no-contract |  |
| 147 | signature | `exec_sub` | `trait ExecSpecMultisetSub` | public | no-contract |  |
| 161 | definition | `exec_count` | `impl< 'a, T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, > ExecSpecMultisetCount for &'a ExecMultiset<T>` | private | post (ensures) | external_body |
| 175 | definition | `exec_empty` | `impl<T: DeepView + std::hash::Hash + std::cmp::Eq> ExecSpecMultisetEmpty for ExecMultiset<T>` | private | post (ensures) | external_body |
| 190 | definition | `exec_singleton` | `impl< T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq, > ExecSpecMultisetSingleton for ExecMultiset<T>` | private | post (ensures) | external_body |
| 205 | definition | `exec_add` | `impl<'a, T> ExecSpecMultisetAdd<'a, ExecMultiset<T>> for &'a ExecMultiset<T> where T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq,` | private | post (ensures) | external_body |
| 227 | definition | `exec_sub` | `impl<'a, T> ExecSpecMultisetSub<'a, ExecMultiset<T>> for &'a ExecMultiset<T> where T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq,` | private | post (ensures) | external_body |
### `contrib::exec_spec::option`

- Definitions: 5
- Signature-only declarations: 1

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 10 | definition | `get_ref` | `impl<'a, T: Sized + DeepView> ToRef<&'a Option<T>> for &'a Option<T>` | private | no-contract |  |
| 17 | definition | `get_owned` | `impl<'a, T: DeepView + DeepViewClone> ToOwned<Option<T>> for &'a Option<T>` | private | no-contract |  |
| 24 | definition | `deep_clone` | `impl<T: DeepViewClone> DeepViewClone for Option<T>` | private | no-contract |  |
| 36 | definition | `exec_eq` | `impl<'a, T: DeepView> ExecSpecEq<'a> for &'a Option<T> where &'a T: ExecSpecEq<'a, Other = &'a T>` | private | no-contract |  |
| 52 | signature | `exec_unwrap` | `trait ExecSpecOptionUnwrap` | public | requires-only |  |
| 67 | definition | `exec_unwrap` | `impl<'a, T> ExecSpecOptionUnwrap<'a> for &'a Option<T> where T: DeepView + DeepViewClone` | private | post (ensures) |  |
### `contrib::exec_spec::seq`

- Definitions: 25
- Signature-only declarations: 18

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 15 | definition | `get_ref` | `impl<'a, T: DeepView> ToRef<&'a [T]> for &'a Vec<T>` | private | no-contract |  |
| 24 | definition | `get_owned` | `impl<'a, T: DeepView + DeepViewClone> ToOwned<Vec<T>> for &'a [T]` | private | no-contract | external_body |
| 33 | definition | `deep_clone` | `impl<T: DeepViewClone> DeepViewClone for Vec<T>` | private | no-contract | external_body |
| 43 | definition | `exec_eq` | `impl<'a, T: DeepView> ExecSpecEq<'a> for &'a [T] where &'a T: ExecSpecEq<'a, Other = &'a T>` | private | no-contract | external_body |
| 55 | definition | `exec_eq` | `impl<'a, T: DeepView> ExecSpecEq<'a> for &'a Vec<T> where &'a T: ExecSpecEq<'a, Other = &'a T>` | private | no-contract | external_body |
| 64 | definition | `exec_len` | `impl<'a, T: DeepView> ExecSpecLen for &'a [T]` | private | post (ensures) |  |
| 76 | definition | `exec_index` | `impl<'a, T: DeepView> ExecSpecIndex<'a> for &'a [T]` | private | post (ensures) |  |
| 89 | signature | `exec_add` | `trait ExecSpecSeqAdd` | public | no-contract |  |
| 96 | signature | `exec_push` | `trait ExecSpecSeqPush` | public | no-contract |  |
| 103 | signature | `exec_update` | `trait ExecSpecSeqUpdate` | public | no-contract |  |
| 110 | signature | `exec_subrange` | `trait ExecSpecSeqSubrange` | public | requires-only |  |
| 118 | signature | `exec_empty` | `trait ExecSpecSeqEmpty` | public | no-contract |  |
| 125 | signature | `exec_to_multiset` | `trait ExecSpecSeqToMultiset` | public | no-contract |  |
| 135 | signature | `exec_drop_first` | `trait ExecSpecSeqDropFirst` | public | requires-only |  |
| 145 | signature | `exec_drop_last` | `trait ExecSpecSeqDropLast` | public | requires-only |  |
| 155 | signature | `exec_take` | `trait ExecSpecSeqTake` | public | requires-only |  |
| 165 | signature | `exec_skip` | `trait ExecSpecSeqSkip` | public | requires-only |  |
| 175 | signature | `exec_last` | `trait ExecSpecSeqLast` | public | requires-only |  |
| 185 | signature | `exec_first` | `trait ExecSpecSeqFirst` | public | requires-only |  |
| 195 | signature | `exec_is_prefix_of` | `trait ExecSpecSeqIsPrefixOf` | public | no-contract |  |
| 202 | signature | `exec_is_suffix_of` | `trait ExecSpecSeqIsSuffixOf` | public | no-contract |  |
| 209 | signature | `exec_contains` | `trait ExecSpecSeqContains` | public | no-contract |  |
| 216 | signature | `exec_index_of` | `trait ExecSpecSeqIndexOf` | public | no-contract |  |
| 223 | signature | `exec_index_of_first` | `trait ExecSpecSeqIndexOfFirst` | public | no-contract |  |
| 230 | signature | `exec_index_of_last` | `trait ExecSpecSeqIndexOfLast` | public | no-contract |  |
| 239 | definition | `exec_add` | `impl<'a, T: DeepView + DeepViewClone> ExecSpecSeqAdd<'a, Vec<T>> for &'a [T]` | private | post (ensures) | external_body |
| 252 | definition | `exec_push` | `impl<'a, T: DeepView + DeepViewClone> ExecSpecSeqPush<'a, Vec<T>> for &'a [T]` | private | post (ensures) | external_body |
| 266 | definition | `exec_update` | `impl<'a, T: DeepView + DeepViewClone> ExecSpecSeqUpdate<'a, Vec<T>> for &'a [T]` | private | post (ensures) | external_body |
| 281 | definition | `exec_subrange` | `impl<'a, T: DeepView> ExecSpecSeqSubrange<'a> for &'a [T]` | private | post (ensures) | external_body |
| 294 | definition | `exec_empty` | `impl<T: DeepView> ExecSpecSeqEmpty for Vec<T>` | private | post (ensures) |  |
| 309 | definition | `exec_to_multiset` | `impl<'a, T: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> ExecSpecSeqToMultiset< 'a, > for &'a [T]` | private | post (ensures) | external_body |
| 332 | definition | `exec_drop_first` | `impl<'a, T: DeepView> ExecSpecSeqDropFirst<'a> for &'a [T]` | private | post (ensures) |  |
| 344 | definition | `exec_drop_last` | `impl<'a, T: DeepView> ExecSpecSeqDropLast<'a> for &'a [T]` | private | post (ensures) |  |
| 356 | definition | `exec_take` | `impl<'a, T: DeepView> ExecSpecSeqTake<'a> for &'a [T]` | private | post (ensures) |  |
| 368 | definition | `exec_skip` | `impl<'a, T: DeepView> ExecSpecSeqSkip<'a> for &'a [T]` | private | post (ensures) |  |
| 380 | definition | `exec_last` | `impl<'a, T: DeepView> ExecSpecSeqLast<'a> for &'a [T]` | private | post (ensures) |  |
| 392 | definition | `exec_first` | `impl<'a, T: DeepView> ExecSpecSeqFirst<'a> for &'a [T]` | private | post (ensures) |  |
| 407 | definition | `exec_is_prefix_of` | `impl<'a, T: DeepView> ExecSpecSeqIsPrefixOf<'a> for &'a [T] where &'a T: ExecSpecEq<'a, Other = &'a T>, &'a [T]: DeepView<V = Seq<<&'a T as DeepView>::V>>,` | private | post (ensures) |  |
| 425 | definition | `exec_is_suffix_of` | `impl<'a, T: DeepView> ExecSpecSeqIsSuffixOf<'a> for &'a [T] where &'a T: ExecSpecEq<'a, Other = &'a T>, &'a [T]: DeepView<V = Seq<<&'a T as DeepView>::V>>,` | private | post (ensures) |  |
| 443 | definition | `exec_contains` | `impl<'a, T: DeepView + PartialEq> ExecSpecSeqContains<'a> for &'a [T] where &'a T: ExecSpecEq<'a, Other = &'a T>,` | private | post (ensures) | external_body |
| 459 | definition | `exec_index_of` | `impl<'a, T: DeepView + PartialEq> ExecSpecSeqIndexOf<'a> for &'a [T] where &'a T: ExecSpecEq<'a, Other = &'a T>,` | private | post (ensures) | external_body |
| 478 | definition | `exec_index_of_first` | `impl<'a, T: DeepView + PartialEq> ExecSpecSeqIndexOfFirst<'a> for &'a [T] where &'a T: ExecSpecEq<'a, Other = &'a T>,` | private | post (ensures) | external_body |
| 502 | definition | `exec_index_of_last` | `impl<'a, T: DeepView + PartialEq> ExecSpecSeqIndexOfLast<'a> for &'a [T] where &'a T: ExecSpecEq<'a, Other = &'a T>,` | private | post (ensures) | external_body |
### `contrib::exec_spec::set`

- Definitions: 12
- Signature-only declarations: 7

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 18 | definition | `get_ref` | `impl<'a, K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> ToRef< &'a HashSet<K>, > for &'a HashSet<K>` | private | no-contract |  |
| 28 | definition | `get_owned` | `impl<'a, K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> ToOwned< HashSet<K>, > for &'a HashSet<K>` | private | no-contract | external_body |
| 40 | definition | `deep_clone` | `impl<K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> DeepViewClone for HashSet<K>` | private | no-contract | external_body |
| 56 | definition | `exec_eq` | `impl<'a, K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> ExecSpecEq< 'a, > for &'a HashSet<K> where &'a K: ExecSpecEq<'a, Other = &'a K>` | private | no-contract | external_body |
| 74 | definition | `exec_len` | `impl<'a, K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq> ExecSpecLen for &'a HashSet< K, >` | private | post (ensures) | external_body |
| 85 | signature | `exec_empty` | `trait ExecSpecSetEmpty` | public | no-contract |  |
| 92 | signature | `exec_contains` | `trait ExecSpecSetContains` | public | no-contract |  |
| 99 | signature | `exec_insert` | `trait ExecSpecSetInsert` | public | no-contract |  |
| 106 | signature | `exec_remove` | `trait ExecSpecSetRemove` | public | no-contract |  |
| 111 | signature | `exec_intersect` | `trait ExecSpecSetIntersect` | public | no-contract |  |
| 116 | signature | `exec_union` | `trait ExecSpecSetUnion` | public | no-contract |  |
| 121 | signature | `exec_difference` | `trait ExecSpecSetDifference` | public | no-contract |  |
| 127 | definition | `exec_empty` | `impl<K: DeepView + std::hash::Hash + std::cmp::Eq> ExecSpecSetEmpty for HashSet<K>` | private | post (ensures) |  |
| 140 | definition | `exec_contains` | `impl<'a, K: DeepView + std::hash::Hash + std::cmp::Eq> ExecSpecSetContains<'a> for &'a HashSet<K>` | private | post (ensures) | external_body |
| 155 | definition | `exec_insert` | `impl<'a, K> ExecSpecSetInsert<'a, HashSet<K>> for &'a HashSet<K> where K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq,` | private | post (ensures) | external_body |
| 172 | definition | `exec_remove` | `impl<'a, K> ExecSpecSetRemove<'a, HashSet<K>> for &'a HashSet<K> where K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq,` | private | post (ensures) | external_body |
| 187 | definition | `exec_intersect` | `impl<'a, K> ExecSpecSetIntersect<'a, HashSet<K>> for &'a HashSet<K> where K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq,` | private | post (ensures) | external_body |
| 206 | definition | `exec_union` | `impl<'a, K> ExecSpecSetUnion<'a, HashSet<K>> for &'a HashSet<K> where K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq,` | private | post (ensures) | external_body |
| 223 | definition | `exec_difference` | `impl<'a, K> ExecSpecSetDifference<'a, HashSet<K>> for &'a HashSet<K> where K: DeepView + DeepViewClone + std::hash::Hash + std::cmp::Eq,` | private | post (ensures) | external_body |
### `contrib::exec_spec::string`

- Definitions: 7
- Signature-only declarations: 0

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 20 | definition | `get_ref` | `impl<'a> ToRef<&'a str> for &'a String` | private | no-contract |  |
| 28 | definition | `get_owned` | `impl<'a> ToOwned<String> for &'a str` | private | no-contract | external_body |
| 35 | definition | `deep_clone` | `impl DeepViewClone for String` | private | no-contract |  |
| 45 | definition | `exec_eq` | `impl<'a> ExecSpecEq<'a> for &'a str` | private | no-contract | external_body |
| 56 | definition | `exec_eq` | `impl<'a> ExecSpecEq<'a> for &'a String` | private | no-contract | external_body |
| 63 | definition | `exec_len` | `impl<'a> ExecSpecLen for &'a str` | private | post (ensures) |  |
| 75 | definition | `exec_index` | `impl<'a> ExecSpecIndex<'a> for &'a str` | private | post (ensures) |  |
### `pervasive`

- Definitions: 8
- Signature-only declarations: 2

| Line | Kind | Function | Context | Visibility | Contract | Flags |
|---:|---|---|---|---|---|---|
| 124 | definition | `exec_nonstatic_call` | `free` | private | post (ensures) | external_body+hidden |
| 190 | definition | `unreached` | `free` | public | requires-only | external_body |
| 199 | definition | `print_u64` | `free` | public | no-contract | external_body |
| 204 | definition | `runtime_assert` | `free` | public | requires-only | external_body |
| 381 | signature | `set` | `trait VecAdditionalExecFns` | public | no-contract |  |
| 383 | signature | `set_and_swap` | `trait VecAdditionalExecFns` | public | no-contract |  |
| 390 | definition | `set` | `impl<T> VecAdditionalExecFns<T> for alloc::vec::Vec<T>` | private | post (ensures) | external_body |
| 401 | definition | `set_and_swap` | `impl<T> VecAdditionalExecFns<T> for alloc::vec::Vec<T>` | private | post (ensures) | external_body |
| 443 | definition | `__call_panic` | `free` | public | requires-only | external_body+hidden |
| 454 | definition | `__new_argument` | `free` | public | no-contract | external_body+hidden |

<!-- END GENERATED MODULE INVENTORY -->
