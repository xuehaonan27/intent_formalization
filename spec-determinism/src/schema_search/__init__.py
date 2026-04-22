"""Schema-driven determinism search.

One cargo-verus call produces a guarded template encoding all
independent narrowing schemas. Subsequent rounds execute entirely in
z3-py via push/pop + assume-guard toggling (sub-ms per round).

Public API:
    - enumerate_schemas(det_spec) -> list[SchemaBinding]
    - render_guarded_template(det_spec, schemas) -> str
    - translate_assume(assume, schemas) -> (guard_name, k_bindings) | None
    - build_schema_ctx(det_spec, smt2_path, schemas) -> SchemaCtx
    - run_schema_search(det_spec, schema_ctx) -> Witness
"""
from .schemas import (
    SchemaBinding, SchemaKind,
    enumerate_schemas, render_guarded_template, translate_assume,
)
from .search import SchemaCtx, SchemaSearchContext, run_schema_search, build_schema_ctx

__all__ = [
    "SchemaBinding", "SchemaKind",
    "enumerate_schemas", "render_guarded_template", "translate_assume",
    "SchemaCtx", "SchemaSearchContext", "run_schema_search", "build_schema_ctx",
]
