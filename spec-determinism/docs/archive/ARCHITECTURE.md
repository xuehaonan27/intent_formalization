# spec-determinism — Architecture & Code Review

本文档分两部分：
1. **Code Review** —— 按优先级列出 `src/` 下的真实 bug、设计债和风格问题。
2. **架构讲解** —— 自顶向下解释 pipeline 的每个阶段，以及 `src/` 下每个文件的职责、关键函数和痛点。

---

## Part 1. Code Review

### 🔴 高优先级（真实 bug / 会误判）

#### B1. `orchestrator.py` 已经与当前代码库不一致，基本是死代码
- `from .gen_det import generate_det_check` —— 这个函数早就改名成 `build_det_check_spec` 了。
- 调用 `binary_search(spec, runner, ...)` 传的是 `FunctionSpec`，但 `binary_search` 现在收 `DetCheckSpec`。
- 实际的 driver 是仓库根目录的 `test_all.py`，`orchestrator.run_pipeline` / `main` 已经没人调用。
- **建议**：要么用 `test_all.py` 的逻辑重写 orchestrator，要么直接删掉并更新 README，免得新人被误导。

#### B2. `binary_search.test_and_set` 把 timeout / error 当 PASS 处理，witness 可能失真
- `src/binary_search.py:477-484`：`timeout` / `error` 只 log 一句警告然后 `return False`，和 PASS 一样让上层跳过这条 assume。
- 后果：Verus 偶发超时或 cargo 抽风时，narrowing 会"装作没这回事"继续往下走，最终的 witness 里会缺掉本应加上的约束。
- **建议**：至少在 `trace` 里把 `result.status` 原样记下来（现在只记 `fail`/`pass`）。严格一点可以累计 error 次数到阈值后 abort，或加重试。

#### B3. `parse_result` 的 fail 判定太宽松，可能误判
- `src/verify.py:180-184`：只要输出里同时出现 `"postcondition not satisfied"` 和当前 fn 名字（任意位置），就判 fail。
- 如果 Verus 同一次调用里有别的函数失败（例如 proof-file 里陈旧的 `det_*` 定义），而它们的 stderr 里交叉引用了我们当前 fn 名字，会误报 fail。
- 实际工程中 `inject_proof_fn` 会 strip 旧注入，窗口很小，但并非完全没有。
- **建议**：如果 Verus 有 `--json-output` 就改用结构化输出；否则把 fn_name 检查收紧为"该错误行所在的 note 堆栈中出现 fn_name"。

### 🟡 中优先级（设计债，不会立刻出问题）

#### D1. `inject_proof_fn → run_cargo_verus → restore_file` 在两个 backend 里各写了一遍
- `VerusRunner.check` (verify.py:295-317) 和 `Z3Backend.check_with_model` (z3_backend.py:226-256) 结构几乎一模一样。
- **建议**：抽到 `backend.py` 里，例如 `run_with_injection(proof_file, code, marker, run_fn)`；两个 backend 只各自实现"如何解析 raw 结果"。

#### D2. `binary_search` 用 `hasattr(runner, "last_model")` duck-type Z3Backend
- 当前可接受，但如果将来多一个 backend（比如直接用 `z3-solver` 重跑 SMT），很容易意外匹配。
- **建议**：在 `backend.py` 里加 `ModelProvidingBackend(Protocol)`，显式声明 `last_model` 和 `set_det_spec`；`binary_search` 用 `isinstance(...)` 代替 `hasattr`。

#### D3. `tracked_symbols_from_det_spec` 用字符串特征过滤投影符号
- `z3_backend.py:352`：`if "@" in s.name or "." in s.name: continue`。正确但脆弱——未来如果引入别的非 SMT-bound 符号类型（如 closure capture），不会被识别。
- **建议**：在 `Symbol` 里加一个 `smt_bound: bool = True`，构造时由 `gen_det._build_symbols` 显式决定。

#### D4. `render_template` 每次都把 `equal_fn_def` 重新拼到前面
- `gen_det.py:295-311`：二分搜索每一轮都会 render 一次，`equal_fn_def` 就被拼上去 N 次（结果正确，但是一次性可以避免的开销）。
- **建议**：在 `DetCheckSpec` 里缓存 `equal_fn_def + "\n\n" + template`，或者让 `render_template` 检查 template 中是否已包含 equal fn。

