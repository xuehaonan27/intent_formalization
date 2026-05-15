You are helping a Verus-based determinism checker compute **semantic
equality** for a user-defined Rust type. The checker currently falls
back to *structural* `==` whenever it can't find a `View` impl,
producing spurious "two implementations differ" witnesses on fields
the spec author never meant to pin down (allocator addresses, ghost
indices, sequence ordering inside a Set, etc.).

Your job: emit a Verus `impl View for <T>` block that projects the
type to an abstract view capturing **only the dimensions the spec
actually constrains**. The checker will then compare `lhs.view() ==
rhs.view()` instead of structural `==`.

## Target type
Project: `nrkernel`
kind=enum  qualified_name=GPDE  derives=[]  cfg=[]

```
pub ghost enum GPDE {
    Directory {
        addr: usize,
        /// Present; must be 1 to map a page or reference a directory
        P: bool,
        /// Read/write; if 0, writes may not be allowed to the page controlled by this entry
        RW: bool,
        /// User/supervisor; user-mode accesses are not allowed to the page controlled by this entry
        US: bool,
        /// Page-level write-through
        PWT: bool,
        /// Page-level cache disable
        PCD: bool,
        ///// Accessed; indicates whether software has accessed the page referenced by this entry
        //A: bool,
        /// If IA32_EFER.NXE = 1, execute-disable (if 1, instruction fetches are not allowed from
        /// the page controlled by this entry); otherwise, reserved (must be 0)
        XD: bool,
    },
    Page {
        addr: usize,
        /// Present; must be 1 to map a page or reference a directory
        P: bool,
        /// Read/write; if 0, writes may not be allowed to the page controlled by this entry
        RW: bool,
        /// User/supervisor; if 0, user-mode accesses are not allowed to the page controlled by this entry
        US: bool,
        /// Page-level write-through
        PWT: bool,
        /// Page-level cache disable
        PCD: bool,
        /// Global; if CR4.PGE = 1, determines whether the translation is global; ignored otherwise
        G: bool,
        /// Indirectly determines the memory type used to access the page referenced by this entry
        PAT: bool,
        /// If IA32_EFER.NXE = 1, execute-disable (if 1, instruction fetches are not allowed from
        /// the page controlled by this entry); otherwise, reserved (must be 0)
        XD: bool,
    },
    /// An `Invalid` entry is an entry that does not contain a valid mapping. I.e. the entry is
    /// either empty or has a bit set that the intel manual designates as must-be-zero. Both empty
    /// and invalid entries cause a page fault if used during translation.
    Invalid,
}
```

## Already-resolved views of dependency types

(no dependency views — all field types are primitives or unknown)

## Output format (single fenced ```json block)

```json
{
  "viewed_type":  "<the Verus type expression for Self::V>",
  "view_decl":    "<the complete `impl View for <T>` block, source-form Verus>",
  "depends_on_views_of": ["<short type name>", ...],
  "rationale":    "<1-3 sentences explaining the projection choice>"
}
```

Required keys: `viewed_type`, `view_decl`, `rationale`. The
`depends_on_views_of` array lists short names of other user types
whose `.view()` you used inside `view_decl` (so a future pass can
synthesise them recursively). Omit or empty if none.

The `view_decl` must:
- be a single `impl<...> View for <T>{ ... }` item, valid Verus
  syntax (it will be parsed by tree-sitter-verus before caching);
- contain exactly one `type V = ...;` and one
  `closed spec fn view(&self) -> Self::V { ... }` (or
  `open spec fn`, your choice);
- preserve all generic parameters and where-clause bounds from the
  original type;
- never reference identifiers that aren't already in scope at the
  type-def site (no fresh imports);
- use `Seq<X@>`, `Set<X@>`, `Map<K@, V@>`, `Option<X@>`, `X@`
  recursively for fields whose types have a view — `@` is sugar for
  `.view()` and works on any type with an `impl View`. For
  primitives (u8/usize/bool/&str/...) and unit `()`, the view is the
  value itself (DO NOT call `@` on a primitive — it won't compile).
- For raw pointer fields (`*mut T`, `*const T`), omit them from the
  view entirely (the checker treats raw pointers as
  allocator-opaque). For `Ghost<T>` / `Tracked<T>` ghost wrappers,
  project to the inner value's view: `self.<name>@@` (the first `@`
  unwraps Ghost, the second is the view of T).
- For variants of an enum, return a `Seq`/`int`/tagged-union view as
  appropriate — typically `pub enum <T>View { ... }` declared just
  above the `impl View` is acceptable IF you also include the enum
  declaration in `view_decl`.

Rules of thumb:
- A `Vec<X>` field that the spec only treats as an unordered
  multiset → view as `Set<X@>` or `Multiset<X@>`.
- A `Vec<X>` whose order matters → `Seq<X@>`.
- A `Map<K, V>` field always views to `Map<K@, V@>`.
- An allocator handle / opaque ID → omit from the view.
- A field that the ensures clause never inspects → omit.

## Example

### Type
```
pub struct Page {
    pub ptr: *mut u8,         // raw pointer — opaque
    pub size: usize,
    pub state: PageState,
    pub owner: Ghost<OwnerId>, // ghost wrapper
}
```

Already-resolved views of dependencies:
- `PageState`: identity view (it's a `#[derive(Eq)]` enum of unit
  variants — its structural equality is already semantic).
- `OwnerId`: identity view.

### Response

```json
{
  "viewed_type": "PageView",
  "view_decl": "pub struct PageView { pub size: usize, pub state: PageState, pub owner: OwnerId }\n\nimpl View for Page {\n    type V = PageView;\n    closed spec fn view(&self) -> PageView {\n        PageView { size: self.size, state: self.state, owner: self.owner@ }\n    }\n}",
  "depends_on_views_of": [],
  "rationale": "Drop ptr (allocator-opaque), keep size/state which are spec-meaningful, project Ghost<OwnerId> to its inner identity view. PageState's structural eq is already semantic so we use it as-is."
}
```

## Your task

Produce the JSON block described above for the target type.
Output **nothing** outside the fenced ```json block.
