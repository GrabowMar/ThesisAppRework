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

## Open Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Hidden legacy include paths break after shim removal | Medium | Medium | CI test enumerating renderable templates before removal |
| Fragment size bloat over time | Performance | Medium | Add size budget check script |
| A11y regressions not caught early | Compliance | Medium | Integrate axe-core sooner |
| Duplicate components reintroduced | Maintainability | Medium | Taxonomy review in PR template |

## Pending Decisions
| Topic | Notes |
|-------|-------|
| Dedicated `pages/dashboard/` vs reusing `pages/analysis/` for root dashboard | Decide during Stage 2 |
| Adopt Alpine.js for minor client state? | Evaluate after initial migrations |