#### D5. `report.py::complete_witness` 的 `_extract_concrete_values` 完全是占位实现
- 只处理最朴素的 `var == value`，不处理 Ok/Err 嵌套、view 投影、`@.field`。
- `category` 参数根本没用（逻辑中看不出当前 assume 属于 input 还是 output）。
- **建议**：Z3 后端已经能直接产出 `Witness.inputs/output1/output2`；让 `binary_search` 的窄化路径也走同一条，统一由 `witness_from_assumes(det_spec, assumes)` 填字段。

### 🟢 低优先级（风格 / 注释）

- `extract.py:219, 365` 有多处 `import re` 在函数内部重新 import，顶层已经有了。
- `types.py::FunctionSpec.output_vars` 似乎没人调用，可以删。
- `llm_fallback.py` 的 `extract_spec` / `classify_gap` / `suggest_narrowing` 都是遗留占位，当前项目主要用 `llm_refine.py` 和 `equal_llm.py`。
- `z3_backend.py` 里 `_RE_RESPONSE` 定义了但没用到。

### 建议修复优先级

1. **B1**（orchestrator 死代码）—— 5 分钟删掉或改。
2. **D2**（duck typing → 显式 Protocol）—— 15 分钟。
3. **D5**（统一 binary_search 的 witness 构造和 Z3 路径）—— 和后续把 Z3 接入 `test_all.py` 一起做。
4. **B2**（timeout/error 在 trace 里原样记录）—— 小改。
5. **D1**（inject/restore 共用 helper）—— 中等改动，想好抽象再做。

---

## Part 2. 架构讲解

### 0. 顶层设计：四阶段 pipeline

```
source.rs (Rust/Verus)
     │
     ▼  [Stage 1a]  extract.py
  FunctionSpec  ← params / return / requires / ensures / type_defs
     │
     ▼  [Stage 1b]  gen_det.py  (+ equal_policy / equal_llm)
  DetCheckSpec  ← proof fn template + symbol table + equal fn
     │
     ▼  [Stage 1.5, optional]  llm_refine.py
  DetCheckSpec with UNKNOWN types instantiated
     │
     ▼  [Stage 2 + 3]  binary_search.py  +  backend.py
  Witness  ← 通过多轮 Verus 调用收敛出的具体反例
     │       backend 是 VerusRunner (subprocess) 或 Z3Backend (读 SMT transcript)
     ▼  [Stage 4]  report.py
  traces.md / witnesses.md / summary.json
```

**数据流主线**（`types.py` 中的 dataclass）：

```
TypeInfo / FieldInfo / VariantInfo       ← 类型元数据
       │
  Param  →  FunctionSpec                 ← 从源码抽出来的"原材料"
                 │
           Symbol  →  DetCheckSpec       ← 加工成 binary_search 消费的格式
                          │
                    Assume / VerifyResult   ← 搜索过程中的中间件
                          │
                    ConcreteValue  →  Witness  ← 最终反例
```

所有这些都是 `@dataclass`，有 `to_dict` / `from_dict` / `to_json` / `from_json`，可以 snapshot 到 `results/artifacts/`，方便调试和 LLM refine 缓存。

---

### 1. Stage 1a — `extract.py`：源码 → FunctionSpec

**职责**：用 `tree-sitter-verus` 把 `pub fn foo(...) -> T` 的签名、`#[verus_spec(...)]` 和内联 `requires/ensures` 抽出来；另外把相关的 struct / enum 递归解析成 `TypeInfo`。

**核心函数**：
- `extract_spec(source, fn_name, type_sources)` —— 唯一公开 API。
- `_extract_fn_chunk` —— 当整文件 parse 失败（因为 `proof!{}` 或奇葩 `cfg_attr` 把 tree-sitter 搞懵）时 fallback：只 parse 包含 `fn foo(` 的代码块。
- `_find_verus_spec_for_fn` —— 两层策略：先找 sibling `attribute_item`，再 fallback 按字节距离找最近的 `verus_spec_attribute`。
- `_find_impl_type` —— 三层 fallback（parent 链 → byte range 搜 `impl_item` → top-level token 扫描）。把 `&mut self` 的 `self` 解析成具体类型（比如 `Bitmap`）。
- `_resolve_types` —— 把 `TypeInfo.kind = UNKNOWN` 的类型去 `type_sources` 里找定义；transitive（Error → struct with `code: ErrorCode` → 也去解 ErrorCode）；之后再拉 `XView` 类型作为 `spec_view`（这是 Verus 的用户可见数据模型，例如 `Bitmap → BitmapView { num_bits, set_bits }`）。

