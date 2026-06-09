"""Step 2 (view-quotient / abstract determinism) sweep.

For each pub-fn det artifact produced by the concrete-determinism
pipeline (``spec-determinism-verusage`` → ``<corpus>/artifacts/<key>/``),
take its existing ``injected.rs`` (already self-contained with all
supporting definitions and a ``proof fn det_<fn>(self_, args, r1, r2)``
template) and append a NEW proof fn::

    proof fn det_step2_<fn>(self1, self2, args, r1, r2)
        requires
            self1@ == self2@,            // or self1 == self2 if no view
            <self requires, applied to self1 AND self2>,
            <r1 ensures-clauses with self_ -> self1>,
            <r2 ensures-clauses with self_ -> self2>,
            <shared ensures-clauses applied to both>,
        ensures
            <equal_fn_name>(r1, r2),
    {}

Empty body: Verus must derive the conclusion from the requires alone.
Verification outcome:

* ``verified``    — no errors → Step 2 holds for this function
* ``failed``      — postcondition not satisfied → Step 2 leak
  (view-quotient candidate; see ``docs/view-quotient-failure-summary-*``)
* ``compile_fail`` — generator produced invalid code (need triage)

CLI: ``python -m spec_determinism.verus.step2_sweep [--corpus DIR] [...]``
or ``spec-determinism-step2`` (see ``pyproject.toml``).

Library: callers can import :func:`gen_step2`, :func:`process_artifact`,
:func:`run_verus`, and :func:`run_sweep` after calling
:func:`set_paths`.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from spec_determinism.verus.single_file import _DEFAULT_VERUS

# Defaults; overridden by set_paths() / CLI args.
ROOT = "spec-determinism/results-verusage-viewreg"
SRC = "verusage/source-projects"
PROJECTS = ["atmosphere", "ironkv", "memory-allocator", "nrkernel",
            "anvil-library", "storage", "vest"]
VERUS_BIN_DIR = _DEFAULT_VERUS
VERUS = str(Path(_DEFAULT_VERUS) / "verus")
TIMEOUT_SECS = 120


def set_paths(corpus_root=None, source_root=None, projects=None,
              verus_bin_dir=None, timeout=None):
    """Configure module-level paths used by :func:`lookup_view`,
    :func:`process_artifact`, :func:`run_verus`, and :func:`run_sweep`.

    Any argument left ``None`` keeps the current value.
    """
    global ROOT, SRC, PROJECTS, VERUS_BIN_DIR, VERUS, TIMEOUT_SECS
    if corpus_root is not None:
        ROOT = str(corpus_root)
    if source_root is not None:
        SRC = str(source_root)
        _view_cache.clear()
    if projects is not None:
        PROJECTS = list(projects)
    if verus_bin_dir is not None:
        VERUS_BIN_DIR = str(verus_bin_dir)
        VERUS = str(Path(verus_bin_dir) / "verus")
    if timeout is not None:
        TIMEOUT_SECS = int(timeout)


def strip_generics(t):
    return re.split(r'[<\s]', (t or "").strip(), maxsplit=1)[0]


_view_cache = {}
def lookup_view(typ):
    base = strip_generics(typ)
    if base in _view_cache: return _view_cache[base]
    found = None
    for path in glob.glob(f"{SRC}/**/*.rs", recursive=True):
        try: txt = open(path, errors="ignore").read()
        except Exception: continue
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


def has_view_in_source(src, typ):
    """Check if the given source text has a `view` impl for `typ`. Used to
    decide whether `<self>@` works in injected Step 2 obligations.
    """
    base = strip_generics(typ)
    if base not in src:
        return False
    for m in re.finditer(rf'\bimpl\b[^{{]*\b{re.escape(base)}\b[^{{]*\{{', src):
        i, d = m.end(), 1
        while i < len(src) and d > 0:
            if src[i] == '{': d += 1
            elif src[i] == '}': d -= 1
            i += 1
        block = src[m.end():i-1]
        if re.search(r'(?:open|closed)?\s*spec\s+fn\s+view\s*\(', block):
            return True
    # Also check `impl View for <Type>` blocks
    for m in re.finditer(rf'\bimpl\s+View\s+for\s+\b{re.escape(base)}\b[^{{]*\{{', src):
        return True
    return False


_pub_cache = {}
def is_pub_fn(file_path, fn_name):
    key = (file_path, fn_name)
    if key in _pub_cache: return _pub_cache[key]
    res = 'none'
    if os.path.exists(file_path):
        try:
            txt = open(file_path, errors="ignore").read()
            if re.search(rf'\bpub(?:\s*\([^)]*\))?\s+fn\s+{re.escape(fn_name)}\s*[<(]', txt):
                res = 'pub'
            elif re.search(rf'\b(spec|proof)\s+fn\s+{re.escape(fn_name)}\s*[<(]', txt):
                res = 'spec'
            elif re.search(rf'\bfn\s+{re.escape(fn_name)}\s*[<(]', txt):
                res = 'priv'
        except Exception:
            pass
    _pub_cache[key] = res
    return res


def split_top_level_commas(s):
    """Paren/bracket/brace-aware comma split. Treats `<` as generic
    delimiter ONLY when preceded by `::` (turbofish). All other `<` are
    treated as comparison operators. This avoids false-positives on
    `KERNEL_X < 512` patterns common in requires-clauses.
    """
    out, cur = [], []
    stack = []
    pairs = {'(':')', '[':']', '{':'}'}
    n = len(s)
    i = 0
    while i < n:
        ch = s[i]
        if ch in '([{':
            stack.append(pairs[ch]); cur.append(ch)
            i += 1; continue
        if stack and ch == stack[-1]:
            stack.pop(); cur.append(ch)
            i += 1; continue
        if ch == '<':
            # Generic if `<` is preceded DIRECTLY (no space) by an
            # identifier char or `::`. Comparison `a < b` always has space
            # before `<`, and `<=` `<<` are always operators.
            if i + 1 < n and s[i+1] in ('=', '<'):
                cur.append(ch); i += 1; continue
            j = i - 1
            is_generic = False
            if j >= 1 and s[j] == ':' and s[j-1] == ':':
                is_generic = True
            elif j >= 0 and (s[j].isalnum() or s[j] == '_'):
                is_generic = True
            if is_generic:
                stack.append('>'); cur.append(ch)
                i += 1; continue
            cur.append(ch); i += 1; continue
        if ch == '>' and stack and stack[-1] == '>':
            stack.pop(); cur.append(ch)
            i += 1; continue
        if ch == ',' and not stack:
            out.append(''.join(cur).strip()); cur = []
            i += 1; continue
        cur.append(ch); i += 1
    if cur:
        out.append(''.join(cur).strip())
    return [x for x in out if x]


def parse_clauses_block(text):
    """Given an ensures-block body containing `&&& (...) &&& (...)`, return
    the list of clause bodies (the inside of each top-level parenthesised
    clause). Mirrors split_clauses from vq_scan_pubfn."""
    cl, i = [], 0
    while True:
        idx = text.find('&&&', i)
        if idx < 0: break
        p = text.find('(', idx)
        if p < 0: break
        d, j = 1, p+1
        while j < len(text) and d > 0:
            if text[j] == '(': d += 1
            elif text[j] == ')': d -= 1
            j += 1
        cl.append(text[p+1:j-1].strip())
        i = j
    return cl


def split_top_clauses(text):
    """Split by top-level (paren-depth-0) commas. Each chunk is then
    stripped of any wrapping `(...)`. Used for requires-blocks that are
    comma-separated rather than &&&-joined."""
    parts = split_top_level_commas(text)
    out = []
    for p in parts:
        p = p.strip()
        if not p: continue
        if p.startswith('(') and p.endswith(')'):
            # Strip the wrap if the outermost parens balance
            d, j = 1, 1
            while j < len(p) and d > 0:
                if p[j] == '(': d += 1
                elif p[j] == ')': d -= 1
                j += 1
            if j == len(p):
                p = p[1:-1].strip()
        out.append(p)
    return out


SELF_TOK = re.compile(r'\bself_\b')


def _balance_braces(text, start, open_ch='{', close_ch='}'):
    """From `start` (pointing at open_ch), return index of matching close."""
    d, i = 1, start + 1
    while i < len(text) and d > 0:
        if text[i] == open_ch: d += 1
        elif text[i] == close_ch: d -= 1
        i += 1
    return i if d == 0 else -1


def _find_fn_body_brace(src, p_close):
    """Find the fn-body `{` after the param-list `)` at p_close-1.

    Strategy: walk forward. When we hit a `{` at paren-depth 0, balance
    it. Then look at what follows (skipping whitespace):
      - EOF or non-special char => balanced brace WAS the body, return k.
      - `,` => clause separator, continue.
      - `else` => if-then-else continuation, continue.
      - `{` => the just-balanced was a clause-block (`match`, `forall`,
        `if-then`), and the NEXT `{` is the body; return j.
      - `where` => continue (where clauses after sig).
    """
    p_depth = 0
    k = p_close
    while k < len(src):
        ch = src[k]
        if ch == '(':
            p_depth += 1; k += 1; continue
        if ch == ')':
            p_depth -= 1; k += 1; continue
        if ch == '{' and p_depth == 0:
            close = _balance_braces(src, k, '{', '}')
            if close < 0:
                return -1
            j = close
            while j < len(src) and src[j] in ' \t\r\n':
                j += 1
            if j >= len(src):
                return k
            nxt = src[j]
            if nxt == ',':
                k = j + 1
                continue
            if nxt == '{':
                return j
            if src.startswith('else', j) and (j + 4 >= len(src) or not (src[j+4].isalnum() or src[j+4] == '_')):
                k = j + 4
                continue
            if src.startswith('where', j) and (j + 5 >= len(src) or not (src[j+5].isalnum() or src[j+5] == '_')):
                k = j + 5
                continue
            return k
        k += 1
    return -1


def _extract_mut_ref_params(params_blob):
    """Return list of param names whose type begins with `&mut`. Always
    includes 'self' if blob contains `&mut self` (self has no separate type).
    Handles only top-level params (paren-/angle-aware comma split).
    """
    names = []
    seen = set()
    if re.search(r'&\s*mut\s+self\b', params_blob):
        names.append('self')
        seen.add('self')
    # Top-level comma split respecting (), [], <>
    parts = []
    depth_p = depth_b = depth_a = 0
    buf = []
    for ch in params_blob:
        if ch == ',' and depth_p == 0 and depth_b == 0 and depth_a == 0:
            parts.append(''.join(buf).strip())
            buf = []
            continue
        if ch == '(': depth_p += 1
        elif ch == ')': depth_p -= 1
        elif ch == '[': depth_b += 1
        elif ch == ']': depth_b -= 1
        elif ch == '<': depth_a += 1
        elif ch == '>': depth_a -= 1
        buf.append(ch)
    if buf:
        parts.append(''.join(buf).strip())
    for p in parts:
        if not p or p in ('self', '&self', '&mut self', 'mut self'):
            continue
        p = re.sub(r'#\[[^\]]*\]\s*', '', p).strip()
        mt = re.match(r'(?:mut\s+)?([A-Za-z_]\w*)\s*:\s*(.*)$', p, re.S)
        if mt:
            name, ty = mt.group(1), mt.group(2).strip()
            if re.match(r'&\s*mut\b', ty):
                if name not in seen:
                    seen.add(name); names.append(name)
            continue
        # `Tracked(name): Tracked<&mut ...>` or `Ghost(name): Ghost<&mut ...>`
        mt = re.match(r'(?:Tracked|Ghost)\s*\(\s*([A-Za-z_]\w*)\s*\)\s*:\s*(?:Tracked|Ghost)\s*<(.*)>\s*$', p, re.S)
        if mt:
            name, inner = mt.group(1), mt.group(2).strip()
            if re.match(r'&\s*mut\b', inner):
                if name not in seen:
                    seen.add(name); names.append(name)
            continue
    return names


def _rewrite_mut_ref_postcond(ens_blob, name):
    """In ens_blob, rewrite bare `<name>` references per Verus &mut
    postcondition rules. `final(x)` returns `&mut T`, so it auto-coerces
    in argument positions. Idempotent.
    """
    SENT_OLD = f'\x00OLD_{name}\x00'
    SENT_FIN = f'\x00FIN_{name}\x00'
    SENT_MEM = f'\x00MEM_{name}\x00'
    SENT_VAL = f'\x00VAL_{name}\x00'
    SENT_DRF = f'\x00DRF_{name}\x00'
    tmp = re.sub(rf'\bold\s*\(\s*{re.escape(name)}\s*,?\s*\)', SENT_OLD, ens_blob)
    tmp = re.sub(rf'\bfinal\s*\(\s*{re.escape(name)}\s*,?\s*\)', SENT_FIN, tmp)
    tmp = re.sub(
        rf'(?<![\w\.]){re.escape(name)}\b(?=\s*(?:->|[\.\[@]))',
        SENT_MEM,
        tmp,
    )
    tmp = re.sub(rf'\*\s*{re.escape(name)}\b', SENT_DRF, tmp)
    tmp = re.sub(rf'(?<![\w\.]){re.escape(name)}\b', SENT_VAL, tmp)
    tmp = (tmp
           .replace(SENT_OLD, f'old({name})')
           .replace(SENT_FIN, f'final({name})')
           .replace(SENT_MEM, f'final({name})')
           .replace(SENT_DRF, f'*final({name})')
           .replace(SENT_VAL, f'final({name})'))
    return tmp


def patch_mut_self_postconditions(src):
    """The corpus injected.rs files were generated against an older Verus.
    Current Verus rejects bare `<name>.X` in &mut-<name> postconditions and
    demands `final(<name>).X` / `old(<name>).X`. We rewrite every &mut
    param's ensures clause references. Handles `self` AND any
    `&mut <name>: T` (or `Tracked<&mut name>`) params. Idempotent.
    """
    out = []
    i = 0
    fn_re = re.compile(r'\bfn\s+([A-Za-z_]\w*)\s*(?:<[^>]*>)?\s*\(')
    for m in fn_re.finditer(src):
        out.append(src[i:m.start()])
        i = m.start()
        p_open = m.end() - 1
        p_close = _balance_braces(src, p_open, '(', ')')
        if p_close < 0:
            continue
        params_blob = src[p_open + 1:p_close - 1]
        mut_names = _extract_mut_ref_params(params_blob)
        if not mut_names:
            continue
        body_start = _find_fn_body_brace(src, p_close)
        if body_start < 0:
            continue
        sig_tail = src[p_close:body_start]
        em = re.search(r'\bensures\b', sig_tail)
        if em is None:
            out.append(src[i:body_start])
            i = body_start
            continue
        ens_start = p_close + em.end()
        ens_blob = src[ens_start:body_start]
        patched = ens_blob
        for nm in mut_names:
            patched = _rewrite_mut_ref_postcond(patched, nm)
        out.append(src[i:ens_start])
        out.append(patched)
        i = body_start
    out.append(src[i:])
    return ''.join(out)


def gen_step2(det_spec, src=''):
    """Return the Step 2 proof-fn source, or None if we can't transform.

    Two template families:
      * Family 1 (immutable / by-value / no self):
          fn det_X(self_, args, r1, r2) ensures (BLOCK) ==> equal(r1, r2)
        Step 2: split self_ -> self1/self2; require self1@==self2@;
        per-side substitute r1 vs r2 clauses; conclusion equal(r1,r2).
      * Family 2 (&mut self):
          fn det_X(pre_self_, args, post1_self_, r1, post2_self_, r2)
              ensures (BLOCK uses post1_self_/post2_self_/pre_self_)
                  ==> equal(r1, r2, post1_self_, post2_self_)
        Step 2: split pre_self_ -> pre1_self_/pre2_self_; require
        pre1_self_@==pre2_self_@; per-side substitute pre_self_ in
        clauses that mention post1_self_/post2_self_; conclusion
        uses full equal_arg_pairs.
    """
    tpl = det_spec.get("det_check_template", "")
    fn  = det_spec["function"]
    eq_name = det_spec["equal_fn_name"]
    eq_pairs = det_spec.get("equal_arg_pairs") or [{"lhs":"r1","rhs":"r2"}]
    self_type = det_spec.get("self_type") or ""
    gen_decl  = det_spec.get("generics_decl", "")
    where_decl = det_spec.get("where_decl", "")

    sig = re.match(r'\s*proof\s+fn\s+det_\w+\s*(?:<[^>]*>)?\s*\(', tpl)
    if not sig:
        return None
    p_start = sig.end() - 1
    d, j = 1, p_start + 1
    while j < len(tpl) and d > 0:
        if tpl[j] == '(': d += 1
        elif tpl[j] == ')': d -= 1
        j += 1
    if d != 0:
        return None
    params_str = tpl[p_start + 1:j - 1]
    # Find body brace
    depth_paren = 0
    body_brace = -1
    k = j
    while k < len(tpl):
        c = tpl[k]
        if c == '(': depth_paren += 1
        elif c == ')': depth_paren -= 1
        elif c == '{' and depth_paren == 0:
            body_brace = k; break
        k += 1
    if body_brace < 0:
        return None
    body_pre = tpl[j:body_brace]
    params = split_top_level_commas(params_str)
    if len(params) < 2:
        return None

    # Detect family by parameter names
    param_names = [p.split(':',1)[0].strip() for p in params]
    is_family2 = ('pre_self_' in param_names) or any('post1_self_' in n or 'post2_self_' in n for n in param_names)

    # requires extraction (split into individual clauses)
    req_m = re.search(r'requires\s+([\s\S]*?),?\s*ensures', body_pre + '\nensures')
    req_clauses = []
    if req_m:
        req_blob = req_m.group(1).strip().rstrip(',').strip()
        req_clauses = split_top_clauses(req_blob)

    ens_m = re.search(r'ensures\s+([\s\S]*)$', body_pre.rstrip())
    if not ens_m:
        return None
    ens = ens_m.group(1).strip().rstrip(',').strip()

    # Parse ensures: `(BLOCK) ==> equal(...)`. Extract BLOCK.
    eb = None
    if ens.startswith('('):
        d2, jj = 1, 1
        while jj < len(ens) and d2 > 0:
            if ens[jj] == '(': d2 += 1
            elif ens[jj] == ')': d2 -= 1
            jj += 1
        eb = ens[1:jj-1].strip()
    if eb is None:
        eb = ens

    clauses = parse_clauses_block(eb)

    if is_family2:
        return _gen_step2_family2(
            fn, eq_name, eq_pairs, params, req_clauses, clauses,
            gen_decl, where_decl, src)
    else:
        return _gen_step2_family1(
            fn, eq_name, eq_pairs, params, req_clauses, clauses, self_type,
            gen_decl, where_decl, src)


def _gen_step2_family1(fn, eq_name, eq_pairs, params, req_clauses, clauses,
                       self_type, gen_decl, where_decl, src=''):
    if len(params) < 2:
        return None
    r1_p, r2_p = params[-2], params[-1]
    others = params[:-2]
    has_self = bool(others) and others[0].strip().startswith('self_:')
    self_p = others[0] if has_self else None
    arg_ps = others[1:] if has_self else others

    r1_cls, r2_cls, shared_cls = [], [], []
    for c in clauses:
        has_r1 = bool(re.search(r'\br1\b', c))
        has_r2 = bool(re.search(r'\br2\b', c))
        if has_r1 and not has_r2: r1_cls.append(c)
        elif has_r2 and not has_r1: r2_cls.append(c)
        else: shared_cls.append(c)

    new_req_lines = []
    self_ty_str = None
    if has_self:
        mm = re.match(r'self_\s*:\s*(.+)', self_p.strip())
        if mm:
            self_ty_str = mm.group(1).strip().rstrip(',').strip()
        if src and not has_view_in_source(src, self_type):
            has_view = False
        else:
            _, has_view = lookup_view(self_type)
        new_req_lines.append('self1@ == self2@' if has_view else 'self1 == self2')

    if req_clauses:
        for rc in req_clauses:
            new_req_lines.append(SELF_TOK.sub('self1', rc))
            new_req_lines.append(SELF_TOK.sub('self2', rc))
    for c in r1_cls:
        new_req_lines.append(SELF_TOK.sub('self1', c))
    for c in r2_cls:
        new_req_lines.append(SELF_TOK.sub('self2', c))
    for c in shared_cls:
        new_req_lines.append(SELF_TOK.sub('self1', c))
        new_req_lines.append(SELF_TOK.sub('self2', c))

    new_params = []
    if has_self and self_ty_str:
        new_params.append(f'self1: {self_ty_str}')
        new_params.append(f'self2: {self_ty_str}')
    new_params.extend(arg_ps)
    new_params.extend([r1_p, r2_p])

    where_clause = f' where {where_decl}' if where_decl else ''
    params_block = ', '.join(new_params)
    req_block = ',\n        '.join(f'({c})' for c in new_req_lines)
    concl_args = ', '.join(arg for p in eq_pairs for arg in (p['lhs'], p['rhs']))  # family1: just r1,r2

    return f"""

