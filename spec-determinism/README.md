# Spec Determinism — Project Documentation

## Big Picture

**Goal:** Automatically detect specification incompleteness in Verus-verified code by checking whether specs are *deterministic* — i.e., whether they uniquely determine the output for each valid input.

**Core insight:** A complete specification allows exactly one valid output for each input. If the same input admits two different valid outputs, the spec is incomplete (under-constrained). We detect this mechanically via SMT, then use type-guided binary search to construct a concrete witness.

**No LLM required** for the core pipeline — pure SMT + type-guided search. LLM is only used as fallback when the parser/type system encounters unknown patterns.

## What We Built

### Tool: `spec-determinism`

Location: `~/intent_formalization/spec-determinism/`

**Architecture:** 6 modules, each with parser path + LLM fallback.

```
extract → gen_det → verify → binary_search → witness → reporter
```

| Module | What it does | Status |
|--------|-------------|--------|
| `extract` | Parse function sig + requires/ensures from Verus source | Basic (regex), needs tree-sitter |
| `gen_det` | Generate `Q(x,y1) && Q(x,y2) ==> y1==y2` proof fn | Working |
| `verify` | Inject proof fn, run cargo verus, parse result | Working |
| `binary_search` | Type-guided narrowing with AssumeTree | Working |
| `report` | Generate markdown/JSON reports | Basic |
| `llm_fallback` | Unified LLM fallback interface | Scaffolded |

### Key Data Structure: AssumeTree

A tree where each node holds one assume constraint. Refinement (e.g. `[0,8] → [3,4] → 3`) replaces the node's assume in-place. Different nodes (e.g. `r1 is Ok` + `r1->Ok_0 == 0`) accumulate.

```
root
├── pre_self_ (Bitmap)
│   ├── num_bits: == 8                    ← same-node replace during bisection
│   └── set_bits: == Set::empty()
├── r1 (Result)
│   ├── variant: r1 is Ok                ← different node, kept
│   └── Ok_0: == 0                       ← different node, kept
├── r2 (Result)
│   ├── variant: r2 is Ok
│   └── Ok_0: == 1
├── post1_self_ (Bitmap)
│   ├── num_bits: == 8
│   └── set_bits: == {}.insert(0)
└── post2_self_ (Bitmap)
    ├── num_bits: == 8
    └── set_bits: == {}.insert(1)
```

Single operation: `test_and_set(node, assume)` — set node.assume, collect all tree assumes, run Verus, FAIL → keep, PASS → revert.

### Binary Search Protocol

**Phase 1: Narrow inputs (all input variables)**
- `&mut self` → split into `pre` (input) + `post` (output)
- `&mut param` → same split
- Value params → input only

**Phase 2: Narrow outputs (simple types first, then compound)**
- Phase 2a: Result/Option/Enum variants + inner values (simple)
- Phase 2b: Struct fields, Set elements (compound)
- Heuristic: enum variants first → gives Z3 the match-branch context before narrowing dependent fields

**Type strategies** (decorator-based registry):

| Type | Strategy |
|------|----------|
| `Result<T,E>` | Binary: try Ok, FAIL → narrow inner, PASS → cross-variant gap |
| `Option<T>` | Binary: try Some/None |
| `Enum` | Try each variant |
| `Struct` | Recurse into fields (use spec view `@` if available) |
| `int/usize/...` | Small range first `[0,16]`/`[-8,8]`, FAIL → bisect, PASS → try full range → PASS → skip |
| `bool` | Try true/false |
| `Set<T>` | Empty → len bisection → element-by-element via `contains()` + full set expr |
| `Seq<T>` | Len → element-by-element |
| Unknown | LLM fallback |

### Integer Bisection

```
_bisect_range(var, lo, hi):
  if lo == hi: test_and_set(var == lo)
  else:
    mid = (lo + hi) // 2
    test_and_set(var >= lo && var <= mid)
    FAIL → recurse [lo, mid]
    PASS → recurse [mid+1, hi]
```

Small range PASS → full range PASS → skip (not a nondeterminism source).
Small range PASS → full range FAIL → bisect full range.

### Set Element Narrowing

Sets have no index operation. Strategy:
1. Python-side maintains element list
2. Find each element via `var.contains(val)` probing
3. Confirm with full set expression: `var == Set::empty().insert(e1).insert(e2)...`

