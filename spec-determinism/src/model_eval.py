"""
Pure-Python evaluator for Z3 `(get-model)` responses.

Verus leaves behind an SMT transcript that contains — even for
`unknown`/`sat` queries — a full `(get-model)` dump. The dump is a
self-contained interpretation of every declared function, so we can
evaluate arbitrary SMT terms (e.g. `(view pre_self_!).slabs[6].free_addrs`)
against it *without* re-invoking Z3 and without asking an LLM to
translate opaque `Poly!val!N` skolems back to Rust values.

The evaluator has two layers:

1. `load_model(response_text)` — an s-expression tokenizer + parser that
   produces `fns: dict[str, FnDef]` (all `(define-fun …)` entries,
   including 0-arity constants) and `decls: dict[str, SExp]`
   (universe-element `declare-fun`s).

2. `Evaluator.eval(expr, env={})` — recursively rewrites `expr` using
   the function definitions. `ite`, `and`/`or`/`not`, `=`, and `let`
   are handled natively. Unknown heads (constructors, uninterpreted
   sorts) are left as-is; their arguments are still evaluated, so the
   final result is a structural s-expression of concrete datatype
   constructors / numbers.

Higher-level helpers (`decode_slabview`, `witness_from_typeinfo`) walk
a Rust-level `TypeInfo` tree and synthesize the SMT terms for each
projection, producing a human-readable witness mapping like::

    pre_self_.slabs[0] = SlabView { block_size: 8, start_addr: 128,
                                     end_addr: 144, … }
    post1_self_.slabs[6].free_addrs = Set!val!13
    post2_self_.slabs[6].free_addrs = Set!val!19

See `docs/model_eval.md` (TBD) for the full encoding reference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SExp = Any  # str | list[SExp]


# ---------------------------------------------------------------------------
# s-expression parser
# ---------------------------------------------------------------------------

_RE_COMMENT = re.compile(r";[^\n]*")


def tokenize(s: str) -> list[str]:
    s = _RE_COMMENT.sub(" ", s)
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c in "()":
            out.append(c)
            i += 1
            continue
        j = i
        while j < n and not s[j].isspace() and s[j] not in "()":
            j += 1
        out.append(s[i:j])
        i = j
    return out


def parse_sexp(s: str) -> SExp:
    toks = tokenize(s)
    e, _ = _parse_one(toks, 0)
    return e


def _parse_one(toks: list[str], i: int) -> tuple[SExp, int]:
    t = toks[i]
    if t == "(":
        out: list[SExp] = []
        i += 1
        while toks[i] != ")":
            e, i = _parse_one(toks, i)
            out.append(e)
        return out, i + 1
    return t, i + 1


def render(e: SExp) -> str:
    if isinstance(e, list):
        return "(" + " ".join(render(x) for x in e) + ")"
    return str(e)


# ---------------------------------------------------------------------------
# Model loader
# ---------------------------------------------------------------------------

@dataclass
class FnDef:
    params: list[tuple[str, SExp]]   # [(var_name, sort)]
    ret: SExp
    body: SExp


@dataclass
class Model:
    fns: dict[str, FnDef]
    decls: dict[str, SExp]           # 0-arity declare-fun: name -> sort


def load_model(response_text: str) -> Model:
    """Parse a `(get-model)` response into (fns, decls)."""
    toks = tokenize(response_text)
    top, _ = _parse_one(toks, 0)
    fns: dict[str, FnDef] = {}
    decls: dict[str, SExp] = {}
    for e in top:
        if not isinstance(e, list) or not e:
            continue
        head = e[0]
        if head == "define-fun" and len(e) >= 5:
            name = e[1]
            params_sexp = e[2]
            ret = e[3]
            body = e[4]
            params = [(p[0], p[1]) for p in params_sexp]
            fns[name] = FnDef(params, ret, body)
        elif head == "declare-fun" and len(e) >= 4:
            name = e[1]
            args = e[2]
            ret = e[3]
            if not args:
                decls[name] = ret
    return Model(fns=fns, decls=decls)


_RE_GET_MODEL_MARKER = re.compile(r"^\(get-model\)\s*$")


def extract_model_response(transcript: str | Path) -> str | None:
    """Extract the (last) `(get-model)` RESPONSE block from an SMT transcript.

    Returns the raw outer-parenthesized s-expression text, or None if the
    transcript contains no model dump.
    """
    if isinstance(transcript, (str, Path)) and Path(str(transcript)).exists():
        text = Path(transcript).read_text()
    else:
        text = str(transcript)
    lines = text.splitlines(keepends=True)
    gm_idx = None
    for i, line in enumerate(lines):
        if _RE_GET_MODEL_MARKER.match(line.strip()):
            gm_idx = i
    if gm_idx is None:
        return None
    # Find next RESPONSE marker after gm_idx
    for r_idx in range(gm_idx, len(lines)):
        if lines[r_idx].startswith(";;;>>> RESPONSE"):
            break
    else:
        return None
    buf: list[str] = []
    depth = 0
    started = False
    for line in lines[r_idx + 1:]:
        if line.startswith(";;;>>>"):
            break
        buf.append(line)
        for ch in line:
            if ch == "(":
                depth += 1
                started = True
            elif ch == ")":
                depth -= 1
        if started and depth == 0:
            break
    return "".join(buf)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class Evaluator:
    """Recursive rewriter for SMT terms against a parsed model.

    Unknown heads (datatype constructors, uninterpreted-sort members,
    numeric literals) are preserved; their arguments are still evaluated.
    This means `eval` always terminates as long as the model's function
    definitions are acyclic, which is the case for every interpretation
    Z3 produces via finite ite cascades.
    """

    # Keep evaluation bounded in case the model accidentally recurses
    # through datatype accessors; this limit is higher than the nesting
    # encountered on any real Verus case so far (≤ ~40).
    MAX_DEPTH = 2048

    def __init__(self, model: Model):
        self.model = model

    def eval(self, e: SExp, env: dict[str, SExp] | None = None, _d: int = 0) -> SExp:
        if _d > self.MAX_DEPTH:
            return e
        env = env or {}
        if isinstance(e, str):
            if e in env:
                return env[e]
            fn = self.model.fns.get(e)
            if fn is not None and not fn.params:
                return self.eval(fn.body, {}, _d + 1)
            return e
        if not isinstance(e, list) or not e:
            return e

        head = e[0]

        # Special forms
        if head == "ite" and len(e) == 4:
            cond = self.eval(e[1], env, _d + 1)
            if cond == "true":
                return self.eval(e[2], env, _d + 1)
            if cond == "false":
                return self.eval(e[3], env, _d + 1)
            return ["ite", cond,
                    self.eval(e[2], env, _d + 1),
                    self.eval(e[3], env, _d + 1)]
        if head == "and":
            vs = [self.eval(a, env, _d + 1) for a in e[1:]]
            if any(v == "false" for v in vs):
                return "false"
            if all(v == "true" for v in vs):
                return "true"
            return ["and", *vs]
        if head == "or":
            vs = [self.eval(a, env, _d + 1) for a in e[1:]]
            if any(v == "true" for v in vs):
                return "true"
            if all(v == "false" for v in vs):
                return "false"
            return ["or", *vs]
        if head == "not" and len(e) == 2:
            v = self.eval(e[1], env, _d + 1)
            if v == "true":
                return "false"
            if v == "false":
                return "true"
            return ["not", v]
        if head == "=" and len(e) == 3:
            a = self.eval(e[1], env, _d + 1)
            b = self.eval(e[2], env, _d + 1)
            return "true" if render(a) == render(b) else "false"
        if head == "let" and len(e) == 3:
            bindings = e[1]
            body = e[2]
            new_env = dict(env)
            for b in bindings:
                new_env[b[0]] = self.eval(b[1], env, _d + 1)
            return self.eval(body, new_env, _d + 1)

        # User-defined function application
        if isinstance(head, str):
            fn = self.model.fns.get(head)
            if fn is not None:
                args_v = [self.eval(a, env, _d + 1) for a in e[1:]]
                if len(args_v) == len(fn.params):
                    new_env = {p[0]: v for p, v in zip(fn.params, args_v)}
                    return self.eval(fn.body, new_env, _d + 1)

        # Constructor / uninterpreted: evaluate args, keep structure.
        return [head] + [self.eval(a, env, _d + 1) for a in e[1:]]


def as_int(value: SExp) -> int | None:
    """Return `value` as a Python int if it is a numeric literal, else None."""
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    # Z3 also emits `(- 5)` for negatives.
    if isinstance(value, list) and len(value) == 2 and value[0] == "-":
        inner = as_int(value[1])
        return -inner if inner is not None else None
    return None


# ---------------------------------------------------------------------------
# High-level witness helpers
# ---------------------------------------------------------------------------

# Hard-coded SMT encoding facts we depend on. These are stable across Verus
# versions because they come from vir/src/poly.rs + vir/src/sst_to_air.rs.
DCR_ZERO = "Dcr!val!0"
VIEW_FN = "vstd!view.View.view.?"


def smt_type_symbol(crate_type_name: str) -> str:
    """Return the SMT `TYPE%…` sort symbol for a fully-qualified Rust type."""
    return f"TYPE%{crate_type_name}"


def poly_wrap(ev: Evaluator, type_sym: str, value: SExp) -> SExp:
    """Apply `Poly%<T>.` to wrap a raw datatype value into a Poly."""
    return ev.eval([f"Poly%{type_sym[len('TYPE%'):]}", value])


def poly_unwrap(ev: Evaluator, type_sym: str, poly: SExp) -> SExp:
    """Apply `%Poly%<T>.` to extract a raw datatype value from a Poly."""
    return ev.eval([f"%Poly%{type_sym[len('TYPE%'):]}", poly])


def view_of(ev: Evaluator, type_sym: str, value: SExp) -> SExp:
    """Apply Verus's `View::view` and return the raw Poly."""
    wrapped = poly_wrap(ev, type_sym, value)
    return ev.eval([VIEW_FN, DCR_ZERO, type_sym, wrapped])


