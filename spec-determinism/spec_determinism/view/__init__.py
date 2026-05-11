"""View-fn resolver — Phase 2 of the A-2 fix.

This subpackage owns everything related to **constructing per-type
`spec fn view(&self) -> ...`** for use by ``gen_det.build_equal_expr``.
The goal is to replace the structural ``==`` fallback (which produces
~290 false-positive determinism witnesses in the verusage corpus) with
``lhs@ == rhs@`` for every type whose spec ensures actually treats it
as having a semantic view.

A four-layer resolver picks a view source per type, highest-priority
first:

* **L1 — prelude.** Hard-coded rules for container types
  (``Vec``/``Option``/``Map``/``&T``/``Box``/``Ghost``/``Tracked`` …)
  in :mod:`.prelude`.
* **L2 — type alias.** Re-uses ``alias_target_expr`` from the
  Phase-1.5 :class:`spec_determinism.type_registry.TypeRegistry` and
  recursively resolves the RHS. Implemented inside :mod:`.registry`.
* **L3 — impl scan.** Finds existing ``impl View for X { ... }`` blocks
  in the source. Module :mod:`.impl_scanner`.
* **L4 — LLM.** Last-resort generation; cached on disk under
  ``results-verusage/view_registry/<project>/<type>.json``. Module
  :mod:`.llm`.

The :class:`.registry.ViewRegistry` is the public façade — callers
(``gen_det``, witness-gen) ask it for a view of a type and get back a
:class:`.registry.ViewInfo` that says where the view came from and how
to render the equality check.

Design context: see ``ISSUES.md#A-2`` and the session plan ``plan.md``
under "Phase 2 plan — LLM-at-fallback design".
"""