**痛点**：tree-sitter-verus 对整个 file parse 时经常 ERROR-recover 把函数吃掉（内层 `proof!{}` 或嵌套 `cfg_attr`），多处 fallback 都是绕这个。

---

### 2. Stage 1b — `gen_det.py`：FunctionSpec → DetCheckSpec

**职责**：把真实的 `fn foo(x: T) -> R` 改造成 Verus 的确定性检查 proof fn：

```rust
proof fn det_foo(x: T, r1: R, r2: R)
    requires <reqs>
    ensures (<run1_postconditions> && <run2_postconditions>)
           ==> det_foo_equal(r1, r2)
```

Verus 如果无法证明这个 ensures，就说明存在两次调用返回不等的反例——即 spec 非确定。

三个子任务：

#### (a) `_build_symbols(spec) -> list[Symbol]`
符号表，binary_search 按顺序遍历并逐个窄化：
- `phase="input"`：函数参数（`&mut self` 时命名为 `pre_self_`）。
- `phase="output_simple"`：`r1`, `r2`（如果返回值是 `Result`/`Option`/`int`/`bool`...）。
- `phase="output_compound"`：`post1_self_`, `post2_self_`（如果返回 struct/Seq 或有 `&mut` 参数）。

#### (b) `_build_template(spec)` —— 生成 proof fn 模板
- 签名里把每个 `&mut` 参数拆成 `pre_*`, `post1_*`, `post2_*`。
- `_substitute_input(requires)`：`self → pre_self_`。
- `_substitute_run(ensures, run_id)`：`self → post{1,2}_self_`、`result → r{1,2}`、`old(self) → pre_self_`。
- **AST 级别的 match-arm binding rename**（`_rename_match_bindings`）：ensures 里如果有 `result matches Ok(x) ==> x > 0`，两次 run 都要把 `x` 重命名成 `x_1` / `x_2`，否则两次 run 的绑定会碰撞。这里用 tree-sitter 解析 `matches_expression` 的 pattern，收集 binding identifiers，递归查找 scoped references（跳过 `let x = ...` / quantifier 闭包等 shadow 作用域），做字节级 byte-range replace。
- 模板里留一个 `{ASSUMES}` 占位符给 binary_search 填。

#### (c) `_build_equal_fn(fn_name, params, arg_pairs, policy)` —— 结构等价 spec fn
`build_equal_expr(ty, lhs, rhs, policy)` 递归：
- primitive / Set / Seq：`lhs == rhs`。
- Result：`(lhs is Ok) == (rhs is Ok) && ((lhs is Ok) ==> build_equal_expr(ok_ty, lhs->Ok_0, rhs->Ok_0)) && <Err 同理或用 errs_equivalent 收缩>`。
- Struct with `spec_view`：逐 field 对比 view 的 fields（例如 `Bitmap.view().num_bits`）。
- ENUM：为每个 variant 发 `(lhs is V) == (rhs is V) && (lhs is V) ==> <inner eq>`。

`policy` 由 `equal_policy.py::EqualPolicy` 控制：
- `errs_equivalent`（默认 True）：所有 Err 归一类。
- `opaque_ok`：所有 Ok 归一类（allocator 返回不透明 handle 时用）。
- `ignore_fields` / `opaque_types`：按 field/type 名粗化。
- `custom_body`：彻底接管整个 fn body（人工兜底）。

`equal_llm.py::suggest_equal_policy` 是 LLM 兜底——把 spec 喂给 `copilot` CLI，让它判断需要哪些 knob（比如看到 `alloc` 返回 `Ok(addr)` 就建议 `opaque_ok=True`）。**带 JSON 格式的 cache**，同一 spec 不会重复调用。

`rebuild_equal_fn(det_spec)` 是 llm_refine 之后的 hook——UNKNOWN 类型被实例化成 struct 后，需要用更细的类型信息重新生成 equal fn。

---

### 3. Stage 1.5 — `llm_refine.py`：修补 UNKNOWN 类型（可选）

当 `type_sources` 里找不到某个类型定义（比如 kernel 里跨 crate 的类型），`Symbol.type.kind` 会留成 `UNKNOWN`。这时让 Copilot CLI 读整个 workspace，把 `DetCheckSpec` 的 symbols 数组 dump 成 JSON 发给它，让它返回 instantiated 版本：

- 带 `pre` / `post` / `refined` 三份 snapshot 到 `results/refine_cache/`。
- 用 `(function, symbols)` 的 sha256 做 cache key，再跑同一函数直接读 cache。
- refine 完后自动调 `rebuild_equal_fn` 重建 equal fn（类型变细了）。