def walk_datatype(
    ev: Evaluator,
    value: SExp,
    ctor_tag: str,
    field_names: Iterable[str],
) -> dict[str, SExp] | None:
    """Decompose `(Ctor f0 f1 …)` into `{field_name: value}`."""
    if not isinstance(value, list) or not value:
        return None
    if not str(value[0]).endswith("/" + ctor_tag):
        return None
    names = list(field_names)
    if len(value) - 1 < len(names):
        return None
    return {n: value[i + 1] for i, n in enumerate(names)}


# ---------------------------------------------------------------------------
# Uninterpreted-sort expansion via model algebraic facts
# ---------------------------------------------------------------------------

# Set operators whose `(get-model)` ite cascade encodes concrete algebraic
# facts like `insert(pre_set_poly, elem_poly) = post_set_poly`. Verus's
# encoding for `vstd::set::Set` wraps every operator as `<op>.?` taking
# (Dcr, Type, arg_polys...) and returning a Poly (for set-valued ops) or
# Bool (for contains). We use these to derive relational witnesses for
# opaque `Set!val!N` values.
_SET_POLY_OPS = {
    # op_name: (n_set_args, n_elem_args, result_is_set)
    "vstd!set.Set.insert.?": (1, 1, True),   # (s, e) → s ∪ {e}
    "vstd!set.Set.remove.?": (1, 1, True),   # (s, e) → s \ {e}
    "vstd!set.Set.empty.?":  (0, 0, True),   # () → ∅  (0-ary rhs)
    "vstd!set.Set.union.?":  (2, 0, True),
    "vstd!set.Set.intersect.?": (2, 0, True),
    "vstd!set.Set.difference.?": (2, 0, True),
}