## Case Study: `bitmap::alloc`

**Function:** `pub fn alloc(&mut self) -> Result<usize, Error>`

**Spec summary:** If bitmap is not full, allocate any free bit and return its index. If full, return error.

**Result: NONDETERMINISTIC** — 60 Verus calls

```
INPUT:
  pre = Bitmap { num_bits: 8, set_bits: {} }     // empty 8-bit bitmap

OUTPUT 1:
  result = Ok(0)
  post = Bitmap { num_bits: 8, set_bits: {0} }   // allocated bit 0

OUTPUT 2:
  result = Ok(1)
  post = Bitmap { num_bits: 8, set_bits: {1} }   // allocated bit 1
```

**Gap type:** Design choice — spec intentionally does not constrain which free bit is selected. This is **not a real bug** — it's intentional nondeterminism.

**Filtering:** Use `custom_equality` (human/LLM written) to accept any Ok result as equivalent:
```rust
spec fn alloc_equal(r1, r2, post1, post2) -> bool {
    match (r1, r2) {
        (Ok(_), Ok(_)) => true,
        (Err(e1), Err(e2)) => e1 == e2,
        _ => false,
    }
}
```

## Design Decisions & Lessons Learned

1. **`&mut` params are both input and output** — split ALL `&mut` (not just self) into pre/post
2. **Input first, then output** — output depends on input
3. **Simple outputs before compound outputs** — enum variants give Z3 match-branch context, making struct field narrowing much easier
4. **Same-node replace, different-node accumulate** — the AssumeTree naturally handles this
5. **Z3 can fail on valid constraints** — `closed spec fn` is visible in same crate, but complex Set/quantifier reasoning can still timeout. Output ordering mitigates this.
6. **Small range PASS ≠ skip** — must also try full range before skipping (trigger could be at large value)
7. **Set elements need full-set comparison** — no index access, use `contains()` to find elements then confirm with full set expr

## Known Limitations / TODOs

### Immediate
- [ ] **Extract module**: currently requires manual `FunctionSpec` construction. Need to auto-parse `#[verus_spec(...)]` macros.
- [ ] **Duplicate rounds**: R14/R15 both try `r1->Ok_0 == 0` (bisect reaches lo==hi then tries exact again). Minor cleanup.
- [ ] **custom_equality**: add `FunctionSpec.equality_fn` field and `gen_det` support for `==> my_equal(...)` instead of `==> y1 == y2`.
- [ ] **Witness completion**: derive exec-level fields from view fields (e.g. `usage` from `set_bits.len()`).

### Next Steps
- [ ] Run `bitmap::new` and `bitmap::set` through the tool
- [ ] Run `slab` and `sorted-vec` modules
- [ ] Implement auto-extraction from Verus source (tree-sitter or regex for `#[verus_spec]`)
- [ ] Build reporter that generates human-readable witness docs (like `det_complete_witnesses.md`)
- [ ] Integrate `custom_equality` — human/LLM writes `my_equal`, tool reruns with it

### Future
- [ ] Composition testing: multi-function traces (`alloc(); set(); free()`)
- [ ] Z3 model extraction: when binary search is too slow, extract SMT model directly
- [ ] Automation: given a crate, find all pub fns, extract specs, run det check, report
- [ ] Publish as standalone tool / ClawHub skill

## Repository Structure

```
~/intent_formalization/spec-determinism/
├── DESIGN.md              # Architecture design doc
├── test_bitmap.py         # Integration test on bitmap::alloc
├── results/
│   └── bitmap_alloc.md    # Complete witness report
└── src/
    ├── __init__.py
    ├── types.py           # Shared data types
    ├── extract.py         # Spec extraction (regex + LLM fallback)
    ├── gen_det.py         # Det proof fn generator
    ├── verify.py          # Verus runner (inject/restore/parse)
    ├── binary_search.py   # AssumeTree + strategy registry + search driver
    ├── report.py          # Witness completion + reporters
    ├── llm_fallback.py    # Unified LLM fallback
    └── orchestrator.py    # Pipeline driver + CLI

~/.openclaw/workspace/skills/spec-determinism/
└── SKILL.md               # Skill doc (theory + protocol)
```