---

### 4. Stage 2 + 3 — `binary_search.py` + `backend.py` + `verify.py` / `z3_backend.py`

搜索核心。

#### `backend.py`：一个 10 行的 Protocol
```python
class DetBackend(Protocol):
    def check(self, code: str, fn_name: str) -> VerifyResult: ...
```
两个 backend 都 satisfy。

#### `verify.py`：VerusRunner（subprocess 老路径）
- `inject_proof_fn(proof_file, code, marker="} // end verus!")` —— 在 `.proof.rs` 的 `} // end verus!` 前面插 `// === INJECTED DET CHECK ===\n<code>\n// === END INJECTED ===`。**防御性地**先 strip 掉旧注入（防止前一次 crash 留下的残骸）。
- `run_cargo_verus(...)` —— 跑 `cargo +nightly-2025-12-08 verus build -p <crate> --fwd-verus-args-to roots -- --verify-root --verify-function det_foo`。注意用 `build` 而不是 `verify` 是为了绕 cargo 的 fingerprint cache。支持通过 `verus_extra_args` 把 Verus flags（如 `--log smt-transcript`）穿透给 Verus。
- `parse_result` —— regex 把 stdout/stderr 解析成 `pass` / `fail` / `timeout` / `error`。
- `VerusRunner` —— 状态机，封装 inject + run + restore。`_ensure_baseline` 在第一次 check 前做一次"不注入的全量 verify"，防止 baseline 本身就坏导致所有结果不可信。

#### `z3_backend.py`：Z3Backend（快路径，本 session 新加）
- `run_cargo_verus` 加 `--log smt-transcript`，Verus 把整个 SMT session dump 到 `root.smt_transcript`。
- 正则分三层：
  - `_RE_CHECK_SAT_RESPONSE`：最后一次 check-sat 是 `sat` / `unsat` / `unknown`。
  - `_RE_GET_MODEL_RESPONSE`：找 `(get-model)` 后的 response block（Verus 失败时 Z3 自动 dump）。
  - `_lookup_model_value(body, name)`：手写的 s-expression scanner，提取 `(define-fun name () Sort Value)` 里的 Value。
- `tracked_symbols_from_det_spec(det_spec)` —— 取 `DetCheckSpec.symbols` 里不含 `@` / `.` 的 top-level 符号，加 `!` 后缀（Verus 的 SMT 命名惯例）。
- `witness_from_model(det_spec, model)` —— 如果 model 覆盖了**所有** tracked symbols，直接构造 `Witness.inputs/output1/output2`（按 `pre_` / `post1_` / `post2_` / `r1` / `r2` 前缀分桶），跳过整轮 narrowing。
- `summarise_model` —— 把 Z3 原始的 `(core!result.Result./Err Poly!val!4)` 压缩成 `Err(<opaque>)`。

**A/B 数据（bitmap 8 个函数）**：Z3 快路径相对原 binary_search 加速 **2.7×～76.7×**（其中 `alloc_range` 72 轮 → 2 轮）；所有函数的 verdict 两个 backend 一致。

#### `binary_search.py`：类型制导的窄化
核心数据结构 `AssumeNode`（一棵树）：
```
root
├── r1 (Result)
│   ├── variant: assume(r1 is Ok)
│   └── Ok_0:   assume(r1->Ok_0 == 3)
└── r2 (Result)
    └── variant: assume(r2 is Err)
```
同一个 node 改 assume 是 refinement（`[0,8] → [3,4] → 3`）；不同 node 累积（所有 constraints 都 AND 起来）。

`@strategy_for(TypeKind.X)` 装饰器注册每种类型的 narrowing 策略：
- **Result**：先试 `Ok`，fail 就递归进 Ok 内部；pass 就试 `Err`。
- **Option**：同理。
- **ENUM**：遍历每个 variant。
- **Struct**：递归每个 field（用 `spec_view` 的 fields 如果有）。
- **Integer**：先小范围 `[-8, 8]` 或 `[0, 16]`；fail 就二分 bisect；pass 就用完整类型范围再二分。
- **Set**：`empty` vs `len > 0`；非空则先 narrow length 再按 `.contains(v)` 找元素。SET 特别处理是因为 Verus 对无限 set 的 `Set::len()==0` 有歧义。
- **Seq**：len → elem bisect。
- **bool / unit / str**：有限候选枚举。
- **UNKNOWN**：LLM fallback（`llm_fallback.py::suggest_narrowing`）。

