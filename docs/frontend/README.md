# Frontend Revamp Documentation

This folder contains the living documents guiding the iterative rebuild of the Flask/Jinja/HTMX frontend, now migrating from AdminLTE to Bootstrap 5.

Contents (high-level):
- 00_MASTER_PROMPT.md – Master AI/system prompt to keep generation aligned
- 01_CORE_PRINCIPLES.md – Architectural & design principles
- 02_TECH_STACK.md – Technologies, versions, rationale (updated for Bootstrap 5)
- 03_TEMPLATE_STRUCTURE.md – Target template & asset hierarchy
- 04_COMPONENT_TAXONOMY.md – Classification of partials/components (Bootstrap 5 focused)
- 05_NAMING_CONVENTIONS.md – File, block, id/data-* naming rules
- 06_STATE_MANAGEMENT.md – Server + HTMX + progressive enhancement state patterns
- 07_ROUTES_MAPPING.md – Route groups → templates mapping & legacy shim notes
- 08_ITERATIVE_MIGRATION_PLAN.md – Ordered refactor stages & acceptance criteria (includes Bootstrap 5 migration)
- 09_CODING_STANDARDS.md – HTML/Jinja/HTMX/JS/CSS lint rules & patterns
- 10_PERFORMANCE_ACCESSIBILITY.md – Performance budgets & a11y checklist
- 11_TEST_STRATEGY.md – Template, route, interaction and visual regression testing
- 12_STYLE_GUIDE.md – Design tokens & CSS strategy (Bootstrap 5 focused)
- 13_OBSERVABILITY.md – Logging, metrics, tracing hooks in templates
- 14_RISKS_DECISIONS.md – ADR-style log of decisions & open risks (includes Bootstrap 5 migration decision)
- 15_BOOTSTRAP_5_MIGRATION.md – Comprehensive guide for migrating from AdminLTE to Bootstrap 5

## Key Changes for Bootstrap 5 Migration

- **Removed jQuery dependencies**: Bootstrap 5 is jQuery-free
- **Updated component system**: AdminLTE components → Bootstrap 5 equivalents
- **Modern CSS framework**: Leverage Bootstrap 5 utilities and components
- **Icon migration**: Font Awesome → Bootstrap Icons (preferred)
- **Responsive improvements**: Better mobile-first approach

## Migration Status

- **Stage 1**: Documentation & Standards (In Progress)
- **Stage 2**: Bootstrap 5 Foundation & Layout Migration (Pending)
- **Stages 3-7**: Component migration with Bootstrap 5 (Pending)
- **Stage 8**: Legacy cleanup and AdminLTE removal (Pending)

Use PRs to evolve; each change must update MASTER_PROMPT if principle-level shifts occur.
