# View-quotient determinism candidates on the complete corpus — 2026-06-04

Sweep of all Step-1-complete (`status: ok`) entries in
`spec-determinism/results-verusage-viewreg/<project>/full_run.json` looking for
**A-type** cases:

> Concrete-input determinism passes (Step 1), but view-quotient determinism
> fails (Step 2) under the view-aware `E_R` defined in
> [`view-quotient-determinism-plan-2026-06-04.en.md`](view-quotient-determinism-plan-2026-06-04.en.md).

Companion doc to the plan (this is the empirical evaluation that backs §5/§6
of that plan).

## 1. Method

For each `status: ok` det-spec artifact:

1. Parse `det_check_template` into `requires` and `ensures`.
2. Look up `self_type`'s `view()` definition in the corpus mirror at
   `verusage/source-projects/`; record the set of fields it reads as the
   **view-field set** `vf(T)`. A type with no `view()` is skipped (view-quotient
   degenerates to concrete determinism).
3. Walk each `ensures` clause on the side of `r1` / `post1_self_`. The clause
   is a **hidden-state leak** iff:
   - it mentions `(pre_)?self_.X` with `X ∉ vf(self_type)`, **and**
   - it constrains an output observable under the new view-aware `E_R`:
     - `r1` directly, **or**
     - `post1_self_@` (whole view), **or**
     - `post1_self_.Y` / `post1_self_.Y@` with `Y ∈ vf`.

   Frame clauses of the shape `post1_self_.X == (pre_)?self_.X` with
   `X ∉ vf` are **not** a leak — `post.X` is not observable when the post-state
   is compared by view.
4. The candidate is **A-type** iff `requires` does not contain a wf-style
   predicate (`(pre_)?self_.{wf,valid,invariant,invariants,inv}()`) that could
   rescue the leak.

`E_R` rule (consistent with the plan, §1):

```
E_R(r1, r2)  :=  ⋀_i  eq_i(r1[i], r2[i])
  where  eq_i(x, y)  =  x@ == y@      if τ_i has a `view`
                       x == y         otherwise
```

`&mut self` post-states are an output position and follow the same rule.