// === STEP 2 OBLIGATION ===
proof fn det_step2_{fn}{gen_decl}({params_block}){where_clause}
    requires
        {req_block},
    ensures
        {eq_name}({concl_args}),
{{
}}
// === END STEP 2 ===
"""


PRE_TOK = re.compile(r'\bpre_self_\b')


def _gen_step2_family2(fn, eq_name, eq_pairs, params, req_clauses, clauses,
                       gen_decl, where_decl, src=''):
    """For &mut self templates: split pre_self_ into pre1/pre2; conclusion
    uses equal_arg_pairs (typically r1, r2, post1_self_, post2_self_)."""
    pre_self_ty = None
    other_params = []
    for p in params:
        m = re.match(r'pre_self_\s*:\s*(.+)$', p.strip())
        if m:
            pre_self_ty = m.group(1).strip().rstrip(',').strip()
        else:
            other_params.append(p)

    r1_cls, r2_cls, shared_cls = [], [], []
    for c in clauses:
        has_p1 = ('post1_self_' in c) or bool(re.search(r'\br1\b', c))
        has_p2 = ('post2_self_' in c) or bool(re.search(r'\br2\b', c))
        if has_p1 and not has_p2: r1_cls.append(c)
        elif has_p2 and not has_p1: r2_cls.append(c)
        else: shared_cls.append(c)

    new_req_lines = []
    if pre_self_ty is not None:
        if src and not has_view_in_source(src, pre_self_ty):
            has_view = False
        else:
            _, has_view = lookup_view(pre_self_ty)
        new_req_lines.append('pre1_self_@ == pre2_self_@' if has_view else 'pre1_self_ == pre2_self_')

    if req_clauses:
        for rc in req_clauses:
            new_req_lines.append(PRE_TOK.sub('pre1_self_', rc))
            new_req_lines.append(PRE_TOK.sub('pre2_self_', rc))

    # Per-side clauses use only their respective pre_
    for c in r1_cls:
        new_req_lines.append(PRE_TOK.sub('pre1_self_', c))
    for c in r2_cls:
        new_req_lines.append(PRE_TOK.sub('pre2_self_', c))
    for c in shared_cls:
        # Apply to both
        new_req_lines.append(PRE_TOK.sub('pre1_self_', c))
        new_req_lines.append(PRE_TOK.sub('pre2_self_', c))

    # Build new param list: pre1_self_, pre2_self_, args/post/r in original order
    new_params = []
    if pre_self_ty is not None:
        new_params.append(f'pre1_self_: {pre_self_ty}')
        new_params.append(f'pre2_self_: {pre_self_ty}')
    new_params.extend(other_params)

    where_clause = f' where {where_decl}' if where_decl else ''
    params_block = ', '.join(new_params)
    req_block = ',\n        '.join(f'({c})' for c in new_req_lines)
    # Conclusion args from equal_arg_pairs (lhs, rhs per pair flattened)
    concl_args = ', '.join(arg for p in eq_pairs for arg in (p['lhs'], p['rhs']))

    return f"""

