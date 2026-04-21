"""A' (schema-driven) determinism search.

One cargo-verus call produces a guarded template encoding all
independent narrowing schemas. Subsequent rounds execute entirely in
z3-py via push/pop + assume-guard toggling (sub-ms per round).

Public API:
    - enumerate_schemas(det_spec) -> list[SchemaBinding]
    - render_guarded_template(det_spec, schemas) -> str
    - translate_assume(rust_expr, schemas) -> (guard_name, k_bindings) | None
    - build_schema_ctx(det_spec, smt2_path, schemas) -> APrimeCtx
    - binary_search_a_prime(det_spec, a_prime_ctx) -> Witness
"""
from .schemas import (
    SchemaBinding, SchemaKind,
    enumerate_schemas, render_guarded_template, translate_assume,
)
from .search import APrimeCtx, APrimeSearchContext, binary_search_a_prime

__all__ = [
    "SchemaBinding", "SchemaKind",
    "enumerate_schemas", "render_guarded_template", "translate_assume",
    "APrimeCtx", "APrimeSearchContext", "binary_search_a_prime",
]
