# Spec-generation + determinism feedback case: `verus-gym-1000-b`

> Date: 2026-06-23
> Benchmark: Verus-SpecGym / Codeforces 1000B
> Task: `verus-gym-1000-b` — **Light It Up**
> Experiment directory:
> `results/specgen_det_feedback_batch_10_twostage_v2/verus-gym-1000-b/`

## 1. Problem

The problem gives a strictly increasing sequence of lamp switch times

```text
0 < a_1 < a_2 < ... < a_n < M
```

The lamp is on at time `0`; each `a_i` flips the on/off state; at time `M`
the lamp powers off. We may insert **at most one** additional switch time while
keeping the program good. The output is the maximum total time during which the
lamp is lit.

The Verus-SpecGym logical types are:

```rust
pub struct In1 {
    pub n: i64,
    pub m: i64,
    pub a: Seq<i64>,
    pub layout: i64,
}

pub struct Out {
    pub max_lit_time: i64,
}
```

This is a unique-output problem: for a fixed valid input, the expected answer is
a single integer `max_lit_time`.

## 2. Experiment setting

The corrected experiment uses a two-stage generation protocol.

1. **Oracle/equality stage.** Generate `specgen_output_equiv` first and freeze
   it. This function is the semantic equality used by determinism checking.
2. **Spec stage.** Generate `pre_spec` / `post_spec` with the oracle frozen.
3. **Determinism check.** Generate the usual determinism proof obligation:

   ```rust
   proof fn det_post_spec(input: In1, out1: Out, out2: Out)
       requires
           post_spec(input, out1),
           post_spec(input, out2),
       ensures
           specgen_output_equiv(input, out1, out2),
   {
   }
   ```

   The checker asks whether two outputs satisfying `post_spec` for the same
   input are equivalent under the frozen `specgen_output_equiv`.

Equivalently, the generated determinism equality is:

```rust
spec fn det_post_spec_equal(in1: In1, out1: Out, out2: Out) -> bool {
    specgen_output_equiv(in1, out1, out2)
}
```

## 2.1 What this case is meant to show

This case is a representative **algorithmic-spec** example. The LLM did not
write a declarative relational specification such as "there exists an insertion
and no insertion is better" in first-order form. Instead, it naturally wrote a
small **spec-level judge / reference algorithm** and then specified the output
as:

```rust
out.max_lit_time == specgen_best_lit_time_with_one_insert(...)
```

This is the common shape for competitive-programming specifications:

1. define input validity (`pre_spec`);
2. reimplement the intended computation in `spec fn` helpers;
3. assert that the observed result equals the helper result.

The determinism check is useful here because it asks a very narrow question:
after the LLM writes this judge-like spec, does the spec actually pin the
observable output field?  For this case, the answer is yes.

## 3. Frozen semantic oracle

The oracle pass generated:

```rust
pub open spec fn specgen_output_equiv(in1: In1, out1: Out, out2: Out) -> bool {
    out1.max_lit_time == out2.max_lit_time
}
```

Review: this is appropriate for this problem because `Out` has exactly one
observable field and the problem expects a unique integer answer.

## 4. Generated specification

The spec pass generated:

```rust
pub open spec fn pre_spec(in1: In1) -> bool {
    &&& 1 <= in1.n <= 100000
    &&& 2 <= in1.m <= 1000000000
    &&& in1.a.len() <= 100000
    &&& in1.n == in1.a.len() as i64
    &&& specgen_is_good_program_rec(in1.a, in1.m, 0, false)
}
```

with the helper:

```rust
pub open spec fn specgen_is_good_program_rec(
    rem: Seq<i64>,
    m: i64,
    prev: i64,
    seen_any: bool,
) -> bool
    decreases rem.len()
{
    if rem.len() == 0 {
        seen_any
    } else {
        let cur = rem.first();
        &&& 0 < cur
        &&& cur < m
        &&& (!seen_any || prev < cur)
        &&& specgen_is_good_program_rec(rem.drop_first(), m, cur, true)
    }
}
```

For the output relation, it generated a recursive characterization of lit time:

```rust
pub open spec fn specgen_lit_time_from(
    rem: Seq<i64>,
    m: i64,
    prev: i64,
    is_on: bool,
) -> int
    decreases rem.len()
{
    if rem.len() == 0 {
        if is_on {
            m - prev
        } else {
            0
        }
    } else {
        let nxt = rem.first();
        let here = if is_on { nxt - prev } else { 0 };
        here + specgen_lit_time_from(rem.drop_first(), m, nxt, !is_on)
    }
}
```

