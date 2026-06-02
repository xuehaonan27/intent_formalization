我看完你的 draft 之后，感觉和我刚才的判断有一点变化。

因为你的 paper 其实已经做了一件非常重要的事：

> 你没有停留在 "spec completeness 是什么" 的哲学层面，而是找到了一条从 intent-level property → intent-free property 的桥。

具体来说：

```text
Spec Completeness
      ↓
Theorem 1
      ↓
Spec Determinism
      ↓
VC
      ↓
SMT Check
```

这是一个非常强的模式。

---

我觉得现在的问题变成：

> 在 Fan 提的那些 accountability principles 里面，
> 哪些还能像 determinism 一样，被 reduction 成一个可验证对象？

这决定了哪些方向是真 research。

哪些只是 checklist。

---

# 第一档：我觉得最有希望

## 1. Non-vacuity

这是我最看好的。

事实上甚至比 determinism 更通用。

---

你现在的 determinism 本质上在检查：

```text
Too many behaviors
```

spec 允许太多东西。

而 vacuity 检查：

```text
Too few meaningful constraints
```

spec 看起来很强。

实际上没说任何东西。

---

例如：

```rust
ensures result > 0
```

对于：

```rust
fn max(a,b)
```

这可能完全 vacuous。

因为：

```rust
result == max(a,b)
```

才是 intent。

---

Formal Methods 里其实有很多 vacuity work：

* model checking vacuity
* temporal logic vacuity
* mutation vacuity

但 Verus/Dafny spec 上几乎没人认真做。

---

而且它天然符合你的 theorem 风格。

你完全可以定义：

```text
Constraint Contribution
```

某个 ensures clause 被删除以后：

是否改变 admissible implementation space。

---

如果不改变：

```text
Vacuous
```

---

这和 determinism 一样：

从 intent-free 的 admissible implementation 出发。

---

我觉得这是最值得做的。

---

# 2. Assumption Accountability

这是第二个我觉得有机会的。

---

你的 draft 里面其实已经暴露出这个问题。

你写：

> Assume spec correctness.

然后证明：

```text
correctness + determinism
=
completeness
```

---

但：

spec correctness 从哪里来？

---

这是整个体系最大的 trusted base。

---

例如：

```rust
ensures result >= 0
```

可能 deterministic。

可能 non-vacuous。

但就是错的。

---

所以可以研究：

```text
What assumptions does completeness depend on?
```

---

类似：

```text
completeness certificate
```

输出：

```text
Requires:

- eq_f is correct
- user intent represented by g0
- implementation g0 trusted
- ...
```

---

这其实很接近 Fan 说的：

```text
trusted-base disclosure
```

但比 accountability 更具体。

---

# 3. Compositional Sufficiency

这个我觉得 surprisingly strong。

---

现实里的很多 verified systems：

问题不是单个 function spec。

而是：

```text
Function A spec
+
Function B spec
+
Function C spec
```

组合以后漏了东西。

---

例如：

```text
A guarantees X
B assumes X'
```

其中：

```text
X != X'
```

---

每个 spec 单独 deterministic。

系统不 deterministic。

---

这非常符合你现在的 entailment machinery。

因为本质上：

```text
cross-spec entailment
```

---

我甚至怀疑：

这个可能比 determinism 更有 impact。

因为真实 bug 更多。

---

# 第二档：值得做，但不一定能立住

## Intent Traceability

Fan 很喜欢这个。

但我有点怀疑。

---

因为它很容易退化成：

```text
Requirement
    ↓
Spec
```

mapping。

---

最后变成：

```text
coverage matrix
```

---

工业界喜欢。

学术界不一定买账。

---

除非你能证明：

```text
missing trace
⇒
higher bug rate
```

---

否则很难形成 theorem。

---

# Drift Sensitivity

这个方向挺有趣。

但感觉更偏 tool。

---

例如：

需求改一句话。

哪些 spec 会坏。

---

这更像：

```text
impact analysis
```

而不是 foundational property。

---

# 第三档：我觉得比较危险

## Determinacy

你已经做完了。

其实就是 determinism。

---

## Ambiguity

Formal spec 里没什么 ambiguity。

---

如果是：

```rust
ensures result > 0
```

语义是明确的。

只是 incomplete。

---

所以 ambiguity 更像自然语言问题。

---

很容易变成 LLM benchmark。

---

## Reader Convergence

## Decision Consistency

## Human Agreement

这些我会非常小心。

---

因为：

```text
People agree
≠
Spec correct
```

---

很多错误需求大家都能一致理解。

---

这个指标适合 HCI。

不太适合 FM。

---

# 如果我是你

结合你已经完成的 determinism paper。

我会把整个 roadmap 变成：

```text
Spec Accountability
    |
    +-- Determinism
    |      (done)
    |
    +-- Non-Vacuity
    |      (next paper)
    |
    +-- Assumption Accountability
    |      (trusted base)
    |
    +-- Compositional Sufficiency
           (system-level)
```

原因很简单：

这三个都有机会复用你现在的套路：

```text
Intent-level property
        ↓
Reduction theorem
        ↓
Intent-free property
        ↓
VC / SMT
        ↓
Witness
```

而这正是你这篇 draft 最有价值的地方。  

实际上我看完以后有个更激进的想法：

你们这个长期 agenda 未必叫 **Spec Accountability**。

它可能叫：

> **Specification Obligations**

即一个 spec 想被信任，需要满足哪些 obligation。

目前你已经完成了第一项：

```text
Determinism Obligation
```

下一项很自然就是：

```text
Non-Vacuity Obligation
```

这条线比一个大而泛的 accountability manifesto 更像能持续产出 5-10 年论文的研究计划。
