"""
Module 2: gen_det — Determinism Check Generator

Merged with extract into Step 1 of the pipeline.
Produces a DetCheckSpec (template + symbol table) that Step 2 consumes.
"""

import re
from typing import Optional

from .types import (
    TypeKind, TypeInfo, Param, FunctionSpec, Assume,
    Symbol, DetCheckSpec,
)


class Unsupported(Exception):
    """Triggers LLM fallback for ensures substitution."""
    pass


def _var_name(param: Param, prefix: str = "") -> str:
    name = "self_" if param.is_self else param.name
    return f"{prefix}{name}" if prefix else name


def _type_name(param: Param) -> str:
    return param.type.name


# ---------------------------------------------------------------------------
# Symbol table construction
# ---------------------------------------------------------------------------

def _classify_phase(ty: TypeInfo) -> str:
    """Classify a type as simple or compound for output ordering."""
    if ty.kind in (TypeKind.RESULT, TypeKind.OPTION, TypeKind.ENUM,
                   TypeKind.BOOL, TypeKind.UNIT,
                   TypeKind.INT, TypeKind.USIZE, TypeKind.ISIZE,
                   TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
                   TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64):
        return "output_simple"
    return "output_compound"


def _build_symbols(spec: FunctionSpec) -> list[Symbol]:
    """Build the symbol table: variables to narrow, in order."""
    symbols = []

    # Phase 1: Input variables
    for p in spec.params:
        if p.is_mut_ref:
            base = _var_name(p)
            symbols.append(Symbol(
                name=f"pre_{base}",
                type=p.type,
                phase="input",
            ))
        elif p.is_ref:
            symbols.append(Symbol(
                name=_var_name(p),
                type=p.type,
                phase="input",
            ))
        else:
            symbols.append(Symbol(
                name=_var_name(p),
                type=p.type,
                phase="input",
            ))

    # Phase 2: Output variables — simple first, then compound
    simple_outputs = []
    compound_outputs = []

    # Return value (r1, r2)
    ret_phase = _classify_phase(spec.return_type)
    if ret_phase == "output_simple":
        simple_outputs.append(("r1", spec.return_type))
        simple_outputs.append(("r2", spec.return_type))
    else:
        compound_outputs.append(("r1", spec.return_type))
        compound_outputs.append(("r2", spec.return_type))

    # Post-state of &mut params (post1_*, post2_*)
    for p in spec.params:
        if p.is_mut_ref:
            base = _var_name(p)
            phase = _classify_phase(p.type)
            pair = [
                (f"post1_{base}", p.type),
                (f"post2_{base}", p.type),
            ]
            if phase == "output_simple":
                simple_outputs.extend(pair)
            else:
                compound_outputs.extend(pair)

    for name, ty in simple_outputs:
        symbols.append(Symbol(name=name, type=ty, phase="output_simple"))
    for name, ty in compound_outputs:
        symbols.append(Symbol(name=name, type=ty, phase="output_compound"))

    return symbols


# ---------------------------------------------------------------------------
# Template generation
# ---------------------------------------------------------------------------

def _build_template(spec: FunctionSpec, check_name: str | None = None) -> str:
    """
    Generate the det check proof fn with {ASSUMES} placeholder.
    
    The template has a single {ASSUMES} marker where binary search
    will insert accumulated assume expressions.
    """
    fn_name = check_name or f"det_{spec.name}"

    # Build parameter list
    input_params = []
    output1_params = []
    output2_params = []

    for p in spec.params:
        ty = _type_name(p)
        if p.is_mut_ref:
            pre_name = f"pre_{_var_name(p)}"
            post1_name = f"post1_{_var_name(p)}"
            post2_name = f"post2_{_var_name(p)}"
            input_params.append((pre_name, ty))
            output1_params.append((post1_name, ty))
            output2_params.append((post2_name, ty))
        elif p.is_ref:
            input_params.append((_var_name(p), ty))
        else:
            input_params.append((_var_name(p), ty))

    ret_ty = spec.return_type.name
    output1_params.append(("r1", ret_ty))
    output2_params.append(("r2", ret_ty))

    all_params = input_params + output1_params + output2_params
    params_str = ", ".join(f"{name}: {ty}" for name, ty in all_params)

    # Requires
    requires_str = ""
    if spec.requires:
        requires_raw = "\n".join(spec.requires)
        requires_sub = _substitute_input(requires_raw, spec)
        requires_str = f"\n    requires {requires_sub},"

    # Ensures: run1 && run2
    ensures_raw = "\n        && ".join(spec.ensures)
    run1 = _substitute_run(ensures_raw, spec, run_id=1)
    run2 = _substitute_run(ensures_raw, spec, run_id=2)

    # Equality conclusion
    eq_parts = []
    for name1, _ in output1_params:
        name2 = name1.replace("post1_", "post2_").replace("r1", "r2")
        if name1 == "r1":
            eq_parts.append("r1 == r2")
        else:
            eq_parts.append(f"{name1}@ == {name2}@")
    conclusion = " && ".join(eq_parts)

    code = f"""proof fn {fn_name}({params_str}){requires_str}
    ensures
        ({run1}
        && {run2}
        {{ASSUMES}})
        ==> {conclusion}
{{
}}"""

    return code


