# View-quotient determinism — mechanical sweep failure summary (2026-06-05)

| # | Function(s) | Why it fails (one sentence) | Suggested fix |
|---|-------------|-----------------------------|---------------|
| 1 | [`StaticLinkedList::len`](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L65) (atmosphere) | An ensures clause reads the hidden field `value_list_len` directly, and the function has no `requires` constraining the precondition | Add `requires self.wf()`, or widen `view` to include `value_list_len` |
| 2 | [`StaticLinkedList::get_value`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L401) / [`get_next`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L413) / [`get_prev`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__remove_helper3.rs#L367) (atmosphere) | All three take a **physical slot index** and return the raw `arr_seq[index].{value/next/prev}`; the view only sees the abstract value-list `spec_seq`, leaving `arr_seq` unconstrained | `pub` → `pub(crate)/private` (preferred — these are internal slab-navigation helpers) |

---

## 1. Case 1: `StaticLinkedList::len`

Source: [`atmosphere/.../free_pages_are_not_mapped.rs`](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs) — struct at [L42](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L42), `len` at [L65](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L65), `view` at [L82](../../verusage/source-projects/atmosphere/verified/allocator/allocator__page_allocator_spec_impl__impl1__free_pages_are_not_mapped.rs#L82).

### 1.1 Struct

```rust
struct StaticLinkedList<T, N> {
    spec_seq:       Ghost<Seq<T>>,   // view fields = {spec_seq}
    value_list_len: usize,           // hidden
    head, tail, free_head, ...       // hidden
}
spec fn view(self) -> Seq<T> { self.spec_seq@ }
```

### 1.2 Function

```rust
fn len(&self) -> (l: usize)
    ensures
        l == self.value_list_len,            // (E1) directly exposes a hidden field
        self.wf() ==> l == self@.len(),      // (E2) conditional; aligns with the view only under wf
```

The function has **no `requires`**. (E2) is conditional: once the input fails `wf()`, it degenerates to `true`, leaving only (E1), which constrains a hidden field and says nothing about the view side.

### 1.3 Minimal counterexample

Let both `s1` and `s2` have `spec_seq@` equal to the empty sequence, with `value_list_len` set to `0` and `7` respectively; other fields are arbitrary. Neither state satisfies `wf()`, but because there is no precondition enforcing `wf()`, both calls are legal inputs.

- `pre1@ == pre2@ == ε` ✓
- Both satisfy ensures (only (E1) is active; (E2) trivially holds)
- `r1 = 0`, `r2 = 7`; `usize` has no view, so comparison falls back to `==` — fails.

### 1.4 Fixes

- **Add `requires self.wf()`**.
- **Widen `view` to include `value_list_len`**, e.g. `view(self) -> (Seq<T>, usize)`.

---

## 2. Case 2: `StaticLinkedList::get_value` / `get_next` / `get_prev`

These three functions share one signature shape, one precondition, one root cause, and one fix. 

Source (all on the same `StaticLinkedList<T, N>`):
- struct at [`slinkedlist__spec_impl_u__impl2__pop.rs:L20`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L20)
- `view`           at [`...pop.rs:L59`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L59)
- `array_wf`       at [`...pop.rs:L196`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L196)
- `spec_seq_wf`    at [`...pop.rs:L201`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L201)
- `get_value`      at [`...pop.rs:L401`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L401)
- `get_next`       at [`...pop.rs:L413`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__pop.rs#L413)
- `get_prev`       at [`slinkedlist__spec_impl_u__impl2__remove_helper3.rs:L367`](../../verusage/source-projects/atmosphere/verified/slinkedlist/slinkedlist__spec_impl_u__impl2__remove_helper3.rs#L367)

### 2.1 Struct (three-layer ghost design)

```rust
pub struct Node<T> { pub value: Option<T>, pub next: SLLIndex, pub prev: SLLIndex }

pub struct StaticLinkedList<T, const N: usize> {
    pub ar:              [Node<T>; N],            // exec — actual slab memory
    pub spec_seq:        Ghost<Seq<T>>,           // abstract value-list (== view)
    pub value_list:      Ghost<Seq<SLLIndex>>,    // logical-position ↔ physical-slot permutation
    pub value_list_head: SLLIndex,
    pub value_list_tail: SLLIndex,
    pub value_list_len:  usize,
    pub free_list:       Ghost<Seq<SLLIndex>>,
    pub free_list_head:  SLLIndex,
    pub free_list_tail:  SLLIndex,
    pub free_list_len:   usize,
    pub size:            usize,
    pub arr_seq:         Ghost<Seq<Node<T>>>,     // spec-mode shadow of `ar` (a Seq, not a [T;N])
}
pub open spec fn view(&self) -> Seq<T> { self.spec_seq@ }
```

### 2.2 Function

```rust
pub fn get_value(&self, index: SLLIndex) -> (ret: Option<T>)
    requires 0 <= index < N, self.array_wf(),
    ensures  ret == self.arr_seq@[index as int].value;

pub fn get_next (&self, index: SLLIndex) -> (next: SLLIndex)
    requires 0 <= index < N, self.array_wf(),
    ensures  next == self.arr_seq@[index as int].next;

pub fn get_prev (&self, index: SLLIndex) -> (prev: SLLIndex)
    requires 0 <= index < N, self.array_wf(),
    ensures  prev == self.arr_seq@[index as int].prev;
```

All three take a **physical slot index**, require only `array_wf()` (just `arr_seq.len() == N && size == N`), and return the raw `arr_seq` cell entry.

### 2.3 Where the defect lies

All three functions' return values are read from `arr_seq@[index]`. Their precondition is only `array_wf()`, which says nothing more than `arr_seq.len() == N && size == N` — **it does not constrain the relationship between `arr_seq` and `spec_seq`**. Under just `array_wf()`, two states with the same `spec_seq@` (i.e. the same view) can hold completely different `arr_seq@`, and so the returned `arr_seq@[index].{value,next,prev}` can differ.

### 2.4 Minimal counterexample (`get_value` representative)

Let `N = 3`, `index = 1`. Both states have `spec_seq@ == seq![1]`, `value_list@ == seq![0]` (so logical position 0 maps to physical slot 0):

| state | `spec_seq@` | `arr_seq@[0].value` | `arr_seq@[1].value` | `arr_seq@[2].value` | `value_list_len` | `wf()` |
|-------|-------------|---------------------|---------------------|---------------------|:----------------:|:------:|
| `s1`  | `seq![1]`   | `Some(1)` | `None`       | `None` | `1` | ✓ |
| `s2`  | `seq![1]`   | `Some(1)` | `Some(999)`  | `None` | `1` | ✓ |

Both have view `seq![1]`. But `s1.get_value(1) = None ≠ Some(999) = s2.get_value(1)`. The same construction works for `get_next` / `get_prev` (slot 1's `next`/`prev` fields are unconstrained by the view because slot 1 is outside `value_list`).

### 2.5 Fixes

- **`pub` → `pub(crate)/private` (recommended)** — call-site survey shows `get_value` / `get_next` / `get_prev` are used only by internal slab-navigation paths (`pop`, `remove_helper2`, `remove_helper3`).
- **Strengthen `fn wf`** — add clauses that determine the full contents of `arr_seq` from the view, and tighten the three functions' precondition from `array_wf()` to `wf()`.