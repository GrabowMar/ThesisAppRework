## Frontend Re-Architecture Plan (Phase 1)

This document maps the existing (pre-refactor) template landscape and defines the target consolidated architecture for the Flask + Jinja2 + HTMX + _hyperscript + AdminLTE UI.

### 1. Removed Legacy / Duplicate Pages (this commit)
The following bloated or unreferenced templates have been removed to reduce noise:

- `advanced_results.html` (unused analytics experiment)
- `applications_new.html` / `applications_old.html` (superseded by `applications.html`)
- `models_overview_old.html` (old layout)
- `security_analysis_complete_old.html` (legacy full view)
- `security_analysis_compact.html` (variant superseded by unified complete page)
- `security_analysis_results.html` / `security_analysis_results_new.html` / `security_analysis_results_old.html` (multiple result variants collapsed into `security_analysis_complete.html` route usage)

### 2. Current Page Set (After Removal)
Keeps only actively referenced or core navigation endpoints:

| Page | Purpose | To Refactor |
|------|---------|-------------|
| applications.html | Apps catalogue + filters | Reduce inline styles, move JS -> hyperscript/HTMX |
| application_detail.html | Single app view | Modularize panels |
| apps_grid.html | Advanced grid (HTMX endpoints) | Possibly merge into applications.html (Phase 2) |
| analysis_hub.html | Analysis landing | Will be replaced by `analysis.html` unified hub |
| batch_testing.html | Batch operations UI | Will consume new partials |
| dashboard.html | High-level KPIs | Strip inline style/JS; convert widgets to HTMX fragments |
| error.html | Error page | Reduce inline styling blocks |
| logs.html | Log viewer | Replace polling JS with HTMX interval / hyperscript |
| maintenance.html | Maintenance ops | Convert progress scripting |
| model_apps.html | Model ↔ apps mapping | Candidate for merge into model detail tabs |
| model_details.html | Model detail | Convert metrics bars to pure classes |
| models_overview.html | Global model list | Keep – streamline |
| performance_testing.html | Performance test page | Merge into unified testing hub |
| security_analysis_complete.html | Security analysis results | Keep as canonical results view (rename to `security_analysis.html` Phase 2) |
| security_testing.html | Security test launcher | Merge into unified testing hub |
| statistics_overview.html | Statistics | Keep – modularize widgets |
| system_status.html | System health | Convert to HTMX partial composition |
| testing.html | Legacy console | Will be deprecated after hub unification |
| testing_center.html | Multi-test overview | Merge -> unified `testing_hub.html` |
| testing_console.html | Ad‑hoc console | Tab/panel inside hub |
| testing_results.html | Historical results | Panel inside hub |

### 3. Target Folder Structure (End of Phase 3)

```
templates/
  base.html
  pages/
    applications.html            (apps + grid modes via HTMX params)
    application_detail.html      (tabbed partial panels)
    analysis.html                (unified analysis hub)
    testing_hub.html             (security + performance + batch)
    security_analysis.html       (single canonical results view)
    models_overview.html
    model_details.html
    dashboard.html
    statistics_overview.html
    system_status.html
    logs.html
    maintenance.html
    error.html
  partials/
    analysis/
      stats_cards.html
      recent_activity.html
      task_table.html
      start_forms.html
      result_summary.html
      tool_breakdown.html
    testing/
      security_form.html
      performance_form.html
      batch_form.html (existing will migrate)
      active_tests.html
      test_results_table.html
    apps/
      filters.html
      grid.html
      list.html
      compact.html
      details_panel.html
    models/
      (consolidate existing variants into: cards.html, table.html, grid.html)
    common/
      activity_timeline.html
      sidebar_stats.html
      status_badge.html
      pagination.html
```

### 4. HTMX & _hyperscript Principles
1. All dynamic zones become HTMX fragments served by dedicated `/api/...` routes (many already exist).
2. No inline `<script>` or `<style>` tags inside page/partial templates (exception: minimal `<script type="text/hyperscript">` behaviors allowed).
3. Polling replaced with `hx-trigger="every 30s"` or server push (future).
4. Stateful UI interactions (expand/collapse, tab switching, bulk select) implemented with `_hyperscript` before falling back to JS.

### 5. Inline Style & JS Elimination Strategy
| Pattern | Replacement |
|---------|-------------|
| `style="width: X%"` progress bars | Use utility classes or data-* + hyperscript to set width post-swap |
| Toast / notification JS | `_hyperscript` behavior injecting alert markup |
| Polling setInterval | `hx-trigger="every Ns"` on container |
| Dynamic button enable/disable | `_="on input from <form/> ..."` directives |

### 6. Security Analysis Consolidation
- Keep only one page: `security_analysis_complete.html` → rename to `security_analysis.html` (Phase 2).
- Charting: replace Chart.js where possible with pure HTML progress + small sparkline (optional later).
- Large JSON viewers: load on demand (lazy `hx-get` into a `<div>`).

### 7. Testing Hub Unification (Phase 2 Draft)
Components loaded as tabs (hyperscript toggles) or HTMX swap:
- Launch Panel (security/performance/batch forms consolidated)
- Active Tasks (reuse `partials/common/active_tasks.html` after cleanup)
- Recent Results Table (security, performance combined with filter chips)
- Aggregated Metrics (cards: Avg Duration, Open Vulnerabilities, Pass Rate)

### 8. Next Implementation Steps
1. (DONE) Remove unused duplicate templates.
2. Create new partial namespace `analysis/` & migrate pieces from `analysis_hub.html`.
3. Replace inline `<style>` blocks incrementally (focus on high-traffic pages first).
4. Normalize progress & badge markup using AdminLTE classes.
5. Route updates: point old endpoints to new consolidated templates (backwards compatible where feasible).

### 9. Guidelines for Future Contributions
- Before adding a new page: can it be a partial in an existing hub?
- No embedded `<script>` except `type="text/hyperscript"` and no business logic JS.
- Prefer `hx-get` + `hx-trigger="revealed"` for lazy panels.
- Always supply an error fallback partial (`partials/common/error.html`).

---
Phase 1 complete; proceed to creating unified analysis/testing hubs and stripping inline styles in subsequent commits.
