# 别名归一化新增 26 目标 determinism 实验 review（2026-07-21）

## 背景

P0（别名归一化，`normalize_verus_aliases`）使 6 个之前不可见的 module 进入
public-post 目标集：`cell::invcell`、`cell::pcell`、`cell::pcell_maybe_uninit`、
`std_specs::core`、`std_specs::iter`、`std_specs::vec`。本目录的两个 run
（`alias-new-2026-07-21/` 初跑、`alias-new-fixup-2026-07-21/` 修复后重跑）
覆盖全部 26 个新目标。与历史 111 目标实验完全相同的工具链与口径
（May 快照 `0.2026.05.17.e479cce`，rlimit 60，默认 equal policy）。

## 为跑通所做的 runner 快照兼容修复

- `cell::invcell`：补 `vstd::predicate::*` 导入（`Predicate` trait 在
  `vstd/predicate.rs` 定义，不在 glob 导入里）。
- `cell::pcell`：五月 `PointsTo` 是恒初始化类型（只有 `id()`/`value()`），
  equal-fn/schema 的 maybe-uninit 形状（`is_init` 守卫）在此恒为真——runner
  将 `.is_init()` 常数折叠为 `true`（并修掉初版正则吞括号的 bug）。
- `cell::pcell_maybe_uninit`：补 `vstd::cell::MemContents` 导入。
- 三个新 cell module 纳入 `_MAY_PTR_ADDR_MODULES` 版本门
  （`.addr()` → `.ptr().addr()` → `.id()`，并丢弃不可用的标量守卫）。
- `std_specs::vec`：补 `alloc::alloc::Allocator` 导入 +
  `#![feature(allocator_api)]`（新 `MODULE_FEATURES` 机制）。

## 结果总览（26 目标）

| 结果 | 数量 | 目标 |
|---|---:|---|
| complete | 12 | pcell borrow/into_inner/replace/write；pc_mu put/take/replace/borrow/into_inner/write；iter::new；vec::vec_index |
| unknown | 8 | invcell 全部 4 个；pcell::new；pc_mu::empty/new；iter::next |
| unsupported（`&mut` 返回） | 3 | pcell::borrow_mut；pc_mu::borrow_mut；vec::vec_index_mut |
| no_ensures（提取缺口） | 2 | pcell::read；pc_mu::read |
| verus_error（pipeline 缺口） | 1 | core::index_set |
| sat witness | 0 | — |

## 逐项语义归类（对应 111 目标审计的 A/B/C 口径）

### invcell —— §13 P4 要求的复查结论

非弃用版 `cell::invcell::InvCell` 与已判 C 类的弃用版契约形状完全相同：

| 目标 | R0 | 归类 | 说明 |
|---|---|---|---|
| `new@105` | unknown | A 类同型 | ensures 只钉 `predicate() == pred`；cell 身份有意自由。在"谓词商等号"下可判 complete，裸结构等号下无法判定 |
| `replace@123` | unknown | **C 类（真欠约束）** | `ensures self.inv(old_val)`——任意不变式谓词非函数性，`inv(0) ∧ inv(1)` 可同时成立，返回值确实不唯一 |
| `get@139` | unknown | **C 类（真欠约束）** | 同上 |
| `into_inner@155` | unknown | **C 类（真欠约束）** | 同上（弃用版无此 fn；对应 rwlock::into_inner 的 C 类形状） |

§13 P4 的复查项由此完成：invcell 的 3 个返回值 API 均为**真正的语义欠约束**，
处理方式与弃用版相同（接受并记录 / 加 ghost 精确取值访问器 / 改 API），见 §13 P4。

### 其余 unknown

| 目标 | 归类 | 说明 |
|---|---|---|
| `pcell::new@132` | B 类同型 | fresh `CellId`，与弃用版 `PCell::new` 相同的有意非确定 |
| `pc_mu::empty@107`、`new@117` | B 类同型 | 同上 |
| `std_specs::iter::next@287` | 待审计 | ensures 在 `obeys_prophetic_iter_laws()` 下钉住 `ret == seq[index]`；prophecy 公理未实例化时返回 Option 不唯一。疑似 A（缺 prophecy 公理），未深挖 |

### 提取/pipeline 缺口（非 spec 判定）

- `pcell::read@224`、`pc_mu::read@234`：两个 fn 都用 **`returns` 子句**
  （`returns *perm.value()`），extractor 目前只提取 `ensures`，不会把
  `returns expr` 降为 `ensures result == expr` → runner 报 `no_ensures`。
  这是确定的提取缺口（vstd 共 49 个 `returns` 子句点），值得单独立项修复。
- `std_specs::core::index_set@215`：`T: ?Sized` 泛型边界在合成 det fn 中
  不满足（E0277），属泛型边界提取缺口，暂记 pipeline gap。

## 与既有结论合并后的 corpus 全景

| 目标集 | complete | unknown | unsupported | 其他 |
|---|---:|---:|---:|---|
| 原 111+6（文档基线） | 87 | 20 | 4 | 0 |
| 新增 26 | 12 | 8 | 3 | 2 no_ensures + 1 pipeline gap |
| **合计 143** | **99** | **28** | **7** | 3 |

unknown 的语义构成（按审计口径）：A 类工具缺口 8（原 7 + invcell::new），
B 类有意非确定 12（原 9 + 3 个新 cell 构造器），C 类真欠约束 **7**（原 4 +
invcell 3 个），iter::next 待归类 1。