The scan is in [`/tmp/vq/scan_a_type_v3.py`](#) (script reproduced in §6).

## 2. Summary

| project          | Step-1 ok entries | leak candidates (unique) | A-type | rescued by `requires` |
|------------------|------------------:|-------------------------:|------:|----------------------:|
| atmosphere       |              1242 |                        4 |     4 |                     0 |
| ironkv           |               171 |                        1 |     0 |                     1 |
| memory-allocator |                15 |                        0 |     0 |                     0 |
| nrkernel         |                 6 |                        0 |     0 |                     0 |
| anvil-library    |                 0 |                        0 |     0 |                     0 |
| storage          |                 0 |                        0 |     0 |                     0 |
| vest             |                 2 |                        0 |     0 |                     0 |
| **total**        |          **1436** |                    **5** | **4** |                 **1** |

Unique here means `(project, function, type-base)`. The 4 A-type candidates
expand to **136 ok instances** when counted at the per-callsite level the
harness inlines into:

| (function, type)                          | distinct ok instances |
|-------------------------------------------|----------------------:|
| `StaticLinkedList::len`                   |                   114 |
| `StaticLinkedList::set_next`              |                    10 |
| `StaticLinkedList::set_prev`              |                    10 |
| `StaticLinkedList::set_value`             |                     2 |
| **total**                                 |               **136** |

Note the next section narrows this further: **only `len` is A-type under the
new view-aware `E_R`**. The three `set_*` cases are A-type only under the
**existing dumper-generated `E_R`** (which compares `post_self_` structurally
via `==`); they cease to be A-type once `E_R` is fixed to compare by view as
the plan prescribes. They are included here because they expose a parallel
issue: the dumper's equality function itself is not yet view-aware.

## 3. Confirmed A-type: `StaticLinkedList<T, N>::len`

### 3.1 Source

```rust
// atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__init.rs:43-50
pub fn len(&self) -> (l: usize)
    // no requires
    ensures
        l == self.value_list_len,             // ① reads hidden field
        self.wf() ==> l == self.len(),         // ② only under wf
        self.wf() ==> l == self@.len(),        // ③ only under wf
{ unimplemented!() }

// view definition (same file, line 59)
pub open spec fn view(&self) -> Seq<T> { self.spec_seq@ }
```

Struct (line 20):

```rust
pub struct StaticLinkedList<T, const N: usize> {
    pub ar: [Node<T>; N],
    pub spec_seq: Ghost<Seq<T>>,            // view reads this
    pub value_list: Ghost<Seq<SLLIndex>>,
    pub value_list_head: SLLIndex,
    pub value_list_tail: SLLIndex,
    pub value_list_len: usize,              // ← leaked by `len`'s ensures
    pub free_list: Ghost<Seq<SLLIndex>>,
    pub free_list_head: SLLIndex,
    pub free_list_tail: SLLIndex,
    pub free_list_len: usize,
    pub size: usize,
    pub arr_seq: Ghost<Seq<Node<T>>>,
}
```

Generated obligation (artifact
`atmosphere__..__free_pages_are_not_mapped__len`):

```
proof fn det_len<T, const N: usize>(self_: StaticLinkedList<T, N>, r1: usize, r2: usize)
    ensures
        ({ &&& (r1 == self_.value_list_len)
           &&& (self_.wf() ==> r1 == self_.len())
           &&& (self_.wf() ==> r1 == self_@.len())
           &&& (r2 == self_.value_list_len)
           &&& (self_.wf() ==> r2 == self_.len())
           &&& (self_.wf() ==> r2 == self_@.len())
        }) ==> det_len_equal(r1, r2),
{ {ASSUMES}}

spec fn det_len_equal(r1: usize, r2: usize) -> bool { (r1 == r2) }
```

### 3.2 Step 1 (concrete-input determinism)

```
P(self_)    := true
Q(self_, r) := r == self_.value_list_len
             ∧ (self_.wf() ⟹ r == self_.len())
             ∧ (self_.wf() ⟹ r == self_@.len())
E_R(r1, r2) := r1 == r2

⊢  ∀ self_, r1, r2.  Q(self_, r1) ∧ Q(self_, r2) ⟹ r1 == r2
```

Trivially valid (both equal `self_.value_list_len`). Verus confirms in
913ms on the artifact; corpus marks `status: ok`.

### 3.3 Step 2 (view-quotient determinism)

```
V(s1, s2) := s1@ == s2@  ≡  s1.spec_seq@ == s2.spec_seq@

⊬  ∀ s1, s2, r1, r2.  Q(s1, r1) ∧ Q(s2, r2) ∧ V(s1, s2) ⟹ r1 == r2
```

Counterexample with `T = u8`, `N = 4`:

| state | `spec_seq@` | `value_list_len` | `wf()` | view |
|-------|-------------|------------------|--------|------|
| `s1`  | `Seq::empty()` | `0`           | `false` (arbitrary garbage in other fields) | `ε` |
| `s2`  | `Seq::empty()` | `7`           | `false` (arbitrary garbage in other fields) | `ε` |
| `r1 = 0`, `r2 = 7` | | | | |

Per-clause check:

| obligation | `s1, r1=0` | `s2, r2=7` |
|------------|------------|------------|
| `r == self_.value_list_len`            | `0 == 0` ✓ | `7 == 7` ✓ |
| `wf ⟹ r == self_.len()`                | vacuous (`wf=false`) ✓ | vacuous ✓ |
| `wf ⟹ r == self_@.len()`               | vacuous ✓               | vacuous ✓ |
| `V(s1, s2)`: `s1@ == s2@`              | `ε == ε`            ✓    | — |
| `E_R(r1, r2)`: `r1 == r2`              | `0 == 7`            ✗    | — |

`P` is vacuous so the domain-preservation sub-obligation
`P(s1) ∧ V(s1, s2) ⟹ P(s2)` is trivially satisfied — the failure is in the
**core** view-quotient obligation, not in domain preservation.

### 3.4 Why this is a real spec issue, not just a counter-modelling artifact

The two pieces of state in the struct are intentionally separate:

- `spec_seq: Ghost<Seq<T>>` — the spec/view side.
- `value_list_len: usize` — the impl's runtime length counter; the
  caller never observes it directly except through `len()`.

`wf()` is what ties them together (e.g. it asserts
`value_list_len == self@.len()`). `len`'s author wrote three ensures clauses:
the unconditional one reads the runtime counter, the two conditional ones
relate the result to the view **only under `wf`**. Without a
`requires self.wf()`, the spec is committing to "this function returns
`value_list_len`" regardless of whether the struct is well-formed —
which leaks hidden state through the result, exactly what view-quotient
captures.

### 3.5 Two minimal fixes (either makes Step 2 pass)

1. Move the view-level statement out of the conditional and drop the leak:
   ```rust
   pub fn len(&self) -> (l: usize)
       requires self.wf(),
       ensures  l == self@.len() as usize,
   ```
   The unconditional clause `l == self.value_list_len` is no longer needed —
   under `wf` it follows from `l == self@.len()`.

2. Keep the unconditional clause but add the rescue:
   ```rust
   pub fn len(&self) -> (l: usize)
       requires self.wf(),
       ensures  l == self.value_list_len,
                l == self@.len(),
   ```
   Now `wf` forces `value_list_len == self@.len()`, so the witness pair
   above is no longer reachable.

### 3.6 Reach in the corpus

114 `ok` instances of `StaticLinkedList::len` across atmosphere — the harness
inlines `len` into every transitive caller (allocator, page-map, container,
syscall layers). All 114 share the same root spec.

## 4. Borderline cases

### 4.1 `StaticLinkedList::{set_value, set_next, set_prev}` — A-type only under old `E_R`

These three mutating helpers share the pattern (showing `set_value`):

```
requires (pre_self_.array_wf()),
ensures
    ({  &&& (post1_self_.array_wf())
        &&& (post1_self_.arr_seq@[index].value == v)
        &&& (∀ i ≠ index, post1_self_.arr_seq@[i] =~= pre_self_.arr_seq@[i])
        &&& (post1_self_.spec_seq@      == pre_self_.spec_seq@)         // view frame
        &&& (post1_self_.value_list_head == pre_self_.value_list_head)  // hidden frames
        &&& (post1_self_.value_list_tail == pre_self_.value_list_tail)
        &&& (post1_self_.value_list_len  == pre_self_.value_list_len)
        &&& (post1_self_.free_list_head  == pre_self_.free_list_head)
        &&& (post1_self_.free_list_tail  == pre_self_.free_list_tail)
        &&& (post1_self_.free_list_len   == pre_self_.free_list_len)
        ... (symmetric for post2_self_)
    }) ==> det_set_value_equal(r1, r2, post1_self_, post2_self_)
```

The dumper-generated `equal_fn` is **structural**:
```
spec fn det_set_value_equal(r1, r2, post1, post2) -> bool {
    (r1 == r2) && (post1 == post2)
}
```

- **Old `E_R` (struct `==`)**: under view-equal `pre_self_` with differing
  hidden fields (say `value_list_head`), the frame ties
  `post.value_list_head = pre.value_list_head`, so
  `post1.value_list_head ≠ post2.value_list_head`, and structural `==`
  fails. **A-type.**
- **New view-aware `E_R`** (`post_self_@ == post_self_@`, i.e. compare
  `spec_seq@`): the frame `post.spec_seq@ == pre.spec_seq@` pins the
  view, and `pre1.spec_seq@ = pre2.spec_seq@` forces
  `post1.spec_seq@ = post2.spec_seq@`. **Not A-type.**

So adopting the view-aware `E_R` in the plan **automatically removes** these
three cases. They are still recorded here because they motivate one of the
plan's implementation choices: the equal-fn generator must compare
view-bearing post-states by `@`, not structurally.

`requires pre_self_.array_wf()` does not rescue them under the old `E_R`
(`array_wf` is a partial invariant on `arr_seq` and `ar` only — it says nothing
about `value_list_head/_tail/_len` etc.). Hence they show up in my scan as
"no wf-style requires."

Instance counts: `set_value` ×2, `set_next` ×10, `set_prev` ×10 ok rows.

### 4.2 `DelegationMap<K>::get_internal` (ironkv) — rescued by `requires self.valid()`

```rust
// ironkv/verified/delegation_map_v/delegation_map_v__impl4__set.rs:238-246
fn get_internal(&self, k: &K) -> (res: (ID, Ghost<KeyIterator<K>>))
    requires
        self.valid(),
    ensures ({
        let (id, glb) = res;
        &&& id@ == self@[*k]
        &&& self.lows.greatest_lower_bound_spec(KeyIterator::new_spec(*k), glb@)  // ← reads self.lows
        &&& id@.valid_physical_address()
    }),
{ unimplemented!() }
```

- `view = self.m@`; `self.lows` is a hidden concrete field.
- The second ensures clause pins `glb@` (the ghost output) via `self.lows`,
  which view does not project.
- **Rescued by** `requires self.valid()`. `valid()` (line 225-235) asserts
  ```
  ∀ k, i, j.  self.lows@.contains_key(i) ∧ self.lows.gap(...,j) ∧ ...
              ⟹  self@[k] == self.lows@[i]@
  ```
  i.e. `self.lows@` is fully determined by `self.m@` (= the view). Hence
  any two `valid` view-equal states already agree on `self.lows@`, and
  `greatest_lower_bound_spec` produces the same `glb` on both. Step 2 holds.

Recorded for completeness. It is a **negative result** for the audit (the
spec is fine *because* the wf-rescue genuinely closes the gap), not an
A-type case.

### 4.3 `PageAllocator::set_*` etc. — view-quotient degenerate

`atmosphere::PageAllocator`, `atmosphere::Quota`, `atmosphere::Page`,
`atmosphere::PageTable`, `atmosphere::Kernel` do not define `spec fn view`
anywhere in the corpus. For these self-types `V(s1, s2)` collapses to
structural equality, Step 2 ≡ Step 1, and there is no view-quotient question
to ask. My v1 scan listed seven `PageAllocator::set_*` rows under the
naive "ensures references hidden field" criterion; they are all filtered
out at step 2 of the methodology.

If/when these types acquire a `view`, the same scan should be re-run.

## 5. Implications

1. **Coverage finding**: of 1436 Step-1-complete obligations across seven
   projects, exactly **one** unique function is A-type under the
   view-quotient framework (`StaticLinkedList::len`), with 114 corpus
   instances. The audit is high-precision: the new check fires only on
   genuinely under-specified spec.
2. **By-product**: the three `set_*` candidates surface a separate weakness
   in the existing dumper — it still compares view-bearing post-states
   structurally. Fixing the equal-fn generator to honour the type's `view()`
   would close those cases without changing the ensures.
3. **`requires` discipline**: the rescued `DelegationMap::get_internal`
   case shows that `valid()` (when it ties hidden state to the view) is
   the right idiom for any function that needs to read hidden state in
   ensures. The `len` author should either drop the hidden-state ensures
   or add `requires self.wf()` — both fixes appear in §3.5.

## 6. Reproducer

Scan script (run as `python3 scan_a_type_v3.py`):

```python
"""
A-type scanner: ensures clause leaks pre_self_'s hidden field into an
output observable under the view-aware E_R.
"""
import os, re, json, glob
ROOT = "spec-determinism/results-verusage-viewreg"
SRC  = "verusage/source-projects"
PROJECTS = ["atmosphere","ironkv","memory-allocator","nrkernel",
            "anvil-library","storage","vest"]
WF_HINTS  = re.compile(r'(?:pre_)?self_\.(wf|valid|invariants?|inv)\(\)')

def strip_generics(t):
    return re.split(r'[<\s]', (t or "").strip(), maxsplit=1)[0]

def split_template(tpl):
    req = ens = ''
    m = re.search(r'\n\s*requires\s+([\s\S]*?)\n\s*ensures\b', tpl)
    if m: req = m.group(1)
    me = re.search(r'\n\s*ensures\s+([\s\S]*?)\n\s*\{', tpl)
    if me: ens = me.group(1)
    return req, ens

def has_pre_self_hidden(expr, vf):
    for m in re.finditer(r'(?:pre_)?self_\.([a-zA-Z_]\w*)(?![@(\w])', expr):
        if m.group(1) not in vf:
            return m.group(1)
    return None

def split_clauses(ens):
    cl, i = [], 0
    while True:
        idx = ens.find('&&&', i)
        if idx < 0: break
        p = ens.find('(', idx)
        if p < 0: break
        d, j = 1, p+1
        while j < len(ens) and d > 0:
            if ens[j]=='(': d += 1
            elif ens[j]==')': d -= 1
            j += 1
        cl.append(ens[p+1:j-1].strip())
        i = j
    return cl

_view_cache = {}
def lookup_view(typ):
    base = strip_generics(typ)
    if base in _view_cache: return _view_cache[base]
    found = None
    for path in glob.glob(f"{SRC}/**/*.rs", recursive=True):
        try: txt = open(path, errors="ignore").read()
        except: continue
        if base not in txt: continue
        for m in re.finditer(rf'\bimpl\b[^{{]*\b{re.escape(base)}\b[^{{]*\{{', txt):
            i,d = m.end(), 1
            while i < len(txt) and d > 0:
                if txt[i]=='{': d += 1
                elif txt[i]=='}': d -= 1
                i += 1
            block = txt[m.end():i-1]
            vm = re.search(r'(?:open|closed)?\s*spec\s+fn\s+view\s*\(', block)
            if vm:
                bstart = block.find('{', vm.end())
                if bstart < 0:
                    found = set(); continue
                dd, j = 1, bstart+1
                while j < len(block) and dd > 0:
                    if block[j]=='{': dd += 1
                    elif block[j]=='}': dd -= 1
                    j += 1
                body = block[bstart+1:j-1]
                ff = set(re.findall(r'\bself\.([a-zA-Z_]\w*)', body))
                if ff or 'unimplemented!' not in body:
                    _view_cache[base] = (ff, True); return _view_cache[base]
                found = ff
    _view_cache[base] = ((found or set()), found is not None)
    return _view_cache[base]

results = []; seen = set()
for proj in PROJECTS:
    fr = os.path.join(ROOT, proj, "full_run.json")
    if not os.path.exists(fr): continue
    for r in json.load(open(fr)):
        if r.get("status") != "ok": continue
        ds = os.path.join(ROOT, proj, "artifacts", r["artifact_key"], "det_spec.json")
        if not os.path.exists(ds): continue
        d = json.load(open(ds))
        st = d.get("self_type") or ""
        if not st: continue
        req, ens = split_template(d.get("det_check_template", ""))
        vf, has_view = lookup_view(st)
        if not has_view: continue
        wf_safe = bool(WF_HINTS.search(req))
        leaks = []
        for c in split_clauses(ens):
            if 'r2' in c or 'post2_self_' in c: continue
            hf = has_pre_self_hidden(c, vf)
            if not hf: continue
            mfr = re.fullmatch(r'\s*post1_self_\.([a-zA-Z_]\w*)\s*==\s*(?:pre_)?self_\.\1\s*', c)
            if mfr and mfr.group(1) not in vf: continue
            if re.search(r'\br1\b', c):
                leaks.append(('return', hf, c)); continue
            mv = re.search(r'post1_self_(?:@|\.([a-zA-Z_]\w*))', c)
            if mv:
                if mv.group(1) is None or mv.group(1) in vf:
                    leaks.append(('post_view', hf, c))
        if not leaks: continue
        key = (proj, r["function"], strip_generics(st))
        if key in seen: continue
        seen.add(key)
        results.append((proj, r["function"], st, wf_safe, leaks, r["artifact_key"]))

A = [x for x in results if not x[3]]
print(f"candidates={len(results)}, A-type={len(A)}, rescued={len(results)-len(A)}")
for proj, fn, st, wf, leaks, ak in A:
    print(f"[{proj}] {st}::{fn}  ({len(leaks)} leaks)  {ak}")
```

Expected output (2026-06-04 corpus):

```
candidates=2, A-type=1, rescued=1
[atmosphere] StaticLinkedList<T, N>::len  (1 leaks)  atmosphere__verified__allocator__allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped__len
```

## 7. Open follow-ups

- Extend the wf-rescue filter: today we conservatively treat any
  `requires self.wf()/valid()/...` as a rescue. To classify more precisely,
  unfold each rescue predicate's body and check whether it tightens the
  hidden field enough for view-determinism. `DelegationMap::get_internal`
  is verified by hand in §4.2; the rest are presumed but not mechanised.
- Re-run on `PageAllocator`, `Quota`, `Page`, `PageTable`, `Kernel` once
  they grow a `view`.
- Audit `&mut` parameters other than `self_`. The current scan only
  considers `post_self_`. If the dumper ever emits a det template with
  `post1_arg_` for a view-bearing `&mut arg`, the same rule applies.
