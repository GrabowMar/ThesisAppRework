# Risks & Architecture Decisions Log

Record decisions (ADRs) and known risks; update as migration proceeds.

## Format
`ADR-<seq>` – Title
- Date
- Status: Proposed | Accepted | Superseded (ADR-x)
- Context
- Decision
- Consequences

## Decisions

### ADR-0001 – Server-First with HTMX
- Date: 2025-08-28
- Status: Accepted
- Context: Need interactivity without SPA complexity.
- Decision: Use HTMX for partial swaps; no full SPA framework.
- Consequences: Lower JS footprint; must design endpoints for fragment returns.

### ADR-0002 – Component Taxonomy Table
- Date: 2025-08-28
- Status: Accepted
- Context: Prevent proliferation of ad-hoc partials.
- Decision: Maintain centralized table (04_COMPONENT_TAXONOMY.md).
- Consequences: Slight documentation overhead; improved discoverability.

### ADR-0003 – `c-` Prefix for Custom Classes
- Date: 2025-08-28
- Status: Accepted
- Context: Avoid collision with AdminLTE/Bootstrap.
- Decision: Prefix custom component classes with `c-`.
- Consequences: Predictable styling namespace.

### ADR-0004 – Migrate from AdminLTE to Bootstrap 5
- Date: 2025-08-28
- Status: Accepted
- Context: AdminLTE has jQuery dependencies and complex styling that conflicts with modern development practices.
- Decision: Replace AdminLTE with plain Bootstrap 5 for cleaner, jQuery-free styling foundation.
- Consequences: 
  - Positive: Modern CSS framework, no jQuery dependencies, better accessibility, cleaner component system
  - Negative: Migration effort required, need to rebuild navigation components, potential visual regressions during transition
  - Mitigation: Incremental migration per domain, comprehensive testing, fallback to AdminLTE during transition if needed

## Open Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Hidden legacy include paths break after shim removal | Medium | Medium | CI test enumerating renderable templates before removal |
| Fragment size bloat over time | Performance | Medium | Add size budget check script |
| A11y regressions not caught early | Compliance | Medium | Integrate axe-core sooner |
| Duplicate components reintroduced | Maintainability | Medium | Taxonomy review in PR template |
| Bootstrap 5 migration introduces visual regressions | User Experience | Medium | Incremental migration, comprehensive testing, visual regression testing |
| jQuery dependencies not fully removed | Technical Debt | Low | Automated detection in CI, manual review during migration |

## Pending Decisions
| Topic | Notes |
|-------|-------|
| Dedicated `pages/dashboard/` vs reusing `pages/analysis/` for root dashboard | Decide during Stage 2 |
| Adopt Alpine.js for minor client state? | Evaluate after initial migrations |
| Bootstrap Icons vs Font Awesome for iconography | Prefer Bootstrap Icons for consistency, but Font Awesome may be needed for legacy compatibility |
