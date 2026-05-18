"""Tier 1.5 — LLM-driven type-definition completion.

Pipeline position::

    extract → [llm_type] → gen_det → z3-only → llm_proof (Tier 2)

Runs after ``extract_spec`` and before gen_det, gap-driven (skipped entirely
when ``detect_gaps`` returns nothing). Fills missing ``TypeInfo`` entries in
``FunctionSpec.type_defs`` so codegen produces a structurally-tight equal_fn
(view-eq / errs_equivalent / piecewise) instead of falling back to ``==``.

Modules
-------
* ``parse``      — round-trip ``type_str`` → ``TypeInfo`` through tree-sitter.
* ``gaps``       — static gap detector. Lists what is missing from a spec.
* ``apply``      — convert a ``TypePatch`` into ``TypeInfo`` and merge it into
  ``spec.type_defs``.
* ``validator``  — V1..V3 gates.
* ``prompt``     — Copilot CLI prompt builder.
* ``runner``     — orchestrator.
* ``cache``      — per-project cache keyed by ``(project_hash, type_name)``.

Soundness story
---------------
Tier 1.5 only *completes* ``TypeInfo``; it never proposes semantic relaxations.
The downstream gen_det then derives equal_fn structurally (struct-eq / view-eq
/ errs_equivalent / piecewise). All these forms are sound w.r.t.
``lhs == rhs ⇒ equal_fn(lhs, rhs)`` by construction. The only LLM-introduced
risk is a wrong field type; that surfaces as a Verus type-check failure when
gen_det's output is compiled (V4 / verus smoke).

Submodules are imported lazily to keep the package importable even when
the optional Copilot-CLI tooling isn't on the path.
"""

from __future__ import annotations

