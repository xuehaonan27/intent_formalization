# 七月快照（cf3b5c3）全量 determinism 复跑 review（2026-07-21）

## 目的与结论

在从源码构建的七月工具链（`0.2026.07.13.cf3b5c3`，rust 1.96.0，
`~/verus/source/target-verus/release/verus` + `~/verus/source/vstd`）上，
用与五月实验完全相同的口径（rlimit 60，默认 equal policy + strict 指针复跑）
跑完七月 inventory 的全部 135 个 public-post 目标，并与五月基线逐项对比。

**结论：全部研究发现零漂移地转移到当前上游。** 122 个同行号共享目标判定
0 差异；13 个仅行号漂移的函数判定全部一致；2 个函数（`std_specs::iter` 的
for-loop wrapper）在七月快照中被上游移除。

## 数字总览

| 快照 | complete | unknown | unsupported | no_ensures | pipeline gap | 合计 |
|---|---:|---:|---:|---:|---:|---:|
| 五月（e479cce） | 99 | 28 | 7 | 2 | 1 | 137 |
| 七月（cf3b5c3） | 98 | 27 | 7 | 2 | 1 | 135 |

差值恰为被移除的 `iter::new`（complete）与 `iter::next`（unknown）。

## 行号漂移对照（判定全部一致）

- `atomic::{fetch_and, fetch_xor, fetch_or}`：May @610/630/650 → July @604/624/644，均 unknown；
- `simple_pptr` 11 个方法：行号整体上移约 11 行，判定全同
  （`new` unknown、其余 complete、`borrow_mut` unsupported）；
- `std_specs::core::index_set`：@215 → @205，两快照均为同一 pipeline 缺口
  （`T: ?Sized` 泛型边界，verus_error）。

## 关键复核点

- C 类真欠约束（`cell::invcell::{replace,get,into_inner}` 及原 4 个）在七月
  快照中全部复现为 unknown，语义判定不变；
- B 类有意非确定（3 个 cell 构造器、allocate、spawn/join、float_cast 等）
  同样复现；
- strict 指针复跑与五月完全同构：同一组 6 个 trivial-equality 目标在
  `--compare-raw-pointers` 下全部 complete。

## 环境说明（本 run 与五月 run 的差异）

- runner 新增 `--vstd-snapshot jul2026` profile：唯一实质差异是
  `MemContents` 从 `vstd::cell`（五月）迁到 `vstd::raw_ptr`（七月）；
  `PointsTo` API 形状在两快照中一致（raw_ptr/deprecated cell 均无 `addr()`），
  既有版本门与 `pcell is_init` 折叠继续适用；
- 源码构建布局无 `version.json`，runner 已改为回退读取 `version.txt`；
- 提取/parser 同为 tree-sitter-verus 0.23.2 + 别名归一化。

## 产物

- `july-2026-07-21-public-free/`（37 目标）
- `july-2026-07-21-impl-methods/`（98 目标）
- `july-2026-07-21-raw-pointer-strict/`（6 目标）

至此 P1 全部闭环：七月 inventory 有了匹配的 executable snapshot，
项目不再混用五/七月 artifact。
