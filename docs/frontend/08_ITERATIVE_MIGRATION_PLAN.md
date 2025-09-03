# Iterative Migration Plan

Incremental, low-risk stages. Each stage is a PR (or small series) producing a stable, deployable system.

## Stage 0 – Baseline Inventory (DONE / confirm)
- Freeze new template creation (except critical fixes)
- Generate list of all templates & includes (scriptable)
- Categorize duplicates

## Stage 1 – Documentation & Standards (CURRENT)
- Establish core docs (this folder)
- Ratify naming & principles via review
- Add automated template path smoke test

## Stage 2 – Bootstrap 5 Foundation & Layout Migration
- **NEW**: Migrate from AdminLTE to Bootstrap 5
  - Update base layouts (`base.html`, `dashboard.html`) to use Bootstrap 5
  - Replace AdminLTE CSS/JS with Bootstrap 5 CDN or local copy
  - Convert navigation components (navbar, sidebar) to Bootstrap 5 equivalents
  - Update theme CSS to use Bootstrap 5 CSS variables and utilities
- Refactor layouts to final block set
- Migrate main dashboard route off compatibility wrapper
- Extract shared dashboard widgets (stats cards, recent activity)
- Tests: route returns 200 & component markers

## Stage 3 – Analysis Domain
- Migrate `pages/analysis/*` to normalized names
- Extract task list row, progress widget, batch summary components
- Replace any legacy partial includes with new ui/elements locations
- Add HTMX fragment tests for task progress & batch creation
- **Bootstrap 5**: Convert analysis components to use Bootstrap 5 classes

## Stage 4 – Models Domain
- Migrate overview & detail pages
- Extract model capability badge, application grid item partials
- Consolidate comparison matrix
- **Bootstrap 5**: Convert model components to Bootstrap 5 grid system and cards

## Stage 5 – Applications Domain
- Normalize app detail & file browser templates
- Componentize file list, metadata panel, container controls
- **Bootstrap 5**: Convert application components to Bootstrap 5 layouts

## Stage 6 – Statistics & Reports
- Refactor chart & generation pages; move chart containers into dedicated partials
- Standardize data loading (HTMX + placeholders)
- **Bootstrap 5**: Convert statistics components to Bootstrap 5 data display patterns

## Stage 7 – System & Tasks
- Migrate status/logs/settings + tasks overview
- Introduce reusable log table & status badge macros
- **Bootstrap 5**: Convert system components to Bootstrap 5 utilities

## Stage 8 – Cleanup Legacy & Shim Removal
- Remove unused legacy folders (`views/`, scattered `partials/` duplicates)
- Retire compatibility wrapper after verifying zero legacy path usage in codebase
- **Bootstrap 5**: Remove AdminLTE-specific CSS/JS dependencies

## Stage 9 – Accessibility & Performance Hardening
- Run axe audits; remediate issues
- Set performance baselines; trim payloads exceeding budgets
- **Bootstrap 5**: Leverage Bootstrap 5's built-in accessibility features

## Stage 10 – Observability Enhancements
- Add data-component markers across all dynamic regions
- Optional: instrumentation for fragment load timing

## Stage 11 – Final Polishing & ADR Review
- Close or formalize open decisions in ADR log
- Update MASTER_PROMPT with any last refinements

## Bootstrap 5 Migration Checklist
- [ ] Replace AdminLTE CSS/JS with Bootstrap 5
- [ ] Convert navigation components (navbar, sidebar)
- [ ] Update form components to use Bootstrap 5 classes
- [ ] Convert card layouts to Bootstrap 5 card system
- [ ] Update button styles to Bootstrap 5 variants
- [ ] Convert table layouts to Bootstrap 5 table classes
- [ ] Update alert/message components
- [ ] Test responsive behavior across breakpoints
- [ ] Verify no jQuery dependencies remain
- [ ] Update icon usage to Bootstrap Icons where possible

## Acceptance Criteria Per Stage
- All modified routes directly reference new template paths
- No broken includes (CI test renders each top-level page)
- Updated docs (taxonomy, routes mapping, plan progress)
- Tests pass; coverage for new components
- **Bootstrap 5**: No AdminLTE classes or jQuery dependencies in migrated components

## Rollback Strategy
If a stage introduces regressions:
1. Revert the stage branch
2. Restore compatibility mapping entries if path changes already merged
3. Open issue capturing root cause before retry

## Parallelization Guidelines
- Do not migrate two domains touching same shared partials concurrently
- If necessary, branch from latest main after each merge to reduce conflicts

## Tracking Progress
Update progress table below:

| Stage | Status | PR(s) | Notes |
|-------|--------|-------|-------|
| 0 | Done | # | inventory script results archived |
| 1 | In Progress | # | docs authored |
| 2 | Pending | - | Bootstrap 5 foundation |
| 3 | Pending | - |  |
| 4 | Pending | - |  |
| 5 | Pending | - |  |
| 6 | Pending | - |  |
| 7 | Pending | - |  |
| 8 | Pending | - |  |
| 9 | Pending | - |  |
| 10 | Pending | - |  |
| 11 | Pending | - |  |