`SearchContext.test_and_set`：
1. 把 assume 临时装到 node 上。
2. DFS 收集整棵树的所有 assume，render 进模板。
3. `runner.check(code, fn_name)`。
4. FAIL → 保留，返回 True（继续深入 narrow）。
5. PASS → revert，返回 False（此分支不是 nondet 的出处，换一条）。

`binary_search(det_spec, runner)` 主流程：
1. **R0** 无 assume check —— pass 就是 det，直接返回；fail 就开始 narrow；error 视为 smoke-test 失败（template 本身 malformed）。
2. **Z3 快路径**（本 session 新加）：`hasattr(runner, "last_model")` 如果覆盖所有 top-level 符号，`witness_from_model` 直接构造 Witness 跳过 narrowing。
3. 按 symbol table 顺序（input → output_simple → output_compound）依次 narrow。
4. `_add_distinctness_witnesses` 最后补一刀：尝试 `!det_foo_equal(r1, r2, ...)` assume，FAIL 说明确实存在两个不等价的输出 tuple——强证据。

---

### 5. Stage 4 — `report.py`

**现状与实际功能有 gap**（见 Code Review D5）：

- `complete_witness(spec, witness, llm_client)` —— 从 assumes 反推 `inputs` / `output1` / `output2`（实际上只能处理 `var == value`，不处理嵌套 / view）。
- `_classify_gap` —— LLM 分类 gap 类型（`liveness` / `error_wildcard` / `frame_condition` / ...）。
- `generate_trace_report` / `generate_witness_report` / `generate_summary_json` —— Markdown + JSON 输出。

实际项目的主 driver 是仓库根目录的 `test_all.py`，它自己写了 results 的渲染，基本绕过了 report.py 的一半功能。

---

### 6. `llm_fallback.py` vs `llm_refine.py` vs `equal_llm.py`

这三个都用 LLM，但职责不同：

| 文件 | 何时调 | 输入 | 输出 | 状态 |
|---|---|---|---|---|
| `equal_llm.py` | Stage 1b，`gen_det` 之前 | `FunctionSpec` | `EqualPolicy` | **在用**（test_all.py 里有 `use_llm_equal_policy=True`） |
| `llm_refine.py` | Stage 1b 之后、Stage 2 之前 | `DetCheckSpec` with UNKNOWNs | `DetCheckSpec` with concrete types | **在用** |
| `llm_fallback.py` | Stage 2 narrowing 遇到 UNKNOWN 类型时 | `type_name`, `var_name`, `assumes` | "assume 表达式"字符串 | **几乎不用**（refine 之后基本没有 UNKNOWN） |

---

### 7. 文件速查表

| 文件 | 行数 | 主要职责 | 关键函数 |
|---|---|---|---|
| `types.py` | 254 | 所有 dataclass 契约 | `TypeInfo`, `Symbol`, `DetCheckSpec`, `Witness` |
| `backend.py` | 37 | Backend Protocol | `DetBackend.check` |
| `extract.py` | 784 | Stage 1a 源码解析 | `extract_spec`, `_resolve_types`, `_find_impl_type` |
| `gen_det.py` | 834 | Stage 1b 模板 + equal fn | `build_det_check_spec`, `_build_template`, `build_equal_expr`, `_rename_match_bindings` |
| `equal_policy.py` | 77 | Equal fn policy 数据类 | `EqualPolicy` |
| `equal_llm.py` | 226 | LLM 选 EqualPolicy | `suggest_equal_policy` |
| `llm_refine.py` | 298 | LLM 修 UNKNOWN 类型 | `refine_with_llm` |
| `llm_fallback.py` | 172 | 遗留 LLM narrow | `LLMFallback.suggest_narrowing` |
| `verify.py` | 321 | VerusRunner subprocess backend | `inject_proof_fn`, `run_cargo_verus`, `VerusRunner` |
| `z3_backend.py` | ~470 | Z3 model 解析 backend（新） | `Z3Backend.check_with_model`, `witness_from_model` |
| `binary_search.py` | 602 | Stage 2+3 类型制导窄化 | `binary_search`, `SearchContext`, `@strategy_for` |
| `orchestrator.py` | 174 | ⚠ 死代码，已与主干脱节 | `run_pipeline`, `main` |
| `report.py` | 200 | Stage 4 witness 渲染 | `complete_witness`, `write_reports` |
| `legacy/` | — | pre-Z3 版本的备份 | `binary_search.py`, `verify.py` |