and a best-answer helper:

```rust
pub open spec fn specgen_best_lit_time_with_one_insert(
    rem: Seq<i64>,
    m: i64,
    prev: i64,
    is_on: bool,
) -> int
    decreases rem.len()
{
    if rem.len() == 0 {
        let base = if is_on { m - prev } else { 0 };
        let with_insert = if m - prev >= 2 { m - prev - 1 } else { base };
        if with_insert >= base {
            with_insert
        } else {
            base
        }
    } else {
        let nxt = rem.first();
        let tail = rem.drop_first();
        let here = if is_on { nxt - prev } else { 0 };
        let best_without_here =
            here + specgen_best_lit_time_with_one_insert(tail, m, nxt, !is_on);
        let best_with_here = if nxt - prev >= 2 {
            (nxt - prev - 1) + specgen_lit_time_from(tail, m, nxt, is_on)
        } else {
            best_without_here
        };
        if best_with_here >= best_without_here {
            best_with_here
        } else {
            best_without_here
        }
    }
}
```

The generated `post_spec` was:

```rust
pub open spec fn post_spec(in1: In1, out: Out) -> bool {
    pre_spec(in1) ==> out.max_lit_time as int
        == specgen_best_lit_time_with_one_insert(in1.a, in1.m, 0, true)
}
```

In other words, the generated postcondition has exactly the expected
"`result == judge(input)`" shape.

## 5. Determinism result

The determinism check result for round 0 was:

```json
{
  "status": "ok",
  "r0_z3": "unsat",
  "n_schemas": 77,
  "n_rounds": 1,
  "assumes": []
}
```

Interpretation:

- `r0_z3 = unsat` means the generated `post_spec` is deterministic with respect
  to the frozen semantic equality.
- No witness was needed.
- Since `specgen_output_equiv` compares `max_lit_time`, the result says the
  spec pins the numeric output uniquely for every valid input.

## 6. Review notes

This is a clean positive example for the experiment:

- The equality/oracle stage is independent from `post_spec`.
- The oracle is not vacuous (`true`) and does not call `pre_spec` or `post_spec`.
- The generated `post_spec` implies equality of `out.max_lit_time` across any
  two admissible outputs.

## 7. Is the generated judge correct?

The generated judge is:

```rust
specgen_best_lit_time_with_one_insert(in1.a, in1.m, 0, true)
```

The recurrence is a plausible and mostly correct dynamic-programming
characterization of the Codeforces task.

Why it matches the problem:

- `specgen_lit_time_from(rem, m, prev, is_on)` computes the remaining lit time
  for the current lamp state and the remaining original switch sequence.
- `specgen_best_lit_time_with_one_insert(rem, m, prev, is_on)` branches between:
  - not inserting in the current gap and using the one insertion later; and
  - inserting once in the current gap, when the integer gap has room
    (`next - prev >= 2` or `m - prev >= 2`).
- If the current state is on, inserting in the current gap should be as late as
  possible (`next - 1`) to lose only one lit unit; if the current state is off,
  inserting should be as early as possible (`prev + 1`) to gain as much lit time
  as possible. Both cases contribute `gap - 1`, which is exactly what the
  helper uses.
- The no-insertion option is preserved by the recursive `best_without_here`
  branch and by the base `base` value.

For the sample cases, this recurrence is consistent with the expected answers:

```text
[4, 6, 7], M = 10  -> 8
[1, 10],   M = 12  -> 9
[3, 4],    M = 7   -> 6
```

So for the purpose of this case study, the generated judge looks semantically
right.

Remaining caveats:

- The determinism check proves that `post_spec` is complete relative to the
  generated helper `specgen_best_lit_time_with_one_insert`; it does **not**
  independently prove that this helper exactly matches the Codeforces problem
  semantics.
- The generated `pre_spec` ignores the `layout` field. This may be acceptable if
  `layout` is a parser artifact that is always fixed by the harness, but it is
  not checked by the determinism experiment.
- Therefore this case supports the claim "determinism checking can detect
  whether generated specs leave observable outputs underconstrained", but it
  does not by itself validate semantic correctness against the natural-language
  problem.