def _ite_entries(body: SExp) -> list[tuple[dict[str, SExp], SExp]]:
    """Flatten a nested `(ite cond then else)` cascade in a model body.

    Returns a list of `({var_name: matched_val}, value_in_that_branch)`
    plus a final `({}, default_value)` entry for the terminal else. Each
    condition is assumed to be either `(= x!i VAL)` or a conjunction of
    such equalities (the shape Z3 always emits for model interpretations).
    """
    out: list[tuple[dict[str, SExp], SExp]] = []
    cur = body
    while isinstance(cur, list) and len(cur) == 4 and cur[0] == "ite":
        cond, then_b, else_b = cur[1], cur[2], cur[3]
        d: dict[str, SExp] = {}
        if isinstance(cond, list):
            parts = cond[1:] if cond and cond[0] == "and" else [cond]
            for c in parts:
                if isinstance(c, list) and len(c) == 3 and c[0] == "=":
                    if isinstance(c[1], str):
                        d[c[1]] = c[2]
        out.append((d, then_b))
        cur = else_b
    out.append(({}, cur))
    return out


def build_set_poly_index(model: Model, ev: Evaluator, max_id: int = 200) -> dict[str, str]:
    """Return a map `Poly!val!N → Set!val!K` for all declared Set values.

    Note: multiple Set universe elements CAN share a Poly (if the model's
    `Poly%<SetType>.` function is not injective on that Set), so the map
    is first-writer-wins — good enough for naming purposes.
    """
    out: dict[str, str] = {}
    # Scan model.decls for declared Set universe elements.
    for name in model.decls:
        if ".Set<" not in name or "!val!" not in name:
            continue
        set_type = name.split("!val!")[0]      # e.g. `vstd!set.Set<usize.>.`
        p = ev.eval([f"Poly%{set_type}", name])
        if isinstance(p, str) and p not in out:
            out[p] = name
    return out