# ---------------------------------------------------------------------------
# Public API: produce DetCheckSpec
# ---------------------------------------------------------------------------

def build_det_check_spec(
    spec: FunctionSpec,
    check_name: str | None = None,
    verus_config: dict | None = None,
) -> DetCheckSpec:
    """
    Build a DetCheckSpec from a FunctionSpec.
    
    This is the output of Step 1 (extract + gen_det).
    """
    template = _build_template(spec, check_name)
    symbols = _build_symbols(spec)

    return DetCheckSpec(
        function=spec.name,
        det_check_template=template,
        symbols=symbols,
        verus_config=verus_config or {},
    )


def render_template(template: str, assumes: list[Assume]) -> str:
    """
    Render a det check template with concrete assumes.
    
    Replaces {ASSUMES} with the assume expressions.
    """
    if assumes:
        assume_parts = [a.expression for a in assumes]
        assume_str = "\n        && " + "\n        && ".join(assume_parts)
    else:
        assume_str = ""

    return template.replace("{ASSUMES}", assume_str)


# ---------------------------------------------------------------------------
# Substitution helpers (unchanged)
# ---------------------------------------------------------------------------

def _substitute_input(requires_raw: str, spec: FunctionSpec) -> str:
    result = requires_raw
    for p in spec.params:
        if p.is_self:
            vn = _var_name(p)
            if p.is_mut_ref:
                target = f'pre_{vn}'
            else:
                target = vn
            result = re.sub(r'\bold\s*\(\s*self\s*,?\s*\)', target, result)
            result = re.sub(r'\bself\b', target, result)
    return result


def _substitute_run(ensures_raw: str, spec: FunctionSpec, run_id: int) -> str:
    result = ensures_raw

    for p in spec.params:
        if p.is_mut_ref and p.is_self:
            vn = _var_name(p)
            result = result.replace('__PRE__', f'pre_{vn}')
            result = result.replace('__POST__', f'post{run_id}_{vn}')
            result = result.replace('__RESULT__', f'r{run_id}')
            result = re.sub(r'\bold\s*\(\s*self\s*,?\s*\)', f'pre_{vn}', result)
            result = re.sub(r'\bself\b', f'post{run_id}_{vn}', result)
        elif p.is_mut_ref:
            vn = _var_name(p)
            result = re.sub(rf'\bold\s*\(\s*{re.escape(p.name)}\s*,?\s*\)', f'pre_{vn}', result)
            result = re.sub(rf'\b{re.escape(p.name)}\b', f'post{run_id}_{vn}', result)
        elif p.is_self:
            vn = _var_name(p)
            result = re.sub(r'\bold\s*\(\s*self\s*,?\s*\)', vn, result)
            result = re.sub(r'\bself\b', vn, result)

    result = re.sub(r'\bresult\b', f'r{run_id}', result)
    result = result.replace('__RESULT__', f'r{run_id}')

    # Rename match-arm bindings to avoid collisions between runs.
    # Find patterns like Ok(name), Err(name), Some(name) and rename the binding.
    result = _rename_match_bindings(result, run_id)

    return result


def _rename_match_bindings(text: str, run_id: int) -> str:
    """
    Rename match-arm binding variables to be unique per run.
    
    Finds patterns like `Ok(name)`, `Err(name)`, `Some(name)` where `name`
    is an identifier (not `_` or a literal), and renames both the binding
    and all references within the same match arm.
    """
    # Find all match-arm bindings: Ok(identifier), Err(identifier), Some(identifier)
    binding_pattern = re.compile(
        r'\b(Ok|Err|Some)\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)'
    )
    
    bindings_found = set()
    for m in binding_pattern.finditer(text):
        name = m.group(2)
        if name != '_':  # skip wildcard
            bindings_found.add(name)
    
    # Rename each binding: name → name_{run_id}
    for name in bindings_found:
        new_name = f"{name}_{run_id}"
        # Replace the binding in pattern position and all references
        text = re.sub(rf'\b{re.escape(name)}\b', new_name, text)
    
    return text
