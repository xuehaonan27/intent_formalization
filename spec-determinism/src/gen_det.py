"""
Module 2: gen_det — Determinism Check Generator

Generates Verus proof fns that check: Q(x,y1) && Q(x,y2) ==> y1 == y2
"""

import re
from typing import Optional

from .types import (
    TypeKind, TypeInfo, Param, FunctionSpec, Assume,
)


class Unsupported(Exception):
    """Triggers LLM fallback for ensures substitution."""
    pass


def _var_name(param: Param, prefix: str = "") -> str:
    """Generate variable name for a param."""
    name = "self_" if param.is_self else param.name
    return f"{prefix}{name}" if prefix else name


def _type_name(param: Param) -> str:
    """Get the concrete type name (strip & and &mut)."""
    return param.type.name


def generate_det_check(
    spec: FunctionSpec,
    extra_assumes: list[Assume] | None = None,
    check_name: str | None = None,
    conclusion: str | None = None,
) -> str:
    """
    Generate a determinism-checking proof fn.

    Args:
        spec: Extracted function spec
        extra_assumes: Additional constraints to add to the ensures antecedent
        check_name: Override proof fn name (default: det_{spec.name})
        conclusion: Override conclusion (default: all outputs equal)

    Returns:
        Verus proof fn source code as string
    """
    fn_name = check_name or f"det_{spec.name}"

    # Build parameter list for the proof fn
    proof_params = []
    input_params = []
    output1_params = []
    output2_params = []

    for p in spec.params:
        ty = _type_name(p)
        if p.is_mut_ref:
            # &mut → pre (input) + post1, post2 (output)
            pre_name = f"pre_{_var_name(p)}"
            post1_name = f"post1_{_var_name(p)}"
            post2_name = f"post2_{_var_name(p)}"
            input_params.append((pre_name, ty))
            output1_params.append((post1_name, ty))
            output2_params.append((post2_name, ty))
        elif p.is_ref:
            # & → input only
            input_params.append((_var_name(p), ty))
        else:
            # value → input only
            input_params.append((_var_name(p), ty))

    # Return value → output
    ret_ty = spec.return_type.name
    output1_params.append(("r1", ret_ty))
    output2_params.append(("r2", ret_ty))

    # All params: inputs, then output1 vars, then output2 vars
    all_params = input_params + output1_params + output2_params
    params_str = ", ".join(f"{name}: {ty}" for name, ty in all_params)

    # Build requires clause (on input variables)
    requires_str = ""
    if spec.requires:
        requires_raw = "\n".join(spec.requires)
        # Substitute self → pre_self_
        requires_sub = _substitute_input(requires_raw, spec)
        requires_str = f"\n    requires {requires_sub},"

    # Build ensures clause
    # Run 1: substitute for (post1_*, r1)
    # Run 2: substitute for (post2_*, r2)
    ensures_raw = "\n".join(spec.ensures)
    run1 = _substitute_run(ensures_raw, spec, run_id=1)
    run2 = _substitute_run(ensures_raw, spec, run_id=2)

    # Build equality conclusion
    if conclusion is None:
        eq_parts = []
        for name1, _ in output1_params:
            name2 = name1.replace("post1_", "post2_").replace("r1", "r2")
            if name1 == "r1":
                eq_parts.append("r1 == r2")
            else:
                # For structs with @, compare spec views
                eq_parts.append(f"{name1}@ == {name2}@")
        conclusion = " && ".join(eq_parts)

    # Extra assumes (from binary search)
    assume_str = ""
    if extra_assumes:
        assume_parts = [a.expression for a in extra_assumes]
        assume_str = "\n        && " + "\n        && ".join(assume_parts)

    code = f"""proof fn {fn_name}({params_str}){requires_str}
    ensures
        ({run1}
        && {run2}{assume_str})
        ==> {conclusion}
{{
}}"""

    return code


def _substitute_input(requires_raw: str, spec: FunctionSpec) -> str:
    """Substitute self references in requires with pre_ names."""
    result = requires_raw
    for p in spec.params:
        if p.is_self:
            result = re.sub(r'\bself\b', f'pre_{_var_name(p)}', result)
    return result


def _substitute_run(ensures_raw: str, spec: FunctionSpec, run_id: int) -> str:
    """
    Substitute ensures clause for a specific run.
    
    Handles both original Verus names and placeholder names:
    - old(self) / __PRE__  → pre_self_  (shared, not run-specific)
    - self / __POST__      → post{run_id}_self_
    - result / __RESULT__  → r{run_id}
    
    For non-self &mut params:
    - old(param) → pre_{param}
    - param      → post{run_id}_{param}
    """
    result = ensures_raw

    for p in spec.params:
        if p.is_mut_ref and p.is_self:
            vn = _var_name(p)
            # Placeholders
            result = result.replace('__PRE__', f'pre_{vn}')
            result = result.replace('__POST__', f'post{run_id}_{vn}')
            result = result.replace('__RESULT__', f'r{run_id}')
            # Original Verus names
            result = re.sub(r'\bold\(self\)', f'pre_{vn}', result)
            result = re.sub(r'\bself\b', f'post{run_id}_{vn}', result)
        elif p.is_mut_ref:
            vn = _var_name(p)
            result = re.sub(rf'\bold\({re.escape(p.name)}\)', f'pre_{vn}', result)
            result = re.sub(rf'\b{re.escape(p.name)}\b', f'post{run_id}_{vn}', result)

    # result → r1 or r2 (original Verus name)
    result = re.sub(r'\bresult\b', f'r{run_id}', result)
    # Placeholder
    result = result.replace('__RESULT__', f'r{run_id}')

    return result