def set_algebraic_facts(
    model: Model,
    ev: Evaluator,
    target_set_name: str,
) -> list[tuple[str, list[SExp], SExp]] | None:
    """Find explicit algebraic relations for an opaque Set universe element.

    Returns a list of `(op_name, args_polys, produces)` triples where the
    model has committed `op(args) = target_set_name` as a concrete ite
    entry. Each `args_polys[i]` is the Poly wrapper of the i-th argument
    (set or element) as it appeared in the ite condition.

    The returned list may be empty if the model assigned `target_set_name`
    via the default fall-through branch of every operator (no concrete
    relational fact). In that case, the caller should fall back to simply
    naming the Set as opaque.
    """
    # Find the Poly encoding of the target set.
    set_type_match = re.match(r"^(.+?)!val!\d+$", target_set_name)
    if not set_type_match:
        return None
    set_type = set_type_match.group(1)
    target_poly = ev.eval([f"Poly%{set_type}", target_set_name])
    if not isinstance(target_poly, str):
        return None

    facts: list[tuple[str, list[SExp], SExp]] = []
    for op_name, (n_set, n_elem, _) in _SET_POLY_OPS.items():
        fn = model.fns.get(op_name)
        if fn is None:
            continue
        for cond_map, branch_val in _ite_entries(fn.body):
            # We only care about branches that equate the Poly output to
            # our target_poly. Skip the default fall-through entry — its
            # value has no committed algebraic meaning.
            if not cond_map:
                continue
            if branch_val != target_poly:
                # Try rendered equality in case branch_val is a list.
                if render(branch_val) != target_poly:
                    continue
            # Extract per-param Poly args from cond_map; the arg names
            # follow `x!2`, `x!3` (indices 2+ are the set-or-elem polys,
            # x!0 is Dcr, x!1 is Type).
            args: list[SExp] = []
            ok = True
            for i in range(2, 2 + n_set + n_elem):
                key = f"x!{i}"
                if key not in cond_map:
                    ok = False
                    break
                args.append(cond_map[key])
            if ok:
                facts.append((op_name, args, target_poly))
    return facts


def friendly_op_name(smt_op: str) -> str:
    """`vstd!set.Set.insert.?` → `Set::insert`."""
    m = re.match(r"^vstd!(\w+)\.(\w+)\.(\w+)\.\?$", smt_op)
    if m:
        return f"{m.group(2)}::{m.group(3)}"
    return smt_op
    """Return `value` as a Python int if it is a numeric literal, else None."""
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    # Z3 also emits `(- 5)` for negatives.
    if isinstance(value, list) and len(value) == 2 and value[0] == "-":
        inner = as_int(value[1])
        return -inner if inner is not None else None
    return None