// === STEP 2 OBLIGATION ===
proof fn det_step2_{fn}{gen_decl}({params_block}){where_clause}
    requires
        {req_block},
    ensures
        {eq_name}({concl_args}),
{{
}}
// === END STEP 2 ===
"""


def run_verus(rs_file, verify_function=None):
    env = os.environ.copy()
    env['PATH'] = VERUS_BIN_DIR + os.pathsep + env.get('PATH', '')
    env['RUSTC_BOOTSTRAP'] = '1'
    cmd = [VERUS, str(rs_file)]
    if verify_function is not None:
        cmd += ['--verify-root', '--verify-function', verify_function]
    try:
        r = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=TIMEOUT_SECS,
        )
    except subprocess.TimeoutExpired:
        return 'timeout', '', ''
    out = (r.stdout or '') + (r.stderr or '')
    m = re.search(r'verification results::\s*(\d+)\s+verified,\s*(\d+)\s+errors', out)
    if m:
        v, e = int(m.group(1)), int(m.group(2))
        return ('verified' if e == 0 else 'failed', f'{v}v/{e}e', out)
    if 'error:' in out or 'errors:' in out or 'failed' in out:
        return 'compile_fail', '', out
    return 'unknown', '', out


def process_artifact(proj, art_key, det_spec):
    art_dir = os.path.join(ROOT, proj, 'artifacts', art_key)
    inj = os.path.join(art_dir, 'injected.rs')
    if not os.path.exists(inj):
        return ('missing_injected', '', '')
    src = open(inj).read()
    src = patch_mut_self_postconditions(src)
    step2 = gen_step2(det_spec, src=src)
    if step2 is None:
        return ('parse_fail', '', '')
    last_brace = src.rfind('}')
    if last_brace < 0:
        return ('parse_fail', '', '')
    new_src = src[:last_brace] + step2 + src[last_brace:]
    with tempfile.NamedTemporaryFile(suffix='.rs', mode='w', delete=False) as tf:
        tf.write(new_src)
        tmp = tf.name
    try:
        fn = det_spec['function']
        status, summary, full = run_verus(tmp, verify_function=f'det_step2_{fn}')
        return (status, summary, full)
    finally:
        os.unlink(tmp)
        d_file = tmp[:-3] + '.d'
        if os.path.exists(d_file): os.unlink(d_file)
        bin_file = tmp[:-3]
        if os.path.exists(bin_file): os.unlink(bin_file)


def collect_targets(only=None):
    """Build the dedup'd pub-fn target set used by :func:`run_sweep`.

    Restricts to concretely-deterministic cases (``status == 'ok'`` AND
    ``assumes == []``). Functions that required ``assume`` hypotheses to
    verify are NOT in the concrete-completeness pile and are excluded.

    ``only`` (optional): list of function names or artifact keys; if
    provided, the returned target list is filtered to that subset.
    """
    unique = {}
    for proj in PROJECTS:
        fr = os.path.join(ROOT, proj, 'full_run.json')
        if not os.path.exists(fr):
            continue
        for r in json.load(open(fr)):
            if r.get('status') != 'ok':
                continue
            if r.get('assumes') != []:
                continue
            ds = os.path.join(ROOT, proj, 'artifacts',
                              r['artifact_key'], 'det_spec.json')
            if not os.path.exists(ds):
                continue
            d = json.load(open(ds))
            st = d.get('self_type') or ''
            key = (proj, r['function'], strip_generics(st) or '<free>')
            if key in unique:
                unique[key]['count'] += 1
                continue
            unique[key] = dict(
                proj=proj, fn=r['function'], type=st,
                type_base=strip_generics(st), file=r['file'],
                artifact=r['artifact_key'], det_spec=d, count=1)

    targets = [v for v in unique.values()
               if is_pub_fn(v['file'], v['fn']) == 'pub']
    if only:
        only_set = set(only)
        targets = [v for v in targets
                   if v['fn'] in only_set or v['artifact'] in only_set]
    return targets


def run_sweep(only=None, out_path=None, progress=True):
    """Run the Step-2 sweep over all eligible pub-fn targets.

    Returns the list of result dicts (one per target). If ``out_path`` is
    given, also writes them as JSON.
    """
    targets = collect_targets(only=only)
    if progress:
        print(f'targets: {len(targets)}', flush=True)
    results = []
    t0 = time.time()
    for i, v in enumerate(targets, 1):
        status, summary, _full = process_artifact(
            v['proj'], v['artifact'], v['det_spec'])
        v['status'] = status
        v['summary'] = summary
        results.append(v)
        if progress:
            print(f'  [{i}/{len(targets)}] {status:12s} {summary:10s} '
                  f'[{v["proj"]}] {v["type_base"]}::{v["fn"]}',
                  flush=True)
    dt = time.time() - t0
    if progress:
        print(f'\nelapsed: {dt:.1f}s')
        from collections import Counter
        c = Counter(r['status'] for r in results)
        print('\n--- status histogram ---')
        for s, n in c.most_common():
            print(f'  {s}: {n}')
        print('\n--- FAILED (Step 2 candidate leaks) ---')
        for r in results:
            if r['status'] == 'failed':
                print(f'  [{r["proj"]}] {r["type_base"]}::{r["fn"]}  '
                      f'({r["summary"]})  inlines={r["count"]}')

    if out_path is not None:
        serializable = [{k: v for k, v in r.items() if k != 'det_spec'}
                        for r in results]
        with open(out_path, 'w') as f:
            json.dump(serializable, f, indent=2)
        if progress:
            print(f'\nfull results -> {out_path}')
    return results


def _build_argparser():
    ap = argparse.ArgumentParser(
        prog='spec-determinism-step2',
        description=('Step-2 (view-quotient / abstract determinism) sweep '
                     'over concretely-deterministic pub fns.'))
    ap.add_argument('--corpus', default=ROOT,
                    help=('Corpus root containing per-project full_run.json + '
                          'artifacts/ (default: %(default)s)'))
    ap.add_argument('--source', default=SRC,
                    help=('Source project root used for view-impl lookup + '
                          'pub-fn detection (default: %(default)s)'))
    ap.add_argument('--projects', default=','.join(PROJECTS),
                    help=('Comma-separated project list to sweep '
                          '(default: %(default)s)'))
    ap.add_argument('--verus-bin', default=VERUS_BIN_DIR,
                    help='Verus binary directory (default: %(default)s)')
    ap.add_argument('--timeout', type=int, default=TIMEOUT_SECS,
                    help='Per-target Verus timeout seconds (default: %(default)s)')
    ap.add_argument('--out', default=None,
                    help=('Result JSON path '
                          '(default: <corpus>/step2_sweep.json)'))
    ap.add_argument('targets', nargs='*',
                    help=('Optional positional filter: only run targets whose '
                          'function name or artifact key matches'))
    return ap


def main(argv=None):
    args = _build_argparser().parse_args(argv)
    projects = [p.strip() for p in args.projects.split(',') if p.strip()]
    set_paths(corpus_root=args.corpus, source_root=args.source,
              projects=projects, verus_bin_dir=args.verus_bin,
              timeout=args.timeout)
    out_path = args.out or os.path.join(ROOT, 'step2_sweep.json')
    run_sweep(only=args.targets or None, out_path=out_path, progress=True)


if __name__ == '__main__':
    main()
