# Frontend Revamp Documentation

This folder contains the living documents guiding the iterative rebuild of the Flask/Jinja/HTMX frontend.

Contents (high-level):
- 00_MASTER_PROMPT.md – Master AI/system prompt to keep generation aligned
- 01_CORE_PRINCIPLES.md – Architectural & design principles
- 02_TECH_STACK.md – Technologies, versions, rationale
- 03_TEMPLATE_STRUCTURE.md – Target template & asset hierarchy
- 04_COMPONENT_TAXONOMY.md – Classification of partials/components
- 05_NAMING_CONVENTIONS.md – File, block, id/data-* naming rules
- 06_STATE_MANAGEMENT.md – Server + HTMX + progressive enhancement state patterns
- 07_ROUTES_MAPPING.md – Route groups → templates mapping & legacy shim notes
- 08_ITERATIVE_MIGRATION_PLAN.md – Ordered refactor stages & acceptance criteria
- 09_CODING_STANDARDS.md – HTML/Jinja/HTMX/JS/CSS lint rules & patterns
- 10_PERFORMANCE_ACCESSIBILITY.md – Performance budgets & a11y checklist
- 11_TEST_STRATEGY.md – Template, route, interaction and visual regression testing
- 12_STYLE_GUIDE.md – Design tokens & CSS strategy
- 13_OBSERVABILITY.md – Logging, metrics, tracing hooks in templates
- 14_RISKS_DECISIONS.md – ADR-style log of decisions & open risks

Use PRs to evolve; each change must update MASTER_PROMPT if principle-level shifts occur.
